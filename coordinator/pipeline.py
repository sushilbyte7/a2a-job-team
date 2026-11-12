"""Coordinator pipeline — Scout -> Scribe over A2A.

The Coordinator knows nothing about either agent's internals. It discovers
both through their Agent Cards (/.well-known/agent-card.json), sends each a
task as plain text, and reads the structured JSON back from the task
artifact. That is the whole A2A point: a LangGraph agent and a plain-Python
agent cooperating without sharing any code.

run_pipeline(role, location) is an async generator of trace events. Each
event is a dict: {"seq", "time", "agent", "event", "detail"}. The last event
has event == "result" and carries the full payload in "detail":
{"role", "location", "jobs", "top_job", "application"}.

Env:
  SCOUT_URL   default http://127.0.0.1:10001
  SCRIBE_URL  default http://127.0.0.1:10002
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest, TaskState

SCOUT_URL = os.environ.get("SCOUT_URL", "http://127.0.0.1:10001")
SCRIBE_URL = os.environ.get("SCRIBE_URL", "http://127.0.0.1:10002")

# Day 6 hardening: ddgs (Scout's free search backend) flakes — on 12 Nov 2026
# a run died mid-demo with "No results found" on all backends, then worked on
# retry. One Scout retry, 5s later, covers that. Scribe gets no coordinator
# retry: it already retries Gemini 429/503 internally, and a second attempt
# would spend a whole extra Gemini call.
SCOUT_MAX_ATTEMPTS = 2
SCOUT_RETRY_DELAY_SECONDS = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unwrap_task(chunk: Any) -> Any | None:
    """Pull the Task out of a send_message chunk.

    Gotcha (found 12 Nov 2026): with streaming=False, send_message does NOT
    yield a Task — it yields a StreamResponse proto whose oneof holds the
    Task at `.task` (or a status/message/artifact update instead). Reading
    `.artifacts` off the StreamResponse silently returns nothing.
    """
    if isinstance(chunk, dict):
        return chunk if "artifacts" in chunk else chunk.get("task")
    if hasattr(chunk, "HasField"):
        try:
            if chunk.HasField("task"):
                return chunk.task
        except ValueError:
            pass
    if hasattr(chunk, "artifacts"):
        return chunk  # already a Task
    return None


def _chunk_state(chunk: Any) -> int | None:
    """Best-effort task state (int) from any chunk shape."""
    if isinstance(chunk, dict):
        task = chunk.get("task") or chunk
        state = (task.get("status") or {}).get("state")
        return int(state) if state is not None else None
    target = chunk
    if hasattr(chunk, "HasField"):
        try:
            if chunk.HasField("status_update"):
                target = chunk.status_update
            elif chunk.HasField("task"):
                target = chunk.task
        except ValueError:
            pass
    status = getattr(target, "status", None)
    state = getattr(status, "state", None)
    return int(state) if state is not None else None


def _artifact_text(task: Any) -> str:
    """Pull the first artifact's text out of a completed Task (proto or dict)."""
    if isinstance(task, dict):
        artifacts = task.get("artifacts") or []
        if artifacts:
            parts = artifacts[0].get("parts") or []
            if parts:
                return str(parts[0].get("text", ""))
        return ""
    artifacts = getattr(task, "artifacts", None) or []
    if artifacts:
        parts = getattr(artifacts[0], "parts", None) or []
        if parts:
            return str(getattr(parts[0], "text", "") or "")
    return ""


async def _discover(
    httpx_client: httpx.AsyncClient, base_url: str
) -> tuple[Any, dict[str, Any]]:
    """Fetch one agent's card. Returns (card, card summary for the trace)."""
    resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
    card = await resolver.get_agent_card()
    return card, {
        "name": card.name,
        "version": card.version,
        "skills": [s.id for s in card.skills],
    }


async def _send_task(
    httpx_client: httpx.AsyncClient,
    card: Any,
    agent_name: str,
    payload: str,
) -> str:
    """Send one task to a discovered agent; return its artifact text."""
    client = await create_client(
        agent=card,
        client_config=ClientConfig(streaming=False, httpx_client=httpx_client),
    )
    try:
        message = new_text_message(payload, role=Role.ROLE_USER)
        task = None
        async for chunk in client.send_message(SendMessageRequest(message=message)):
            unwrapped = _unwrap_task(chunk)
            if unwrapped is not None:
                task = unwrapped
        if task is None:
            raise RuntimeError(f"{agent_name} returned no task")
        state = _chunk_state(task)
        if state is not None and state != int(TaskState.TASK_STATE_COMPLETED):
            raise RuntimeError(f"{agent_name} ended in state {state}")
        text = _artifact_text(task)
        if not text:
            raise RuntimeError(f"{agent_name} returned a task with no artifact")
        return text
    finally:
        await client.close()


async def run_pipeline(role: str, location: str) -> AsyncIterator[dict[str, Any]]:
    """Yield trace events, ending with a 'result' event carrying the payload."""
    seq = 0

    def event(agent: str, name: str, detail: Any = None) -> dict[str, Any]:
        nonlocal seq
        seq += 1
        return {"seq": seq, "time": _now(), "agent": agent, "event": name, "detail": detail}

    role, location = role.strip(), location.strip()
    yield event("coordinator", "run_started", {"role": role, "location": location})

    # One shared client: trust_env=False so localhost bypasses system proxy
    # vars, and a 300s timeout — Scout's live search plus Scribe's Gemini
    # call take far longer than httpx's 5s default.
    async with httpx.AsyncClient(trust_env=False, timeout=300.0) as httpx_client:
        yield event("scout", "discovering", {"url": SCOUT_URL})
        try:
            scout_card, scout_info = await _discover(httpx_client, SCOUT_URL)
        except Exception as exc:
            yield event("scout", "failed", {"error": f"card discovery failed: {exc}"})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": [],
                "top_job": None, "application": None,
                "error": f"Scout discovery failed: {exc}",
            })
            return
        yield event("scout", "discovered", scout_info)
        yield event("scout", "task_sent", {"role": role, "location": location})
        scout_text = None
        last_error = ""
        for attempt in range(1, SCOUT_MAX_ATTEMPTS + 1):
            try:
                text = await _send_task(
                    httpx_client, scout_card, "Scout",
                    json.dumps({"role": role, "location": location}),
                )
            except Exception as exc:  # noqa: BLE001 — transient failures are retryable
                text, last_error = None, str(exc)
            # Scout reports its own failures as plain text ("Scout failed:
            # ...") instead of raising — that is a retryable failure too.
            if text is not None and not text.strip().startswith("Scout failed:"):
                scout_text = text
                break
            last_error = (text or last_error or "empty result").strip()[:300]
            if attempt < SCOUT_MAX_ATTEMPTS:
                yield event("scout", "retrying", {
                    "attempt": attempt + 1,
                    "error": last_error[:200],
                    "delay_seconds": SCOUT_RETRY_DELAY_SECONDS,
                })
                await asyncio.sleep(SCOUT_RETRY_DELAY_SECONDS)
        if scout_text is None:
            yield event("scout", "failed", {"error": last_error})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": [],
                "top_job": None, "application": None,
                "error": last_error if last_error.startswith("Scout failed") else f"Scout failed: {last_error}",
            })
            return
        try:
            scout_result = json.loads(scout_text)
            jobs = scout_result.get("jobs", [])
        except (json.JSONDecodeError, AttributeError):
            # The agent reports its own failures as plain text
            # ("Scout failed: ...") — pass that through, don't wrap it as a
            # parse error.
            err = scout_text.strip()[:300] or "empty result"
            yield event("scout", "failed", {"error": err})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": [],
                "top_job": None, "application": None,
                "error": err if err.startswith("Scout failed") else f"Scout returned an unparsable result: {err}",
            })
            return
        if not jobs:
            yield event("scout", "completed", {"jobs": 0})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": [],
                "top_job": None, "application": None,
                "error": "Scout found no fresher jobs for this role + location.",
            })
            return
        top_job = jobs[0]  # Scout sorts by score, best first.
        yield event("scout", "completed", {
            "jobs": len(jobs),
            "top_job": {"title": top_job.get("title"), "company": top_job.get("company")},
        })

        yield event("scribe", "discovering", {"url": SCRIBE_URL})
        try:
            scribe_card, scribe_info = await _discover(httpx_client, SCRIBE_URL)
        except Exception as exc:
            yield event("scribe", "failed", {"error": f"card discovery failed: {exc}"})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": jobs,
                "top_job": top_job, "application": None,
                "error": f"Scribe discovery failed: {exc}",
            })
            return
        yield event("scribe", "discovered", scribe_info)
        yield event("scribe", "task_sent", {
            "title": top_job.get("title"), "company": top_job.get("company"),
        })
        try:
            scribe_text = await _send_task(
                httpx_client, scribe_card, "Scribe", json.dumps(top_job),
            )
        except Exception as exc:
            yield event("scribe", "failed", {"error": str(exc)})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": jobs,
                "top_job": top_job, "application": None,
                "error": f"Scribe failed: {exc}",
            })
            return
        try:
            application = json.loads(scribe_text)
        except (json.JSONDecodeError, AttributeError):
            err = scribe_text.strip()[:300] or "empty result"
            yield event("scribe", "failed", {"error": err})
            yield event("coordinator", "result", {
                "role": role, "location": location, "jobs": jobs,
                "top_job": top_job, "application": None,
                "error": err if err.startswith("Scribe failed") else f"Scribe returned an unparsable result: {err}",
            })
            return
        yield event("scribe", "completed", {
            "bullets": len(application.get("bullets", [])),
            "model": application.get("model"),
        })

    yield event("coordinator", "result", {
        "role": role, "location": location, "jobs": jobs,
        "top_job": top_job, "application": application,
    })


async def run_pipeline_sync(role: str, location: str) -> dict[str, Any]:
    """Run the pipeline and collect the trace + final result in one dict."""
    trace: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    async for evt in run_pipeline(role, location):
        if evt["event"] == "result":
            result = evt["detail"]
        else:
            trace.append(evt)
    return {"trace": trace, "result": result}


async def check_agents() -> dict[str, dict[str, Any]]:
    """Probe both Agent Cards with a short timeout. Powers GET /health and
    the UI's status dots, so a missing server is obvious before a run."""
    statuses: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(trust_env=False, timeout=5.0) as client:
        for name, url in (("scout", SCOUT_URL), ("scribe", SCRIBE_URL)):
            try:
                _, info = await _discover(client, url)
                statuses[name] = {"status": "ok", "url": url, **info}
            except Exception as exc:  # noqa: BLE001 — any failure means "down" here
                statuses[name] = {"status": "down", "url": url, "error": str(exc)[:200]}
    return statuses
