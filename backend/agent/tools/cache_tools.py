"""
Cache Tools for Agent
Agent 缓存工具

Provides tools for the Agent to query cached extraction data.
Replaces the Supabase JSON storage query tools.

Tools:
- list_cached_extractions: List all available cached extractions
- get_extraction_data: Get specific data from a cache entry
- get_component_html: Get HTML code for a specific component
"""

import json
import logging
from typing import Dict, Any, List, Optional

# Import the global cache instance
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from cache.memory_store import extraction_cache

logger = logging.getLogger(__name__)


# ============================================
# Tool Definitions
# ============================================

CACHE_TOOL_DEFINITIONS = [
    {
        "name": "list_cached_extractions",
        "description": """List all available cached web page extractions.
Returns a list of cached pages with their IDs, URLs, titles, and available data keys.
Use this to see what page data is available for code generation.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_extraction_data",
        "description": """Get specific data from a cached extraction.
Use this to retrieve page structure, styles, components, or other data needed for code generation.

Available data keys typically include:
- metadata: Page title, URL, dimensions
- dom_tree: Full DOM structure
- style_summary: Colors, fonts, spacing statistics
- css_data: CSS rules, variables, animations
- components: Identified page components/sections
- assets: Images, fonts, scripts
- tech_stack: Detected frameworks and libraries

You can request specific keys to reduce data size.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "cache_id": {
                    "type": "string",
                    "description": "The cache entry ID (get from list_cached_extractions)",
                },
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific data keys to retrieve. If not specified, returns all data (may be large).",
                },
            },
            "required": ["cache_id"],
        },
    },
    {
        "name": "get_component_html",
        "description": """Get the HTML code for a specific page component/section.
Use this to get the exact HTML for a header, footer, hero section, etc.
The component index is from the components list in the extraction data.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "cache_id": {
                    "type": "string",
                    "description": "The cache entry ID",
                },
                "component_index": {
                    "type": "integer",
                    "description": "Component index (0-based) from the components list",
                },
            },
            "required": ["cache_id", "component_index"],
        },
    },
    {
        "name": "get_page_styles",
        "description": """Get style information from a cached extraction.
Returns color palette, typography, spacing, and other design tokens.
Useful for matching the original page's visual design.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "cache_id": {
                    "type": "string",
                    "description": "The cache entry ID",
                },
            },
            "required": ["cache_id"],
        },
    },
]


# ============================================
# Tool Executors
# ============================================

async def execute_cache_tool(name: str, params: Dict[str, Any]) -> str:
    """
    Execute a cache tool
    执行缓存工具

    Args:
        name: Tool name
        params: Tool parameters

    Returns:
        Tool result as string
    """
    try:
        if name == "list_cached_extractions":
            return await _list_cached_extractions()

        elif name == "get_extraction_data":
            return await _get_extraction_data(
                cache_id=params.get("cache_id", ""),
                keys=params.get("keys"),
            )

        elif name == "get_component_html":
            return await _get_component_html(
                cache_id=params.get("cache_id", ""),
                component_index=params.get("component_index", 0),
            )

        elif name == "get_page_styles":
            return await _get_page_styles(
                cache_id=params.get("cache_id", ""),
            )

        else:
            return f"Error: Unknown cache tool: {name}"

    except Exception as e:
        logger.error(f"Cache tool error: {e}", exc_info=True)
        return f"Error executing {name}: {str(e)}"


async def _list_cached_extractions() -> str:
    """List all cached extractions"""
    entries = extraction_cache.list_all()

    if not entries:
        return "No cached extractions available. Use the Extractor to capture a web page first."

    lines = ["Available cached extractions:", ""]
    for e in entries:
        lines.append(f"ID: {e.id}")
        lines.append(f"  URL: {e.url}")
        lines.append(f"  Title: {e.title or 'Untitled'}")
        lines.append(f"  Created: {e.created_at}")
        lines.append(f"  Size: {e.size_bytes:,} bytes")
        lines.append(f"  Keys: {', '.join(e.to_summary()['top_keys'])}")
        lines.append("")

    return "\n".join(lines)


async def _get_extraction_data(
    cache_id: str,
    keys: Optional[List[str]] = None,
) -> str:
    """Get extraction data"""
    entry = extraction_cache.get(cache_id)

    if not entry:
        return f"Error: Cache entry '{cache_id}' not found or expired"

    data = entry.data
    if not data:
        return f"Error: Cache entry '{cache_id}' has no data"

    # Filter to requested keys if specified
    if keys:
        data = {k: data.get(k) for k in keys if k in data}
        if not data:
            available = list(entry.data.keys())
            return f"Error: None of the requested keys found. Available keys: {available}"

    # Serialize and truncate if too large
    try:
        result = json.dumps(data, indent=2, ensure_ascii=False)
        max_size = 50000  # 50KB limit for agent context

        if len(result) > max_size:
            result = result[:max_size] + "\n\n... [TRUNCATED - data too large. Request specific keys to get full data]"

        return result

    except Exception as e:
        return f"Error serializing data: {str(e)}"


async def _get_component_html(
    cache_id: str,
    component_index: int,
) -> str:
    """Get component HTML"""
    entry = extraction_cache.get(cache_id)

    if not entry:
        return f"Error: Cache entry '{cache_id}' not found or expired"

    components_data = entry.data.get("components", {})
    components = components_data.get("components", [])

    if not components:
        return f"Error: No components found in cache entry '{cache_id}'"

    if component_index < 0 or component_index >= len(components):
        return f"Error: Component index {component_index} out of range (0-{len(components)-1})"

    component = components[component_index]

    # Try to get HTML from various possible locations
    html = None

    # Check code_location
    code_loc = component.get("code_location", {})
    if code_loc:
        html = code_loc.get("full_html") or code_loc.get("raw_html")

    # Check raw_html directly
    if not html:
        html = component.get("raw_html")

    if not html:
        # Return component info instead
        return json.dumps({
            "component_name": component.get("name", f"Component {component_index}"),
            "component_type": component.get("type", "unknown"),
            "bounding_box": component.get("bounding_box"),
            "note": "No HTML content available for this component",
        }, indent=2)

    return html


async def _get_page_styles(cache_id: str) -> str:
    """Get page style information"""
    entry = extraction_cache.get(cache_id)

    if not entry:
        return f"Error: Cache entry '{cache_id}' not found or expired"

    data = entry.data
    styles = {}

    # Collect style information from various sources
    if "style_summary" in data:
        styles["style_summary"] = data["style_summary"]

    if "css_data" in data:
        css = data["css_data"]
        styles["css_variables"] = css.get("variables", [])[:50]  # Limit
        styles["color_palette"] = css.get("colors", [])[:20]
        styles["fonts"] = css.get("fonts", [])[:10]

    # Extract from metadata if available
    if "metadata" in data:
        meta = data["metadata"]
        if "computed_styles" in meta:
            styles["computed_styles"] = meta["computed_styles"]

    if not styles:
        return f"No style information found in cache entry '{cache_id}'"

    return json.dumps(styles, indent=2, ensure_ascii=False)


# ============================================
# Tool Registration Helper
# ============================================

def get_cache_tool_definitions() -> List[Dict[str, Any]]:
    """Get cache tool definitions for MCP registration"""
    return CACHE_TOOL_DEFINITIONS


def is_cache_tool(name: str) -> bool:
    """Check if a tool name is a cache tool"""
    return name in {t["name"] for t in CACHE_TOOL_DEFINITIONS}
