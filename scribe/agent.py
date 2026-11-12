"""Scribe — plain-Python + Gemini application writer (Day 3).

Deliberately a *different* framework from Scout (LangGraph): that is the
point of the demo — without A2A these two agents could not talk at all.

Input: one job (usually a Scout lead) + profile.md (his real history).
Output: 3 tailored resume bullets + a short cover note, as JSON.

Honesty rule, enforced in the prompt and in the dry-run path: Scribe must
never invent experience. He is a fresher with no job or internship history,
so every bullet has to ground itself in profile.md or in the job text.

Public entry point: run_scribe(job: TailorRequest) -> TailoredApplication

Env:
  GEMINI_API_KEY   required unless SCRIBE_DRY_RUN=1
  GEMINI_MODEL     default gemini-3.5-flash — verified working 12 Nov 2026.
                   2.5-flash / 2.5-flash-lite are retired for new users (404);
                   3.7/3.8-flash timed out and flash-latest was 503 that day,
                   so 3.5-flash is the reliable pick. 3.6-flash also worked.
  SCRIBE_DRY_RUN=1 skips the LLM and returns a template tailoring instead.
                   For plumbing tests and demos without a key — the output
                   says so (dry_run: true).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from .models import TailoredApplication, TailorRequest

load_dotenv()

PROFILE_PATH = Path(__file__).with_name("profile.md")
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
MAX_ATTEMPTS = 3


def load_profile() -> str:
    return PROFILE_PATH.read_text(encoding="utf-8")


def build_prompt(job: TailorRequest, profile: str) -> str:
    return f"""You are Scribe, an assistant that tailors a job application for a
fresher developer. Write in clear, plain English. No hype, no buzzwords.

CANDIDATE PROFILE (the only facts you may use about him):
{profile}

JOB TO APPLY FOR:
- Title: {job.title}
- Company: {job.company or "not stated"}
- Location: {job.location or "not stated"}
- Link: {job.link or "not stated"}
- Description/snippet: {job.snippet or "not stated"}

HARD RULES:
1. He is a FRESHER with NO job or internship experience. Never claim any
   job, internship, client work, employer, or years of experience.
2. Never invent metrics, users, revenue, or tools he has not used. Every
   bullet must trace back to the profile above or to the job text.
3. If the job needs a skill he does not have, say the closest real skill he
   has — do not claim the missing one.

OUTPUT — reply with JSON only, no markdown fences, no extra text:
{{
  "bullets": ["<3 resume bullets, each one line, tailored to this job>"],
  "cover_note": "<short cover note, 3-5 sentences, first person>"
}}
Exactly 3 bullets. The cover note must mention the company by name when it
is known, and one specific project that fits this role.
"""


def _call_gemini(prompt: str, model: str) -> str:
    """One Gemini call with retries on rate limits / transient 5xx."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in .env (see .env.example) "
            "or run with SCRIBE_DRY_RUN=1 for a no-LLM template tailoring."
        )
    client = genai.Client(api_key=api_key)
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # NOTE (verified 12 Nov 2026): gemini-3.5-flash thinks by default
            # and thinking tokens count against max_output_tokens — with a
            # 1024 budget the model spent 982 tokens thinking and the output
            # was cut off mid-bullet (FinishReason.MAX_TOKENS). This task
            # needs no thinking, so disable it; JSON mode guarantees the
            # output parses. Keep the 4096 budget as headroom.
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.7,
                    "max_output_tokens": 4096,
                    "response_mime_type": "application/json",
                    "thinking_config": {"thinking_budget": 0},
                },
            )
            text = (response.text or "").strip()
            if text:
                return text
            raise RuntimeError("Gemini returned an empty response")
        except Exception as exc:  # noqa: BLE001 — retry transient, raise rest
            last_error = exc
            message = str(exc).lower()
            if ("429" in message or "503" in message or "overloaded" in message) and attempt < MAX_ATTEMPTS:
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError(f"Gemini call failed after {MAX_ATTEMPTS} attempts: {last_error}")


def _parse_output(text: str, job: TailorRequest, model: str) -> TailoredApplication:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
    data: dict = {}
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # The model sometimes wraps JSON in prose; salvage the first {...}.
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}
    try:
        bullets = [str(b).strip() for b in data.get("bullets", []) if str(b).strip()]
        cover_note = str(data.get("cover_note", "")).strip()
    except AttributeError:
        # Fallback: keep the raw text as the cover note instead of failing
        # the whole run on a formatting slip.
        bullets, cover_note = [], text.strip()
    return TailoredApplication(
        job=job,
        bullets=bullets[:3],
        cover_note=cover_note,
        model=model,
        dry_run=False,
    )


def _dry_run_tailor(job: TailorRequest) -> TailoredApplication:
    """Template tailoring, no LLM. Honest about what it is (dry_run: true)."""
    role = job.title or "this role"
    company = job.company or "your team"
    bullets = [
        "MCA graduate (Pimpri Chinchwad University, Pune, CGPA 7.38) with hands-on full-stack skills in React, Node.js, Express and MongoDB.",
        "Built ServeEase, a full-stack home-services booking platform with JWT + OTP auth, Razorpay payments and a Python sentiment microservice.",
        "Shipped a local-first Reels subtitle generator (OpenAI Whisper, Gradio UI) and a PHP/MySQL bike-rental system — comfortable owning a feature end to end.",
    ]
    cover_note = (
        f"I am applying for the {role} role at {company}. As a recent MCA graduate, "
        "my strongest proof of work is what I have built: ServeEase, a full-stack "
        "booking platform, and smaller tools in Python and PHP/MySQL. I learn fast, "
        "I write clean code, and I would love the chance to contribute to your team."
    )
    return TailoredApplication(
        job=job, bullets=bullets, cover_note=cover_note,
        model="dry-run-template", dry_run=True,
    )


def run_scribe(job: TailorRequest) -> TailoredApplication:
    if os.environ.get("SCRIBE_DRY_RUN") == "1":
        return _dry_run_tailor(job)
    prompt = build_prompt(job, load_profile())
    text = _call_gemini(prompt, DEFAULT_MODEL)
    return _parse_output(text, job, DEFAULT_MODEL)


def parse_request(text: str) -> TailorRequest:
    """Accept JSON {"title": ..., "company": ..., ...} or a plain job title."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty request — send a job as JSON or a job title.")
    if text.startswith("{"):
        try:
            return TailorRequest(**json.loads(text))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Could not parse job JSON: {exc}") from exc
    return TailorRequest(title=text)
