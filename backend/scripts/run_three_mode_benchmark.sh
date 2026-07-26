#!/bin/bash
set -e
cd /Users/lakshmanrajith/Downloads/locusai_fresh/backend

restart_server() {
  local mode=$1
  echo "=== restarting server with RETRIEVAL_MODE=$mode ==="
  lsof -ti :8000 | xargs -r kill 2>/dev/null || true
  sleep 3
  RETRIEVAL_MODE=$mode PYTHONPATH=src nohup .venv/bin/python main.py > /tmp/server_${mode}.log 2>&1 &
  sleep 1
  # wait for readiness
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs || echo 000)
    if [ "$code" = "200" ]; then
      echo "server ready (attempt $i)"
      break
    fi
    sleep 1
  done
  # verify actual RETRIEVAL_MODE on the worker process
  pid=$(lsof -ti :8000 | head -1)
  actual_mode=$(ps eww $pid 2>/dev/null | tr ' ' '\n' | grep RETRIEVAL_MODE || echo "NOT_FOUND")
  echo "verified worker env: $actual_mode"
}

for mode in semantic_only keyword_only hybrid_rrf; do
  restart_server $mode
  echo "=== running benchmark for mode=$mode ==="
  PYTHONPATH=src .venv/bin/python scripts/run_full_benchmark.py $mode
  echo "=== completed mode=$mode ==="
done

echo "ALL_THREE_MODES_COMPLETE"
