"""Job search backends for Scout.

Tavily first when TAVILY_API_KEY is set (free tier), otherwise ddgs
(no key needed). Never invents listings: on failure it raises, and the
caller surfaces the error instead of returning fake jobs.
"""

from __future__ import annotations

import os
import re
from typing import Any


def _company_from(title: str, href: str) -> str:
    m = re.search(r"\s[-–|@]\s*(.+)$", title or "")
    if m:
        return m.group(1).strip()[:120]
    m = re.search(r"//(?:www\.)?([^./]+)", href or "")
    return m.group(1).replace("-", " ").title() if m else "Not stated in listing"


def _search_ddgs(query: str, max_results: int) -> list[dict[str, Any]]:
    from ddgs import DDGS

    out: list[dict[str, Any]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            out.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "link": r.get("href", ""),
                "company": _company_from(r.get("title", ""), r.get("href", "")),
                "location": "",
            })
    return out


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
