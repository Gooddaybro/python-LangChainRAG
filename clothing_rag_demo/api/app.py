from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.agent.langgraph_executor import run_langgraph_agent
from clothing_rag_demo.config_data import PROJECT_API_TITLE


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    debug: bool = True

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value):
        if not value.strip():
            raise ValueError("query must not be blank")

        return value


app = FastAPI(
    title=PROJECT_API_TITLE,
    description="API entrypoint for the clothing size and product QA assistant.",
    version="0.1.0",
)


def build_chat_response(agent_result, include_debug):
    if include_debug:
        return agent_result

    return {"answer": agent_result["answer"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    result = run_agent(request.query.strip(), chat_history=request.chat_history)
    return build_chat_response(result, request.debug)


@app.post("/chat/langgraph")
def chat_langgraph(request: ChatRequest):
    result = run_langgraph_agent(request.query.strip(), chat_history=request.chat_history)
    return build_chat_response(result, request.debug)
