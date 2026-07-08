"""
Image Proxy Module

Provides a proxy endpoint for loading external images in WebContainer.
Bypasses CORS restrictions by fetching images through the backend server.

Features:
- File-based caching with LRU eviction
- Configurable cache TTL and size limits
- Automatic cleanup of expired/oversized cache
"""

from .routes_fastapi import router
from .cache_manager import ImageCacheManager

__all__ = ["router", "ImageCacheManager"]
