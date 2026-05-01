"""
Intelligent Request Caching & Retry System
Reduces API calls, handles failures gracefully
"""

import hashlib
import json
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL"""
    
    def __init__(self, value: Any, ttl_seconds: int = 3600):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() - self.created_at > self.ttl_seconds
    
    def access(self) -> Any:
        """Get value and update access info"""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class RequestCache:
    """LRU cache for API requests with TTL"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def _hash_request(self, key: str) -> str:
        """Create hash key for cache"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        hash_key = self._hash_request(key)
        
        if hash_key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[hash_key]
        
        if entry.is_expired():
            del self.cache[hash_key]
            self.misses += 1
            return None
        
        # Move to end (LRU)
        self.cache.move_to_end(hash_key)
        self.hits += 1
        return entry.access()
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set value in cache"""
        hash_key = self._hash_request(key)
        
        if hash_key in self.cache:
            del self.cache[hash_key]
        
        self.cache[hash_key] = CacheEntry(value, ttl_seconds)
        
        # Enforce max size (remove oldest)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "total_entries": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "usage_percent": len(self.cache) / self.max_size * 100
        }


class RetryPolicy:
    """Configurable retry policy with exponential backoff"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_ms: float = 100,
        max_delay_ms: float = 5000,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Retry successful on attempt {attempt + 1}")
                
                return result
            
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate backoff
                    delay_ms = min(
                        self.initial_delay_ms * (self.exponential_base ** attempt),
                        self.max_delay_ms
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay_ms}ms..."
                    )
                    
                    await asyncio.sleep(delay_ms / 1000)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
        
        raise last_exception
    
    def get_config(self) -> Dict[str, Any]:
        """Get retry policy configuration"""
        return {
            "max_retries": self.max_retries,
            "initial_delay_ms": self.initial_delay_ms,
            "max_delay_ms": self.max_delay_ms,
            "exponential_base": self.exponential_base
        }


class CachedRequest:
    """Wrapper for cached requests with retry"""
    
    def __init__(self, cache: Optional[RequestCache] = None):
        self.cache = cache or RequestCache()
        self.retry_policy = RetryPolicy()
    
    async def execute(
        self,
        cache_key: str,
        func: Callable,
        ttl_seconds: int = 3600,
        use_cache: bool = True,
        *args,
        **kwargs
    ) -> Any:
        """Execute request with caching and retry"""
        
        # Check cache first
        if use_cache:
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for: {cache_key}")
                return cached_value
        
        # Execute with retry
        try:
            result = await self.retry_policy.execute_with_retry(func, *args, **kwargs)
            
            # Store in cache
            if use_cache:
                self.cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        except Exception as e:
            logger.error(f"Request failed after retries: {str(e)}")
            raise
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get caching statistics"""
        return {
            "cache": self.cache.get_stats(),
            "retry_policy": self.retry_policy.get_config()
        }


# Global instances
request_cache = RequestCache()
cached_request = CachedRequest(request_cache)
