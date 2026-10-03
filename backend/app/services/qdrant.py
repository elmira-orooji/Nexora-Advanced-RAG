import json
from time import perf_counter
from typing import Any
from urllib.parse import quote

from app.core.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_EMBEDDING_MODEL,
    QDRANT_URL,
)
from app.services.http_resilience import HttpStatusError, ResilientHttpClient, ResilientHttpError
from app.services.performance_measurement import observe_provider_latency
from app.services.provider_errors import VectorStoreError

VECTOR_NAME = "dense"
VECTOR_SIZE = 384
_HTTP = ResilientHttpClient()


class QdrantError(VectorStoreError):
    provider = "qdrant"


class QdrantClient:
    def __init__(self) -> None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise QdrantError("Qdrant configuration is missing")
        self.base_url = QDRANT_URL
        self.api_key = QDRANT_API_KEY
        self.collection = QDRANT_COLLECTION
        self.model = QDRANT_EMBEDDING_MODEL

    def ensure_collection(self) -> None:
        collection = quote(self.collection, safe="")
        collection_info: dict[str, Any] | None = None
        try:
            collection_info = self._request("GET", f"/collections/{collection}")
        except QdrantError as exc:
            if exc.status_code != 404:
                raise
            self._request(
                "PUT",
                f"/collections/{collection}",
                {
                    "vectors": {
                        VECTOR_NAME: {
                            "size": VECTOR_SIZE,
                            "distance": "Cosine",
                        }
                    }
                },
            )

        payload_schema = (collection_info or {}).get("result", {}).get("payload_schema", {})
        if "document_id" not in payload_schema:
            self._request(
                "PUT",
                f"/collections/{collection}/index?wait=true",
                {"field_name": "document_id", "field_schema": "keyword"},
            )

    def check_ready(self, timeout_seconds: float) -> None:
        """Verify collection availability with a read-only, bounded request."""
        collection = quote(self.collection, safe="")
        self._request("GET", f"/collections/{collection}", timeout_seconds=timeout_seconds)

    def replace_document_chunks(
        self,
        document_id: str,
        filename: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        self.delete_document(document_id)
        collection = quote(self.collection, safe="")

        for start in range(0, len(chunks), 32):
            batch = chunks[start : start + 32]
            points = [
                {
                    "id": chunk["id"],
                    "vector": {
                        VECTOR_NAME: {
                            "text": chunk["content"],
                            "model": self.model,
                        }
                    },
                    "payload": {
                        "chunk_id": chunk["id"],
                        "document_id": document_id,
                        "filename": filename,
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"],
                    },
                }
                for chunk in batch
            ]
            self._request(
                "PUT",
                f"/collections/{collection}/points?wait=true",
                {"points": points},
            )

    def delete_document(self, document_id: str) -> None:
        collection = quote(self.collection, safe="")
        self._request(
            "POST",
            f"/collections/{collection}/points/delete?wait=true",
            {
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}}
                    ]
                }
            },
        )

    def delete_points(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        collection = quote(self.collection, safe="")
        self._request("POST", f"/collections/{collection}/points/delete?wait=true", {"points": point_ids})

    def upsert_chunks(self, document_id: str, filename: str, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        collection = quote(self.collection, safe="")
        for start in range(0, len(chunks), 32):
            batch = chunks[start:start + 32]
            points = [{"id": chunk["id"], "vector": {VECTOR_NAME: {"text": chunk["content"], "model": self.model}}, "payload": {"chunk_id": chunk["id"], "document_id": document_id, "filename": filename, "chunk_index": chunk["chunk_index"], "content": chunk["content"]}} for chunk in batch]
            self._request("PUT", f"/collections/{collection}/points?wait=true", {"points": points})

    def search(
        self,
        query: str,
        limit: int,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        collection = quote(self.collection, safe="")
        body: dict[str, Any] = {
            "query": {"text": query, "model": self.model},
            "using": VECTOR_NAME,
            "limit": limit,
            "with_payload": True,
        }
        if document_id:
            body["filter"] = {
                "must": [
                    {"key": "document_id", "match": {"value": document_id}}
                ]
            }
        elif document_ids is not None:
            if not document_ids:
                return []
            body["filter"] = {
                "should": [
                    {"key": "document_id", "match": {"value": doc_id}}
                    for doc_id in document_ids
                ]
            }

        response = self._request(
            "POST",
            f"/collections/{collection}/points/query",
            body,
        )
        return response.get("result", {}).get("points", [])

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout_seconds: float = 60,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        started = perf_counter()
        result = "success"
        try:
            response = _HTTP.request(
                method,
                f"{self.base_url}{path}",
                body=data,
                timeout_seconds=timeout_seconds,
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            return json.loads(response.body.decode("utf-8"))
        except HttpStatusError as exc:
            result = "failed"
            error_message = f"Qdrant returned HTTP {exc.status}"
            try:
                error_body = json.loads(exc.body.decode("utf-8"))
                reason = error_body.get("status", {}).get("error")
                if reason:
                    error_message = f"{error_message}: {reason[:300]}"
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
            raise QdrantError(error_message, status_code=exc.status) from exc
        except ResilientHttpError as exc:
            result = "failed"
            raise QdrantError("Could not communicate with Qdrant") from exc
        except json.JSONDecodeError as exc:
            result = "failed"
            raise QdrantError("Qdrant returned an invalid response") from exc
        finally:
            observe_provider_latency("qdrant", f"{method} {path.split('?')[0]}", perf_counter() - started, result=result)
