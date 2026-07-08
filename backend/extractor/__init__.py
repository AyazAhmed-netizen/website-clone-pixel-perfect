"""
Playwright Extractor Module
Playwright 网页提取模块

Provides web page extraction capabilities:
- Full page extraction with DOM tree, styles, assets
- Quick extraction with staged loading
- AI-powered page division
- Tech stack analysis
- Component analysis
"""

from .extractor_service import PlaywrightExtractorService

# Create singleton service instance
playwright_extractor_service = PlaywrightExtractorService()

from .routes import router as extractor_router

__all__ = [
    "playwright_extractor_service",
    "extractor_router",
    "PlaywrightExtractorService",
]
