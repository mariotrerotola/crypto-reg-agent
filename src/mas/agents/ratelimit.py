"""Simple rate limiter for API clients.

Ensures a minimum interval between successive HTTP calls to stay
within free-tier API limits.
"""

from __future__ import annotations

import time


class RateLimiter:
    """Token-bucket-style rate limiter with minimum interval enforcement.

    Args:
        min_interval: Minimum seconds between calls.
    """

    def __init__(self, min_interval: float = 1.0) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until the minimum interval has elapsed since the last call."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
