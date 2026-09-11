@echo off
REM Run from repo root. Starts the FastAPI dev server on port 8000.
REM Next.js (next dev) proxies /tools/indicationscope/api/* here via next.config.mjs.
REM Uses `py -m uvicorn`: the Python Scripts dir is not on PATH on all machines,
REM so a bare `uvicorn` call fails with "not recognized".
cd /d "%~dp0"
py -m uvicorn api.index:app --reload --port 8000
