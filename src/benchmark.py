#!/usr/bin/env python3
"""Compare extraction agents / prompt versions / models on sample inputs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .agents import heuristic_extract, llm_extract, score_extraction
from .llm_client import LLMConfig

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def run_one(name: str, fn) -> dict:
    t0 = time.perf_counter()
    err = None
    data = None
    try:
        data = fn()
    except Exception as exc:  # noqa: BLE001 - demo benchmark should keep going
        err = str(exc)
    elapsed = time.perf_counter() - t0
    result = {"agent": name, "seconds": round(elapsed, 3), "error": err}
    if data is not None:
        result["extraction"] = data
        result["quality"] = score_extraction(data)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark CRM extraction agents")
    parser.add_argument(
        "--input",
        default=str(SAMPLES / "inbound_email.txt"),
        help="Sample file to score",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated Ollama/OpenAI model names to compare (optional)",
    )
    parser.add_argument("--out", default=str(ROOT / "out" / "benchmark.json"))
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    rows = []

    rows.append(run_one("heuristic_baseline", lambda: heuristic_extract(text)))

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        models = [LLMConfig.from_env().model]

    for model in models:
        for prompt in ("v1", "v2"):
            cfg = LLMConfig.from_env()
            cfg.model = model

            def _fn(p=prompt, c=cfg):
                return llm_extract(text, prompt_version=p, config=c)

            rows.append(run_one(f"llm:{model}:prompt_{prompt}", _fn))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"input": args.input, "results": rows}
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("Agent benchmarking (higher quality.score is better)\n")
    for row in rows:
        q = row.get("quality", {})
        score = q.get("score", "n/a")
        print(
            f"- {row['agent']}: score={score} time={row['seconds']}s error={row['error']}"
        )
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
