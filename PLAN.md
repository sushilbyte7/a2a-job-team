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
- Day 2 (12 Nov 2026): Scout verified end-to-end — query web developer /
  Patna returned 5 real leads (Indeed: 21 fresher jobs in Patna; LinkedIn,
  Glassdoor, PlacementIndia, SimplyHired) in ~15s. Two lessons: (1) ddgs
  default backend times out (mojeek) — search chain is Tavily (if key) →
  ddgs/duckduckgo → ddgs/bing, 2 attempts each (`scout/search.py`);
  (2) httpx's default 5s timeout kills agent calls — clients must set a
  long timeout (300s in `scout/test_client.py`; Coordinator must too).
  Results are job-board listing pages, not parsed individual postings —
  that is the honest scope of Scout v1.

## Day-wise plan (~2–3 hrs/day)

### Day 1 — Plumbing ✅ DONE (verified here)
- Echo A2A server + client: card discovery, non-streaming + streaming send.
- Files: `day1-hello/echo_server.py`, `day1-hello/echo_client.py`.
- Run: `python day1-hello/echo_server.py`, then
  `python day1-hello/echo_client.py` in a second terminal.

### Day 2 — Scout (job researcher, LangGraph) ✅ DONE (verified here, 12 Nov 2026)
- LangGraph agent: query → Tavily search → filter (fresher, role, location,
  posted recently) → structured output (Pydantic: title, company, location,
  link, why-it-fits).
- Wrap in `AgentExecutor`, serve on :10001 with skill `find_jobs`.
- Test with a small client script before moving on.
- Files: `scout/agent.py` (LangGraph search→filter graph + deterministic
  fresher/senior scoring), `scout/search.py` (Tavily when key set, else ddgs),
  `scout/models.py` (JobPosting/ScoutResult), `scout/server.py` (:10001),
  `scout/test_client.py`.
- Verified: filter unit test (senior listing rejected, 2 fresher kept);
  live A2A round-trip — card discovery + `find_jobs` for
  web developer / Patna returned 5 structured jobs via ddgs
  (Shine, Indeed, PlacementIndia, LinkedIn, SimplyHired).
- Honest limit: ddgs returns job-board search pages, not single postings.
  Tavily (optional free key) may return individual listings; revisit Day 6.
- Gotcha fixed in `scout/test_client.py`: `create_client` needs the same
  `trust_env=False` httpx client as the resolver, else system proxy vars
  break localhost calls (httpx InvalidURL). Day 1 `echo_client.py` has the
  same latent bug — fix it the same way if it fails in a sandboxed shell.
- Run: `python -m scout.server`, then `python -m scout.test_client`.

### Day 3 — Scribe (application writer, plain Python + Gemini) ✅ DONE (verified here, 12 Nov 2026)
- Input: one job + `profile.md` (his real skills, projects, education).
- Output: 3 tailored resume bullets + short cover note. No invented
  experience — the prompt must forbid it (fresher, no job history).
- Serve on :10002 with skill `tailor_application`.
- Files: `scribe/agent.py` (prompt + Gemini call with retries, JSON parse
  with fallback, `SCRIBE_DRY_RUN=1` template mode), `scribe/models.py`
  (TailorRequest/TailoredApplication), `scribe/profile.md` (verified real
  history only), `scribe/server.py` (:10002), `scribe/test_client.py`.
- Verified: card discovery + live A2A round-trip; Gemini tailoring from a
  Scout lead (Indeed web-developer fresher, Patna).
- Model note (12 Nov 2026, swept live with his key): `gemini-2.5-flash` and
  `gemini-2.5-flash-lite` return 404 ("no longer available to new users");
  `gemini-3.7-flash` / `gemini-3.8-flash` timed out and `gemini-flash-latest`
  was 503 (high demand). `gemini-3.5-flash` and `gemini-3.6-flash` answered
  instantly — default is `gemini-3.5-flash`, overridable via `GEMINI_MODEL`.

### Day 4 — Coordinator (discovery + delegation) ✅ DONE (verified here, 12 Nov 2026)
- FastAPI service on :8000. Discovers both cards, runs the pipeline
  Scout → Scribe, returns combined result + full task trace as JSON.
- CLI end-to-end demo works before any UI exists.
- Files: `coordinator/pipeline.py` (async-generator pipeline yielding trace
  events, ending in a `result` event; per-agent discovery + send split so
  the trace order is discovering → discovered → task_sent → completed),
  `coordinator/server.py` (GET / health, POST /run one-shot JSON,
  GET /stream SSE — the Day 5 UI consumes the stream),
  `coordinator/test_client.py` (POST + `--stream` modes).
- Verified: POST /run returned 5 jobs + 3 tailored bullets + cover note
  (gemini-3.5-flash) with a 9-event trace; GET /stream streamed the same
  9 events live. Failure paths verified too: a transient ddgs outage
  surfaced as a clean `scout failed` event + error in the result.
- Gotcha (12 Nov 2026): with streaming=False, `send_message` yields a
  `StreamResponse` proto whose oneof holds the Task at `.task` — reading
  `.artifacts` off the chunk returns nothing. `pipeline.py` unwraps with
  `HasField("task")`; task state is an int, compare with
  `int(TaskState.TASK_STATE_COMPLETED)`.

### Day 5 — Trace UI (React + Vite) ✅ DONE (verified here, 12 Nov 2026)
- One page: role/location form → live event feed (SSE from Coordinator) →
  job cards → tailored application text, copy button.
- This is the LinkedIn demo: record a 30-second screen capture of a run.
- Files: `ui/` — package.json (React 19 + Vite 6), vite.config.js
  (`/api` proxy → Coordinator :8000, host pinned to 127.0.0.1),
  index.html, src/main.jsx, src/App.jsx (EventSource stream, auto-scroll
  feed, job cards with top-pick badge, copy-all button with clipboard
  fallback), src/App.css (dark console theme), README.md.
- Verified: `npm run build` clean (29 modules, 1.7s); dev server on :5173
  served the page, the /api proxy reached Coordinator health, and a full
  /api/stream run delivered all 9 trace events + 5 jobs + 3 bullets.
- Gotcha: Vite binds `localhost` by default, which can resolve to IPv6
  only — 127.0.0.1 health checks then fail. Pin `host: '127.0.0.1'` in
  vite.config.js.

### Day 6 — Hardening ✅ DONE (verified here, 12 Nov 2026)
- Timeouts, retries with backoff (Gemini free-tier rate limits), clear
  errors when a key is missing, `profile.md` filled with real data.
- README with architecture, setup, demo GIF/video, honest limitations
  (local-only, free-tier limits, no real applications sent).
- Done: Coordinator retries the Scout task once (5s delay, `retrying`
  trace event) — covers the ddgs flake that killed a Day 4 run; note
  Scout reports failures as artifact text, not exceptions, so the retry
  checks the payload, not just the transport. Scribe has no coordinator
  retry (it retries Gemini internally; a second attempt would re-spend a
  full call). New GET /health probes both Agent Cards (5s timeout) and
  the UI shows green/red status dots for both agents. requirements.txt
  pinned to the verified set. README rewritten (architecture, quickstart,
  honest limitations, troubleshooting table). demo/ has a 60-second
  recording script, start-all.sh/.bat + stop-all.sh.
- Verified: retry unit test (stubbed Scout fails once with the exact ddgs
  text, then succeeds → `retrying` event, 5 jobs + 3 bullets); full live
  run again clean (9 events, 5 jobs, 3 bullets); /health correct both
  ways (all_ok true with agents up, both down with clear errors when
  stopped); UI build clean.

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
