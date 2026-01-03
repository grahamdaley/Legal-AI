"""
Rate limiting utilities for web scraping.

Provides both fixed and adaptive rate limiting to respect server limits
and avoid being blocked.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimiter:
    """
    Simple rate limiter with fixed delay between requests.
    
    Attributes:
        min_delay: Minimum seconds between requests
        max_concurrent: Maximum concurrent requests allowed
    """

    min_delay: float = 3.0
    max_concurrent: int = 2
    _last_request_time: float = field(default=0.0, init=False)
    _semaphore: Optional[asyncio.Semaphore] = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    async def acquire(self) -> None:
        """Acquire rate limit slot, waiting if necessary."""
        await self._semaphore.acquire()

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self.min_delay - elapsed

            if wait_time > 0:
                logger.debug("Rate limiting", wait_seconds=round(wait_time, 2))
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()

    def release(self) -> None:
        """Release rate limit slot."""
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()


@dataclass
class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts delay based on server responses.
    
    Increases delay on errors/rate limits, decreases on success.
    
    Attributes:
        base_delay: Starting delay between requests
        min_delay: Minimum delay (floor)
        max_delay: Maximum delay (ceiling)
        max_concurrent: Maximum concurrent requests
        backoff_factor: Multiplier when increasing delay
        recovery_factor: Multiplier when decreasing delay
    """

    base_delay: float = 3.0
    min_delay: float = 1.0
    max_delay: float = 60.0
    max_concurrent: int = 2
    backoff_factor: float = 2.0
    recovery_factor: float = 0.9

    _current_delay: float = field(default=0.0, init=False)
    _last_request_time: float = field(default=0.0, init=False)
    _semaphore: Optional[asyncio.Semaphore] = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _consecutive_successes: int = field(default=0, init=False)
    _consecutive_failures: int = field(default=0, init=False)

    def __post_init__(self):
        self._current_delay = self.base_delay
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    @property
    def current_delay(self) -> float:
        return self._current_delay

    async def acquire(self) -> None:
        """Acquire rate limit slot, waiting if necessary."""
        await self._semaphore.acquire()

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self._current_delay - elapsed

            if wait_time > 0:
                logger.debug(
                    "Adaptive rate limiting",
                    wait_seconds=round(wait_time, 2),
                    current_delay=round(self._current_delay, 2),
                )
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()

    def release(self) -> None:
        """Release rate limit slot."""
        self._semaphore.release()

    def report_success(self) -> None:
        """Report a successful request to potentially decrease delay."""
        self._consecutive_successes += 1
        self._consecutive_failures = 0

        # Only decrease after several consecutive successes
        if self._consecutive_successes >= 5:
            new_delay = max(
                self.min_delay,
                self._current_delay * self.recovery_factor,
            )
            if new_delay < self._current_delay:
                logger.debug(
                    "Decreasing delay",
                    old_delay=round(self._current_delay, 2),
                    new_delay=round(new_delay, 2),
                )
                self._current_delay = new_delay
            self._consecutive_successes = 0

    def report_failure(self, is_rate_limit: bool = False) -> None:
        """
        Report a failed request to increase delay.
        
        Args:
            is_rate_limit: True if failure was due to rate limiting (429)
        """
        self._consecutive_failures += 1
        self._consecutive_successes = 0

        # Increase delay more aggressively for rate limits
        factor = self.backoff_factor * 2 if is_rate_limit else self.backoff_factor
        new_delay = min(self.max_delay, self._current_delay * factor)

        logger.warning(
            "Increasing delay due to failure",
            old_delay=round(self._current_delay, 2),
            new_delay=round(new_delay, 2),
            is_rate_limit=is_rate_limit,
            consecutive_failures=self._consecutive_failures,
        )
        self._current_delay = new_delay

    def reset(self) -> None:
        """Reset to base delay."""
        self._current_delay = self.base_delay
        self._consecutive_successes = 0
        self._consecutive_failures = 0

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        if exc_type is None:
            self.report_success()
