"""Per-provider Dual Token-Bucket (RPM/TPM) and concurrency rate limiting."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class ProviderLimitSpec:
    provider: str
    max_concurrent: int = 8
    rpm_limit: int = 60
    tpm_limit: int = 100_000


DEFAULT_PROVIDER_LIMITS: dict[str, ProviderLimitSpec] = {
    "ollama": ProviderLimitSpec("ollama", max_concurrent=1, rpm_limit=600, tpm_limit=10_000_000),
    "groq": ProviderLimitSpec("groq", max_concurrent=4, rpm_limit=30, tpm_limit=15_000),
    "openai": ProviderLimitSpec("openai", max_concurrent=16, rpm_limit=500, tpm_limit=200_000),
    "meta": ProviderLimitSpec("meta", max_concurrent=8, rpm_limit=120, tpm_limit=100_000),
    "agentrouter": ProviderLimitSpec(
        "agentrouter", max_concurrent=10, rpm_limit=180, tpm_limit=150_000
    ),
    "mock": ProviderLimitSpec("mock", max_concurrent=32, rpm_limit=60_000, tpm_limit=100_000_000),
}


class AsyncTokenBucket:
    """Thread/Coroutine-safe token bucket with monotonic clock refill."""

    def __init__(self, capacity: float, refill_rate_per_sec: float) -> None:
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._cooldown_until = 0.0

    async def acquire(self, requested: float = 1.0) -> None:
        requested = min(requested, self.capacity)
        while True:
            async with self._lock:
                now = time.monotonic()
                if now < self._cooldown_until:
                    wait_for = self._cooldown_until - now
                else:
                    elapsed = now - self.last_refill
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                    self.last_refill = now
                    if self.tokens >= requested:
                        self.tokens -= requested
                        return
                    wait_for = (
                        (requested - self.tokens) / self.refill_rate
                        if self.refill_rate > 0
                        else 0.1
                    )
            await asyncio.sleep(max(0.005, wait_for))

    async def apply_retry_after(self, seconds: float) -> None:
        """Pause bucket acquisition when a remote 429 Retry-After is encountered."""
        async with self._lock:
            self._cooldown_until = max(self._cooldown_until, time.monotonic() + seconds)
            self.tokens = 0.0


class AsyncProviderLimiter:
    """Combines an in-flight concurrency semaphore with dual token buckets (RPM and TPM)."""

    def __init__(self, spec: ProviderLimitSpec) -> None:
        self.spec = spec
        self.concurrency_sem = asyncio.Semaphore(spec.max_concurrent)
        self.rpm_bucket = AsyncTokenBucket(spec.rpm_limit, spec.rpm_limit / 60.0)
        self.tpm_bucket = AsyncTokenBucket(spec.tpm_limit, spec.tpm_limit / 60.0)

    async def acquire_turn(self, estimated_tokens: int = 1200) -> None:
        await self.rpm_bucket.acquire(1.0)
        await self.tpm_bucket.acquire(float(estimated_tokens))

    async def handle_retry_after(self, seconds: float) -> None:
        await self.rpm_bucket.apply_retry_after(seconds)
        await self.tpm_bucket.apply_retry_after(seconds)


_PROVIDER_LIMITERS: dict[str, AsyncProviderLimiter] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def get_provider_limiter(
    provider: str,
    *,
    max_concurrent: int | None = None,
    rpm_limit: int | None = None,
    tpm_limit: int | None = None,
) -> AsyncProviderLimiter:
    """Retrieve or register an AsyncProviderLimiter for the given provider."""
    normalized = provider.lower().strip()
    async with _REGISTRY_LOCK:
        if normalized not in _PROVIDER_LIMITERS:
            base_spec = DEFAULT_PROVIDER_LIMITS.get(
                normalized,
                ProviderLimitSpec(normalized, max_concurrent=8, rpm_limit=60, tpm_limit=100_000),
            )
            spec = ProviderLimitSpec(
                provider=normalized,
                max_concurrent=max_concurrent or base_spec.max_concurrent,
                rpm_limit=rpm_limit or base_spec.rpm_limit,
                tpm_limit=tpm_limit or base_spec.tpm_limit,
            )
            _PROVIDER_LIMITERS[normalized] = AsyncProviderLimiter(spec)
        return _PROVIDER_LIMITERS[normalized]
