"""Choose the LLM backend from the settings"""
from typing import Optional

from backend.agents.ai_provider import AIProvider
from backend.llm.base import LLMClient
from backend.llm.langchain_client import LangChainClient


def create_llm_client(provider: Optional[str] = None) -> LLMClient:
    """Build the client for `provider` (default: AI_PROVIDER from the settings)"""
    return LangChainClient(AIProvider.get_llm(provider=provider))
