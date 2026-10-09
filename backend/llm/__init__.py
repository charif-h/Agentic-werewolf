"""Language-model backends behind one small interface"""
from backend.llm.base import ASSISTANT, SYSTEM, USER, LLMClient, LLMError, Message
from backend.llm.fake import FakeLLMClient

__all__ = ["ASSISTANT", "SYSTEM", "USER", "FakeLLMClient", "LLMClient", "LLMError", "Message"]
