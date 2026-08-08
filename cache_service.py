import os
import json
import logging
from typing import Optional, Any
import redis
from config import Config

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based caching service for recommendations and vector search results."""
    
    def __init__(self):
        self.redis_url = Config.REDIS_URL
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Redis client with connection pooling."""
        try:
            if self.redis_url and self.redis_url != "redis://localhost:6379/0":
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=10,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                self.client.ping()
                logger.info("Redis cache connected successfully")
            else:
                logger.info("Redis URL not configured, using in-memory fallback")
        except Exception as e:
            logger.warning(f"Redis connection failed, caching disabled: {e}")
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL in seconds."""
        if not self.client:
            return False
        try:
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """Delete all keys matching pattern."""
        if not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
            return False
    
    def get_recommendation(self, user_id: int) -> Optional[dict]:
        """Get cached recommendation for user."""
        return self.get(f"recommendation:{user_id}")
    
    def set_recommendation(self, user_id: int, data: dict, ttl: int = 300) -> bool:
        """Cache recommendation for user."""
        return self.set(f"recommendation:{user_id}", data, ttl)
    
    def invalidate_recommendation(self, user_id: int) -> bool:
        """Invalidate user's cached recommendation."""
        return self.delete(f"recommendation:{user_id}")
    
    def get_vector_search(self, query_hash: str) -> Optional[list]:
        """Get cached vector search results."""
        return self.get(f"vector_search:{query_hash}")
    
    def set_vector_search(self, query_hash: str, results: list, ttl: int = 300) -> bool:
        """Cache vector search results."""
        return self.set(f"vector_search:{query_hash}", results, ttl)


# Global cache instance
cache_service = CacheService()