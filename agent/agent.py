"""
KiranaAI Agent — LangGraph ReAct agent powered by DeepSeek.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agent.prompts import SYSTEM_PROMPT
from agent.tools import create_visualization, neo4j_search, sql_query

load_dotenv()


def build_llm() -> ChatOpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY not found. Add it to your .env file."
        )
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=0,
        streaming=True,
    )


@lru_cache(maxsize=1)
def get_agent():
    """Build and cache the KiranaAI ReAct agent (safe across Streamlit reruns)."""
    llm   = build_llm()
    tools = [sql_query, neo4j_search, create_visualization]
    return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
