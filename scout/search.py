"""Job search backends for Scout.

Tavily first when TAVILY_API_KEY is set (free tier), otherwise ddgs
(no key needed). Never invents listings: on failure it raises, and the
caller surfaces the error instead of returning fake jobs.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

# Free search mirrors are flaky: the default ddgs backend timed out on
# mojeek in testing, while the bing backend worked (sometimes only on retry).
# Try each backend twice before giving up. Verified 12 Nov 2026.
DDGS_BACKENDS = ["duckduckgo", "bing"]
ATTEMPTS_PER_BACKEND = 2
RETRY_SLEEP_SECONDS = 3


def _company_from(title: str, href: str) -> str:
    m = re.search(r"\s[-–|@]\s*(.+)$", title or "")
    if m:
        suffix = m.group(1).strip()
        # Board pages end in "26 Open Jobs ..." / "Latest Vacancies" —
        # that is a count, not a company. Fall through to the domain name.
        if not re.search(r"\d+\s*(open\s+)?jobs?", suffix, re.I) and (
            "vacanc" not in suffix.lower()
        ):
            return suffix[:120]
    m = re.search(r"//(?:www\.)?([^./]+)", href or "")
    return m.group(1).replace("-", " ").title() if m else "Not stated in listing"


def _search_ddgs(query: str, max_results: int) -> list[dict[str, Any]]:
    from ddgs import DDGS

    last_error: Exception | None = None
    for backend in DDGS_BACKENDS:
        for _ in range(ATTEMPTS_PER_BACKEND):
            try:
                out: list[dict[str, Any]] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results, backend=backend):
                        out.append({
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "link": r.get("href", ""),
                            "company": _company_from(r.get("title", ""), r.get("href", "")),
                            "location": "",
                        })
                if out:
                    return out
            except Exception as exc:  # noqa: BLE001 — mirrors fail often; retry, then next backend
                last_error = exc
                time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"ddgs search failed on all backends: {last_error}")


def _search_tavily(query: str, max_results: int) -> list[dict[str, Any]]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    resp = client.search(query=query, search_depth="advanced",
                         max_results=max_results)
    out: list[dict[str, Any]] = []
    for r in resp.get("results", []):
        out.append({
            "title": r.get("title", ""),
            "body": r.get("content", ""),
            "link": r.get("url", ""),
            "company": _company_from(r.get("title", ""), r.get("url", "")),
            "location": "",
        })
    return out


def search_jobs(role: str, location: str, max_results: int = 15) -> list[dict[str, Any]]:
    query = f"{role} fresher jobs in {location} India"
    if os.environ.get("TAVILY_API_KEY"):
        try:
            return _search_tavily(query, max_results)
        except Exception:
            pass  # fall through to ddgs rather than failing the run
    return _search_ddgs(query, max_results)
