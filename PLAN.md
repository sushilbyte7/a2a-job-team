# A2A Job Team — Build Plan

**Idea:** Two specialist AI agents, built on *different* frameworks, that discover
each other through Agent Cards and collaborate over the A2A protocol on a real
task: Chandan's job hunt. A live trace UI shows the whole handoff.

**Why this is the "naya daur" project:** in November 2026 every agent works
alone. MCP connects agents to *tools*; A2A connects agents to *other agents* —
and almost nobody has built on it yet. A working two-framework demo, on a real
problem, with the trace visible, is the differentiator.

**Cost:** ₹0. Gemini free tier + Tavily free tier + everything runs locally.

## Architecture

```
User ──> React trace UI (:5173) ──SSE──> Coordinator (:8000, FastAPI + A2A client)
                                              │  discovers via Agent Cards
                                              ├─> Scout (:10001, LangGraph agent)
                                              │     searches + filters fresher jobs
                                              └─> Scribe (:10002, plain Python + Gemini)
                                                    tailors resume bullets + cover note
```

One run: user enters role + location → Coordinator discovers Scout, sends the
task → Scout returns structured jobs → Coordinator sends top job + profile to
Scribe → Scribe returns tailored application text → UI shows every state
change (submitted → working → artifact → completed) as it happens.

Why two frameworks: that *is* the point. Without A2A, a LangGraph agent and a
plain-Python agent cannot talk. The protocol is the product.

## Stack

| Piece | Choice | Why |
|---|---|---|
| Language | Python 3.10+ (3.12 used here) | A2A SDK requirement |
| Protocol | `a2a-sdk[http-server]==1.3.0` | Spec 1.0, verified working (see below) |
| Scout framework | LangGraph | Real agent framework, shows the multi-framework point |
| Scribe framework | Plain Python + `google-genai` | Deliberately different from Scout |
| LLM | Gemini free tier | Already have a key (notebook pipeline) |
| Job search | Tavily free tier, `ddgs` fallback | Tavily needs a free key; ddgs needs none |
| Coordinator | FastAPI + A2A client | Serves UI + streams task events |
| UI | React + Vite | His own stack |
| Servers | Starlette + uvicorn | Per official A2A tutorial |

Ports: Scout 10001, Scribe 10002, Coordinator 8000, UI 5173.

## Verified facts (12 Nov 2026, tested in this workspace)

- `a2a-sdk==1.3.0` + protobuf 7.36.2: card discovery, non-streaming send and
  streaming send all work. See `day1-hello/`.
- The `/message:send` 500 bug reported against `a2a-sdk 1.0.2` + protobuf 7.x
  does **not** reproduce on 1.3.0. Pin 1.3.0; do not use 1.0.2.
- Agent Card path is `/.well-known/agent-card.json`. Old 0.2.x samples used
  `/.well-known/agent.json` — that silently breaks discovery. Do not copy
  0.2.x code.
- The 1.x SDK is proto-first: `AgentCard` etc. are protobuf messages, not
  Pydantic models. Use the helpers (`new_text_message`, `new_text_part`,
  `get_message_text`, `new_task_from_user_message`) and `TaskUpdater`.
- `pip install a2a-sdk` alone resolves 0.2.16 when `protobuf<5.0` is pinned.
  Install `a2a-sdk[http-server]==1.3.0` with no protobuf pin.
- `httpx.AsyncClient` picks up system proxy vars; for localhost work use
  `trust_env=False` (see `echo_client.py`).

## Day-wise plan (~2–3 hrs/day)

### Day 1 — Plumbing ✅ DONE (verified here)
- Echo A2A server + client: card discovery, non-streaming + streaming send.
- Files: `day1-hello/echo_server.py`, `day1-hello/echo_client.py`.
- Run: `python day1-hello/echo_server.py`, then
  `python day1-hello/echo_client.py` in a second terminal.

### Day 2 — Scout (job researcher, LangGraph)
- LangGraph agent: query → Tavily search → filter (fresher, role, location,
  posted recently) → structured output (Pydantic: title, company, location,
  link, why-it-fits).
- Wrap in `AgentExecutor`, serve on :10001 with skill `find_jobs`.
- Test with a small client script before moving on.

### Day 3 — Scribe (application writer, plain Python + Gemini)
- Input: one job + `profile.md` (his real skills, projects, education).
- Output: 3 tailored resume bullets + short cover note. No invented
  experience — the prompt must forbid it (fresher, no job history).
- Serve on :10002 with skill `tailor_application`.

### Day 4 — Coordinator (discovery + delegation)
- FastAPI service on :8000. Discovers both cards, runs the pipeline
  Scout → Scribe, returns combined result + full task trace as JSON.
- CLI end-to-end demo works before any UI exists.

### Day 5 — Trace UI (React + Vite)
- One page: role/location form → live event feed (SSE from Coordinator) →
  job cards → tailored application text, copy button.
- This is the LinkedIn demo: record a 30-second screen capture of a run.

### Day 6 — Hardening
- Timeouts, retries with backoff (Gemini free-tier rate limits), clear
  errors when a key is missing, `profile.md` filled with real data.
- README with architecture, setup, demo GIF/video, honest limitations
  (local-only, free-tier limits, no real applications sent).

### Day 7 — Ship
- Push to GitHub (`a2a-job-team`), LinkedIn Post 1 about the build:
  what A2A is, why agents can't talk today, what this demo proves.

## What Chandan needs to provide

1. **GitHub repo** `a2a-job-team` (public) — create it himself; the GitHub
   connector cannot create repos. Then the scaffold can be pushed.
2. **Gemini API key** — already has one from the notebook pipeline; confirm
   it still works.
3. **Python 3.10+** on his machine + `pip install -r requirements.txt`.
4. **Tavily free key** (optional) — `ddgs` fallback works without one.

## Risks (honest)

- A2A docs are thin and the SDK moves fast (0.2 → 1.3 in months). Pin
  versions; this scaffold is the known-good reference.
- LangGraph has a learning curve; Day 2 is the hardest day. If it slips,
  Scout can start as a plain-Python agent and gain LangGraph on Day 6 —
  but then the two-framework story weakens, so try LangGraph first.
- Gemini free tier rate-limits: keep prompts small, add retries.
- This is a demo, not a product: it does not apply to jobs by itself.
  That is a feature for the story (agent assists, human decides), not a bug.
