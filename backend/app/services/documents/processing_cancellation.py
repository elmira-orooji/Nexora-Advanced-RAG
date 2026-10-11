"""Cooperative cancellation checkpoints for blocking document extraction."""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable


class ProcessingCancelled(RuntimeError):
    pass


_check: ContextVar[Callable[[], None] | None] = ContextVar("processing_cancel_check", default=None)


def check_processing_cancelled() -> None:
    check = _check.get()
    if check is not None:
        check()


@contextmanager
def cancellation_scope(check: Callable[[], None]):
    token = _check.set(check)
    try:
        check_processing_cancelled()
        yield
        check_processing_cancelled()
    finally:
        _check.reset(token)
