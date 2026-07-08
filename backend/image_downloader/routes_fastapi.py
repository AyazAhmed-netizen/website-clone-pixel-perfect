"""
Image Downloader API Routes

Provides endpoints for:
- Batch downloading and compressing images
- Single image download
- Configuration options
"""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from .downloader import ImageDownloader, ImageDownloadConfig

logger = logging.getLogger(__name__)

# ============================================
# Request/Response Models
# ============================================


class ImageDownloadRequest(BaseModel):
    """Request model for batch image download."""
    urls: List[str] = Field(..., description="List of image URLs to download")

    # Compression settings (all optional with defaults)
    max_size_kb: int = Field(500, ge=10, le=5000, description="Max file size in KB")
    quality: int = Field(80, ge=10, le=100, description="Compression quality (1-100)")
    max_width: int = Field(1200, ge=100, le=4000, description="Max width in pixels")
    max_height: int = Field(1200, ge=100, le=4000, description="Max height in pixels")

    # Processing settings
    max_images: int = Field(20, ge=1, le=50, description="Max images to process")
    output_format: str = Field("webp", description="Output format: webp, jpeg, png")
    output_dir: str = Field("/public/images", description="Output directory path")


class DownloadedImageResponse(BaseModel):
    """Response model for a single downloaded image."""
    original_url: str
    local_path: str
    base64_data: str
    content_type: str
    original_size: int
    compressed_size: int
    width: int
    height: int
    success: bool
    error: Optional[str] = None


class BatchDownloadResponse(BaseModel):
    """Response model for batch download."""
    success: bool
    total_requested: int
    total_success: int
    total_failed: int
    total_original_size_kb: int
    total_compressed_size_kb: int
    images: List[DownloadedImageResponse]


# ============================================
# Router
# ============================================

router = APIRouter(prefix="/api/image-downloader", tags=["Image Downloader"])


# ============================================
# Endpoints
# ============================================

@router.post("/download", response_model=BatchDownloadResponse)
async def download_images(request: ImageDownloadRequest):
    """
    Download and compress multiple images.

    This endpoint:
    1. Downloads images from the provided URLs in parallel
    2. Compresses them according to the specified settings
    3. Returns Base64-encoded data for writing to WebContainer filesystem

    Example:
        POST /api/image-downloader/download
        {
            "urls": ["https://example.com/image1.jpg", "https://example.com/image2.png"],
            "max_size_kb": 500,
            "quality": 80
        }
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    # Validate output format
    if request.output_format not in ("webp", "jpeg", "jpg", "png"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output format: {request.output_format}. Use: webp, jpeg, png"
        )

    # Create config from request
    config = ImageDownloadConfig(
        max_size_kb=request.max_size_kb,
        quality=request.quality,
        max_width=request.max_width,
        max_height=request.max_height,
        max_images=request.max_images,
        output_format=request.output_format,
        output_dir=request.output_dir,
    )

    # Download images
    downloader = ImageDownloader(config)
    try:
        results = await downloader.download_batch(request.urls)
    finally:
        await downloader.close()

    # Build response
    images = [
        DownloadedImageResponse(
            original_url=r.original_url,
            local_path=r.local_path,
            base64_data=r.base64_data,
            content_type=r.content_type,
            original_size=r.original_size,
            compressed_size=r.compressed_size,
            width=r.width,
            height=r.height,
            success=r.success,
            error=r.error,
        )
        for r in results
    ]

    success_count = sum(1 for r in results if r.success)
    total_original = sum(r.original_size for r in results if r.success)
    total_compressed = sum(r.compressed_size for r in results if r.success)

    return BatchDownloadResponse(
        success=success_count > 0,
        total_requested=len(request.urls),
        total_success=success_count,
        total_failed=len(request.urls) - success_count,
        total_original_size_kb=total_original // 1024,
        total_compressed_size_kb=total_compressed // 1024,
        images=images,
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={
        "status": "healthy",
        "service": "image-downloader",
    })
