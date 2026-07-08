"""
Extraction Cache Manager
提取结果缓存管理器

用于存储分阶段提取的中间结果，支持：
- 内存缓存存储
- 自动过期清理（10分钟）
- 线程安全操作
"""

import asyncio
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .models import (
    ExtractionPhase,
    PageMetadata,
    PageAssets,
    ElementInfo,
    StyleSummary,
    CSSData,
    NetworkData,
    DownloadedResources,
    InteractionData,
    TechStackData,
    ComponentAnalysisData,
)

logger = logging.getLogger(__name__)

# 缓存过期时间（秒）
CACHE_TTL_SECONDS = 600  # 10 分钟


@dataclass
class CachedExtraction:
    """
    缓存的提取数据
    """
    request_id: str
    url: str
    created_at: datetime = field(default_factory=datetime.now)
    phase: ExtractionPhase = ExtractionPhase.QUICK
    progress: int = 0
    error: Optional[str] = None

    # 快速阶段数据
    metadata: Optional[PageMetadata] = None
    screenshot: Optional[str] = None
    assets: Optional[PageAssets] = None
    raw_html: Optional[str] = None

    # DOM 阶段数据
    dom_tree: Optional[ElementInfo] = None
    style_summary: Optional[StyleSummary] = None

    # 高级阶段数据
    css_data: Optional[CSSData] = None
    network_data: Optional[NetworkData] = None
    full_page_screenshot: Optional[str] = None
    interaction_data: Optional[InteractionData] = None
    tech_stack: Optional[TechStackData] = None
    components: Optional[ComponentAnalysisData] = None

    # 完成阶段数据
    downloaded_resources: Optional[DownloadedResources] = None

    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return datetime.now() - self.created_at > timedelta(seconds=CACHE_TTL_SECONDS)


class ExtractionCacheManager:
    """
    提取结果缓存管理器
    线程安全的内存缓存实现
    """

    def __init__(self, max_entries: int = 50):
        self._cache: Dict[str, CachedExtraction] = {}
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self):
        """启动自动清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("缓存清理任务已启动")

    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理出错: {e}")

    async def _cleanup_expired(self):
        """清理过期的缓存条目"""
        async with self._lock:
            expired_keys = [
                key for key, value in self._cache.items()
                if value.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.info(f"已清理 {len(expired_keys)} 个过期缓存")

    def generate_request_id(self) -> str:
        """生成唯一请求 ID"""
        return str(uuid.uuid4())

    async def create(self, url: str) -> str:
        """
        创建新的缓存条目

        Args:
            url: 目标 URL

        Returns:
            request_id: 唯一请求 ID
        """
        request_id = self.generate_request_id()
        async with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_entries:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].created_at
                )
                del self._cache[oldest_key]
                logger.info(f"Evicted oldest cache entry: {oldest_key}")
            self._cache[request_id] = CachedExtraction(
                request_id=request_id,
                url=url,
                phase=ExtractionPhase.QUICK,
                progress=0
            )
        logger.debug(f"创建缓存: {request_id} for {url}")
        return request_id

    async def get(self, request_id: str) -> Optional[CachedExtraction]:
        """
        获取缓存条目

        Args:
            request_id: 请求 ID

        Returns:
            CachedExtraction 或 None
        """
        async with self._lock:
            cache = self._cache.get(request_id)
            if cache and cache.is_expired():
                del self._cache[request_id]
                return None
            return cache

    async def update_quick_phase(
        self,
        request_id: str,
        metadata: Optional[PageMetadata] = None,
        screenshot: Optional[str] = None,
        assets: Optional[PageAssets] = None,
        raw_html: Optional[str] = None,
        error: Optional[str] = None
    ):
        """更新快速阶段数据"""
        async with self._lock:
            cache = self._cache.get(request_id)
            if cache:
                cache.metadata = metadata
                cache.screenshot = screenshot
                cache.assets = assets
                cache.raw_html = raw_html
                cache.phase = ExtractionPhase.QUICK
                cache.progress = 25
                if error:
                    cache.error = error
                    cache.phase = ExtractionPhase.ERROR
                logger.debug(f"更新快速阶段: {request_id}")

    async def update_dom_phase(
        self,
        request_id: str,
        dom_tree: Optional[ElementInfo] = None,
        style_summary: Optional[StyleSummary] = None,
        error: Optional[str] = None
    ):
        """更新 DOM 阶段数据"""
        async with self._lock:
            cache = self._cache.get(request_id)
            if cache:
                cache.dom_tree = dom_tree
                cache.style_summary = style_summary
                cache.phase = ExtractionPhase.DOM
                cache.progress = 50
                if error:
                    cache.error = error
                    cache.phase = ExtractionPhase.ERROR
                logger.debug(f"更新 DOM 阶段: {request_id}")
            else:
                logger.warning(f"Cache entry not found for DOM phase update: {request_id}")

    async def update_advanced_phase(
        self,
        request_id: str,
        css_data: Optional[CSSData] = None,
        network_data: Optional[NetworkData] = None,
        full_page_screenshot: Optional[str] = None,
        interaction_data: Optional[InteractionData] = None,
        tech_stack: Optional[TechStackData] = None,
        components: Optional[ComponentAnalysisData] = None,
        error: Optional[str] = None
    ):
        """更新高级阶段数据"""
        async with self._lock:
            cache = self._cache.get(request_id)
            if cache:
                cache.css_data = css_data
                cache.network_data = network_data
                cache.full_page_screenshot = full_page_screenshot
                cache.interaction_data = interaction_data
                cache.tech_stack = tech_stack
                cache.components = components
                cache.phase = ExtractionPhase.ADVANCED
                cache.progress = 75
                if error:
                    cache.error = error
                    cache.phase = ExtractionPhase.ERROR
                logger.debug(f"更新高级阶段: {request_id}")
            else:
                logger.warning(f"Cache entry not found for advanced phase update: {request_id}")

    async def update_complete_phase(
        self,
        request_id: str,
        downloaded_resources: Optional[DownloadedResources] = None,
        error: Optional[str] = None
    ):
        """更新完成阶段数据"""
        async with self._lock:
            cache = self._cache.get(request_id)
            if cache:
                cache.downloaded_resources = downloaded_resources
                cache.phase = ExtractionPhase.COMPLETE
                cache.progress = 100
                if error:
                    cache.error = error
                logger.debug(f"更新完成阶段: {request_id}")

    async def delete(self, request_id: str):
        """删除缓存条目"""
        async with self._lock:
            if request_id in self._cache:
                del self._cache[request_id]
                logger.debug(f"删除缓存: {request_id}")

    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("缓存清理任务已停止")
        self._cleanup_task = None


# 全局缓存管理器实例
extraction_cache = ExtractionCacheManager()
