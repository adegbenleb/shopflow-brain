"""ShopFlow web app: serves the chat page and passes questions to the agent.

Run with:  uv run uvicorn api.main:app --port 18500 --reload
Then open: http://localhost:18500
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="ShopFlow", version="0.1.0")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class Answer(BaseModel):
    answer: str
    tools_used: list[str]


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/logo.svg")
def logo() -> FileResponse:
    return FileResponse(STATIC / "logo.svg", media_type="image/svg+xml")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/ask")
def ask(body: Question) -> Answer:
    # Imported here so the page loads fast and tests don't need Ollama.
    from langchain_core.messages import HumanMessage

    from agents.assistant import FALLBACK, invents_a_tool
    from agents.assistant import app as agent

    try:
        result = agent.invoke({"messages": [HumanMessage(content=body.question)]})
    except Exception as error:  # noqa: BLE001 - surface any failure as a clear message
        raise HTTPException(
            status_code=503, detail=f"The assistant could not finish: {error}"
        )

    tools_used = [
        call["name"]
        for message in result["messages"]
        for call in (getattr(message, "tool_calls", None) or [])
    ]
    answer = result["messages"][-1].content
    if invents_a_tool(answer):
        answer = FALLBACK
    return Answer(answer=answer, tools_used=tools_used)
