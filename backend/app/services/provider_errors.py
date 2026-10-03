"""Failure contracts implemented by external-provider adapters."""


class ProviderError(RuntimeError):
    provider = "external"

    def __init__(self, message: str, status_code: int | None = None, *, reason: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class LanguageModelError(ProviderError):
    provider = "language_model"


class VectorStoreError(ProviderError):
    provider = "vector_store"
