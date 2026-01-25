"""Resilience utilities for external API calls."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar, ParamSpec

import structlog

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for external service calls.

    Prevents cascade failures by stopping calls to failing services
    and allowing them to recover.

    Args:
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds to wait before testing recovery.
        name: Name for logging purposes.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    name: str = "default"

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _log: structlog.BoundLogger = field(init=False)

    def __post_init__(self):
        self._log = logger.bind(circuit_breaker=self.name)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._log.info("Circuit half-open, testing recovery")
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._log.info("Circuit closed after successful recovery test")
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._log.warning(
                "Circuit opened due to failures",
                failure_count=self._failure_count,
                recovery_timeout=self.recovery_timeout,
            )

    def is_call_permitted(self) -> bool:
        """Check if a call is permitted."""
        state = self.state  # This checks for recovery timeout
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow one test call
        return False

    async def call(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: The async function to call.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The function's return value.

        Raises:
            CircuitOpenError: If the circuit is open.
            Exception: Any exception from the function.
        """
        if not self.is_call_permitted():
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is open. "
                f"Retry after {self.recovery_timeout - (time.time() - self._last_failure_time):.1f}s"
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Pre-configured circuit breakers for common services
bedrock_circuit = CircuitBreaker(
    name="bedrock",
    failure_threshold=5,
    recovery_timeout=60.0,
)

azure_openai_circuit = CircuitBreaker(
    name="azure_openai",
    failure_threshold=5,
    recovery_timeout=60.0,
)
