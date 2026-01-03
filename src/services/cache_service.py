import json
import redis
import logging
from functools import wraps
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


def require_redis(default_return=None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            return default_return if not self.redis_client else func(self, *args, **kwargs)
        return wrapper
    return decorator


class CacheService:
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0):
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Caching will be disabled.")
            self.redis_client = None
    
    @require_redis(default_return=None)
    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.redis_client.get(key)
            return self._try_json(value)
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    @require_redis(default_return=False)
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    @require_redis(default_return=False)
    def delete(self, key: str) -> bool:
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False
    
    @require_redis(default_return=0)
    def clear_pattern(self, pattern: str) -> int:
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
        return 0
    
    @require_redis(default_return=False)
    def clear_all(self) -> bool:
        try:
            self.redis_client.flushdb()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    @staticmethod
    def _try_json(value: str) -> bool:
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
