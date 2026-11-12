"""Scout — LangGraph job researcher (Day 2).

Graph: search -> filter -> structured output.
Search uses Tavily when TAVILY_API_KEY is set, otherwise ddgs (no key).
Filtering is deterministic (keyword scoring), so Day 2 works with ₹0 and
no LLM call — the Gemini tailoring lives in Scribe (Day 3).

Public entry point: run_scout(role, location, max_results=5) -> ScoutResult
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .models import JobPosting, ScoutResult
from .search import search_jobs

FRESHER_SIGNALS = (
    "fresher", "fresher's", "freshers", "entry level", "entry-level",
    "0-1 year", "0 - 1 year", "0-2 year", "0 - 2 year", "0 years",
    "0 year", "trainee", "intern", "internship", "junior", "graduate",
    "0 to 1 year", "0 to 2 years", "no experience", "fresh graduate",
)
SENIOR_SIGNALS = (
    "senior", "5+ years", "5 years", "6+ years", "7+ years", "8+ years",
    "10+ years", "manager", "lead ", "principal", "architect",
    "head of", "director", "vp ", "vice president",
)


class ScoutState(TypedDict, total=False):
    role: str
    location: str
    max_results: int
    raw_results: list[dict[str, Any]]
    jobs: list[JobPosting]
    search_error: str | None


def _score(raw: dict[str, Any], role: str, location: str) -> tuple[int, str]:
    """Score one raw result; returns (score, reason). Negative = reject."""
    text = f"{raw.get('title', '')} {raw.get('body', '')}".lower()
    role_words = [w for w in re.split(r"[^a-z0-9+#.]+", role.lower()) if len(w) > 2]
    loc_words = [w for w in re.split(r"[^a-z]+", location.lower()) if len(w) > 2]

    score = 0
    reasons: list[str] = []

    if any(s in text for s in SENIOR_SIGNALS):
        return -100, "looks senior (experience/manager wording)"
    if any(s in text for s in FRESHER_SIGNALS):
        score += 3
        reasons.append("fresher-friendly wording")
    role_hits = sum(1 for w in role_words if w in text)
    if role_hits == 0:
        return -100, "role words not found in listing"
    score += role_hits
    if role_words and role_words[0] in raw.get("title", "").lower():
        score += 2
        reasons.append("role in title")
    if any(w in text for w in loc_words) or "remote" in text or "work from home" in text:
        score += 2
        reasons.append("location/remote match")
    if "india" in text:
        score += 1
    return score, "; ".join(reasons) or "basic match"


def _search_node(state: ScoutState) -> ScoutState:
    try:
        results = search_jobs(
            role=state["role"], location=state["location"],
            max_results=max(state.get("max_results", 5) * 3, 10),
        )
        return {"raw_results": results, "search_error": None}
    except Exception as exc:  # search backend down — surface, don't fake jobs
        return {"raw_results": [], "search_error": str(exc)}


def _filter_node(state: ScoutState) -> ScoutState:
    scored: list[tuple[int, JobPosting]] = []
    for raw in state.get("raw_results", []):
        score, reason = _score(raw, state["role"], state["location"])
        if score < 0:
            continue
        scored.append((
            score,
            JobPosting(
                title=raw.get("title", "Untitled role")[:200],
                company=raw.get("company") or "Not stated in listing",
                location=raw.get("location") or state["location"],
                link=raw.get("link", ""),
                snippet=(raw.get("body") or "")[:300],
                why_it_fits=reason,
                score=score,
            ),
        ))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    # De-dupe by link, keep top N.
    seen: set[str] = set()
    jobs: list[JobPosting] = []
    for _, job in scored:
        key = (job.link or job.title).lower()
        if key in seen:
            continue
        seen.add(key)
        jobs.append(job)
        if len(jobs) >= state.get("max_results", 5):
            break
    return {"jobs": jobs}


def build_scout_graph():
    graph = StateGraph(ScoutState)
    graph.add_node("search", _search_node)
    graph.add_node("filter", _filter_node)
    graph.set_entry_point("search")
    graph.add_edge("search", "filter")
    graph.add_edge("filter", END)
    return graph.compile()


def run_scout(role: str, location: str, max_results: int = 5) -> ScoutResult:
    """Run the Scout graph synchronously and return structured jobs."""
    app = build_scout_graph()
    final = app.invoke({
        "role": role.strip(),
        "location": location.strip(),
        "max_results": max_results,
    })
    error = final.get("search_error")
    if error and not final.get("jobs"):
        raise RuntimeError(f"Job search failed: {error}")
    return ScoutResult(
        role=role.strip(), location=location.strip(),
        jobs=final.get("jobs", []), search_error=error,
    )


def parse_request(text: str) -> tuple[str, str]:
    """Accept JSON {"role": ..., "location": ...} or plain text.

    Plain text forms: "web developer fresher jobs in Patna"
    or "role: web developer, location: Patna".
    """
    text = (text or "").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("role"):
            return str(data["role"]), str(data.get("location") or "India")
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"role\s*:\s*(.+?)\s*,\s*location\s*:\s*(.+)$", text, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"(.+?)\s+in\s+([A-Za-z][A-Za-z ,.-]+)$", text, re.I)
    if m:
        role = re.sub(r"\s+(fresher\s+)?jobs?$", "", m.group(1).strip(), flags=re.I)
        return role, m.group(2).strip()
    return text or "web developer", "India"
