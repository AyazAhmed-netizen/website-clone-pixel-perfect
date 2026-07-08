"""
Memory Store Implementation
内存存储实现

Thread-safe in-memory storage for extraction results.
Replaces Supabase database for the open-source version.

Features:
- Thread-safe operations with Lock
- TTL-based automatic expiration
- LRU eviction when max entries exceeded
- Simple CRUD operations
"""

import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime


@dataclass
class CacheEntry:
    """
    Cache entry data structure
    缓存条目数据结构
    """
    id: str                          # Unique identifier
    url: str                         # Source URL
    title: Optional[str]             # Page title
    data: Dict[str, Any]             # Full extraction data
    timestamp: float                 # Unix timestamp when created
    ttl: float = 86400.0            # Time to live in seconds (default 24h)

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired"""
        return time.time() - self.timestamp >= self.ttl

    @property
    def created_at(self) -> str:
        """Get ISO format creation time"""
        return datetime.fromtimestamp(self.timestamp).isoformat()

    @property
    def expires_at(self) -> str:
        """Get ISO format expiration time"""
        return datetime.fromtimestamp(self.timestamp + self.ttl).isoformat()

    @property
    def size_bytes(self) -> int:
        """Estimate size in bytes"""
        import json
        try:
            return len(json.dumps(self.data, ensure_ascii=False))
        except (TypeError, ValueError, OverflowError):
            return 0

    def to_summary(self) -> Dict[str, Any]:
        """
        Convert to summary dict (for list endpoint)
        Only includes metadata, not full data
        """
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "size_bytes": self.size_bytes,
            "top_keys": list(self.data.keys())[:10] if self.data else [],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dict (for get endpoint)"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "size_bytes": self.size_bytes,
            "data": self.data,
        }


class MemoryStore:
    """
    Thread-safe in-memory storage
    线程安全的内存存储

    Features:
    - Maximum entry limit with LRU eviction
    - TTL-based automatic expiration
    - Thread-safe with Lock
    """

    def __init__(self, max_entries: int = 50, default_ttl: float = 86400.0):
        """
        Initialize memory store

        Args:
            max_entries: Maximum number of entries to keep
            default_ttl: Default time-to-live in seconds (24h)
        """
        self._store: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._max_entries = max_entries
        self._default_ttl = default_ttl

    def store(
        self,
        url: str,
        data: Dict[str, Any],
        title: Optional[str] = None,
        ttl: Optional[float] = None,
    ) -> str:
        """
        Store extraction result
        存储提取结果

        Args:
            url: Source URL
            data: Extraction data (full result from Playwright)
            title: Optional page title
            ttl: Optional custom TTL

        Returns:
            Entry ID
        """
        with self._lock:
            # Clean up expired entries first
            self._cleanup_expired()

            # Generate unique ID (use 12 hex chars for better uniqueness)
            entry_id = str(uuid.uuid4())[:12]
            # Ensure no collision
            while entry_id in self._store:
                entry_id = str(uuid.uuid4())[:12]

            # Evict oldest if at capacity
            if self._max_entries <= 0:
                return entry_id
            while len(self._store) >= self._max_entries:
                oldest_id = min(
                    self._store,
                    key=lambda k: self._store[k].timestamp
                )
                del self._store[oldest_id]

            # Create and store entry
            self._store[entry_id] = CacheEntry(
                id=entry_id,
                url=url,
                title=title or self._extract_title(data),
                data=data,
                timestamp=time.time(),
                ttl=ttl or self._default_ttl,
            )

            return entry_id

    def get(self, entry_id: str) -> Optional[CacheEntry]:
        """
        Get cache entry by ID
        根据 ID 获取缓存条目

        Args:
            entry_id: Entry ID

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        with self._lock:
            entry = self._store.get(entry_id)
            if entry and not entry.is_expired:
                return entry
            # Clean up if expired
            if entry and entry.is_expired:
                del self._store[entry_id]
            return None

    def get_by_url(self, url: str) -> Optional[CacheEntry]:
        """
        Get most recent cache entry for URL
        根据 URL 获取最新缓存条目

        Args:
            url: Source URL

        Returns:
            Most recent CacheEntry for this URL, or None
        """
        with self._lock:
            matching = [
                e for e in self._store.values()
                if e.url == url and not e.is_expired
            ]
            if not matching:
                return None
            return max(matching, key=lambda e: e.timestamp)

    def list_all(self) -> List[CacheEntry]:
        """
        List all valid (non-expired) cache entries
        列出所有有效缓存条目

        Returns:
            List of CacheEntry, sorted by timestamp (newest first)
        """
        with self._lock:
            self._cleanup_expired()
            return sorted(
                self._store.values(),
                key=lambda e: -e.timestamp
            )

    def delete(self, entry_id: str) -> bool:
        """
        Delete cache entry
        删除缓存条目

        Args:
            entry_id: Entry ID

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if entry_id in self._store:
                del self._store[entry_id]
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cache entries
        清空所有缓存

        Returns:
            Number of entries deleted
        """
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        获取缓存统计信息
        """
        with self._lock:
            entries = list(self._store.values())
            total_size = sum(e.size_bytes for e in entries)
            return {
                "total_entries": len(entries),
                "max_entries": self._max_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "default_ttl_hours": self._default_ttl / 3600,
            }

    def _cleanup_expired(self) -> int:
        """
        Remove expired entries (internal, assumes lock held)
        清理过期条目

        Returns:
            Number of entries removed
        """
        expired = [
            k for k, v in self._store.items()
            if v.is_expired
        ]
        for k in expired:
            del self._store[k]
        return len(expired)

    def _extract_title(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract title from extraction data"""
        if not data:
            return None
        # Try metadata.title first
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            title = metadata.get("title")
            if title:
                return title
        return None


# Global singleton instance
# 全局单例实例
extraction_cache = MemoryStore(max_entries=50, default_ttl=86400.0)
