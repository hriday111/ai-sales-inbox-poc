#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://127.0.0.1:8080/v1}"
export OPENAI_MODEL="${OPENAI_MODEL:-/home/hriday/Downloads/MiniCPM5-2B-Q8_0.gguf}"
export LLM_MAX_TOKENS="${LLM_MAX_TOKENS:-700}"

echo "Using $OPENAI_BASE_URL model=$OPENAI_MODEL"
python3 -m src.main reset-crm
python3 -m src.main process samples/inbound_email.txt
python3 -m src.main show-crm
echo
echo "Optional benchmark:"
echo "  python3 -m src.benchmark"
