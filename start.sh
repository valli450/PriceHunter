#!/bin/bash
cd /Users/vali/projects/pricehunter
exec /Users/vali/projects/pricehunter/venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
