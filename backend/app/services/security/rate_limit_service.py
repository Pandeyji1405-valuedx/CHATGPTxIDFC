"""
Redis Rate Limiting Service (Phase 7).

Responsibilities:
  - Enforce tenant-aware and user/IP-aware API rate limits.
  - Use Redis runtime counters with fixed/sliding 60-second window expiring keys.
  - Fail-open gracefully on Redis outage if configured (settings.RATE_LIMIT_FAIL_OPEN).
  - Provide FastAPI dependency for easy route protection.
"""

import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.services.cache.redis_service import RedisService, get_redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimiter:
    """
    FastAPI dependency for governed API rate limiting via Redis.
    """

    def __init__(
        self,
        endpoint_group: str,
        max_requests: Optional[int] = None,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter for an endpoint category.

        Args:
            endpoint_group: Category name ('auth', 'chat', 'document', 'feedback').
            max_requests: Maximum allowed requests in window (default from settings).
            window_seconds: Time window in seconds (default 60s).
        """
        self.endpoint_group = endpoint_group
        self.window_seconds = window_seconds

        if max_requests is not None:
            self.max_requests = max_requests
        else:
            if endpoint_group == "auth":
                self.max_requests = settings.RATE_LIMIT_AUTH_PER_MINUTE
            elif endpoint_group == "chat":
                self.max_requests = settings.RATE_LIMIT_CHAT_PER_MINUTE
            elif endpoint_group == "document":
                self.max_requests = settings.RATE_LIMIT_DOC_PER_MINUTE
            elif endpoint_group == "feedback":
                self.max_requests = settings.RATE_LIMIT_FEEDBACK_PER_MINUTE
            else:
                self.max_requests = 60

    async def __call__(self, request: Request) -> None:
        """
        Check rate limit for incoming FastAPI request.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        # Derive identifier: authenticated user ID or client IP
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", "idfc_bank")
        client_ip = request.client.host if request.client else "unknown"

        identifier = str(user_id) if user_id else client_ip
        key = f"rate_limit:{tenant_id}:{identifier}:{self.endpoint_group}"

        redis_client = await get_redis_client()
        if redis_client is None:
            if settings.RATE_LIMIT_FAIL_OPEN:
                logger.warning(
                    "Redis unavailable — rate limiter failing open for key %s", key
                )
                return
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting service unavailable.",
                )

        try:
            # Multi/exec counter increment
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()

            current_count = results[0]
            ttl = results[1]

            # Set expiration on first hit
            if ttl == -1 or current_count == 1:
                await redis_client.expire(key, self.window_seconds)
                ttl = self.window_seconds

            if current_count > self.max_requests:
                retry_after = max(1, ttl if ttl > 0 else self.window_seconds)
                logger.warning(
                    "Rate limit EXCEEDED: key=%s count=%d max=%d tenant=%s",
                    key,
                    current_count,
                    self.max_requests,
                    tenant_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per minute allowed.",
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Redis rate limit error: %s", exc)
            if settings.RATE_LIMIT_FAIL_OPEN:
                return
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rate limiting error.",
            )
