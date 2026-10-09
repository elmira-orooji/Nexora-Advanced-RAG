import unittest
import json
from unittest.mock import patch
from app.services.openrouter import OpenRouterClient, OpenRouterError
from app.services.http_resilience import HttpResponse, HttpStatusError


class ModelPromptTests(unittest.TestCase):
    def test_rejected_request_logs_reason_without_key_or_prompt(self):
        error = HttpStatusError(403, json.dumps({"error": {"message": "Access denied test-key"}}).encode(), {})
        with patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch("app.services.openrouter._HTTP.request", side_effect=error), self.assertLogs("app.services.openrouter", level="WARNING") as logs:
            with self.assertRaises(OpenRouterError) as raised:
                OpenRouterClient(model="provider/model")._request({"messages": [{"content": "private document"}]})
        self.assertEqual(raised.exception.status_code, 403)
        self.assertIn("Access denied [redacted]", logs.output[0])
        self.assertNotIn("test-key", logs.output[0])
        self.assertNotIn("private document", logs.output[0])

    def test_html_rejection_reports_gateway_title(self):
        error = HttpStatusError(403, b"<html><title>Access Forbidden</title><body>private</body></html>", {})
        with patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch("app.services.openrouter._HTTP.request", side_effect=error):
            with self.assertRaisesRegex(OpenRouterError, "Access Forbidden"):
                OpenRouterClient()._request({})

    def test_length_finish_reason_and_configurable_budget(self):
        for reason, expected in [("length", True), ("stop", False), (None, False)]:
            with self.subTest(reason=reason), patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch("app.services.openrouter.ANSWER_MAX_TOKENS", 2048), patch.object(OpenRouterClient, "_request", return_value={"choices": [{"finish_reason": reason, "message": {"content": "Answer"}}]}) as request:
                result = OpenRouterClient().answer_with_usage("Question", [])
            self.assertEqual(result.truncated, expected)
            self.assertEqual(request.call_args.args[0]["max_tokens"], 2048)

    def test_catalog_filters_non_text_models_and_sorts_free_first(self):
        response = HttpResponse(status=200, headers={}, body=json.dumps({"data": [
            {"id": "provider/paid", "name": "Paid", "pricing": {"prompt": "1", "completion": "2"}},
            {"id": "provider/free", "name": "Free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "provider/image", "architecture": {"output_modalities": ["image"]}},
        ]}).encode())
        with patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch("app.services.openrouter._HTTP.request", return_value=response):
            models = OpenRouterClient().list_models()
        self.assertEqual([model["id"] for model in models], ["provider/free", "provider/paid"])
        self.assertTrue(models[0]["free"])

    def test_hybrid_prompt_and_model_override(self):
        with patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch.object(OpenRouterClient, "_request", return_value={"choices": [{"message": {"content": "Hello"}}]}) as request:
            client = OpenRouterClient(model="openrouter/free")
            client.answer("Hello", [], hybrid=True)
        body = request.call_args.args[0]
        self.assertEqual(body["model"], "openrouter/free")
        self.assertIn("general knowledge", body["messages"][0]["content"])
        self.assertIn("untrusted", body["messages"][0]["content"])
        self.assertNotIn("using only", body["messages"][-1]["content"])

    def test_default_prompt_remains_sources_only(self):
        with patch("app.services.openrouter.OPENROUTER_API_KEY", "test-key"), patch.object(OpenRouterClient, "_request", return_value={"choices": [{"message": {"content": "Answer"}}]}) as request:
            OpenRouterClient().answer("Question", [])
        self.assertIn("using only the sources", request.call_args.args[0]["messages"][-1]["content"])
