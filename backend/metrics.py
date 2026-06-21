import time
from collections import defaultdict, deque
from typing import Any

_MAX_SAMPLES = 1000
_samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_MAX_SAMPLES))


def record(key: str, duration_ms: float) -> None:
    _samples[key].append(duration_ms)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = max(0, min(len(values) - 1, int(len(values) * p / 100)))
    return values[idx]


def snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, values in _samples.items():
        vals = list(values)
        result[key] = {
            "count": len(vals),
            "avg_ms": round(sum(vals) / len(vals), 1) if vals else 0,
            "p50_ms": round(_percentile(vals, 50), 1),
            "p95_ms": round(_percentile(vals, 95), 1),
            "p99_ms": round(_percentile(vals, 99), 1),
        }
    return result


class Timer:
    def __init__(self, key: str):
        self.key = key
        self.start: float = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        ms = (time.perf_counter() - self.start) * 1000
        record(self.key, ms)
