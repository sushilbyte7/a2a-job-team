"""Structured Scribe input/output — the contract the Coordinator consumes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TailorRequest(BaseModel):
    """One job to tailor an application for (usually a Scout lead)."""

    title: str
    company: str = ""
    location: str = ""
    link: str = ""
    snippet: str = ""


class TailoredApplication(BaseModel):
    job: TailorRequest
    bullets: list[str] = Field(default_factory=list)
    cover_note: str = ""
    model: str = ""
    dry_run: bool = False
