# Demo recording script (30–60 seconds)

The LinkedIn demo: one screen capture of a full run. No voiceover needed —
the trace tells the story. Record at 1080p, browser window full screen.

## Before you record

1. Start all four servers (`start-all.bat` on Windows, `start-all.sh` on
   macOS/Linux — or four terminals, see README).
2. Open http://127.0.0.1:5173 and check both status dots are green.
3. Do one throwaway run first (warms the search backends and Gemini, so the
   recorded run is fast and clean). Clear the page with a refresh afterwards.
4. Set role = `web developer`, location = `Patna`.

## Shots (one continuous take)

| Time | What to show |
|---|---|
| 0:00–0:05 | The form, already filled in. Click **Run the team**. |
| 0:05–0:20 | The live trace: `scout discovering → discovered → task_sent → completed`, then the same for Scribe. Let the feed scroll. |
| 0:20–0:35 | Job cards appearing — point at the **top pick** badge on the first card. |
| 0:35–0:50 | Scroll to the tailored application: 3 bullets + cover note. Click **Copy all**. |
| 0:50–0:60 | End on the full page: trace on the left, jobs + application on the right. |

## If something flakes mid-take

- **Scout retry event appears** — keep it in. A visible retry is a better
  demo than a perfect run: it shows the system handling a real failure.
- **A run fails outright** — stop, wait 30 seconds, run again. ddgs mirrors
  recover quickly; do not record a failure as the demo.
- **Gemini 429** — Scribe retries internally; the run just takes longer.
  If it persists, wait a minute (free-tier quota resets quickly).

## Caption draft (for the LinkedIn post)

> Every AI agent today works alone. I built two that talk to each other.
>
> Scout (LangGraph) finds fresher jobs. Scribe (plain Python + Gemini)
> writes the application. Neither knows the other exists — they discover
> each other through Agent Cards and collaborate over the A2A protocol.
>
> This is the 60-second demo. Full code in the repo.
