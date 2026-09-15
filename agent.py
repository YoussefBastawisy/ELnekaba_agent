"""
agent.py — the agent itself. No Streamlit in this file.

Everything you built across Sessions 2, 3 and 4 lives here:
  Session 2  search_handbook   retrieval over your own documents
  Session 3  public_holidays   a tool the agent chooses to call
  Session 4  book_leave        an irreversible action behind an approval gate
  Session 4  checkpointer      memory, and the ability to pause and resume

Keeping this separate from the interface is the point. You could put a different
front end on it tomorrow and change nothing in here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

try:                                    # current name
    from langchain.agents import create_agent
except ImportError:                     # older installs
    from langgraph.prebuilt import create_react_agent as create_agent

load_dotenv()

DATA = Path(__file__).parent / "data"
HOLIDAY_API = "https://date.nager.at/api/v3"

PREFERRED_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

SYSTEM_PROMPT = """You are the Nile Systems HR assistant.

Rules you must follow:
- Answer questions about leave, expenses and refund approvals using search_handbook.
- Use public_holidays for anything about public holidays or days off.
- If the handbook does not cover something, say "That is not in the handbook" and
  name HR as the contact. Never guess a number, a date or a policy.
- Never state a figure that did not come from a tool result.
- Say which source each fact came from.
"""


# --------------------------------------------------------------------------
# Retrieval — semantic if available, keyword if not
# --------------------------------------------------------------------------

def _load_sections() -> list[str]:
    text = (DATA / "handbook.md").read_text(encoding="utf-8")
    parts = [p.strip() for p in text.split("\n## ") if p.strip()]
    return [p if p.startswith("#") else "## " + p for p in parts]


SECTIONS = _load_sections()
_BACKEND = "keyword"
_embedder = None
_vectors = None

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    _embedder = SentenceTransformer("intfloat/multilingual-e5-small")
    _vectors = _embedder.encode(
        ["passage: " + s for s in SECTIONS], normalize_embeddings=True
    )
    _BACKEND = "semantic"
except Exception:
    # No sentence-transformers, no disk space, or no network on first run.
    # The app still works — it just matches words instead of meaning.
    _BACKEND = "keyword"


def retrieval_backend() -> str:
    """Which search the app ended up using. Shown in the sidebar."""
    return _BACKEND


def _search(query: str, k: int = 2) -> list[str]:
    if _BACKEND == "semantic":
        import numpy as np

        q = _embedder.encode(["query: " + query], normalize_embeddings=True)[0]
        order = np.argsort(_vectors @ q)[::-1][:k]
        return [SECTIONS[i] for i in order]

    words = {w for w in query.lower().split() if len(w) > 3}
    scored = [(len(words & set(s.lower().split())), s) for s in SECTIONS]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for score, s in scored[:k] if score > 0] or [SECTIONS[0]]


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool
def search_handbook(query: str) -> str:
    """Search the Nile Systems staff handbook for company policy on annual leave,
    carry over, booking rules, travel expenses and refund approval limits.
    Use this for any question about company rules."""
    return json.dumps({"passages": _search(query)}, ensure_ascii=False)


@tool
def public_holidays(year: int, country_code: str = "EG") -> str:
    """List official public holidays for a country and year. country_code is a
    two-letter ISO code such as EG, SA or US. Use for questions about public
    holidays, long weekends, or whether a date is a holiday."""
    try:
        r = requests.get(
            f"{HOLIDAY_API}/PublicHolidays/{year}/{country_code.upper()}", timeout=20
        )
        if r.status_code != 200:
            return json.dumps({"error": f"no holiday data for {country_code} {year}"})
        days = [{"date": h["date"], "name": h["name"]} for h in r.json()]
        return json.dumps({"count": len(days), "holidays": days}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


@tool
def book_leave(staff_name: str, days: int, start_date: str) -> str:
    """Book annual leave for a member of staff. This writes to the HR system and
    cannot be undone automatically. start_date must be YYYY-MM-DD."""
    decision = interrupt(
        {
            "action": "book_leave",
            "staff_name": staff_name,
            "days": days,
            "start_date": start_date,
        }
    )
    if decision != "approve":
        return json.dumps({"status": "declined by approver"})
    return json.dumps(
        {"status": "booked", "staff_name": staff_name, "days": days,
         "start_date": start_date}
    )


READ_TOOLS = [search_handbook, public_holidays]
WRITE_TOOLS = [book_leave]
ALL_TOOLS = READ_TOOLS + WRITE_TOOLS


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------

def pick_model() -> str:
    """Ask Groq which models are actually live. Names get retired regularly."""
    from groq import Groq

    available = {m.id for m in Groq().models.list().data}
    for name in PREFERRED_MODELS:
        if name in available:
            return name
    raise RuntimeError(
        "None of the preferred models are available. Live models: "
        + ", ".join(sorted(available))
    )


def build_agent(model=None, tools=None, checkpointer=None):
    """Create the agent. Pass `model` to inject a fake one in tests."""
    if model is None:
        from langchain_groq import ChatGroq

        model = ChatGroq(model=pick_model(), temperature=0)
    return create_agent(
        model,
        tools=ALL_TOOLS if tools is None else tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver() if checkpointer is None else checkpointer,
    )


def has_api_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))
