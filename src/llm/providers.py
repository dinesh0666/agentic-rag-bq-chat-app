"""LLM Integration layer supporting multiple providers."""

import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOpenAI
from langchain_ollama import ChatOllama          # updated package with bind_tools support
from langchain_core.messages import BaseMessage


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def get_llm(self, **kwargs):
        """Get the LLM instance."""
        pass
    
    @abstractmethod
    def get_embeddings(self):
        """Get the embeddings model."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")
    
    def get_llm(self, model: str = "gemini-2.5-flash", temperature: float = 0.7, **kwargs):
        """Get Gemini LLM instance."""
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            temperature=temperature,
            **kwargs
        )
    
    def get_embeddings(self):
        """Get Gemini embeddings."""
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=self.api_key
        )


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found")
    
    def get_llm(self, model: str = "openai/gpt-4-turbo-preview", temperature: float = 0.7, **kwargs):
        """Get OpenRouter LLM instance."""
        return ChatOpenAI(
            model=model,
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temperature,
            **kwargs
        )
    
    def get_embeddings(self):
        """Get embeddings (using sentence transformers as fallback)."""
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider (requires a model with tool/function-calling support)."""

    # Models known to support tool-calling in Ollama as of 2025:
    # gpt-oss:20b, kimi-k2.5:cloud, minimax-m2:cloud, llama3.1, mistral-nemo
    DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def get_llm(self, model: Optional[str] = None, temperature: float = 0.1, **kwargs):
        """Get Ollama LLM instance. Model must support tool-calling for the ReAct agent."""
        return ChatOllama(
            model=model or self.DEFAULT_MODEL,
            base_url=self.base_url,
            temperature=temperature,
            **kwargs
        )
    
    def get_embeddings(self):
        """Get embeddings (using sentence transformers as fallback)."""
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )


class LLMFactory:
    """Factory class to create LLM instances."""
    
    _providers = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_name: str, api_key: Optional[str] = None, **kwargs) -> LLMProvider:
        """Create an LLM provider instance."""
        provider_name = provider_name.lower()
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(cls._providers.keys())}")
        
        # Handle different provider initialization signatures
        if provider_name == "ollama":
            # Ollama uses base_url instead of api_key
            base_url = kwargs.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return cls._providers[provider_name](base_url=base_url)
        else:
            # Other providers use api_key
            return cls._providers[provider_name](api_key=api_key)
    
    @classmethod
    def get_llm(cls, provider_name: Optional[str] = None, **kwargs):
        """Get LLM instance directly."""
        provider_name = provider_name or os.getenv("LLM_PROVIDER", "gemini")
        
        provider = cls.create_provider(provider_name)
        return provider.get_llm(**kwargs)
    
    @classmethod
    def get_embeddings(cls, provider_name: Optional[str] = None):
        """Get embeddings model directly."""
        provider_name = provider_name or os.getenv("LLM_PROVIDER", "gemini")
        provider = cls.create_provider(provider_name)
        return provider.get_embeddings()
