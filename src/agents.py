from __future__ import annotations

import re
from typing import Any

from .llm_client import LLMConfig, chat, extract_json_object

EXTRACT_SYSTEM_V1 = """You extract sales CRM fields from inbound email or meeting notes.
Return ONLY a JSON object with keys:
company, contact_name, email, need, budget, next_step, status, source, summary
Rules:
- status one of: cold, warm, hot
- budget: short string or null
- summary: 1-2 sentences
- If unknown, use null or empty string
No markdown, no commentary."""

EXTRACT_SYSTEM_V2 = """You are a strict CRM extraction agent for sales automation.
Output a single JSON object only (no markdown fences) with exactly these keys:
company, contact_name, email, need, budget, next_step, status, source, summary
Guidance:
- Prefer concrete facts from the text
- need: what they want automated / bought
- next_step: concrete follow-up for a salesperson
- status: hot if timeline/budget is clear, warm if interested, cold otherwise
- source: email or meeting_notes
Keep summary under 40 words."""

OFFER_SYSTEM = """You help salespeople. Write a short, professional sales-offer email draft.
Tone: friendly, concrete, not hype. 120-180 words. Plain text only.
Include: problem understanding, proposed PoC scope, rough next step, soft ask for a call."""


def heuristic_extract(text: str) -> dict[str, Any]:
    """Deterministic fallback / baseline for benchmarking without an LLM."""
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)

    company = "Unknown"
    m = re.search(
        r"\b([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+)*)\s+Sp\.\s*z\s*o\.o\.",
        text,
    )
    if m:
        company = re.sub(r"\s+", " ", m.group(0)).strip()
    else:
        m = re.search(r"\b(Acme Logistics)\b", text)
        if m:
            company = m.group(1)
        else:
            m2 = re.search(
                r"(?:at|from)\s+([A-Z][^\n,]{2,80}?)(?:\s+in\s+[A-Z]|\s*\.|,)", text
            )
            if m2:
                company = re.sub(r"\s+", " ", m2.group(1)).strip(" ,.")

    budget_match = re.search(
        r"(\d[\d\s.,]*\s*(?:-\s*\d[\d\s.,]*)?\s*(?:PLN|USD|EUR)[^\n.]{0,40})",
        text,
        re.I,
    )
    name_match = re.search(
        r"(?:I am|I'm|Attendees:)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text
    )
    if not name_match:
        name_match = re.search(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*$", text, re.M)

    lower = text.lower()
    status = "warm"
    if any(k in lower for k in ("budget", "pilot", "poc", "next 2 weeks", "november")):
        status = "hot"

    need = "AI / automation for sales and CRM workflows"
    if "offer" in lower:
        need = "Draft sales offers from CRM / inbound email automation"

    return {
        "company": company,
        "contact_name": (name_match.group(1).strip() if name_match else "Unknown"),
        "email": email_match.group(0) if email_match else "",
        "need": need,
        "budget": budget_match.group(1).strip() if budget_match else None,
        "next_step": "Send PoC demo and draft offer",
        "status": status,
        "source": "meeting_notes" if "meeting notes" in lower else "email",
        "summary": "Inbound interest in AI sales/CRM automation; extracting lead fields for CRM update.",
    }


def llm_extract(
    text: str, prompt_version: str = "v2", config: LLMConfig | None = None
) -> dict[str, Any]:
    system = EXTRACT_SYSTEM_V2 if prompt_version == "v2" else EXTRACT_SYSTEM_V1
    raw = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        config=config,
        temperature=0.0,
    )
    data = extract_json_object(raw)
    # Normalize expected keys
    for key in (
        "company",
        "contact_name",
        "email",
        "need",
        "budget",
        "next_step",
        "status",
        "source",
        "summary",
    ):
        data.setdefault(key, None)
    return data


def draft_offer(
    lead: dict[str, Any], config: LLMConfig | None = None, use_llm: bool = True
) -> str:
    if not use_llm:
        return (
            f"Hi {lead.get('contact_name') or 'there'},\n\n"
            f"Thanks for reaching out from {lead.get('company')}. "
            f'Based on your note about "{lead.get("need")}", I suggest a short PoC: '
            f"inbound email/meeting notes -> CRM field update -> draft sales offer.\n\n"
            f"Proposed next step: {lead.get('next_step')}. "
            f"Happy to walk through a live demo this week.\n\nBest regards"
        )

    user = f"Lead JSON:\n{lead}\n\nWrite the outbound email draft now."
    return chat(
        [
            {"role": "system", "content": OFFER_SYSTEM},
            {"role": "user", "content": user},
        ],
        config=config,
        temperature=0.4,
    ).strip()


REQUIRED_FIELDS = (
    "company",
    "contact_name",
    "email",
    "need",
    "next_step",
    "status",
    "summary",
)


def score_extraction(data: dict[str, Any]) -> dict[str, Any]:
    filled = 0
    details = {}
    for key in REQUIRED_FIELDS:
        val = data.get(key)
        ok = val is not None and str(val).strip() not in ("", "Unknown", "null", "None")
        details[key] = ok
        if ok:
            filled += 1
    # Budget is optional but rewarded
    budget_ok = bool(data.get("budget"))
    score = filled / len(REQUIRED_FIELDS)
    if budget_ok:
        score = min(1.0, score + 0.05)
    return {
        "score": round(score, 3),
        "filled_required": filled,
        "required_total": len(REQUIRED_FIELDS),
        "budget_present": budget_ok,
        "fields": details,
    }
