"""
Cache API Routes
缓存 API 路由

Provides HTTP endpoints for cache operations:
- POST /api/cache/store     - Store extraction result
- GET  /api/cache/list      - List all cached extractions
- GET  /api/cache/{id}      - Get single cache entry
- DELETE /api/cache/{id}    - Delete cache entry
- GET  /api/cache/stats     - Get cache statistics
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from .memory_store import extraction_cache

router = APIRouter(prefix="/api/cache", tags=["cache"])


# ============================================
# Request/Response Models
# ============================================

class StoreCacheRequest(BaseModel):
    """Request model for storing extraction result"""
    url: str = Field(..., description="Source URL")
    data: Dict[str, Any] = Field(..., description="Extraction data")
    title: Optional[str] = Field(None, description="Page title (optional)")

class StoreCacheResponse(BaseModel):
    """Response model for store operation"""
    success: bool
    id: str
    message: str

class CacheSummary(BaseModel):
    """Summary of a cache entry (for list endpoint)"""
    id: str
    url: str
    title: Optional[str]
    timestamp: float
    created_at: str
    expires_at: str
    size_bytes: int
    top_keys: List[str]

class CacheListResponse(BaseModel):
    """Response model for list endpoint"""
    success: bool
    count: int
    items: List[CacheSummary]

class CacheDetailResponse(BaseModel):
    """Response model for get endpoint"""
    success: bool
    id: str
    url: str
    title: Optional[str]
    timestamp: float
    created_at: str
    expires_at: str
    size_bytes: int
    data: Dict[str, Any]

class CacheStatsResponse(BaseModel):
    """Response model for stats endpoint"""
    total_entries: int
    max_entries: int
    total_size_bytes: int
    total_size_mb: float
    default_ttl_hours: float


# ============================================
# API Endpoints
# ============================================

@router.post("/store", response_model=StoreCacheResponse)
async def store_cache(request: StoreCacheRequest):
    """
    Store extraction result to cache
    存储提取结果到缓存

    This replaces the Supabase JSON storage.
    Agent can later retrieve this data for code generation.
    """
    try:
        entry_id = extraction_cache.store(
            url=request.url,
            data=request.data,
            title=request.title,
        )
        return StoreCacheResponse(
            success=True,
            id=entry_id,
            message=f"Stored successfully with ID: {entry_id}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=CacheListResponse)
async def list_cache():
    """
    List all cached extractions
    列出所有缓存的提取结果

    Returns summaries only (no full data) for efficiency.
    Use GET /api/cache/{id} to get full data.
    """
    entries = extraction_cache.list_all()
    return CacheListResponse(
        success=True,
        count=len(entries),
        items=[
            CacheSummary(**e.to_summary())
            for e in entries
        ],
    )


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """
    Get cache statistics
    获取缓存统计信息
    """
    stats = extraction_cache.stats()
    return CacheStatsResponse(**stats)


@router.get("/{entry_id}")
async def get_cache(entry_id: str):
    """
    Get single cache entry with full data
    获取单个缓存条目（包含完整数据）

    Returns the full extraction result stored by Playwright.
    """
    entry = extraction_cache.get(entry_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Cache entry '{entry_id}' not found or expired"
        )
    return {
        "success": True,
        **entry.to_dict(),
    }


@router.delete("/{entry_id}")
async def delete_cache(entry_id: str):
    """
    Delete cache entry
    删除缓存条目
    """
    if extraction_cache.delete(entry_id):
        return {
            "success": True,
            "message": f"Deleted cache entry: {entry_id}",
        }
    raise HTTPException(
        status_code=404,
        detail=f"Cache entry '{entry_id}' not found"
    )


@router.post("/clear")
async def clear_cache():
    """
    Clear all cache entries
    清空所有缓存

    Use with caution - this deletes all stored extractions.
    """
    count = extraction_cache.clear()
    return {
        "success": True,
        "message": f"Cleared {count} cache entries",
        "deleted_count": count,
    }
