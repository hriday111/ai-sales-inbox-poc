from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CRM = ROOT / "data" / "crm.json"
SEED_CRM = ROOT / "data" / "crm_seed.json"


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def ensure_crm(path: Path = DEFAULT_CRM) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(SEED_CRM.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def load_crm(path: Path = DEFAULT_CRM) -> dict[str, Any]:
    ensure_crm(path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_crm(data: dict[str, Any], path: Path = DEFAULT_CRM) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _next_id(leads: list[dict[str, Any]]) -> str:
    nums = []
    for lead in leads:
        m = re.search(r"(\d+)$", str(lead.get("id", "")))
        if m:
            nums.append(int(m.group(1)))
    return f"L-{(max(nums) + 1) if nums else 1001}"


def upsert_lead(
    extracted: dict[str, Any], source_text: str, path: Path = DEFAULT_CRM
) -> dict[str, Any]:
    crm = load_crm(path)
    leads = crm.setdefault("leads", [])
    email = (extracted.get("email") or "").strip().lower()
    company = (extracted.get("company") or "").strip().lower()

    match = None
    for lead in leads:
        if email and str(lead.get("email", "")).lower() == email:
            match = lead
            break
        if company and str(lead.get("company", "")).lower() == company:
            match = lead
            break

    payload = {
        "company": extracted.get("company") or "Unknown",
        "contact_name": extracted.get("contact_name") or "Unknown",
        "email": extracted.get("email") or "",
        "need": extracted.get("need") or "",
        "budget": extracted.get("budget"),
        "next_step": extracted.get("next_step") or "Follow up",
        "status": extracted.get("status") or "warm",
        "source": extracted.get("source") or "inbound",
        "updated_at": _now(),
    }

    note = {
        "at": _now(),
        "summary": extracted.get("summary") or "",
        "raw_excerpt": source_text.strip()[:500],
    }

    if match is None:
        match = {"id": _next_id(leads), "notes": []}
        leads.append(match)

    match.update(payload)
    match.setdefault("notes", []).append(note)
    save_crm(crm, path)
    return match
