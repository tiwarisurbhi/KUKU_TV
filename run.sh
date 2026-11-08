#!/usr/bin/env bash
# Start Screening Room on http://localhost:8000
set -e
cd "$(dirname "$0")"
python3 -m pip install -q -r backend/requirements.txt
# First run, or keys still blank: walk through key setup (skipped when not in a terminal)
if [ -t 0 ] && ! grep -Eq '^SILICONFLOW_API_KEY=.+' backend/.env 2>/dev/null && ! grep -q '^MOCK_LLM=1' backend/.env 2>/dev/null; then
  python3 setup_keys.py
fi
python3 frontend/build.py
cd backend && exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
