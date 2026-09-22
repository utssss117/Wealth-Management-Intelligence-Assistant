import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agent import ask_agent

app = FastAPI(
    title="Wealth Management Intelligence Assistant",
    description=(
        "Ask questions about mutual fund NAVs, SEBI regulations, or general "
        "wealth management concepts. Personal investment advice is out of scope "
        "and will be politely declined."
    ),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # TODO: lock this down before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request / response shapes — Pydantic validates the JSON body automatically
# and gives FastAPI enough information to generate the OpenAPI docs.


class ChatRequest(BaseModel):
    question: str  
class ChatResponse(BaseModel):
    answer: str  
class HealthResponse(BaseModel):
    status: str 
@app.get("/health", response_model=HealthResponse, tags=["Meta"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse, tags=["Chatbot"])
def chat(request: ChatRequest) -> ChatResponse:
    """
    Send any mutual fund question here and the ReAct agent will
    autonomously decide which tools to call:

    - NAV / price questions    → agent calls find_scheme_by_name + compare_funds
    - Concept / regulation Qs  → agent calls ask_concept_question (RAG)
    - Trend questions          → agent calls get_nav_trend
    - "Should I invest in X?"  → politely declined (no personalised advice)

    The answer already includes the educational disclaimer, so you can
    display it as-is in the frontend.
    """
    try:
        answer = ask_agent(request.question, verbose=False)
        return ChatResponse(answer=answer)
    except Exception as exc:
        # Print the real traceback to the server logs so we can debug it,
        # but only send a vague message to the client — no stack traces.
        print(f"[ERROR] /chat failed — question={request.question!r}  reason={exc}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong processing your question. Please try again.",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
