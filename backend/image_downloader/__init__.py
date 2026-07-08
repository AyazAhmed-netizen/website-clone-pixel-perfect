"""
Image Downloader Module

Provides batch download and compression for external images.
Used by WebContainer to localize external images for preview.

Features:
- Batch parallel download
- Image compression (quality, size limits)
- Configurable parameters
- Base64 output for WebContainer filesystem
"""

from .routes_fastapi import router
from .downloader import ImageDownloader

__all__ = ["router", "ImageDownloader"]
