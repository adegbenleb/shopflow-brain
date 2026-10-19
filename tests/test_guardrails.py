from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agents import assistant
from agents.assistant import FALLBACK, KNOWN_TOOLS, invents_a_tool
from api.main import app

client = TestClient(app)


def test_new_tools_are_registered():
    assert {"list_categories", "top_products", "top_customers"} <= KNOWN_TOOLS


def test_plain_answer_passes():
    assert not invents_a_tool("The top category is health_beauty with R$ 1,258,681.")


def test_real_tool_mention_passes():
    assert not invents_a_tool("I used the `top_products` tool.")


def test_invented_tool_call_written_as_text_is_caught():
    assert invents_a_tool(
        '{"name": "best_selling", "parameters": {"category": "beauty"}}'
    )


def test_invented_tool_mention_is_caught():
    assert invents_a_tool("You could try the `best_selling` tool.")


class FakeAgent:
    def __init__(self, answer: str):
        self.answer = answer

    def invoke(self, _state: dict) -> dict:
        return {"messages": [AIMessage(content=self.answer)]}


def test_api_replaces_invented_tool_with_fallback(monkeypatch):
    monkeypatch.setattr(assistant, "app", FakeAgent('{"name": "best_selling"}'))
    response = client.post("/api/ask", json={"question": "Best beauty products?"})
    assert response.json()["answer"] == FALLBACK


def test_api_keeps_honest_answer(monkeypatch):
    monkeypatch.setattr(assistant, "app", FakeAgent("Health_beauty leads."))
    response = client.post("/api/ask", json={"question": "Best category?"})
    assert response.json()["answer"] == "Health_beauty leads."
