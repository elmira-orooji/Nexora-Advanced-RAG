import ast
from pathlib import Path
from unittest.mock import patch

from app.services import provider_factory
from app.services.eval_service import _llm_judge


def test_concrete_clients_are_only_imported_by_factory():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    violations = []
    for path in app_dir.rglob("*.py"):
        if path.name == "provider_factory.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom):
                if any(alias.name in {"QdrantClient", "OpenRouterClient"} for alias in node.names):
                    violations.append(str(path.relative_to(app_dir)))
    assert violations == []


def test_factory_preserves_model_selection():
    with patch.object(provider_factory, "OpenRouterClient") as adapter:
        assert provider_factory.get_language_model(model="custom") is adapter.return_value
        adapter.assert_called_once_with(model="custom")


def test_factory_creates_vector_adapter():
    with patch.object(provider_factory, "QdrantClient") as adapter:
        assert provider_factory.get_vector_store() is adapter.return_value
        adapter.assert_called_once_with()


def test_evaluation_uses_public_completion_contract():
    class Model:
        def complete(self, prompt, *, system_prompt, temperature, max_tokens):
            assert prompt == "judge this"
            assert system_prompt
            assert temperature == 0.0
            assert max_tokens == 300
            return '{"score": 0.8, "reason": "grounded"}'

    assert _llm_judge(Model(), "judge this") == (0.8, "grounded")
