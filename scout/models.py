"""Structured Scout output — the contract Coordinator/Scribe will consume."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    title: str
    company: str
    location: str
    link: str = ""
    snippet: str = ""
    why_it_fits: str = ""
    score: int = 0


class ScoutResult(BaseModel):
    role: str
    location: str
    jobs: list[JobPosting] = Field(default_factory=list)
    search_error: str | None = None
