# A2A Job Team

Two specialist AI agents, built on **different frameworks**, that discover each
other through Agent Cards and collaborate over the **A2A protocol** on a real
task: finding fresher jobs and tailoring applications.

Today every agent works alone. MCP connects agents to tools; A2A connects
agents to other agents — and almost nobody has built on it yet. This is a
working demo of that missing layer, with the full handoff visible in a live
trace UI.

## How it works

```
User → React trace UI → Coordinator (FastAPI + A2A client)
                              ├─→ Scout  (LangGraph, :10001) — finds + filters jobs
                              └─→ Scribe (plain Python + Gemini, :10002) — tailors application
```

1. You enter a role + location.
2. The Coordinator discovers Scout via its Agent Card and delegates the search.
3. Scout returns structured jobs; the Coordinator sends the top job + your
   profile to Scribe.
4. Scribe returns tailored resume bullets + a cover note. No invented
   experience — the agent is instructed to use only your real history.

## Status

- [x] Day 1 — A2A plumbing verified: card discovery, non-streaming + streaming
      send on `a2a-sdk==1.3.0` (see `day1-hello/`)
- [x] Day 2 — Scout (LangGraph job researcher) — verified live 12 Nov 2026:
      card discovery + find_jobs returned 5 structured Patna listings (see `scout/`)
- [x] Day 3 — Scribe (Gemini application writer) — verified live 12 Nov 2026:
      card discovery + tailor_application returned 3 tailored bullets + cover
      note for a Scout lead (see `scribe/`). Set `SCRIBE_DRY_RUN=1` for a
      no-LLM template tailoring.
- [x] Day 4 — Coordinator (discovery + delegation pipeline) — verified live
      12 Nov 2026: POST /run and GET /stream both ran Scout → Scribe
      end-to-end, 5 jobs + tailored application with a 9-event trace
      (see `coordinator/`)
- [ ] Day 5 — Trace UI (React + SSE)
- [ ] Day 6 — Hardening + demo recording
- [ ] Day 7 — Ship + LinkedIn post

Full plan: [`PLAN.md`](PLAN.md)

## Quickstart (Day 1 demo)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1: echo agent
python day1-hello/echo_server.py

# Terminal 2: test client (card discovery + send)
python day1-hello/echo_client.py
```

Copy `.env.example` to `.env` and add your `GEMINI_API_KEY` (needed from Day 3;
Tavily key optional, `ddgs` fallback works without one).

## Cost

₹0. Gemini free tier + Tavily free tier + everything runs locally.
