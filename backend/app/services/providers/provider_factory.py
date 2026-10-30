"""Composition root for external AI and retrieval providers."""

from dataclasses import dataclass

from app.core.config import LLM_PROVIDER
from app.services.providers.lm_studio import LMStudioClient

from app.services.providers.openrouter import OpenRouterClient
from app.services.ports import LanguageModelPort, ProviderFactoryPort, VectorSearchPort
from app.services.providers.qdrant import QdrantClient


def get_vector_store() -> VectorSearchPort:
    return QdrantClient()


def get_language_model(model: str | None = None) -> LanguageModelPort:
    if LLM_PROVIDER == "lm_studio":
        return LMStudioClient()
    if LLM_PROVIDER != "openrouter":
        raise ValueError("LLM_PROVIDER must be openrouter or lm_studio")
    return OpenRouterClient(model=model)


@dataclass(frozen=True)
class DefaultProviderFactory(ProviderFactoryPort):
    """Production wiring; concrete clients remain isolated in this module."""

    def vector_store(self) -> VectorSearchPort:
        return get_vector_store()

    def language_model(self, model: str | None = None) -> LanguageModelPort:
        return get_language_model(model=model)


def get_provider_factory() -> ProviderFactoryPort:
    return DefaultProviderFactory()
