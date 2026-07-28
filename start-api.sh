#!/bin/bash
# Run from repo root. Starts the FastAPI dev server on port 8000.
# Next.js (vercel dev / next dev) proxies /api/* here via next.config.mjs rewrites.
set -e
cd "$(dirname "$0")"
uvicorn api.index:app --reload --port 8000
