@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run setup_trugrade.bat first.
  exit /b 1
)

rem Apply any new schema first — idempotent, and the same thing the Docker
rem entrypoint does. Without it, a pull that adds a table (like the analysis
rem job queue) leaves the app running against an older database.
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\init_db.py"

rem Three processes, not two. Film analysis no longer runs inside the web
rem process (it loaded torch into it, which a small web instance cannot
rem hold) — it runs in the worker below, which polls the job queue. Without
rem the worker running, uploads succeed and analysis jobs sit at "queued"
rem forever. See docs/RUN_ON_V2.md.
start "TruGrade Backend" /min "%~dp0.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
start "TruGrade Worker" /min "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\run_worker.py"
start "TruGrade Frontend" /min cmd /k "cd /d ""%~dp0frontend"" && python -m http.server 5173"

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000"

echo TruGrade is starting at http://127.0.0.1:8000
echo   Backend  - uvicorn on :8000
echo   Worker   - analysis job queue (required for film analysis)
echo   Frontend - static server on :5173
endlocal
