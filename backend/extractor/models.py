"""
Playwright Extractor Data Models
定义数据结构和类型

包含：
- ElementRect: 元素尺寸和位置
- ElementStyles: 元素样式信息
- ElementInfo: 单个元素的完整信息
- PageAssets: 页面资源统计
- PageMetadata: 页面元数据
- CSSAnimation: CSS 动画定义
- CSSTransition: CSS 过渡定义
- CSSVariable: CSS 变量
- NetworkRequest: 网络请求
- ResourceContent: 资源内容
- InteractionState: 交互状态
- ExtractionResult: 完整提取结果
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


# ==================== Theme Models ====================

class ThemeMode(str, Enum):
    """
    主题模式枚举
    """
    LIGHT = "light"
    DARK = "dark"


class ThemeSupport(str, Enum):
    """
    页面主题支持类型
    """
    LIGHT_ONLY = "light-only"    # 仅支持亮色模式
    DARK_ONLY = "dark-only"      # 仅支持暗色模式
    BOTH = "both"                # 支持双模式
    UNKNOWN = "unknown"          # 无法确定


class ThemeDetectionResult(BaseModel):
    """
    主题检测结果
    """
    support: ThemeSupport = ThemeSupport.UNKNOWN
    current_mode: ThemeMode = ThemeMode.LIGHT
    has_significant_difference: bool = False

    # 检测细节
    detection_method: str = "none"  # css_media, class_toggle, color_scheme, none
    css_variables_diff_count: int = 0
    color_diff_count: int = 0
    image_diff_count: int = 0


class ThemedData(BaseModel):
    """
    按主题分类的数据
    用于存储 light/dark 两种模式下可能不同的数据
    """
    # 截图
    screenshot: Optional[str] = None
    full_page_screenshot: Optional[str] = None

    # 样式相关
    style_summary: Optional['StyleSummary'] = None
    css_data: Optional['CSSData'] = None

    # 资源（图片可能不同）
    assets: Optional['PageAssets'] = None
    downloaded_resources: Optional['DownloadedResources'] = None


# ==================== Element Models ====================

class ElementRect(BaseModel):
    """
    元素的位置和尺寸信息
    对应 getBoundingClientRect() 返回的数据
    """
    x: float           # 左边距离视口左边的距离
    y: float           # 上边距离视口顶部的距离
    width: float       # 元素宽度
    height: float      # 元素高度
    top: float         # 同 y
    right: float       # x + width
    bottom: float      # y + height
    left: float        # 同 x


class ElementStyles(BaseModel):
    """
    元素的计算后样式
    只提取布局和视觉相关的关键样式
    """
    # 布局相关
    display: Optional[str] = None
    position: Optional[str] = None
    float_: Optional[str] = None  # float 是保留字
    clear: Optional[str] = None

    # Flexbox
    flex_direction: Optional[str] = None
    flex_wrap: Optional[str] = None
    justify_content: Optional[str] = None
    align_items: Optional[str] = None
    align_content: Optional[str] = None
    gap: Optional[str] = None

    # Grid
    grid_template_columns: Optional[str] = None
    grid_template_rows: Optional[str] = None
    grid_column: Optional[str] = None
    grid_row: Optional[str] = None

    # 尺寸
    width: Optional[str] = None
    height: Optional[str] = None
    min_width: Optional[str] = None
    min_height: Optional[str] = None
    max_width: Optional[str] = None
    max_height: Optional[str] = None

    # 间距
    margin: Optional[str] = None
    margin_top: Optional[str] = None
    margin_right: Optional[str] = None
    margin_bottom: Optional[str] = None
    margin_left: Optional[str] = None
    padding: Optional[str] = None
    padding_top: Optional[str] = None
    padding_right: Optional[str] = None
    padding_bottom: Optional[str] = None
    padding_left: Optional[str] = None

    # 定位
    top: Optional[str] = None
    right: Optional[str] = None
    bottom: Optional[str] = None
    left: Optional[str] = None
    z_index: Optional[str] = None

    # 视觉
    background_color: Optional[str] = None
    background_image: Optional[str] = None
    color: Optional[str] = None
    border: Optional[str] = None
    border_radius: Optional[str] = None
    box_shadow: Optional[str] = None
    opacity: Optional[str] = None
    overflow: Optional[str] = None
    visibility: Optional[str] = None

    # 文字
    font_family: Optional[str] = None
    font_size: Optional[str] = None
    font_weight: Optional[str] = None
    line_height: Optional[str] = None
    text_align: Optional[str] = None

    # 变换
    transform: Optional[str] = None

    class Config:
        # 允许使用 float_ 作为 float 的别名
        populate_by_name = True


class ElementInfo(BaseModel):
    """
    单个 DOM 元素的完整信息
    """
    # 基础信息
    tag: str                              # 标签名 (div, span, etc.)
    id: Optional[str] = None              # 元素 ID
    classes: List[str] = []               # CSS 类名列表

    # 位置和尺寸
    rect: ElementRect

    # 样式
    styles: ElementStyles

    # 内容
    text_content: Optional[str] = None    # 直接文本内容（不含子元素）
    inner_html_length: int = 0            # 有效 innerHTML 长度（排除 base64 图片、SVG 等）
    raw_html_length: int = 0              # 原始 innerHTML 长度（包含所有内容）

    # 属性
    attributes: Dict[str, str] = {}       # 其他重要属性 (href, src, alt, etc.)

    # 元素类型标记
    is_visible: bool = True               # 是否可见
    is_interactive: bool = False          # 是否可交互 (button, a, input, etc.)

    # 子元素
    children: List['ElementInfo'] = []    # 子元素列表
    children_count: int = 0               # 直接子元素数量

    # 路径标识
    xpath: Optional[str] = None           # XPath 路径
    selector: Optional[str] = None        # CSS 选择器


# ==================== Page Level Models ====================

class AssetInfo(BaseModel):
    """
    单个资源的信息
    """
    url: str
    type: str                             # image, script, stylesheet, font, etc.
    size: Optional[int] = None            # 文件大小（字节）


class PageAssets(BaseModel):
    """
    页面资源统计
    """
    images: List[AssetInfo] = []          # 图片资源
    scripts: List[AssetInfo] = []         # JS 脚本
    stylesheets: List[AssetInfo] = []     # CSS 样式表
    fonts: List[AssetInfo] = []           # 字体文件

    # 统计
    total_images: int = 0
    total_scripts: int = 0
    total_stylesheets: int = 0
    total_fonts: int = 0


class StyleSummary(BaseModel):
    """
    页面样式汇总统计
    """
    # 颜色
    colors: Dict[str, int] = {}           # 颜色 -> 使用次数
    background_colors: Dict[str, int] = {}

    # 字体
    font_families: Dict[str, int] = {}    # 字体 -> 使用次数
    font_sizes: Dict[str, int] = {}       # 字号 -> 使用次数

    # 间距
    margins: Dict[str, int] = {}          # margin 值 -> 使用次数
    paddings: Dict[str, int] = {}         # padding 值 -> 使用次数

    # 布局
    display_types: Dict[str, int] = {}    # display 值 -> 使用次数
    position_types: Dict[str, int] = {}   # position 值 -> 使用次数


class PageMetadata(BaseModel):
    """
    页面元数据
    """
    url: str                              # 页面 URL
    title: str                            # 页面标题

    # 视口信息
    viewport_width: int
    viewport_height: int

    # 页面尺寸
    page_width: int                       # 完整页面宽度
    page_height: int                      # 完整页面高度（含滚动）

    # 统计
    total_elements: int                   # 总元素数
    max_depth: int                        # DOM 树最大深度

    # 性能
    load_time_ms: int                     # 页面加载时间（毫秒）


class ExtractionResult(BaseModel):
    """
    完整的提取结果
    """
    success: bool
    message: str

    # 页面基础信息
    metadata: Optional[PageMetadata] = None

    # 截图（Base64 编码）- 当前预览模式的截图
    screenshot: Optional[str] = None

    # 全页截图（Base64 编码）
    full_page_screenshot: Optional[str] = None

    # DOM 结构
    dom_tree: Optional[ElementInfo] = None

    # 样式汇总
    style_summary: Optional[StyleSummary] = None

    # 资源列表（URL）
    assets: Optional[PageAssets] = None

    # ========== 新增字段 ==========

    # 原始 HTML
    raw_html: Optional[str] = None

    # 完整 CSS 数据（样式表内容、动画、变量等）
    css_data: Optional['CSSData'] = None

    # 网络请求数据（API 调用等）
    network_data: Optional['NetworkData'] = None

    # 已下载的资源内容
    downloaded_resources: Optional['DownloadedResources'] = None

    # 交互状态（hover、focus 等）
    interaction_data: Optional['InteractionData'] = None

    # 技术栈分析
    tech_stack: Optional['TechStackData'] = None

    # 组件分析
    components: Optional['ComponentAnalysisData'] = None

    # 错误信息（如果有）
    error: Optional[str] = None

    # ========== 主题相关字段 ==========

    # 主题检测结果
    theme_detection: Optional[ThemeDetectionResult] = None

    # 亮色模式数据（当支持双模式时）
    light_mode_data: Optional[ThemedData] = None

    # 暗色模式数据（当支持双模式时）
    dark_mode_data: Optional[ThemedData] = None

    # 当前预览的主题模式
    current_theme: ThemeMode = ThemeMode.LIGHT


# ==================== CSS Animation Models ====================

class CSSKeyframe(BaseModel):
    """
    单个关键帧
    """
    offset: str                           # 0%, 50%, 100% 等
    styles: Dict[str, str] = {}           # 该帧的样式


class CSSAnimation(BaseModel):
    """
    CSS @keyframes 动画定义
    """
    name: str                             # 动画名称
    keyframes: List[CSSKeyframe] = []     # 关键帧列表
    source_stylesheet: Optional[str] = None  # 来源样式表 URL


class CSSTransitionInfo(BaseModel):
    """
    CSS 过渡定义
    """
    property: str                         # 过渡属性
    duration: str                         # 持续时间
    timing_function: str                  # 缓动函数
    delay: str                            # 延迟


class CSSVariable(BaseModel):
    """
    CSS 变量定义
    """
    name: str                             # 变量名 (--primary-color)
    value: str                            # 变量值
    scope: str = ":root"                  # 定义作用域


class PseudoElementStyle(BaseModel):
    """
    伪元素样式
    """
    selector: str                         # 元素选择器
    pseudo: str                           # ::before, ::after 等
    styles: Dict[str, str] = {}           # 样式
    content: Optional[str] = None         # content 属性值


class StylesheetContent(BaseModel):
    """
    完整样式表内容
    """
    url: str                              # 样式表 URL（内联为 "inline"）
    content: str                          # 原始 CSS 内容
    is_inline: bool = False               # 是否为内联样式


class CSSData(BaseModel):
    """
    完整的 CSS 数据
    """
    stylesheets: List[StylesheetContent] = []     # 所有样式表
    animations: List[CSSAnimation] = []           # @keyframes 动画
    transitions: List[CSSTransitionInfo] = []     # 过渡效果
    variables: List[CSSVariable] = []             # CSS 变量
    pseudo_elements: List[PseudoElementStyle] = [] # 伪元素样式
    media_queries: Dict[str, str] = {}            # 媒体查询规则


# ==================== Network Models ====================

class NetworkRequestType(str, Enum):
    """网络请求类型"""
    XHR = "xhr"
    FETCH = "fetch"
    DOCUMENT = "document"
    STYLESHEET = "stylesheet"
    SCRIPT = "script"
    IMAGE = "image"
    FONT = "font"
    OTHER = "other"


class NetworkRequest(BaseModel):
    """
    网络请求记录
    """
    url: str                              # 请求 URL
    method: str = "GET"                   # 请求方法
    request_type: str = "other"           # 请求类型
    headers: Dict[str, str] = {}          # 请求头
    post_data: Optional[str] = None       # POST 数据
    response_status: Optional[int] = None # 响应状态码
    response_headers: Dict[str, str] = {} # 响应头
    response_body: Optional[str] = None   # 响应体（仅 XHR/Fetch）
    response_size: Optional[int] = None   # 响应大小
    timing: Optional[float] = None        # 请求耗时（毫秒）


class NetworkData(BaseModel):
    """
    网络请求数据汇总
    """
    requests: List[NetworkRequest] = []   # 所有请求
    api_calls: List[NetworkRequest] = []  # API 调用（XHR/Fetch）
    total_requests: int = 0
    total_size: int = 0


# ==================== Resource Content Models ====================

class ResourceContent(BaseModel):
    """
    下载的资源内容
    """
    url: str                              # 资源 URL
    type: str                             # image, font, script, stylesheet
    content: Optional[str] = None         # Base64 编码的内容
    size: int = 0                         # 文件大小（字节）
    mime_type: Optional[str] = None       # MIME 类型
    filename: Optional[str] = None        # 文件名


class DownloadedResources(BaseModel):
    """
    已下载的资源汇总
    """
    images: List[ResourceContent] = []
    fonts: List[ResourceContent] = []
    scripts: List[ResourceContent] = []
    stylesheets: List[ResourceContent] = []


# ==================== Interaction State Models ====================

class InteractionState(BaseModel):
    """
    交互状态捕获
    """
    selector: str                         # 元素选择器
    state: str                            # hover, focus, active, visited
    styles: Dict[str, str] = {}           # 该状态下的样式
    screenshot: Optional[str] = None      # 该状态的截图（Base64）


class InteractionData(BaseModel):
    """
    交互状态数据汇总
    """
    hover_states: List[InteractionState] = []
    focus_states: List[InteractionState] = []
    active_states: List[InteractionState] = []


# ==================== Tech Stack Models ====================

class DependencyInfo(BaseModel):
    """
    依赖库信息
    """
    name: str                             # 库名称
    version: Optional[str] = None         # 版本号
    type: str = "library"                 # library, framework, tool, plugin
    confidence: int = 0                   # 置信度 0-100


class TechStackData(BaseModel):
    """
    技术栈分析结果
    """
    # 前端框架
    frameworks: List[DependencyInfo] = []

    # UI 库和组件库
    ui_libraries: List[DependencyInfo] = []

    # 工具库
    utilities: List[DependencyInfo] = []

    # 构建工具和打包器
    build_tools: List[DependencyInfo] = []

    # 样式方案
    styling: Dict[str, Optional[str]] = {
        "preprocessor": None,  # sass, less, stylus
        "framework": None,     # tailwind, bootstrap, bulma
        "css_in_js": None,     # styled-components, emotion
    }

    # 包管理器信息
    package_manager: Optional[str] = None

    # 检测到的技术特征
    features: List[str] = []

    # Meta 标签中的信息
    meta_tags: Dict[str, str] = {}


# ==================== Component Analysis Models ====================

class SectionStyles(BaseModel):
    """
    Section 的完整计算样式
    包含背景、颜色、间距等关键视觉信息
    """
    # 背景相关
    background_color: Optional[str] = None
    background_image: Optional[str] = None
    background_size: Optional[str] = None
    background_position: Optional[str] = None
    background_repeat: Optional[str] = None
    background_gradient: Optional[str] = None  # 渐变

    # 颜色
    color: Optional[str] = None  # 文字颜色

    # 间距和布局
    padding: Optional[str] = None
    margin: Optional[str] = None
    gap: Optional[str] = None

    # 装饰
    border: Optional[str] = None
    border_radius: Optional[str] = None
    box_shadow: Optional[str] = None

    # 布局类型
    display: Optional[str] = None
    flex_direction: Optional[str] = None
    justify_content: Optional[str] = None
    align_items: Optional[str] = None

    # 背景来源（如果背景继承自父元素）
    background_inherited_from: Optional[str] = None

    # CSS 变量
    css_variables: Dict[str, str] = {}


class ComponentInfo(BaseModel):
    """
    页面组件/模块信息
    """
    # 基本信息
    id: str                               # 组件唯一 ID
    name: str                             # 组件名称
    type: str = "other"                   # header, footer, navigation, hero, section, sidebar, modal, other

    # 定位信息
    selector: str                         # CSS 选择器
    xpath: Optional[str] = None           # XPath 路径
    rect: ElementRect                     # 位置和尺寸

    # ⭐ 完整计算样式（新增）
    styles: Optional[SectionStyles] = None

    # 样式信息（保留旧字段兼容）
    colors: Dict[str, List[str]] = {
        "background": [],
        "text": [],
        "border": [],
        "accent": [],
    }

    # 动效信息
    animations: Dict[str, List[str]] = {
        "css_animations": [],
        "transitions": [],
        "transform_effects": [],
    }

    # 内部链接
    internal_links: List[Dict[str, str]] = []

    # 外部链接
    external_links: List[Dict[str, str]] = []

    # 图片资源
    images: List[Dict[str, Any]] = []

    # 文本内容摘要
    text_summary: Dict[str, Any] = {
        "headings": [],
        "paragraph_count": 0,
        "word_count": 0,
    }

    # 代码位置信息（用于在原始 HTML 中定位组件）
    code_location: Optional[Dict[str, Any]] = {
        "start_line": 0,              # 在原始 HTML 中的起始行号
        "end_line": 0,                # 在原始 HTML 中的结束行号
        "html_snippet": "",           # HTML 代码片段（前10行预览）
        "full_html": "",              # 完整的 outerHTML（用于精确复制）
        "char_start": 0,              # 字符起始位置
        "char_end": 0,                # 字符结束位置
    }

    # CSS 规则（组件使用的所有 CSS 类定义）
    # 包含完整的 CSS 规则字符串，如：
    # .text-brand { color: rgb(251, 101, 30); }
    # .bg-beige-light { background-color: rgb(245, 245, 238); }
    css_rules: str = ""

    # 子组件
    sub_components: List['ComponentInfo'] = []


class ComponentAnalysisData(BaseModel):
    """
    页面组件分析结果
    """
    # 识别出的主要组件
    components: List[ComponentInfo] = []

    # 组件统计
    stats: Dict[str, Any] = {
        "total_components": 0,
        "by_type": {},
        "total_links": 0,
        "total_images": 0,
    }


# ==================== Phased Extraction Models (分阶段提取) ====================

class ExtractionPhase(str, Enum):
    """
    提取阶段枚举
    用于分阶段返回数据，优化首屏加载速度
    """
    QUICK = "quick"         # 快速阶段：metadata, screenshot, assets, raw_html
    DOM = "dom"             # DOM 阶段：dom_tree, style_summary
    ADVANCED = "advanced"   # 高级阶段：css_data, network_data, interaction_data
    COMPLETE = "complete"   # 完成：downloaded_resources
    ERROR = "error"         # 错误状态


class QuickExtractionResult(BaseModel):
    """
    快速提取结果（首次响应）
    包含足够渲染 Overview Tab 的数据
    """
    success: bool
    message: str
    request_id: str                           # 唯一请求 ID，用于后续轮询
    phase: ExtractionPhase = ExtractionPhase.QUICK
    progress: int = 25                        # 进度百分比

    # 快速数据
    metadata: Optional[PageMetadata] = None
    screenshot: Optional[str] = None
    assets: Optional[PageAssets] = None
    raw_html: Optional[str] = None

    # 主题相关
    theme_detection: Optional[ThemeDetectionResult] = None
    current_theme: ThemeMode = ThemeMode.LIGHT

    # 亮色/暗色模式数据（当支持双模式时）
    light_mode_data: Optional[ThemedData] = None
    dark_mode_data: Optional[ThemedData] = None

    # 错误信息
    error: Optional[str] = None


class ExtractionStatus(BaseModel):
    """
    提取状态查询响应
    用于轮询获取后续阶段的数据
    """
    request_id: str
    phase: ExtractionPhase
    progress: int                             # 0-100
    is_complete: bool = False

    # 各阶段数据（按需返回）
    # DOM 阶段
    dom_tree: Optional[ElementInfo] = None
    style_summary: Optional[StyleSummary] = None

    # 高级阶段
    css_data: Optional['CSSData'] = None
    network_data: Optional['NetworkData'] = None
    full_page_screenshot: Optional[str] = None
    interaction_data: Optional['InteractionData'] = None
    tech_stack: Optional['TechStackData'] = None
    components: Optional['ComponentAnalysisData'] = None

    # 完成阶段
    downloaded_resources: Optional['DownloadedResources'] = None

    # 主题相关（完成阶段后更新）
    light_mode_data: Optional[ThemedData] = None
    dark_mode_data: Optional[ThemedData] = None

    # 错误信息
    error: Optional[str] = None


# ==================== Request Models ====================

class ExtractRequest(BaseModel):
    """
    提取请求参数
    """
    url: str                              # 目标 URL
    viewport_width: int = 1920            # 视口宽度
    viewport_height: int = 1080           # 视口高度
    wait_for_selector: Optional[str] = None  # 等待特定选择器
    wait_timeout: int = 30000             # 等待超时（毫秒）
    include_screenshot: bool = True       # 是否包含截图
    max_depth: int = 50                   # 最大遍历深度
    include_hidden: bool = False          # 是否包含隐藏元素
    # 新增选项
    download_resources: bool = True       # 是否下载资源文件
    capture_network: bool = True          # 是否捕获网络请求
    capture_interactions: bool = True     # 是否捕获交互状态
    extract_css: bool = True              # 是否提取完整 CSS
    full_page_screenshot: bool = False    # 是否全页截图


# 允许自引用和前向引用
ElementInfo.model_rebuild()
ComponentInfo.model_rebuild()
ThemedData.model_rebuild()
ExtractionResult.model_rebuild()
QuickExtractionResult.model_rebuild()
ExtractionStatus.model_rebuild()
