import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

# These are INTERNAL safety defaults for generic public HTTP access.
# Real provider adapters must replace these with the provider's documented
# limits before use. Never guess a provider's limits.
SOURCE_POLICIES: dict[str, dict[str, float | int]] = {
    "generic_public_source": {
        "requests_per_minute": 12,
        "daily_budget": 200,
        "minimum_delay_seconds": 5,
        "max_retries": 2,
    }
}

_request_times: dict[str, deque[float]] = defaultdict(deque)
_daily_counts: dict[str, tuple[str, int]] = {}
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _today_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


async def _wait_for_budget(source: str) -> None:
    if source not in SOURCE_POLICIES:
        raise RuntimeError(f"Unknown source policy: {source}")

    policy = SOURCE_POLICIES[source]
    async with _locks[source]:
        now = time.monotonic()
        window = _request_times[source]
        while window and now - window[0] >= 60:
            window.popleft()

        day, count = _daily_counts.get(source, (_today_key(), 0))
        if day != _today_key():
            day, count = _today_key(), 0
        if count >= int(policy["daily_budget"]):
            raise RuntimeError(f"Daily budget reached for source={source}")

        if window and len(window) >= int(policy["requests_per_minute"]):
            await asyncio.sleep(max(0.5, 60 - (now - window[0])))
            now = time.monotonic()
            while window and now - window[0] >= 60:
                window.popleft()

        if window:
            elapsed = now - window[-1]
            minimum = float(policy["minimum_delay_seconds"])
            if elapsed < minimum:
                await asyncio.sleep(minimum - elapsed)

        window.append(time.monotonic())
        _daily_counts[source] = (day, count + 1)


async def permitted_get(
    url: str,
    source: str = "generic_public_source",
    timeout: float = 15,
    **kwargs: Any,
) -> httpx.Response:
    await _wait_for_budget(source)
    retries = int(SOURCE_POLICIES[source]["max_retries"])
    last_error: Exception | None = None

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "LeadHunter/1.0 business-research"},
    ) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.get(url, timeout=timeout, **kwargs)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = 2 ** attempt * 5
                    await asyncio.sleep(min(delay, 120))
                    continue
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    await asyncio.sleep(min(2 ** attempt * 2, 30))

    raise last_error or RuntimeError("HTTP request failed")


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


async def discover_businesses(city: str, industry: str) -> list[dict[str, Any]]:
    """Return real candidates only from a configured permitted source.

    Deliberately empty until a concrete compliant provider/source is configured.
    This prevents fabricated leads and accidental restricted scraping.
    """
    log.warning("No discovery provider configured for city=%s industry=%s", city, industry)
    return []
