@echo off
REM Run from repo root. Starts the FastAPI dev server on port 8000.
REM Next.js (vercel dev / next dev) proxies /api/* here via next.config.mjs rewrites.
cd /d "%~dp0"
uvicorn api.index:app --reload --port 8000
