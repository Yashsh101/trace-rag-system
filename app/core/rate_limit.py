import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import RateLimitError


class InMemoryRateLimiter:
    def __init__(self):
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        if not settings.rate_limit_enabled:
            return

        now = time.monotonic()
        window_start = now - settings.rate_limit_window_seconds
        bucket = self._requests[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            raise RateLimitError("Rate limit exceeded")

        bucket.append(now)


@dataclass
class RedisRateLimiter:
    redis_url: str

    def __post_init__(self) -> None:
        import redis

        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        self.client.ping()

    def check(self, key: str) -> None:
        if not settings.rate_limit_enabled:
            return
        redis_key = f"rate-limit:{key}"
        count = self.client.incr(redis_key)
        if count == 1:
            self.client.expire(redis_key, settings.rate_limit_window_seconds)
        if count > settings.rate_limit_requests:
            raise RateLimitError("Rate limit exceeded")


def build_rate_limiter():
    if settings.rate_limit_backend == "redis":
        return RedisRateLimiter(settings.redis_url or "")
    return InMemoryRateLimiter()


rate_limiter = build_rate_limiter()
