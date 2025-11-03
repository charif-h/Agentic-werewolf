"""
AI Provider configuration and LLM initialization
"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv

load_dotenv()


class AIProvider:
    """Factory for creating AI language models"""
    
    @staticmethod
    def get_llm(provider: Optional[str] = None, temperature: float = 0.7):
        """
        Get an LLM instance based on the provider
        
        Args:
            provider: AI provider name (openai, gemini, mistral). 
                     If None, uses AI_PROVIDER from env
            temperature: Temperature for response generation (0.0 to 1.0)
            
        Returns:
            LangChain LLM instance
        """
        if provider is None:
            provider = os.getenv("AI_PROVIDER", "openai").lower()
        
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            return ChatOpenAI(
                model="gpt-4",
                temperature=temperature,
                api_key=api_key
            )
        
        elif provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-pro",
                temperature=temperature,
                google_api_key=api_key
            )
        
        elif provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise ValueError("MISTRAL_API_KEY not found in environment")
            return ChatMistralAI(
                model="mistral-small-latest",
                temperature=temperature,
                mistral_api_key=api_key
            )
        
        else:
            raise ValueError(f"Unknown AI provider: {provider}")
    
    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of configured AI providers"""
        providers = []
        if os.getenv("OPENAI_API_KEY"):
            providers.append("openai")
        if os.getenv("GOOGLE_API_KEY"):
            providers.append("gemini")
        if os.getenv("MISTRAL_API_KEY"):
            providers.append("mistral")
        return providers
