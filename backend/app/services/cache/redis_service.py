"""
Phase 5 Redis Service Wrapper.

Manages connection pooling, session memory persistence, and hot exact response caching.
Supports `fakeredis` for isolated offline PyTest execution.
Handles Redis offline/connection errors gracefully without crashing the app.

Session key format (Phase 5B):
    session:{tenant_id}:{user_id}:{conversation_id}:context

Key security contract:
  - tenant_id, user_id and conversation_id are ALWAYS sourced from the verified
    JWT/ownership chain -- never from client-supplied values.
  - Different tenants, users, and conversations produce distinct Redis keys,
    providing hard namespace isolation.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton client instance
_redis_client = None


async def get_redis_client():
    """Lazy initialize and return the async Redis client."""
    global _redis_client
    if _redis_client is None:
        if not settings.REDIS_ENABLED:
            logger.info("Redis is disabled in application settings.")
            return None

        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Test ping
            await _redis_client.ping()
            logger.info("Connected to Redis at %s", settings.REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Failed to connect to Redis at %s (%s). Operating in fallback mode.",
                settings.REDIS_URL,
                exc,
            )
            _redis_client = None
    return _redis_client


def set_mock_redis_client(mock_client):
    """Inject a fakeredis client for testing."""
    global _redis_client
    _redis_client = mock_client


class RedisService:
    """
    High-level operational wrapper for Redis cache and session memory operations.
    """

    # ------------------------------------------------------------------ #
    # Phase 5B -- Session Memory
    # ------------------------------------------------------------------ #

    @staticmethod
    def _session_key(tenant_id: str, user_id: str, conversation_id: str) -> str:
        """
        Build the fully qualified session key.

        Format: session:{tenant_id}:{user_id}:{conversation_id}:context

        All three segments are required for hard namespace isolation across
        tenants, authenticated users, and conversations.
        """
        return f"session:{tenant_id}:{user_id}:{conversation_id}:context"

    async def get_session_context(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the most recent conversation turns from Redis session memory.

        Args:
            tenant_id:       Tenant identifier (sourced from auth context, never client).
            user_id:         Authenticated user UUID string.
            conversation_id: Conversation UUID string.
            limit:           Maximum turns to return. Defaults to SESSION_MEMORY_MAX_TURNS.

        Returns:
            List of turn dicts (may be empty on cache miss or Redis failure).
        """
        client = await get_redis_client()
        if not client:
            return []

        effective_limit = limit if limit is not None else settings.SESSION_MEMORY_MAX_TURNS
        key = self._session_key(tenant_id, user_id, conversation_id)
        try:
            raw_list = await client.lrange(key, -effective_limit, -1)
            return [json.loads(item) for item in raw_list]
        except Exception as exc:
            logger.warning("Redis session read error for key %s: %s", key, exc)
            return []

    async def append_session_turn(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        turn: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
        max_turns: Optional[int] = None,
    ) -> bool:
        """
        Append a conversation turn to session memory, enforce max-turns bound,
        and refresh sliding TTL.

        The list is trimmed to the configured SESSION_MEMORY_MAX_TURNS bound
        immediately after the push, so memory consumption stays bounded.

        Args:
            tenant_id:       Tenant identifier (sourced from auth context, never client).
            user_id:         Authenticated user UUID string.
            conversation_id: Conversation UUID string.
            turn:            Turn payload dict containing message_id, role,
                             original_query, canonical_query, timestamp.
            ttl_seconds:     Override for SESSION_MEMORY_TTL_SECONDS.
            max_turns:       Override for SESSION_MEMORY_MAX_TURNS.

        Returns:
            True on success, False if Redis is unavailable or an error occurs.
        """
        client = await get_redis_client()
        if not client:
            return False

        ttl = ttl_seconds if ttl_seconds is not None else settings.SESSION_MEMORY_TTL_SECONDS
        bound = max_turns if max_turns is not None else settings.SESSION_MEMORY_MAX_TURNS
        key = self._session_key(tenant_id, user_id, conversation_id)
        try:
            await client.rpush(key, json.dumps(turn))
            # Trim to latest `bound` turns (keep the tail)
            await client.ltrim(key, -bound, -1)
            # Refresh sliding TTL on every write
            await client.expire(key, ttl)
            return True
        except Exception as exc:
            logger.warning("Redis session write error for key %s: %s", key, exc)
            return False

    async def delete_session_context(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        """Delete the session context key entirely (e.g., on conversation deletion)."""
        client = await get_redis_client()
        if not client:
            return False

        key = self._session_key(tenant_id, user_id, conversation_id)
        try:
            await client.delete(key)
            return True
        except Exception as exc:
            logger.warning("Redis session delete error for key %s: %s", key, exc)
            return False

    # ------------------------------------------------------------------ #
    # Phase 5C -- Exact Response Cache (Tier 1 Redis)
    # ------------------------------------------------------------------ #

    async def get_exact_cache(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response by exact SHA-256 query hash (Tier 1).
        """
        client = await get_redis_client()
        if not client:
            return None

        key = f"exact_cache:{query_hash}"
        try:
            raw = await client.get(key)
            if raw:
                logger.debug("Redis Tier 1 Exact Cache HIT for hash %s", query_hash[:8])
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis read error on key %s: %s", key, exc)
        return None

    async def set_exact_cache(
        self,
        query_hash: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Save cached response to Redis with TTL (Tier 1 write-through).
        """
        client = await get_redis_client()
        if not client:
            return False

        ttl = ttl_seconds or settings.EXACT_CACHE_TTL_SECONDS
        key = f"exact_cache:{query_hash}"
        try:
            await client.set(key, json.dumps(payload), ex=ttl)
            return True
        except Exception as exc:
            logger.warning("Redis write error on key %s: %s", key, exc)
            return False

    # ------------------------------------------------------------------ #
    # Phase 5E -- Version Dependency Index
    # ------------------------------------------------------------------ #

    async def index_version_dependency(
        self,
        version_id: str,
        query_hash: str,
    ) -> bool:
        """
        Add query hash to version tracking set for fast invalidation.
        """
        client = await get_redis_client()
        if not client:
            return False

        set_key = f"cache_index:version:{version_id}"
        try:
            await client.sadd(set_key, query_hash)
            return True
        except Exception as exc:
            logger.warning("Redis version index error for key %s: %s", set_key, exc)
            return False

    async def evict_version_keys(self, version_id: str) -> int:
        """
        Evict all Redis exact cache keys that depend on a superseded version.
        """
        client = await get_redis_client()
        if not client:
            return 0

        set_key = f"cache_index:version:{version_id}"
        try:
            hashes = await client.smembers(set_key)
            if not hashes:
                return 0

            keys_to_del = [f"exact_cache:{h}" for h in hashes]
            keys_to_del.append(set_key)
            count = await client.delete(*keys_to_del)
            logger.info(
                "Evicted %d Redis keys dependent on version %s",
                len(hashes),
                version_id,
            )
            return count
        except Exception as exc:
            logger.warning("Redis eviction error for version %s: %s", version_id, exc)
            return 0
