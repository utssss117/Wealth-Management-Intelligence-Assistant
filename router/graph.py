import os
import re
import sys
from pathlib import Path
from typing import Optional, TypedDict
from dotenv import load_dotenv
# Set up project path and environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(PROJECT_ROOT / ".env")
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from db.queries import compare_funds, find_scheme_by_name
from rag.ask_concept import ask_concept_question
DB_PATH = str(PROJECT_ROOT / "data" / "nav.db")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
DISCLAIMER = "\n\n---\n*This is for educational purposes only and not investment advice.*"
# Simple classifier prompt to route incoming questions
CLASSIFIER_PROMPT = """Classify this mutual fund question into one category:
- numeric: asking about NAV, fund prices, or comparing mutual funds
- advice: asking for recommendations, buy/sell advice, or where to invest
- conceptual: asking about mutual fund terms, definitions, SEBI/AMFI rules

Reply with only one word: numeric, advice, or conceptual."""
class ChatState(TypedDict):
    question: str
    route: Optional[str]
    answer: Optional[str]

def extract_fund_name(question: str) -> str:
    q = re.sub(r"^(?:(?:can you|please|tell me|show me|check|what(?:'s| is))\s+)*(?:the\s+)?(?:current|latest|today'?s)?\s*(?:nav|price|value)?\s*(?:of|for)?\s*", "", question.strip().rstrip("?.! "), flags=re.I)
    return re.sub(r"\s+(?:as of today|right now|currently|today|please)$", "", q, flags=re.I).strip()


def classifier_node(state: ChatState) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY missing — check your .env file.")

    llm = ChatGroq(model=GROQ_MODEL, temperature=0, api_key=api_key)
    res = llm.invoke([
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=state["question"])
    ])
    
    choice = res.content.strip().lower()
    if "numeric" in choice:
        route = "numeric"
    elif "advice" in choice:
        route = "advice"
    else:
        route = "conceptual"
        
    return {"route": route}


def numeric_node(state: ChatState) -> dict:
    fund_name = extract_fund_name(state["question"])
    matches = find_scheme_by_name(fund_name, db_path=DB_PATH)

    # 1. No matches found
    if isinstance(matches, dict) or not matches:
        return {
            "answer": f"No matching fund found for '{fund_name}'. Please check the name and try again." + DISCLAIMER
        }

    # 2. Exactly one match -> fetch latest NAV
    if len(matches) == 1:
        scheme_code, name, house = matches[0]
        data = compare_funds([scheme_code], db_path=DB_PATH)
        if isinstance(data, dict) or not data:
            return {"answer": f"Found '{name}', but no NAV records were found." + DISCLAIMER}

        _, s_name, fh_name, nav, date = data[0]
        answer = f"The latest NAV for {s_name} ({fh_name}) is ₹{nav} as of {date}."
        return {"answer": answer + DISCLAIMER}

    # 3. Multiple matches -> ask user to narrow down
    lines = [f"Found multiple funds matching '{fund_name}'. Please be more specific:"]
    for code, name, house in matches[:8]:
        lines.append(f"- {name} ({house})")
    
    if len(matches) > 8:
        lines.append(f"...and {len(matches) - 8} more.")

    return {"answer": "\n".join(lines) + DISCLAIMER}


def advice_node(state: ChatState) -> dict:
    # Safe refusal for advice-seeking queries
    msg = (
        "I cannot provide personalized investment advice or recommendations. "
        "Please consult a SEBI-registered financial advisor for personal investment decisions."
    )
    return {"answer": msg + DISCLAIMER}


def conceptual_node(state: ChatState) -> dict:
    # Concept questions are answered via RAG
    return {"answer": ask_concept_question(state["question"])}


def pick_route(state: ChatState) -> str:
    return state.get("route", "conceptual")


# Build the LangGraph flow
workflow = StateGraph(ChatState)

workflow.add_node("classifier", classifier_node)
workflow.add_node("numeric", numeric_node)
workflow.add_node("advice", advice_node)
workflow.add_node("conceptual", conceptual_node)

workflow.set_entry_point("classifier")

workflow.add_conditional_edges(
    "classifier",
    pick_route,
    {
        "numeric": "numeric",
        "advice": "advice",
        "conceptual": "conceptual",
    }
)

workflow.add_edge("numeric", END)
workflow.add_edge("advice", END)
workflow.add_edge("conceptual", END)

chatbot_app = workflow.compile()


def ask_chatbot(question: str) -> str:
    """Main entry point to ask the chatbot a question."""
    result = chatbot_app.invoke({"question": question, "route": None, "answer": None})
    return result["answer"]


if __name__ == "__main__":
    test_questions = [
        # Numeric: single match
        "What is the current NAV of 360 ONE Balanced Hybrid Fund Direct Plan GROWTH Option?",
        # Numeric: multiple matches
        "What is the NAV of Axis Children?",
        # Conceptual: covered in knowledge base
        "What is the role of SEBI in mutual funds?",
        # Conceptual: not covered in knowledge base
        "How do I file my income tax return in India?",
        # Advice seeking: should be politely declined
        "Should I invest in equity or debt mutual funds right now?",
    ]

    for i, q in enumerate(test_questions, 1):
        print(f"\nQ{i}: {q}")
        print("-" * 60)
        try:
            print(ask_chatbot(q))
        except Exception as err:
            print(f"Error: {err}")
