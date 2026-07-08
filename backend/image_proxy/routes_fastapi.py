"""
Image Proxy API Routes

Provides endpoints for:
- Proxying external images (bypasses CORS)
- Cache statistics
- Cache management (cleanup)
"""

import os
import httpx
import logging
from urllib.parse import urlparse, unquote
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import Response, JSONResponse

from .cache_manager import ImageCacheManager

logger = logging.getLogger(__name__)

# ============================================
# Configuration
# ============================================

# Cache directory (relative to backend_python/)
CACHE_DIR = os.getenv("IMAGE_CACHE_DIR", "./image_cache")
MAX_CACHE_SIZE_MB = int(os.getenv("IMAGE_CACHE_MAX_SIZE_MB", "500"))
CACHE_TTL_HOURS = int(os.getenv("IMAGE_CACHE_TTL_HOURS", "24"))
MAX_IMAGE_SIZE_MB = int(os.getenv("IMAGE_MAX_SIZE_MB", "10"))

# Initialize cache manager
cache_manager = ImageCacheManager(
    cache_dir=CACHE_DIR,
    max_cache_size_mb=MAX_CACHE_SIZE_MB,
    cache_ttl_seconds=CACHE_TTL_HOURS * 3600,
    max_image_size_mb=MAX_IMAGE_SIZE_MB,
)

# HTTP client for fetching images
http_client = httpx.AsyncClient(
    timeout=30.0,
    follow_redirects=True,
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/*,*/*;q=0.8",
    }
)

# Allowed image content types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/x-icon",
    "image/ico",
    "image/vnd.microsoft.icon",
    "image/avif",
    "image/heic",
    "image/heif",
}

# ============================================
# Router
# ============================================

router = APIRouter(prefix="/api/image-proxy", tags=["Image Proxy"])


# ============================================
# Endpoints
# ============================================

@router.get("")
@router.get("/")
async def proxy_image(
    url: str = Query(..., description="URL of the image to proxy"),
    background_tasks: BackgroundTasks = None,
):
    """
    Proxy an external image to bypass CORS restrictions.

    This endpoint:
    1. Checks if the image is already cached
    2. If not, fetches from the original URL
    3. Caches the image for future requests
    4. Returns the image with proper content-type

    Example:
        GET /api/image-proxy?url=https://example.com/image.jpg
    """
    # Decode URL if encoded
    url = unquote(url)

    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme in ("http", "https"):
            raise ValueError("Invalid URL scheme")
        if not parsed.netloc:
            raise ValueError("Invalid URL host")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")

    # Check cache first
    cached = await cache_manager.get(url)
    if cached:
        data, content_type = cached
        logger.debug(f"[ImageProxy] Cache hit: {url[:60]}...")
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "X-Cache": "HIT",
                "Cache-Control": "public, max-age=86400",  # Browser cache 24h
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fetch from original URL
    try:
        logger.info(f"[ImageProxy] Fetching: {url[:80]}...")
        response = await http_client.get(url)
        response.raise_for_status()
    except httpx.TimeoutException:
        logger.error(f"[ImageProxy] Timeout: {url[:60]}...")
        raise HTTPException(status_code=504, detail="Image fetch timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"[ImageProxy] HTTP error {e.response.status_code}: {url[:60]}...")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch image: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"[ImageProxy] Fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {str(e)}")

    # Validate content type
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()

    # Handle cases where server returns wrong content-type
    if content_type not in ALLOWED_CONTENT_TYPES:
        # Try to guess from URL extension
        ext_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        url_lower = url.lower()
        for ext, mime in ext_map.items():
            if ext in url_lower:
                content_type = mime
                break
        else:
            # If still not an image type, check if content looks like an image
            if not content_type.startswith("image/"):
                logger.warning(f"[ImageProxy] Non-image content-type: {content_type} for {url[:60]}...")
                # Still try to serve it - sometimes servers misconfigure content-type
                if content_type in ("application/octet-stream", "binary/octet-stream", ""):
                    content_type = "image/jpeg"  # Default guess

    # Get image data
    image_data = response.content

    # Check size limit
    if len(image_data) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large (max {MAX_IMAGE_SIZE_MB}MB)"
        )

    # Cache the image (in background to not block response)
    if background_tasks:
        background_tasks.add_task(cache_manager.put, url, image_data, content_type)
    else:
        await cache_manager.put(url, image_data, content_type)

    logger.info(f"[ImageProxy] Proxied: {url[:60]}... ({len(image_data)} bytes)")

    return Response(
        content=image_data,
        media_type=content_type,
        headers={
            "X-Cache": "MISS",
            "Cache-Control": "public, max-age=86400",  # Browser cache 24h
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/stats")
async def get_cache_stats():
    """
    Get cache statistics.

    Returns information about:
    - Total cached entries
    - Cache size usage
    - Configuration
    """
    stats = cache_manager.get_stats()
    return JSONResponse(content={
        "success": True,
        "stats": stats
    })


@router.post("/cleanup")
async def cleanup_cache():
    """
    Clean up expired cache entries.

    This is automatically done during normal operation,
    but can be triggered manually if needed.
    """
    removed = await cache_manager.cleanup_expired()
    stats = cache_manager.get_stats()
    return JSONResponse(content={
        "success": True,
        "removed_entries": removed,
        "current_stats": stats
    })


@router.delete("/clear")
async def clear_cache():
    """
    Clear all cached images.

    Use with caution - this removes all cached images.
    """
    removed = await cache_manager.clear_all()
    return JSONResponse(content={
        "success": True,
        "removed_entries": removed,
        "message": "Cache cleared successfully"
    })


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={
        "status": "healthy",
        "service": "image-proxy",
        "cache_stats": cache_manager.get_stats()
    })
