"""
Network Tools (WebFetch and WebSearch)

实现网络访问工具,用于获取外部资源和搜索信息。

功能:
- WebFetch (IJ1): 抓取网页内容
- WebSearch: 网页搜索

这些工具用于获取最新的文档、教程、API参考等外部信息。
"""

from __future__ import annotations
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from urllib.parse import quote_plus

from .webcontainer_tools import ToolResult


# ============================================
# WebFetch Tool (IJ1)
# ============================================

def web_fetch(
    url: str,
    prompt: str,
    timeout: int = 30,
    max_content_length: int = 50000,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    WebFetch (IJ1) - Fetch and analyze web content

    抓取网页内容并使用AI分析提取信息。

    支持:
    - HTML网页 (自动转换为Markdown)
    - API响应 (JSON, XML等)
    - 文档页面
    - GitHub README

    流程:
    1. 抓取URL内容
    2. 转换HTML为Markdown (如果适用)
    3. 使用AI根据prompt提取信息
    4. 返回结构化结果

    Args:
        url: 要抓取的URL (必须是完整的URL,如 https://example.com)
        prompt: 提示词,描述要从页面中提取什么信息
        timeout: 超时时间(秒) (默认 30)
        max_content_length: 最大内容长度 (默认 50000字符)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with extracted content
    """
    # Validate URL
    if not url.startswith("http://") and not url.startswith("https://"):
        return ToolResult(
            success=False,
            result=f"Invalid URL: {url}. URL must start with http:// or https://"
        )

    # Create action for backend to handle
    # (WebFetch需要后端处理,因为涉及网络请求和AI分析)
    action = {
        "type": "web_fetch",
        "payload": {
            "url": url,
            "prompt": prompt,
            "timeout": timeout,
            "max_content_length": max_content_length,
        }
    }

    return ToolResult(
        success=True,
        result=f"Fetching content from {url}...\nAnalyzing with prompt: {prompt}",
        action=action
    )


# ============================================
# WebSearch Tool
# ============================================

def web_search(
    query: str,
    num_results: int = 5,
    time_range: Optional[str] = None,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    WebSearch - Search the web for information

    使用搜索引擎查找最新信息、文档、教程等。

    使用场景:
    - 查找API文档
    - 搜索错误解决方案
    - 获取最新框架版本
    - 查找代码示例

    Args:
        query: 搜索查询
        num_results: 返回结果数量 (默认 5, 最大 10)
        time_range: 时间范围 ("day", "week", "month", "year", None)
        allowed_domains: 允许的域名列表 (可选)
        blocked_domains: 屏蔽的域名列表 (可选)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with search results
    """
    # Validate query
    if not query or len(query.strip()) < 3:
        return ToolResult(
            success=False,
            result="Query is too short. Provide at least 3 characters."
        )

    # Limit results
    num_results = min(num_results, 10)

    # Create action for backend to handle
    action = {
        "type": "web_search",
        "payload": {
            "query": query,
            "num_results": num_results,
            "time_range": time_range,
            "allowed_domains": allowed_domains or [],
            "blocked_domains": blocked_domains or [],
        }
    }

    return ToolResult(
        success=True,
        result=f"Searching for: {query} (top {num_results} results)...",
        action=action
    )


# ============================================
# Synchronous Fetch Helper (for immediate use)
# ============================================

async def _fetch_url_async(url: str, timeout: int = 30) -> tuple[bool, str]:
    """
    异步抓取URL内容

    Args:
        url: URL to fetch
        timeout: Timeout in seconds

    Returns:
        (success, content) tuple
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Handle different content types
            if "text/html" in content_type:
                # For HTML, try to extract text
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)

                return True, text

            elif "application/json" in content_type:
                # For JSON, return formatted
                import json
                try:
                    data = response.json()
                    return True, json.dumps(data, indent=2)
                except:
                    return True, response.text

            else:
                # For other types, return raw text
                return True, response.text

    except Exception as e:
        return False, f"Error fetching URL: {str(e)}"


def fetch_url_sync(url: str, timeout: int = 30) -> ToolResult:
    """
    同步抓取URL (用于简单的内容获取,不使用AI分析)

    Args:
        url: URL to fetch
        timeout: Timeout in seconds

    Returns:
        ToolResult with content
    """
    # Run async function in sync context
    try:
        success, content = asyncio.run(_fetch_url_async(url, timeout))

        if success:
            # Limit content length
            if len(content) > 50000:
                content = content[:50000] + "\n\n... (content truncated)"

            return ToolResult(
                success=True,
                result=f"Content from {url}:\n\n{content}"
            )
        else:
            return ToolResult(
                success=False,
                result=content
            )

    except Exception as e:
        return ToolResult(
            success=False,
            result=f"Error: {str(e)}"
        )


# ============================================
# Tool Definitions
# ============================================

def get_network_tool_definitions() -> List[dict]:
    """
    获取网络工具定义

    Returns:
        List of tool definitions in Claude API format
    """
    return [
        {
            "name": "web_fetch",
            "description": """Fetch and analyze web content using AI.

This tool:
1. Fetches content from the URL
2. Converts HTML to readable format (Markdown)
3. Uses AI to extract information based on your prompt
4. Returns structured results

Use cases:
- Get API documentation: web_fetch(url="https://api.example.com/docs", prompt="Extract authentication methods")
- Find code examples: web_fetch(url="https://github.com/...", prompt="Get usage examples")
- Extract tutorial steps: web_fetch(url="https://tutorial.com/...", prompt="List the main steps")
- Get error solutions: web_fetch(url="https://stackoverflow.com/...", prompt="Summarize the accepted answer")

IMPORTANT:
- URL must be complete (start with http:// or https://)
- HTTP URLs are auto-upgraded to HTTPS
- Prompt should clearly describe what to extract
- Results may be summarized if content is large

Examples:
- web_fetch(url="https://react.dev/learn", prompt="What are React Hooks?")
- web_fetch(url="https://api.github.com", prompt="List available API endpoints")""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",
                        "description": "Complete URL to fetch (must start with http:// or https://)"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "What information to extract from the page"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30, max 60)"
                    },
                    "max_content_length": {
                        "type": "integer",
                        "description": "Maximum content length to fetch (default 50000)"
                    }
                },
                "required": ["url", "prompt"]
            }
        },
        {
            "name": "web_search",
            "description": """Search the web for information.

Returns search results with titles, URLs, and descriptions.

Use cases:
- Find documentation: web_search(query="React hooks documentation 2025")
- Search for errors: web_search(query="TypeError Cannot read property of undefined")
- Find examples: web_search(query="Next.js API routes example")
- Get latest info: web_search(query="latest Node.js version", time_range="week")

Features:
- Filter by time range (day, week, month, year)
- Allow/block specific domains
- Up to 10 results per search

IMPORTANT:
- Use current year (2025) in queries for latest info
- Be specific in queries for better results
- Results include clickable URLs

CRITICAL REQUIREMENT:
After answering with search results, you MUST include a "Sources:" section listing all URLs as markdown links.

Example response format:
[Your answer based on search results]

Sources:
- [Title 1](URL1)
- [Title 2](URL2)

Examples:
- web_search(query="Python async await tutorial")
- web_search(query="FastAPI authentication", allowed_domains=["fastapi.tiangolo.com"])
- web_search(query="React performance", time_range="month")""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (minimum 3 characters)"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10)"
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["day", "week", "month", "year"],
                        "description": "Filter results by time range (optional)"
                    },
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only return results from these domains (optional)"
                    },
                    "blocked_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Never return results from these domains (optional)"
                    }
                },
                "required": ["query"]
            }
        }
    ]


# ============================================
# Tool Registry
# ============================================

NETWORK_TOOLS = {
    "web_fetch": web_fetch,
    "web_search": web_search,
}


def get_network_tools():
    """Get all network tools"""
    return NETWORK_TOOLS
