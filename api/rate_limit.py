from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class SlidingWindowRateLimiter:
    """
    Rate limiter local ao processo usando janela deslizante.

    Cada chave possui uma fila de timestamps.
    Entradas expiradas são removidas antes da decisão.
    """

    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:

        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            events = self._events[key]

            while events and events[0] <= cutoff:
                events.popleft()

            current = len(events)

            if current >= limit:
                retry_after = max(
                    1,
                    int(events[0] + window_seconds - now + 0.999),
                )

                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    retry_after=retry_after,
                )

            events.append(now)

            remaining = max(
                0,
                limit - len(events),
            )

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                retry_after=0,
            )

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._events)


rate_limiter = SlidingWindowRateLimiter()
