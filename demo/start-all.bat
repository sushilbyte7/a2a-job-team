@echo off
REM Start all four A2A Job Team servers, one window each (Windows).
REM Run from the repo root:  demo\start-all.bat
REM Requires: .venv with requirements installed, .env with GEMINI_API_KEY
REM (or set SCRIBE_DRY_RUN=1 before running to run Scribe without a key).
cd /d "%~dp0.."

if not exist .venv\Scripts\python.exe (
  echo No .venv found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

start "Scout :10001" .venv\Scripts\python.exe -m scout.server
start "Scribe :10002" .venv\Scripts\python.exe -m scribe.server
start "Coordinator :8000" .venv\Scripts\python.exe -m coordinator.server
start "UI :5173" cmd /c "cd ui && npm run dev"

echo Started: Scout :10001, Scribe :10002, Coordinator :8000, UI :5173
echo Open http://127.0.0.1:5173
echo Close the four windows to stop everything.
pause
