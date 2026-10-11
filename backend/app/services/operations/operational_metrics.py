"""Small in-process Prometheus-compatible metrics registry."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_lock = Lock()


def increment(name: str, value: float = 1, **labels: str) -> None:
    key = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
    with _lock:
        _counters[key] += value


def observe(name: str, seconds: float, **labels: str) -> None:
    """Record a duration as Prometheus-compatible count and sum counters."""
    increment(f"{name}_seconds_count", **labels)
    increment(f"{name}_seconds_sum", value=seconds, **labels)


def set_gauge(name: str, value: float, **labels: str) -> None:
    """Store the most recent value for a point-in-time measurement."""
    key = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
    with _lock:
        _gauges[key] = value


def render(extra_metrics: dict[str, float] | None = None) -> str:
    with _lock:
        rows = list(_counters.items())
        gauges = list(_gauges.items())
    lines = ["# HELP nexora_operational_metrics Lightweight Nexora operational counters", "# TYPE nexora_operational_metrics counter"]
    for (name, labels), value in sorted(rows):
        suffix = ""
        if labels:
            encoded = ",".join(f'{key}="{value.replace(chr(34), chr(92) + chr(34))}"' for key, value in labels)
            suffix = "{" + encoded + "}"
        lines.append(f"nexora_{name}{suffix} {value}")
    for (name, labels), value in sorted(gauges):
        suffix = ""
        if labels:
            encoded = ",".join(f'{key}="{value.replace(chr(34), chr(92) + chr(34))}"' for key, value in labels)
            suffix = "{" + encoded + "}"
        lines.append(f"nexora_{name}{suffix} {value}")
    for name, value in sorted((extra_metrics or {}).items()):
        lines.append(f"nexora_{name} {value}")
    return "\n".join(lines) + "\n"
