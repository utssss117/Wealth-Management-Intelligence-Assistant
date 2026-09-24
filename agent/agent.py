import os
import sys
import json
from pathlib import Path
from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(PROJECT_ROOT / ".env")

from langchain_groq import ChatGroq
from langchain_core.messages import (BaseMessage, HumanMessage,SystemMessage,ToolMessage,AIMessage,)
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages

from agent.tools import (
    find_scheme_by_name,
    compare_funds,
    get_nav_trend,
    ask_concept_question,
)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")

SYSTEM_PROMPT = """\
You are a Wealth Management Assistant for Indian mutual funds.
Rules:
1. To answer NAV/fund questions: call find_scheme_by_name first to get the scheme_code, then call compare_funds.
2. For concept questions (what is X, explain X): call ask_concept_question.
3. For personal investment advice (should I invest, which fund for me): decline politely, suggest a SEBI-registered advisor.
4. End every reply with: "This is for educational purposes only and not investment advice."
"""

TOOLS: list[BaseTool] = [
    find_scheme_by_name,
    compare_funds,
    get_nav_trend,
    ask_concept_question,
]

TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in TOOLS}


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def call_model(state: AgentState) -> dict:
    """Call the LLM with tools bound on the current message history."""
    api_key = os.environ["GROQ_API_KEY"]
    llm = ChatGroq(model=GROQ_MODEL, temperature=0, api_key=api_key, max_tokens=900)
    llm_with_tools = llm.bind_tools(TOOLS)
    response = llm_with_tools.invoke(list(state["messages"]))
    return {"messages": [response]}


def call_tools(state: AgentState) -> dict:
    """Execute every tool call requested by the last AIMessage."""
    last_msg = state["messages"][-1]
    tool_messages: list[ToolMessage] = []

    for tc in last_msg.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]

        if tool_name not in TOOL_MAP:
            result = json.dumps({"error": f"Unknown tool: {tool_name}"})
        else:
            try:
                result = TOOL_MAP[tool_name].invoke(tool_args)
                if not isinstance(result, str):
                    result = str(result)
            except Exception as exc:
                result = json.dumps({"error": str(exc)})

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tc["id"],
                name=tool_name,
            )
        )

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """Route to tool execution if the model requested tool calls, otherwise finish."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "call_tools"
    return END


def build_agent():
    graph = StateGraph(AgentState)

    graph.add_node("call_model", call_model)
    graph.add_node("call_tools", call_tools)

    graph.set_entry_point("call_model")

    graph.add_conditional_edges(
        "call_model",
        should_continue,
        {"call_tools": "call_tools", END: END},
    )
    graph.add_edge("call_tools", "call_model")

    return graph.compile()


def ask_agent(question: str, verbose: bool = True) -> str:
    """Run the ReAct agent on a question and return the final answer string."""
    return ask_agent_with_trace(question, verbose=verbose)["answer"]


def ask_agent_with_trace(question: str, verbose: bool = True) -> dict:
    """Run the ReAct agent and return a structured result with the answer, tool calls, and full message history."""
    agent = build_agent()
    result = agent.invoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    })

    tool_calls_ordered: list[dict] = []
    for msg in result["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_ordered.append({"name": tc["name"], "args": tc["args"]})

    if verbose:
        print("\n" + "=" * 70)
        print(f"QUESTION: {question}")
        print("=" * 70)
        if tool_calls_ordered:
            print(f"\n[TOOL CALLS — {len(tool_calls_ordered)} total]")
            for i, tc in enumerate(tool_calls_ordered, 1):
                print(f"  {i}. {tc['name']}({tc['args']})")
        else:
            print("\n[NO TOOL CALLS — answered directly]")

        print("\n[MESSAGE TRACE]")
        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"  → TOOL CALL:   {tc['name']}({tc['args']})")
                else:
                    print(f"\n[FINAL ANSWER]\n{msg.content}")
            elif isinstance(msg, ToolMessage):
                preview = msg.content[:250] + "..." if len(msg.content) > 250 else msg.content
                print(f"  ← TOOL RESULT: ({msg.name}) {preview}")
        print("=" * 70)

    return {
        "answer": result["messages"][-1].content,
        "tool_calls": tool_calls_ordered,
        "messages": result["messages"],
    }


if __name__ == "__main__":
    import time

    test_questions = [
        "what is the nav of hdfc flexi cap fund",
        "what is expense ratio",
        "compare hdfc flexi cap fund and hdfc mid cap fund and explain what expense ratio means",
        "should i invest in equity funds",
    ]

    for i, q in enumerate(test_questions):
        if i > 0:
            print("\n[Waiting 65s to respect Groq rate limit...]")
            time.sleep(65)
        ask_agent(q, verbose=True)
        print()
