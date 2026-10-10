"""Language-model backends behind one small interface"""
from backend.llm.base import ASSISTANT, SYSTEM, USER, LLMClient, LLMError, Message
from backend.llm.fake import FakeLLMClient
from backend.llm.formatting import to_alternating
from backend.llm.tokens import estimate_tokens, fit_lines, fit_text

__all__ = ["estimate_tokens", "fit_lines", "fit_text", "to_alternating", "ASSISTANT", "SYSTEM", "USER", "FakeLLMClient", "LLMClient", "LLMError", "Message"]
