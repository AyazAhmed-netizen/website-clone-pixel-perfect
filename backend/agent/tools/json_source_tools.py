"""
JSON Source Tools for Nexting Agent

Provides tools for the Agent to query saved website JSON data from the cache.
These tools are read-only and belong to STATE_QUERY_TOOLS category.

Tools:
1. list_saved_sources() - List all saved website sources (summaries)
2. get_source_overview() - Get overview and available sections of a source
3. query_source_json() - Query specific data using JSONPath

NOTE: This version uses memory cache instead of Supabase for open-source deployment.
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
import os
import logging

# Memory cache for open-source version (replaces Supabase)
from cache.memory_store import extraction_cache

logger = logging.getLogger(__name__)


# ============================================
# Tool Result Type
# ============================================

@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    result: str
    action: Optional[dict] = None

    def to_content(self) -> str:
        """Convert to string content for LLM"""
        if self.success:
            return self.result
        return f"Error: {self.result}"


# ============================================
# Cache Helper Functions (replaces Supabase)
# ============================================

def get_source_from_cache(source_id: str) -> Optional[Dict[str, Any]]:
    """
    Get source data from memory cache (replaces Supabase query)

    Args:
        source_id: Cache entry ID

    Returns:
        Dict with raw_json, page_title, source_url or None if not found
    """
    entry = extraction_cache.get(source_id)
    if not entry:
        return None

    return {
        "id": entry.id,
        "raw_json": entry.data,
        "page_title": entry.title,
        "source_url": entry.url,
        "created_at": entry.created_at,
    }


def list_sources_from_cache(limit: int = 20) -> List[Dict[str, Any]]:
    """
    List all sources from memory cache (replaces Supabase query)

    Args:
        limit: Maximum number of results

    Returns:
        List of source data
    """
    entries = extraction_cache.list_all()
    return [
        {
            "id": entry.id,
            "source_url": entry.url,
            "page_title": entry.title,
            "raw_json": entry.data,
            "created_at": entry.created_at,
        }
        for entry in entries[:limit]
    ]


def get_top_level_keys(data: Any) -> List[str]:
    """Get top-level keys from a dict"""
    if isinstance(data, dict):
        return list(data.keys())
    return []


# ============================================
# JSON Source Query Tools
# ============================================

def list_saved_sources(
    user_id: Optional[str] = None,
    limit: int = 20,
    selected_source_id: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    List all saved website sources from memory cache.

    **IMPORTANT**: If a source is already selected in the UI (selected_source_id is set),
    this will return ONLY that source instead of listing all sources.

    Returns a summary list including:
    - Source ID (for use in other tools)
    - URL and page title
    - Extraction time
    - Top-level JSON structure preview

    Args:
        user_id: User ID (ignored in open-source version)
        limit: Maximum number of sources to return (default 20)
        selected_source_id: If set, only return this specific source

    Returns:
        ToolResult with list of saved sources (or single selected source)
    """
    try:
        # If a source is selected in UI, only return that one
        if selected_source_id:
            source_data = get_source_from_cache(selected_source_id)

            if not source_data:
                return ToolResult(
                    success=False,
                    result=f"Selected source not found: {selected_source_id}"
                )
            sources = [source_data]
        else:
            # No source selected - list all sources
            sources = list_sources_from_cache(limit=limit)

            if not sources:
                return ToolResult(
                    success=True,
                    result="No saved website sources found. Use the Extractor page to extract and save website data first."
                )

        # Format output
        if selected_source_id and len(sources) == 1:
            # Single selected source - show it's pre-selected
            item = sources[0]
            source_id = item["id"]
            url = item.get("source_url", "Unknown URL")
            title = item.get("page_title", "Untitled")
            created = item.get("created_at", "")[:10] if item.get("created_at") else ""
            raw_json = item.get("raw_json", {})
            top_keys = get_top_level_keys(raw_json)
            metadata = raw_json.get("metadata", {}) if isinstance(raw_json, dict) else {}
            element_count = metadata.get("total_elements", "N/A")

            lines = [f"## Currently Selected Source\n"]
            lines.append(f"### {title}")
            lines.append(f"- **ID**: `{source_id}`")
            lines.append(f"- **URL**: {url}")
            lines.append(f"- **Extracted**: {created}")
            lines.append(f"- **Elements**: {element_count}")
            lines.append(f"- **Available data**: {', '.join(top_keys[:8])}")
            lines.append("")
            lines.append("---")
            lines.append("**This source is currently selected in the UI.**")
            lines.append("You can directly use this source ID for queries without asking the user.")
            lines.append("")
            lines.append("Use `get_source_overview(source_id)` to see detailed structure.")
            lines.append("Use `query_source_json(source_id, jsonpath)` to query specific data.")
        else:
            # Multiple sources or no selection
            lines = [f"## Saved Website Sources ({len(sources)} found)\n"]

            for item in sources:
                source_id = item["id"]
                url = item.get("source_url", "Unknown URL")
                title = item.get("page_title", "Untitled")
                created = item.get("created_at", "")[:10] if item.get("created_at") else ""
                raw_json = item.get("raw_json", {})

                # Get structure preview
                top_keys = get_top_level_keys(raw_json)
                metadata = raw_json.get("metadata", {}) if isinstance(raw_json, dict) else {}
                element_count = metadata.get("total_elements", "N/A")

                lines.append(f"### {title}")
                lines.append(f"- **ID**: `{source_id}`")
                lines.append(f"- **URL**: {url}")
                lines.append(f"- **Extracted**: {created}")
                lines.append(f"- **Elements**: {element_count}")
                lines.append(f"- **Available data**: {', '.join(top_keys[:8])}")
                lines.append("")

            lines.append("---")
            lines.append("Use `get_source_overview(source_id)` to see detailed structure.")
            lines.append("Use `query_source_json(source_id, jsonpath)` to query specific data.")

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        logger.error(f"list_saved_sources error: {e}")
        return ToolResult(
            success=False,
            result=f"Failed to list sources: {str(e)}"
        )


def get_source_overview(
    source_id: str,
    user_id: Optional[str] = None,
    selected_source_id: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Get overview of a saved website source, including available data sections.

    This helps you understand what data is available before querying.
    Does NOT return the full JSON (use query_source_json for that).

    Args:
        source_id: The source ID from list_saved_sources()
        user_id: User ID (ignored in open-source version)
        selected_source_id: If set, this source is pre-selected in UI

    Returns:
        ToolResult with source overview and available sections
    """
    if not source_id:
        return ToolResult(
            success=False,
            result="source_id is required. Use list_saved_sources() to get available IDs."
        )

    try:
        # Get from memory cache
        item = get_source_from_cache(source_id)

        if not item:
            return ToolResult(
                success=False,
                result=f"Source not found: {source_id}. Use list_saved_sources() to see available sources."
            )

        raw_json = item.get("raw_json", {})

        # Build overview
        lines = [f"## Source Overview: {item.get('page_title', 'Untitled')}\n"]
        lines.append(f"- **ID**: `{item['id']}`")
        lines.append(f"- **URL**: {item.get('source_url')}")
        lines.append(f"- **Extracted**: {item.get('created_at', '')[:19]}")
        lines.append("")

        # Metadata section
        metadata = raw_json.get("metadata", {})
        if metadata:
            lines.append("### Page Metadata")
            lines.append(f"- Title: {metadata.get('title', 'N/A')}")
            lines.append(f"- Viewport: {metadata.get('viewport_width', 'N/A')}x{metadata.get('viewport_height', 'N/A')}")
            lines.append(f"- Page size: {metadata.get('page_width', 'N/A')}x{metadata.get('page_height', 'N/A')}")
            lines.append(f"- Total elements: {metadata.get('total_elements', 'N/A')}")
            lines.append(f"- Load time: {metadata.get('load_time_ms', 'N/A')}ms")
            lines.append("")

        # Available sections
        lines.append("### Available Data Sections")
        lines.append("Use `query_source_json(source_id, jsonpath)` to query these:\n")

        section_info = {
            "metadata": "Page metadata (title, viewport, dimensions)",
            "dom_tree": "DOM tree structure with element hierarchy",
            "style_summary": "Aggregated style statistics (colors, fonts, spacing)",
            "assets": "Images, scripts, stylesheets, fonts",
            "css_data": "CSS stylesheets, animations, variables",
            "layout_info": "Page layout structure",
            "forms": "Form elements and inputs",
            "links": "All links on the page",
            "semantic_structure": "Semantic HTML structure",
        }

        for key in get_top_level_keys(raw_json):
            value = raw_json.get(key)
            desc = section_info.get(key, "")

            if isinstance(value, dict):
                size = f"object ({len(value)} keys)"
                sub_keys = list(value.keys())[:5]
                if sub_keys:
                    size += f" - keys: {', '.join(sub_keys)}"
            elif isinstance(value, list):
                size = f"array ({len(value)} items)"
            elif isinstance(value, str):
                size = f"string ({len(value)} chars)"
            elif isinstance(value, bool):
                size = f"boolean: {value}"
            elif value is None:
                size = "null"
            else:
                size = type(value).__name__

            lines.append(f"- **$.{key}**: {size}")
            if desc:
                lines.append(f"  {desc}")

        lines.append("")
        lines.append("### Example JSONPath Queries")
        lines.append("```")
        lines.append("$.metadata.title                    # Page title")
        lines.append("$.style_summary.colors              # Color palette")
        lines.append("$.dom_tree.children[0]              # First child element")
        lines.append("$.assets.images[*].url              # All image URLs")
        lines.append("$.css_data.variables                # CSS custom properties")
        lines.append("```")

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        logger.error(f"get_source_overview error: {e}")
        return ToolResult(
            success=False,
            result=f"Failed to get source overview: {str(e)}"
        )


def query_source_json(
    source_id: str,
    jsonpath: str,
    user_id: Optional[str] = None,
    selected_source_id: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Query specific data from a saved website source using JSONPath.

    JSONPath Examples:
    - $.metadata.title           → Get page title
    - $.style_summary.colors     → Get color statistics
    - $.dom_tree.children[0]     → Get first child element
    - $.assets.images[*].url     → Get all image URLs
    - $.css_data.variables       → Get CSS custom properties

    Args:
        source_id: The source ID from list_saved_sources()
        jsonpath: JSONPath expression (e.g., "$.metadata.title")
        user_id: User ID (ignored in open-source version)
        selected_source_id: If set, this source is pre-selected in UI

    Returns:
        ToolResult with queried data
    """
    if not source_id:
        return ToolResult(
            success=False,
            result="source_id is required. Use list_saved_sources() to get available IDs."
        )

    if not jsonpath:
        return ToolResult(
            success=False,
            result="jsonpath is required. Example: '$.metadata.title' or '$.style_summary.colors'"
        )

    try:
        # Get from memory cache
        item = get_source_from_cache(source_id)

        if not item:
            return ToolResult(
                success=False,
                result=f"Source not found: {source_id}"
            )

        raw_json = item.get("raw_json", {})
        source_url = item.get("source_url", "")

        # Execute JSONPath query
        try:
            from jsonpath_ng import parse as jsonpath_parse
            from jsonpath_ng.exceptions import JsonPathParserError
        except ImportError:
            # Fallback: simple dot notation parsing
            return _simple_json_query(raw_json, jsonpath, source_url)

        try:
            expr = jsonpath_parse(jsonpath)
            matches = [match.value for match in expr.find(raw_json)]
        except JsonPathParserError as e:
            return ToolResult(
                success=False,
                result=f"Invalid JSONPath: {jsonpath}\nError: {str(e)}\n\nValid examples:\n- $.metadata.title\n- $.style_summary.colors\n- $.assets.images[*].url"
            )

        if not matches:
            return ToolResult(
                success=True,
                result=f"No matches found for path: {jsonpath}\n\nUse get_source_overview('{source_id}') to see available data sections."
            )

        # Format result
        lines = [f"## Query Result: {jsonpath}"]
        lines.append(f"Source: {source_url}\n")

        if len(matches) == 1:
            lines.append(_format_json_value(matches[0]))
        else:
            lines.append(f"Found {len(matches)} matches:\n")
            for i, match in enumerate(matches[:30], 1):  # Limit to 30 matches
                formatted = _format_json_value(match, max_length=300, indent=2)
                lines.append(f"{i}. {formatted}")

            if len(matches) > 30:
                lines.append(f"\n... and {len(matches) - 30} more matches")

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        logger.error(f"query_source_json error: {e}")
        return ToolResult(
            success=False,
            result=f"Query failed: {str(e)}"
        )


def _simple_json_query(data: dict, path: str, source_url: str = "") -> ToolResult:
    """
    Simple fallback JSON query without jsonpath_ng library.
    Supports basic dot notation: $.foo.bar[0].baz
    """
    try:
        # Remove leading $. if present
        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$"):
            path = path[1:]

        if not path:
            result = data
        else:
            result = data
            parts = path.replace("[", ".").replace("]", "").split(".")

            for part in parts:
                if not part:
                    continue
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list):
                    try:
                        idx = int(part)
                        result = result[idx]
                    except (ValueError, IndexError):
                        result = None
                else:
                    result = None

                if result is None:
                    break

        if result is None:
            return ToolResult(
                success=True,
                result=f"No data found at path: {path}"
            )

        lines = [f"## Query Result: $.{path}"]
        if source_url:
            lines.append(f"Source: {source_url}\n")
        lines.append(_format_json_value(result))

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        return ToolResult(
            success=False,
            result=f"Query failed: {str(e)}"
        )


def _format_json_value(value: Any, max_length: int = 1000, indent: int = 0) -> str:
    """Format a JSON value for readable output"""
    import json

    prefix = " " * indent

    if value is None:
        return f"{prefix}null"
    elif isinstance(value, bool):
        return f"{prefix}{str(value).lower()}"
    elif isinstance(value, (int, float)):
        return f"{prefix}{value}"
    elif isinstance(value, str):
        if len(value) > max_length:
            return f'{prefix}"{value[:max_length]}..." ({len(value)} chars total)'
        return f'{prefix}"{value}"'
    elif isinstance(value, list):
        try:
            text = json.dumps(value, indent=2, ensure_ascii=False)
            if len(text) > max_length:
                # Truncate but show structure
                preview = json.dumps(value[:3], indent=2, ensure_ascii=False) if len(value) > 3 else text
                return f"{prefix}[Array with {len(value)} items]\n{preview}\n{prefix}..."
            return text
        except:
            return f"{prefix}[Array with {len(value)} items]"
    elif isinstance(value, dict):
        try:
            text = json.dumps(value, indent=2, ensure_ascii=False)
            if len(text) > max_length:
                # Show keys and truncated preview
                keys = list(value.keys())
                return f"{prefix}[Object with {len(keys)} keys: {', '.join(keys[:10])}]\n{text[:max_length]}..."
            return text
        except:
            return f"{prefix}[Object with {len(value)} keys]"

    return f"{prefix}{str(value)}"


# ============================================
# Tool Registry
# ============================================

# All JSON source tools are read-only (STATE_QUERY_TOOLS)
JSON_SOURCE_TOOLS = {
    "list_saved_sources": list_saved_sources,
    "get_source_overview": get_source_overview,
    "query_source_json": query_source_json,
}


def get_json_source_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for JSON source tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "list_saved_sources",
            "description": """List saved website sources from the Playwright extraction.

**IMPORTANT**: If a source is already selected in the UI, this will return ONLY that source
instead of listing all sources. The response will indicate it's the currently selected source,
and you can use its ID directly without asking the user.

Use this tool to see what website data is available for reference when building UI components.
Returns a summary list with source IDs that can be used in other tools.

Each source contains extracted data from a webpage including:
- DOM structure and element hierarchy
- Style information (colors, fonts, spacing)
- Assets (images, scripts, stylesheets)
- CSS data (variables, animations)

Call this first to discover available sources, then use get_source_overview() or query_source_json() for details.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of sources to return (default 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_source_overview",
            "description": """Get an overview of a saved website source, showing available data sections.

Use this to understand what data is available in a source before querying specific parts.
Returns the structure of the JSON without the full data.

Shows:
- Page metadata (title, dimensions, element count)
- Available data sections (dom_tree, style_summary, assets, css_data, etc.)
- Example JSONPath queries

Use list_saved_sources() first to get the source_id.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "The source ID from list_saved_sources()"
                    }
                },
                "required": ["source_id"]
            }
        },
        {
            "name": "query_source_json",
            "description": """Query specific data from a saved website source using JSONPath.

Use this to extract specific information like colors, fonts, component styles, etc.

JSONPath Examples:
- $.metadata.title           → Page title
- $.metadata.viewport_width  → Viewport width
- $.style_summary.colors     → Color palette used on the page
- $.style_summary.font_sizes → Font sizes used
- $.dom_tree.children[0]     → First DOM child element
- $.assets.images[*].url     → All image URLs
- $.css_data.variables       → CSS custom properties (--variables)
- $.css_data.animations      → CSS animations defined

Use get_source_overview() first to see what data sections are available.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "The source ID from list_saved_sources()"
                    },
                    "jsonpath": {
                        "type": "string",
                        "description": "JSONPath expression (e.g., '$.style_summary.colors')"
                    }
                },
                "required": ["source_id", "jsonpath"]
            }
        }
    ]
