#!/bin/bash
# Run from repo root. Starts the FastAPI dev server on port 8000.
# Next.js (next dev) proxies /tools/indicationscope/api/* here via next.config.mjs.
# Uses `python -m uvicorn`: the Python Scripts dir is not always on PATH, so a
# bare `uvicorn` call can fail with "command not found".
set -e
cd "$(dirname "$0")"
python -m uvicorn api.index:app --reload --port 8000
