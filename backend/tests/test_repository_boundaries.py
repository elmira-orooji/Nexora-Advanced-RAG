import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.repositories.answer_repository import AnswerRepository
from app.repositories.conversation_repository import ConversationRepository


@pytest.mark.parametrize("repository_type", [AnswerRepository, ConversationRepository])
def test_repository_write_does_not_end_transaction(repository_type):
    db = MagicMock()
    repository = repository_type(db)
    item = object()
    if isinstance(repository, AnswerRepository):
        repository.add(item)
    else:
        repository.save(item)
        repository.delete(item)
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_repository_modules_do_not_own_transaction_boundary():
    repositories = Path(__file__).resolve().parents[1] / "app" / "repositories"
    for path in repositories.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"commit", "rollback"}, path.name
