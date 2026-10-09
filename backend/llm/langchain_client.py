"""Adapter that lets the cloud providers (via LangChain) be used as an LLMClient"""
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.llm.base import ASSISTANT, SYSTEM, LLMError, Message

_CLASSES = {SYSTEM: SystemMessage, ASSISTANT: AIMessage}


class LangChainClient:
    """Wraps a LangChain chat model; `temperature` and `json_schema` are not supported"""

    def __init__(self, chat_model):
        self.chat_model = chat_model

    def generate(self, messages: Sequence[Message], *, max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 json_schema: Optional[Dict[str, Any]] = None) -> str:
        converted = [_CLASSES.get(m.role, HumanMessage)(content=m.content) for m in messages]
        try:
            return self.chat_model.invoke(converted).content
        except Exception as e:
            # Keep the original text: callers look for "rate limit" / "429" in it
            raise LLMError(str(e)) from e
