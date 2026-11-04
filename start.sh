#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> [1/4] Starting PostgreSQL 16 (PostGIS + pgvector) & Redpanda Kafka containers..."
docker compose up -d

echo "==> [2/4] Starting Multi-OEM Telco Emulator Suite on http://127.0.0.1:8001 ..."
PYTHONPATH="$(pwd)" .venv/bin/uvicorn emulators.emu.server:app --host 127.0.0.1 --port 8001 &
EMU_PID=$!

echo "==> [3/4] Starting NOC Copilot Backend API on http://127.0.0.1:8002 ..."
PYTHONPATH="$(pwd)" .venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8002 &
API_PID=$!

echo "==> [4/4] Starting ModernNOC Console UI on http://127.0.0.1:5173 ..."
(cd frontend && npm run dev) &
UI_PID=$!

trap 'kill $EMU_PID $API_PID $UI_PID 2>/dev/null || true' EXIT
echo "==> All services live! Open http://127.0.0.1:5173 in your browser."
wait
