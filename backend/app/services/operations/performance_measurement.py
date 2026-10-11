"""Low-overhead measurements used before cache or query optimizations."""

from __future__ import annotations

import ctypes
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.services.operations.operational_metrics import increment, observe, set_gauge


@dataclass
class RequestMeasurement:
    path: str
    query_count: int = 0
    query_duration_seconds: float = 0.0
    query_started_at: list[float] = field(default_factory=list)


_measurement: ContextVar[RequestMeasurement | None] = ContextVar("request_measurement", default=None)
_sql_listener_registered = False


def begin_request_measurement(path: str) -> Token:
    return _measurement.set(RequestMeasurement(path=path))


def finish_request_measurement(token: Token, elapsed_seconds: float) -> RequestMeasurement | None:
    measurement = _measurement.get()
    _measurement.reset(token)
    if measurement is None:
        return None

    labels = {"path": measurement.path}
    observe("http_request_duration", elapsed_seconds, **labels)
    increment("database_queries_total", value=measurement.query_count, **labels)
    observe("database_query_duration", measurement.query_duration_seconds, **labels)
    set_gauge("process_resident_memory_bytes", process_memory_bytes())
    return measurement


def observe_provider_latency(provider: str, operation: str, elapsed_seconds: float, *, result: str) -> None:
    """Record external-service latency independently from HTTP request timing."""
    observe("provider_latency", elapsed_seconds, provider=provider, operation=operation, result=result)
    increment("provider_requests_total", provider=provider, operation=operation, result=result)


def process_memory_bytes() -> int:
    """Return resident memory without making psutil a production dependency."""
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
        return 0
    try:
        with open("/proc/self/statm", encoding="ascii") as statm:
            resident_pages = int(statm.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (FileNotFoundError, IndexError, OSError, ValueError):
        return 0


def register_sqlalchemy_query_metrics() -> None:
    """Install process-wide SQL timing listeners exactly once."""
    global _sql_listener_registered
    if _sql_listener_registered:
        return

    @event.listens_for(Engine, "before_cursor_execute")
    def _before_cursor_execute(*_args, **_kwargs) -> None:
        measurement = _measurement.get()
        if measurement is not None:
            measurement.query_started_at.append(perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _after_cursor_execute(*_args, **_kwargs) -> None:
        measurement = _measurement.get()
        if measurement is not None and measurement.query_started_at:
            measurement.query_count += 1
            measurement.query_duration_seconds += perf_counter() - measurement.query_started_at.pop()

    @event.listens_for(Engine, "handle_error")
    def _handle_query_error(_exception_context) -> None:
        measurement = _measurement.get()
        if measurement is not None and measurement.query_started_at:
            measurement.query_count += 1
            measurement.query_duration_seconds += perf_counter() - measurement.query_started_at.pop()

    _sql_listener_registered = True
