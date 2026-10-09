"""
AI Provider configuration and LLM initialization
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI

from backend.config import get_settings


class AIProvider:
    """Factory for creating AI language models"""

    @staticmethod
    def get_llm(provider: Optional[str] = None, temperature: Optional[float] = None):
        """
        Get an LLM instance based on the provider

        Args:
            provider: AI provider name (openai, gemini, mistral).
                     If None, uses AI_PROVIDER from the settings
            temperature: Temperature for response generation (0.0 to 1.0).
                     If None, uses PLAYER_TEMPERATURE from the settings

        Returns:
            LangChain LLM instance
        """
        settings = get_settings()
        provider = (provider or settings.ai_provider).lower()
        if temperature is None:
            temperature = settings.player_temperature

        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            return ChatOpenAI(
                model=settings.openai_model,
                temperature=temperature,
                api_key=settings.openai_api_key
            )

        elif provider == "gemini":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            return ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                temperature=temperature,
                google_api_key=settings.google_api_key
            )

        elif provider == "mistral":
            if not settings.mistral_api_key:
                raise ValueError("MISTRAL_API_KEY not found in environment")
            return ChatMistralAI(
                model=settings.mistral_model,
                temperature=temperature,
                mistral_api_key=settings.mistral_api_key
            )

        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of configured AI providers"""
        settings = get_settings()
        providers = []
        if settings.openai_api_key:
            providers.append("openai")
        if settings.google_api_key:
            providers.append("gemini")
        if settings.mistral_api_key:
            providers.append("mistral")
        return providers
