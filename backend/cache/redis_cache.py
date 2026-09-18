import json
import logging
import time
from typing import Any, Optional, Dict, List
import redis

logger = logging.getLogger(__name__)

class InMemoryFallbackCache:
    """Thread-safe in-memory cache with TTL support when Redis is offline."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if not item:
            return None
        if item["expires_at"] is not None and time.time() > item["expires_at"]:
            del self._store[key]
            return None
        return item["value"]

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        expires_at = (time.time() + ex) if ex else None
        self._store[key] = {"value": value, "expires_at": expires_at}
        return True

    def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    def flushall(self):
        self._store.clear()

class RedisCacheManager:
    """
    Robust Redis cache manager with automatic in-memory fallback.
    Provides context mapping, active topic tracking, extracted fact caching,
    and fast semantic Q&A lookup.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.client = None
        self.is_redis_available = False
        self.fallback_cache = InMemoryFallbackCache()
        self._init_connection()

    def _init_connection(self):
        try:
            self.client = redis.from_url(
                self.redis_url,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True
            )
            self.client.ping()
            self.is_redis_available = True
            logger.info("Connected successfully to Redis server.")
        except Exception as e:
            self.is_redis_available = False
            logger.info("Redis server offline or unavailable. Operating with high-performance In-Memory Cache.")

    def get(self, key: str) -> Optional[str]:
        if self.is_redis_available and self.client:
            try:
                return self.client.get(key)
            except Exception:
                pass
        return self.fallback_cache.get(key)

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        if self.is_redis_available and self.client:
            try:
                return bool(self.client.set(key, value, ex=ttl_seconds))
            except Exception:
                pass
        return self.fallback_cache.set(key, value, ex=ttl_seconds)

    def delete(self, *keys: str) -> int:
        if self.is_redis_available and self.client:
            try:
                return self.client.delete(*keys)
            except Exception:
                pass
        return self.fallback_cache.delete(*keys)

    def flushall(self):
        if self.is_redis_available and self.client:
            try:
                self.client.flushall()
            except Exception:
                pass
        self.fallback_cache.flushall()

    # --- Conversation Context Mapping ---
    def cache_conversation_context(self, user_id: str, conv_id: str, context_data: Dict[str, Any], ttl: int = 3600):
        key = f"user:{user_id}:conv:{conv_id}:context"
        self.set(key, json.dumps(context_data), ttl_seconds=ttl)

    def get_conversation_context(self, user_id: str, conv_id: str) -> Optional[Dict[str, Any]]:
        key = f"user:{user_id}:conv:{conv_id}:context"
        raw = self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    # --- Active Topic & Facts Mapping ---
    def cache_topic_facts(self, user_id: str, conv_id: str, entity_name: str, facts: Dict[str, Any], ttl: int = 3600):
        key = f"user:{user_id}:conv:{conv_id}:entity:{entity_name.upper()}"
        self.set(key, json.dumps(facts), ttl_seconds=ttl)

    def get_topic_facts(self, user_id: str, conv_id: str, entity_name: str) -> Optional[Dict[str, Any]]:
        key = f"user:{user_id}:conv:{conv_id}:entity:{entity_name.upper()}"
        raw = self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    # --- Semantic Query Cache ---
    def get_cached_response(self, query_key: str) -> Optional[Dict[str, Any]]:
        key = f"cache:rag:{query_key.lower().strip()}"
        raw = self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    def set_cached_response(self, query_key: str, response_data: Dict[str, Any], ttl: int = 1800):
        key = f"cache:rag:{query_key.lower().strip()}"
        self.set(key, json.dumps(response_data), ttl_seconds=ttl)

redis_cache = RedisCacheManager()
