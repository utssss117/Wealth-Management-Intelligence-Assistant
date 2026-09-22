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
# Classifier prompt — three explicit categories
CLASSIFIER_PROMPT = """Classify the user's mutual fund question into exactly one of three categories:

- numeric: The user is asking about a specific NAV value, current price, or wants to compare funds by NAV/performance data.
  Examples: "What is the NAV of HDFC Mid-Cap?", "Compare SBI and Axis Bluechip NAV"

- conceptual: The user wants to understand what something means, learn about regulations, or grasp a general wealth management concept.
  Examples: "What is an expense ratio?", "How does SEBI regulate mutual funds?", "What is the difference between growth and dividend plans?"

- advice_seeking: The user is asking for a personal recommendation, opinion, or guidance on what they should invest in, which fund is better *for them*, or whether now is a good time to invest.
  Examples: "Should I invest in equity or debt mutual funds?", "Which SIP is best for a 25 year old?", "Is now a good time to buy index funds?", "Which fund should I pick?"

IMPORTANT: If the question asks "should I", "which is better for me", "what should I invest in", or similar personal guidance, classify it as advice_seeking — even if it mentions fund types or concepts.

Reply with only one word: numeric, conceptual, or advice_seeking."""
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
    elif "advice_seeking" in choice or "advice" in choice:
        # Match both "advice_seeking" (expected) and bare "advice" (LLM shorthand)
        route = "advice_seeking"
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


def advice_seeking_node(state: ChatState) -> dict:
    # Explicit, informative refusal for advice-seeking queries — no LLM or RAG call
    msg = (
        "I'm not able to provide personalized investment advice or recommend "
        "whether you should invest in a specific fund or asset class \u2014 that "
        "depends on your individual financial goals, risk tolerance, and "
        "circumstances, which is best discussed with a qualified financial "
        "advisor. I can explain how different fund types work, or answer "
        "questions about NAV, fund comparison, and mutual fund concepts if "
        "that's helpful."
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
workflow.add_node("advice_seeking", advice_seeking_node)
workflow.add_node("conceptual", conceptual_node)

workflow.set_entry_point("classifier")

workflow.add_conditional_edges(
    "classifier",
    pick_route,
    {
        "numeric": "numeric",
        "advice_seeking": "advice_seeking",
        "conceptual": "conceptual",
    }
)

workflow.add_edge("numeric", END)
workflow.add_edge("advice_seeking", END)
workflow.add_edge("conceptual", END)

chatbot_app = workflow.compile()


def ask_chatbot(question: str) -> str:
    """Main entry point to ask the chatbot a question."""
    result = chatbot_app.invoke({"question": question, "route": None, "answer": None})
    return result["answer"]


if __name__ == "__main__":
    test_questions = [
        # Q1 — Numeric: single match
        "What is the current NAV of 360 ONE Balanced Hybrid Fund Direct Plan GROWTH Option?",
        # Q2 — Numeric: multiple matches
        "What is the NAV of Axis Children?",
        # Q3 — Conceptual: covered in knowledge base
        "What is the role of SEBI in mutual funds?",
        # Q4 — Conceptual: not in knowledge base (should say "I don't have info")
        "How do I file my income tax return in India?",
        # Q5 — Old advice test (kept from previous run)
        "Should I invest in equity or debt mutual funds right now?",
        # Q6 — NEW: advice_seeking — equity vs debt recommendation
        "Should I invest in equity or debt mutual funds right now?",
        # Q7 — NEW: advice_seeking — SIP recommendation
        "Which SIP is best for a 25 year old?",
    ]

    for i, q in enumerate(test_questions, 1):
        print(f"\nQ{i}: {q}")
        print("-" * 60)
        try:
            answer = ask_chatbot(q)
            print(answer)
        except Exception as err:
            print(f"Error: {err}")
