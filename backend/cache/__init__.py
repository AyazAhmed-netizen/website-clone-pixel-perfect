"""
Memory Cache Module
内存缓存模块

Provides in-memory storage for extraction results,
replacing Supabase database for the open-source version.
"""

from .memory_store import MemoryStore, CacheEntry, extraction_cache
from .routes import router as cache_router

__all__ = [
    "MemoryStore",
    "CacheEntry",
    "extraction_cache",
    "cache_router",
]
