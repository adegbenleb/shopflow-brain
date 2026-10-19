"""ShopFlow's data assistant: a LangGraph agent running on a local Ollama model."""

import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.tools import TOOLS

load_dotenv()

SYSTEM = SystemMessage(
    content=(
        "You are ShopFlow's data assistant for an online store. "
        "Always use a tool to get numbers. Never invent or estimate data. "
        "You can only use the tools you were given. Never invent a tool name, "
        "and never write a tool call as text in your answer. "
        "If no tool can answer the question, say so plainly and suggest what you can answer. "
        "Revenue is in Brazilian reais (R$). Answer briefly and clearly."
    )
)

llm = ChatOllama(
    model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
    base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    temperature=0,
).bind_tools(TOOLS)


def call_model(state: MessagesState) -> dict:
    """Ask the LLM what to do next: call a tool, or answer."""
    return {"messages": [llm.invoke([SYSTEM, *state["messages"]])]}


graph = StateGraph(MessagesState)
graph.add_node("assistant", call_model)
graph.add_node("tools", ToolNode(TOOLS))
graph.add_edge(START, "assistant")
graph.add_conditional_edges("assistant", tools_condition)
graph.add_edge("tools", "assistant")
app = graph.compile()


KNOWN_TOOLS = {t.name for t in TOOLS}
FALLBACK = (
    "I can't answer that with the tools I have yet. I can help with sales by category, "
    "top products, top customers, customers by state, delivery performance, "
    "and products bought together."
)


def invents_a_tool(text: str) -> bool:
    """True if the answer mentions or writes out a tool that doesn't exist."""
    named = re.findall(r'"name"\s*:\s*"(\w+)"', text)
    mentioned = re.findall(r'["`](\w+)["`]\s+tool', text)
    return any(name not in KNOWN_TOOLS for name in named + mentioned)


def ask(question: str) -> str:
    result = app.invoke({"messages": [HumanMessage(content=question)]})
    answer = result["messages"][-1].content
    return FALLBACK if invents_a_tool(answer) else answer


if __name__ == "__main__":
    print("ShopFlow assistant. Type a question, or 'exit' to quit.")
    while (question := input("\nYou: ").strip()).lower() != "exit":
        if question:
            print(f"\nAssistant: {ask(question)}")
