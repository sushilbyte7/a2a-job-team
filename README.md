# A2A Job Team

Two specialist AI agents, built on **different frameworks**, that discover
each other through Agent Cards and collaborate over the **A2A protocol** on a
real task: finding fresher jobs and tailoring applications.

Today every agent works alone. MCP connects agents to tools; A2A connects
agents to other agents — and almost nobody has built on it yet. This is a
working demo of that missing layer, with the full handoff visible in a live
trace UI.

## How it works

```
You → React trace UI (:5173) ──SSE──> Coordinator (:8000, FastAPI + A2A client)
                                          │  discovers via Agent Cards
                                          ├─> Scout  (:10001, LangGraph)
                                          │     searches + filters fresher jobs
                                          └─> Scribe (:10002, plain Python + Gemini)
                                                tailors resume bullets + cover note
```

1. You enter a role + location.
2. The Coordinator discovers Scout via its Agent Card and delegates the search.
3. Scout returns structured jobs; the Coordinator sends the top job + your
   profile to Scribe.
4. Scribe returns tailored resume bullets + a cover note, grounded only in
   your real history — it never invents experience.

Why two frameworks: that *is* the point. Without A2A, a LangGraph agent and a
plain-Python agent cannot talk. The protocol is the product.

## Quickstart

```bash
git clone https://github.com/sushilbyte7/a2a-job-team.git
cd a2a-job-team
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # add your GEMINI_API_KEY (free, from Google AI Studio)
```

Then start the four servers (one terminal each — or use `start-all.sh` /
`start-all.bat` from `demo/`):

```bash
python -m scout.server        # :10001
python -m scribe.server       # :10002 (needs GEMINI_API_KEY, or SCRIBE_DRY_RUN=1)
python -m coordinator.server  # :8000

cd ui && npm install && npm run dev   # :5173
```

Open http://127.0.0.1:5173, enter a role + location, and watch the trace.

No key? Set `SCRIBE_DRY_RUN=1` for Scribe — it returns a template tailoring
instead of calling Gemini, so the whole pipeline still runs end to end.

## Cost

₹0. Gemini free tier + Tavily free tier (optional — Scout falls back to
`ddgs`, which needs no key) + everything runs locally.

## Honest limitations

- **Demo, not a product.** Nothing is applied for — Scout searches, Scribe
  drafts, you decide. That is deliberate: the agent assists, the human applies.
- **Scout returns job-board listing pages**, not parsed individual postings.
  The top "job" is usually an Indeed/LinkedIn search page for that role, not
  one opening. A Tavily key sometimes returns single listings; parsing real
  postings is future work.
- **Free-tier limits.** Gemini free tier rate-limits (Scribe retries 429/503
  with backoff); `ddgs` search mirrors are flaky (Scout retries each backend,
  the Coordinator retries Scout once).
- **Local only.** All four servers run on your machine; there is no hosted
  deployment, auth, or multi-user support.
- **Gemini model note (Nov 2026).** `gemini-2.5-flash` is retired for new API
  keys (404); Scribe defaults to `gemini-3.5-flash`, overridable with
  `GEMINI_MODEL`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| UI shows an agent offline | That server isn't running | Start it (see Quickstart); check `GET :8000/health` |
| `GEMINI_API_KEY is not set` | No key in `.env` | Add it, or run Scribe with `SCRIBE_DRY_RUN=1` |
| `Scout failed: ddgs search failed on all backends` | Free search mirrors down | Wait and re-run; the Coordinator already retries once |
| `404 ... model ... no longer available` | Retired Gemini model | Set `GEMINI_MODEL=gemini-3.5-flash` |
| Vite page won't open on 127.0.0.1 | Vite bound IPv6 localhost | Already pinned to `127.0.0.1` in `ui/vite.config.js` |
