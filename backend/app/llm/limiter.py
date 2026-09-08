"""Rate limiter and concurrency manager for LLM API calls.

Enforces 15 requests/minute for Gemini free tier, concurrency limit of 1,
and exponential backoff on 429 errors.
"""

import asyncio
import threading
import time
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

# Concurrency semaphore to avoid overwhelming free tier limits.
# threading.Semaphore (not asyncio.Semaphore) because each document's
# pipeline stage runs its own asyncio.run() in its own worker thread —
# an asyncio.Semaphore binds to whichever event loop first contends on
# it and breaks ("bound to a different event loop") once a second
# thread's loop tries to use it. threading.Semaphore is loop-agnostic.
_LLM_SEMAPHORE = threading.Semaphore(1)

# Request timestamp tracking for rate limiting (15 req / minute)
_REQUEST_TIMESTAMPS = []
MAX_REQUESTS_PER_MINUTE = 12  # Safety margin below 15
WINDOW_SECONDS = 60.0


async def acquire_rate_limit():
    """Ensure we stay under rate limit window before firing a call."""
    now = time.time()
    # Remove timestamps older than WINDOW_SECONDS
    global _REQUEST_TIMESTAMPS
    _REQUEST_TIMESTAMPS = [t for t in _REQUEST_TIMESTAMPS if now - t < WINDOW_SECONDS]

    if len(_REQUEST_TIMESTAMPS) >= MAX_REQUESTS_PER_MINUTE:
        sleep_duration = WINDOW_SECONDS - (now - _REQUEST_TIMESTAMPS[0]) + 0.5
        if sleep_duration > 0:
            logger.info(f"Rate limit safety sleep: {sleep_duration:.2f}s")
            await asyncio.sleep(sleep_duration)

    _REQUEST_TIMESTAMPS.append(time.time())


async def execute_with_backoff(func: Callable[[], Any], max_retries: int = 4) -> Any:
    """Execute an async LLM function with concurrency control and 429 backoff."""
    _LLM_SEMAPHORE.acquire()
    try:
        await acquire_rate_limit()

        delay = 2.0
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                err_str = str(e).lower()
                # A per-day quota (e.g. free-tier "GenerateRequestsPerDayPerProjectPerModel")
                # won't clear within a backoff window like a per-minute limit would —
                # retrying just burns ~14s per call before the caller's fallback kicks in.
                is_daily_quota = "perday" in err_str.replace(" ", "")
                is_429 = "429" in err_str or "quota" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str
                if is_daily_quota:
                    logger.warning("Daily quota exhausted; not retrying, raising immediately for fallback.")
                    raise e
                if is_429 and attempt < max_retries - 1:
                    logger.warning(f"Rate limited (429/quota). Backing off {delay:.1f}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(delay)
                    delay *= 2.0
                else:
                    raise e
    finally:
        _LLM_SEMAPHORE.release()
