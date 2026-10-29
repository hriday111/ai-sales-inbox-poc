# AI Sales Inbox PoC

1. Read an inbound sales email or meeting notes
2. Extract CRM fields with an LLM agent (JSON)
3. Upsert into a mock CRM (`data/crm.json`)
4. Draft a short sales-offer email

Also includes a **benchmark** that compares a heuristic baseline vs LLM prompt versions - useful when talking about experimenting / optimizing agents and models.

## Why this fits the job

- PoC automation for sales / CRM-style workflows (exactly their example projects)
- REST/JSON structured extraction + system integration
- Swappable agents/prompts/models you can measure
- Easy Loom: problem -> live run -> CRM before/after -> offer draft

## Setup (local llama.cpp - recommended here)

Ollama on this machine is currently missing its `llama-server` binary, so use llama.cpp:

```bash
export LD_LIBRARY_PATH=/home/hriday/llama.cpp/build/bin
/home/hriday/llama.cpp/build/bin/llama-server \
  -m /home/hriday/Downloads/MiniCPM5-2B-Q8_0.gguf \
  --host 127.0.0.1 --port 8080 -c 4096 -ngl 0
```

In another terminal:

```bash
cd Emfire/ai-sales-inbox-poc
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1
export OPENAI_MODEL=/home/hriday/Downloads/MiniCPM5-2B-Q8_0.gguf
./run_demo.sh
```

Or step by step:

```bash
python3 -m src.main reset-crm
python3 -m src.main process samples/inbound_email.txt
python3 -m src.main show-crm
python3 -m src.main process samples/meeting_notes.txt
python3 -m src.benchmark
```

No-LLM baseline (always works):

```bash
python3 -m src.main process samples/inbound_email.txt --heuristic
```

Outputs: `out/extract_*.json`, `out/offer_*.txt`, `out/benchmark.json`.
