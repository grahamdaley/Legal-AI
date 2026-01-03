"""Tests for rate limiter utilities."""

import asyncio
import time

import pytest
from scrapers.utils.rate_limiter import RateLimiter, AdaptiveRateLimiter


class TestRateLimiter:
    """Tests for basic rate limiter."""

    @pytest.mark.asyncio
    async def test_enforces_delay(self):
        limiter = RateLimiter(min_delay=0.1, max_concurrent=1)
        
        start = time.monotonic()
        
        async with limiter:
            pass
        async with limiter:
            pass
        
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1  # Should have waited at least min_delay

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        limiter = RateLimiter(min_delay=0.0, max_concurrent=2)
        active = 0
        max_active = 0
        
        async def task():
            nonlocal active, max_active
            async with limiter:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.05)
                active -= 1
        
        await asyncio.gather(*[task() for _ in range(5)])
        
        assert max_active <= 2


class TestAdaptiveRateLimiter:
    """Tests for adaptive rate limiter."""

    def test_initial_delay(self):
        limiter = AdaptiveRateLimiter(base_delay=3.0)
        assert limiter.current_delay == 3.0

    def test_backoff_on_failure(self):
        limiter = AdaptiveRateLimiter(base_delay=1.0, backoff_factor=2.0)
        initial = limiter.current_delay
        
        limiter.report_failure()
        
        assert limiter.current_delay == initial * 2.0

    def test_backoff_on_rate_limit(self):
        limiter = AdaptiveRateLimiter(base_delay=1.0, backoff_factor=2.0)
        initial = limiter.current_delay
        
        limiter.report_failure(is_rate_limit=True)
        
        # Rate limit should increase more aggressively
        assert limiter.current_delay == initial * 4.0

    def test_recovery_on_success(self):
        limiter = AdaptiveRateLimiter(
            base_delay=1.0,
            min_delay=0.5,
            recovery_factor=0.9,
        )
        
        # Increase delay first
        limiter.report_failure()
        high_delay = limiter.current_delay
        
        # Report multiple successes to trigger recovery
        for _ in range(5):
            limiter.report_success()
        
        assert limiter.current_delay < high_delay

    def test_respects_max_delay(self):
        limiter = AdaptiveRateLimiter(
            base_delay=1.0,
            max_delay=10.0,
            backoff_factor=2.0,
        )
        
        # Many failures
        for _ in range(10):
            limiter.report_failure()
        
        assert limiter.current_delay <= 10.0

    def test_respects_min_delay(self):
        limiter = AdaptiveRateLimiter(
            base_delay=1.0,
            min_delay=0.5,
            recovery_factor=0.5,
        )
        
        # Many successes
        for _ in range(50):
            limiter.report_success()
        
        assert limiter.current_delay >= 0.5

    def test_reset(self):
        limiter = AdaptiveRateLimiter(base_delay=1.0)
        
        limiter.report_failure()
        limiter.report_failure()
        assert limiter.current_delay > 1.0
        
        limiter.reset()
        assert limiter.current_delay == 1.0
