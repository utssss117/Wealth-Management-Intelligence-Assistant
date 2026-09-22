# agent/tools.py
# LangChain @tool wrappers around the four backend functions.
# Docstrings are kept concise — Groq free tier has a 7k ITPM limit,
# so the tool schemas must be small.

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from langchain_core.tools import tool

from db.queries import (
    find_scheme_by_name as _find_scheme_by_name,
    compare_funds as _compare_funds,
    get_nav_trend as _get_nav_trend,
)
from rag.ask_concept import ask_concept_question as _ask_concept_question


@tool
def find_scheme_by_name(name_query: str) -> str:
    """Search mutual funds by name (partial match). Returns scheme_code,
    scheme_name, fund_house. Call this FIRST when user gives a fund name,
    before calling compare_funds or get_nav_trend which need a scheme_code."""
    result = _find_scheme_by_name(name_query)
    if isinstance(result, dict):
        return json.dumps(result)
    rows = [
        {"scheme_code": str(code), "scheme_name": name, "fund_house": house}
        for code, name, house in result
    ]
    return json.dumps(rows[:10])  # cap at 10 results to keep tokens low


@tool
def compare_funds(scheme_codes: str) -> str:
    """Get latest NAV for one or more funds. Input: comma-separated numeric
    scheme codes (e.g. '119551' or '119551,125497'). Call find_scheme_by_name
    first if you only have a fund name, not a scheme code."""
    codes = [c.strip() for c in scheme_codes.split(",") if c.strip()]
    result = _compare_funds(codes)
    if isinstance(result, dict):
        return json.dumps(result)
    rows = [
        {
            "scheme_code": str(r[0]),
            "scheme_name": r[1],
            "fund_house": r[2],
            "latest_nav": r[3],
            "latest_nav_date": r[4],
        }
        for r in result
    ]
    return json.dumps(rows)


@tool
def get_nav_trend(scheme_code: str, start_date: str, end_date: str) -> str:
    """Get historical NAV data for a fund between two dates (YYYY-MM-DD).
    Requires exact numeric scheme_code — call find_scheme_by_name first if
    you have only a name."""
    result = _get_nav_trend(scheme_code, start_date, end_date)
    if isinstance(result, dict):
        return json.dumps(result)
    rows = [{"nav_date": row[0], "nav": row[1]} for row in result]
    return json.dumps(rows)


@tool
def ask_concept_question(query: str) -> str:
    """Answer conceptual questions about mutual funds and wealth management
    using a RAG knowledge base (NAV, expense ratio, SIP, ELSS, SEBI, etc.).
    Use this for 'what is X?' / 'explain X' questions. Do NOT use for
    personal investment advice questions."""
    return _ask_concept_question(query)
