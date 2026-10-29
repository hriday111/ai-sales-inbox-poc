#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import draft_offer, heuristic_extract, llm_extract, score_extraction
from .crm_store import DEFAULT_CRM, ensure_crm, load_crm, upsert_lead
from .llm_client import LLMConfig


def cmd_process(args: argparse.Namespace) -> int:
    path = Path(args.input)
    text = path.read_text(encoding="utf-8")
    ensure_crm(Path(args.crm))

    print(f"== Input: {path}")
    print(f"== Mode: {'heuristic' if args.heuristic else f'LLM ({args.prompt})'}")

    if args.heuristic:
        extracted = heuristic_extract(text)
        used_llm = False
    else:
        cfg = LLMConfig.from_env()
        if args.model:
            cfg.model = args.model
        print(f"== Model: {cfg.model} @ {cfg.base_url}")
        extracted = llm_extract(text, prompt_version=args.prompt, config=cfg)
        used_llm = True

    print("\n-- Extracted CRM fields --")
    print(json.dumps(extracted, indent=2, ensure_ascii=False))
    print("\n-- Extraction quality --")
    print(json.dumps(score_extraction(extracted), indent=2))

    lead = upsert_lead(extracted, text, path=Path(args.crm))
    print(f"\n-- CRM upserted: {lead['id']} ({lead.get('company')}) --")

    offer = draft_offer(lead, config=None if args.heuristic else LLMConfig.from_env(), use_llm=used_llm and not args.skip_offer)
    if args.skip_offer and not args.heuristic:
        offer = draft_offer(lead, use_llm=False)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    offer_path = out_dir / f"offer_{lead['id']}.txt"
    extract_path = out_dir / f"extract_{lead['id']}.json"
    offer_path.write_text(offer + "\n", encoding="utf-8")
    extract_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n-- Draft sales offer --\n")
    print(offer)
    print(f"\nSaved: {offer_path}")
    print(f"Saved: {extract_path}")
    print(f"CRM:   {args.crm}")
    return 0


def cmd_show_crm(args: argparse.Namespace) -> int:
    crm = load_crm(Path(args.crm))
    print(json.dumps(crm, indent=2, ensure_ascii=False))
    return 0


def cmd_reset_crm(args: argparse.Namespace) -> int:
    path = Path(args.crm)
    if path.exists():
        path.unlink()
    ensure_crm(path)
    print(f"CRM reset -> {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI sales inbox PoC: email/notes -> CRM update -> offer draft"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    process = sub.add_parser("process", help="Run extraction + CRM upsert + offer draft")
    process.add_argument("input", help="Path to email or meeting notes .txt")
    process.add_argument("--crm", default=str(DEFAULT_CRM))
    process.add_argument("--out-dir", default=str(Path(__file__).resolve().parents[1] / "out"))
    process.add_argument("--heuristic", action="store_true", help="No LLM; baseline extractor")
    process.add_argument("--prompt", choices=("v1", "v2"), default="v2")
    process.add_argument("--model", default=None, help="Override OLLAMA_MODEL / OPENAI_MODEL")
    process.add_argument("--skip-offer", action="store_true", help="Skip LLM offer; template only")
    process.set_defaults(func=cmd_process)

    show = sub.add_parser("show-crm", help="Print CRM JSON")
    show.add_argument("--crm", default=str(DEFAULT_CRM))
    show.set_defaults(func=cmd_show_crm)

    reset = sub.add_parser("reset-crm", help="Reset CRM to seed")
    reset.add_argument("--crm", default=str(DEFAULT_CRM))
    reset.set_defaults(func=cmd_reset_crm)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
