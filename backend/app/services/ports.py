"""Provider-agnostic contracts used by application services.

Concrete adapters such as Qdrant and OpenRouter implement these shapes without
leaking their implementation details into retrieval orchestration.
"""

from typing import Any, Protocol


class VectorSearchPort(Protocol):
    def ensure_collection(self) -> None: ...

    def check_ready(self, timeout_seconds: float) -> None: ...

    def replace_document_chunks(self, document_id: str, filename: str, chunks: list[dict[str, Any]]) -> None: ...

    def upsert_chunks(self, document_id: str, filename: str, chunks: list[dict[str, Any]]) -> None: ...

    def delete_document(self, document_id: str) -> None: ...

    def delete_points(self, point_ids: list[str]) -> None: ...

    def search(
        self,
        query: str,
        limit: int,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...


class LanguageModelPort(Protocol):
    def complete(self, prompt: str, *, system_prompt: str, temperature: float, max_tokens: int) -> str: ...

    def list_models(self) -> list[dict[str, Any]]: ...

    def answer(self, question: str, contexts: list[dict[str, Any]], **kwargs: Any) -> str: ...

    def answer_with_usage(self, question: str, contexts: list[dict[str, Any]], **kwargs: Any) -> Any: ...

    def rewrite_query(self, question: str, history: list[dict[str, str]]) -> str: ...

    def research_plan(self, question: str, max_steps: int) -> list[str]: ...


class ProviderFactoryPort(Protocol):
    """Creates infrastructure adapters for an application service."""

    def vector_store(self) -> VectorSearchPort: ...

    def language_model(self, model: str | None = None) -> LanguageModelPort: ...
