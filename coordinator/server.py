"""Coordinator FastAPI server — :8000.

Run (with scout/server.py on :10001 and scribe/server.py on :10002):
  python -m coordinator.server

Endpoints:
  GET  /                        service info + agent URLs
  GET  /health                  probes both Agent Cards, reports per-agent
                                ok/down — the UI shows this before a run
  POST /run                     {"role": ..., "location": ...} -> full result
                                + trace as one JSON document
  GET  /stream?role=..&location=..   same run as a server-sent event stream
                                (one `data:` line per trace event; the last
                                event is the result) — this is what the
                                Day 5 trace UI consumes
"""

from __future__ import annotations

import json
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .pipeline import SCOUT_URL, SCRIBE_URL, check_agents, run_pipeline, run_pipeline_sync

app = FastAPI(title="A2A Job Team — Coordinator")


class RunRequest(BaseModel):
    role: str = "web developer"
    location: str = "Patna"


@app.get("/")
def info() -> dict:
    return {
        "service": "coordinator",
        "status": "ok",
        "scout_url": SCOUT_URL,
        "scribe_url": SCRIBE_URL,
    }


@app.get("/health")
async def health() -> dict:
    agents = await check_agents()
    return {
        "coordinator": "ok",
        "agents": agents,
        "all_ok": all(a["status"] == "ok" for a in agents.values()),
    }


@app.post("/run")
async def run(request: RunRequest) -> dict:
    return await run_pipeline_sync(request.role, request.location)


@app.get("/stream")
async def stream(role: str = "web developer", location: str = "Patna"):
    async def event_source():
        async for evt in run_pipeline(role, location):
            yield f"data: {json.dumps(evt)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
