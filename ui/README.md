# Trace UI (Day 5)

React + Vite single page that runs the whole team and shows the handoff live:
a role/location form, a streaming event feed (SSE from the Coordinator), job
cards, and the tailored application with a copy button.

## Run

Four terminals, from the repo root:

```bash
# 1 — Scout
python -m scout.server

# 2 — Scribe (needs GEMINI_API_KEY in .env, or SCRIBE_DRY_RUN=1)
python -m scribe.server

# 3 — Coordinator
python -m coordinator.server

# 4 — UI
cd ui
npm install   # first time only
npm run dev   # http://127.0.0.1:5173
```

The Vite dev server proxies `/api` to the Coordinator on :8000, so the page
works with no CORS setup. `npm run build` produces a static `dist/` for
`npm run preview`.

## How it works

`App.jsx` opens an `EventSource` to `/api/stream?role=..&location=..`. Each
trace event appends to the feed as it arrives; the final `result` event
carries the jobs and the tailored application. The "top pick" job card is the
one the Coordinator sent to Scribe.
