"""LM Studio adapter reusing the source-grounded chat protocol."""
import json
from dataclasses import replace
from urllib.parse import urlsplit

from app.core.config import LM_STUDIO_API_KEY, LM_STUDIO_BASE_URL, LM_STUDIO_MODEL
from app.services.providers.openrouter import OpenRouterClient
from app.services.providers.provider_errors import LanguageModelError
from app.services.providers.http_resilience import ResilientHttpClient, ResilientHttpError, HttpStatusError

_HTTP = ResilientHttpClient()

class LMStudioError(LanguageModelError):
    provider = "lm_studio"

class LMStudioClient(OpenRouterClient):
    def __init__(self) -> None:
        parsed = urlsplit(LM_STUDIO_BASE_URL)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise LMStudioError("Invalid LM Studio base URL", reason="missing_configuration")
        if not LM_STUDIO_MODEL:
            raise LMStudioError("LM_STUDIO_MODEL is required", reason="missing_configuration")
        self.model = LM_STUDIO_MODEL
        self.api_key = LM_STUDIO_API_KEY

    def _request(self, body):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = _HTTP.request("POST", f"{LM_STUDIO_BASE_URL}/chat/completions", body=json.dumps(body).encode("utf-8"), headers=headers, timeout_seconds=180)
            result = json.loads(response.body.decode("utf-8"))
            if not isinstance(result, dict) or not result.get("choices"):
                raise LMStudioError("Invalid LM Studio response")
            return result
        except HttpStatusError as exc:
            raise LMStudioError("LM Studio rejected the request", status_code=exc.status) from exc
        except ResilientHttpError as exc:
            raise LMStudioError("Could not communicate with LM Studio") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise LMStudioError("Invalid LM Studio response") from exc

    def answer_with_usage(self, *args, **kwargs):
        try:
            result = super().answer_with_usage(*args, **kwargs)
        except LanguageModelError as exc:
            if isinstance(exc, LMStudioError):
                raise
            raise LMStudioError("Invalid LM Studio answer") from exc
        return replace(result, estimated_cost_usd=0.0)
