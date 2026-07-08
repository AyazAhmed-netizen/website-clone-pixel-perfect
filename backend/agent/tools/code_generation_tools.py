"""
Code Generation Tools for Nexting Agent

Provides advanced tools for generating React components from JSON data and extracting design tokens.
These tools help the Agent create high-quality, data-driven code instead of hardcoded placeholders.

Tools:
1. generate_component_from_json() - Generate React component code from JSON data
2. extract_design_tokens() - Extract design tokens (colors, fonts, spacing) from styles

NOTE: This version uses memory cache instead of Supabase for open-source deployment.
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
import os
import logging
import json

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


# ============================================
# Helper Functions
# ============================================

def analyze_data_structure(data: Any) -> Dict[str, Any]:
    """
    Analyze the structure of data to understand how to generate code.

    Returns:
        Dict with analysis including:
        - data_type: "array" | "object" | "primitive"
        - item_schema: schema of array items (if array)
        - fields: list of field names (if object/array of objects)
        - suggested_component: suggested component type
    """
    if data is None:
        return {
            "data_type": "null",
            "suggested_component": "EmptyState",
        }

    if isinstance(data, list):
        if not data:
            return {
                "data_type": "array",
                "item_count": 0,
                "suggested_component": "EmptyList",
            }

        # Analyze first few items to understand structure
        sample = data[:5]
        item_type = type(sample[0]).__name__

        if isinstance(sample[0], dict):
            # Extract common fields from sample items
            all_fields = set()
            for item in sample:
                if isinstance(item, dict):
                    all_fields.update(item.keys())

            return {
                "data_type": "array",
                "item_type": "object",
                "item_count": len(data),
                "fields": sorted(list(all_fields)),
                "suggested_component": "ListComponent",
                "sample_item": sample[0],
            }
        else:
            return {
                "data_type": "array",
                "item_type": item_type,
                "item_count": len(data),
                "suggested_component": "SimpleList",
            }

    elif isinstance(data, dict):
        return {
            "data_type": "object",
            "fields": list(data.keys()),
            "suggested_component": "ObjectDisplay",
        }

    else:
        return {
            "data_type": type(data).__name__,
            "suggested_component": "ValueDisplay",
        }


def generate_react_component_code(
    component_name: str,
    data: Any,
    analysis: Dict[str, Any],
    use_typescript: bool = True
) -> str:
    """
    Generate React component code based on data structure analysis.

    Args:
        component_name: Name of the component to generate
        data: The actual data to use
        analysis: Result from analyze_data_structure()
        use_typescript: Whether to generate TypeScript code

    Returns:
        Generated React component code as string
    """
    data_type = analysis.get("data_type")
    suggested_component = analysis.get("suggested_component")

    # Generate appropriate component based on data structure
    if data_type == "array" and analysis.get("item_type") == "object":
        return _generate_list_component(component_name, data, analysis, use_typescript)
    elif data_type == "object":
        return _generate_object_component(component_name, data, analysis, use_typescript)
    elif data_type == "array":
        return _generate_simple_list_component(component_name, data, analysis, use_typescript)
    else:
        return _generate_value_component(component_name, data, use_typescript)


def _generate_list_component(
    name: str,
    data: List[dict],
    analysis: Dict[str, Any],
    use_typescript: bool
) -> str:
    """Generate a list component with cards/items"""

    fields = analysis.get("fields", [])
    item_count = analysis.get("item_count", 0)
    sample_item = analysis.get("sample_item", {})

    # Detect likely field purposes (title, description, image, etc.)
    # Extended patterns for better detection
    title_field = _detect_field(fields, ["title", "name", "heading", "label", "header", "caption"])
    desc_field = _detect_field(fields, ["description", "desc", "content", "text", "body", "summary", "detail", "intro"])
    image_field = _detect_field(fields, ["image", "img", "icon", "avatar", "thumbnail", "picture", "photo", "logo", "src"])
    link_field = _detect_field(fields, ["link", "url", "href", "path", "to", "uri"])
    date_field = _detect_field(fields, ["date", "time", "created", "updated", "timestamp", "published"])

    # Build interface/type
    type_def = ""
    if use_typescript:
        type_def = f"""interface {name}Item {{\n"""
        for field in fields[:10]:  # Limit to first 10 fields
            sample_value = sample_item.get(field)
            ts_type = _infer_typescript_type(sample_value)
            type_def += f"  {field}: {ts_type};\n"
        type_def += "}\n\n"

    # Generate component code
    ext = "tsx" if use_typescript else "jsx"
    props_type = f": {{ items: {name}Item[] }}" if use_typescript else ""

    code = f"""import React from 'react';

{type_def}/**
 * {name} Component
 *
 * Displays a list of {item_count} items with the following fields:
 * {', '.join(fields[:8])}
 */
export function {name}({props_type}) {{
  const items{': ' + name + 'Item[]' if use_typescript else ''} = [
"""

    # Add actual data (limit to prevent huge output)
    for i, item in enumerate(data[:50]):  # Limit to 50 items
        code += "    " + json.dumps(item, ensure_ascii=False) + ",\n"

    if len(data) > 50:
        code += f"    // ... and {len(data) - 50} more items\n"

    code += "  ];\n\n"

    # Generate render code
    code += "  return (\n"
    code += "    <div className=\"grid gap-6 md:grid-cols-2 lg:grid-cols-3\">\n"
    code += "      {items.map((item, index) => (\n"
    code += "        <div\n"
    code += "          key={index}\n"
    code += "          className=\"rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-shadow\"\n"
    code += "        >\n"

    # Add image if detected
    if image_field and sample_item.get(image_field):
        code += f"          {{item.{image_field} && (\n"
        code += f"            <img\n"
        code += f"              src={{item.{image_field}}}\n"
        code += f"              alt={{item.{title_field or 'title'}}}\n"
        code += f"              className=\"w-full h-48 object-cover rounded-lg mb-4\"\n"
        code += f"            />\n"
        code += f"          )}}\n"

    # Add title if detected (with optional link)
    if title_field:
        if link_field and sample_item.get(link_field):
            # Title with link
            code += f"          <h3 className=\"text-xl font-semibold mb-2 text-gray-900 dark:text-white\">\n"
            code += f"            {{item.{link_field} ? (\n"
            code += f"              <a href={{item.{link_field}}} className=\"hover:text-blue-600 dark:hover:text-blue-400 transition-colors\">\n"
            code += f"                {{item.{title_field}}}\n"
            code += f"              </a>\n"
            code += f"            ) : (\n"
            code += f"              item.{title_field}\n"
            code += f"            )}}\n"
            code += f"          </h3>\n"
        else:
            # Title without link
            code += f"          <h3 className=\"text-xl font-semibold mb-2 text-gray-900 dark:text-white\">\n"
            code += f"            {{item.{title_field}}}\n"
            code += f"          </h3>\n"

    # Add description if detected
    if desc_field:
        code += f"          <p className=\"text-gray-600 dark:text-gray-300 mb-4\">\n"
        code += f"            {{item.{desc_field}}}\n"
        code += f"          </p>\n"

    # Add date if detected
    if date_field:
        code += f"          <p className=\"text-sm text-gray-500 dark:text-gray-400\">\n"
        code += f"            {{item.{date_field}}}\n"
        code += f"          </p>\n"

    code += "        </div>\n"
    code += "      ))}\n"
    code += "    </div>\n"
    code += "  );\n"
    code += "}\n"

    return code


def _generate_object_component(
    name: str,
    data: dict,
    analysis: Dict[str, Any],
    use_typescript: bool
) -> str:
    """Generate a component to display object data"""

    fields = analysis.get("fields", [])
    ext = "tsx" if use_typescript else "jsx"

    code = f"""import React from 'react';

/**
 * {name} Component
 *
 * Displays object data with {len(fields)} fields
 */
export function {name}() {{
  const data = {json.dumps(data, indent=2, ensure_ascii=False)};

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <dl className="space-y-4">
"""

    # Generate key-value pairs
    for field in fields[:20]:  # Limit to 20 fields
        value = data.get(field)
        code += f"        <div>\n"
        code += f"          <dt className=\"text-sm font-medium text-gray-500 dark:text-gray-400\">\n"
        code += f"            {field}\n"
        code += f"          </dt>\n"
        code += f"          <dd className=\"mt-1 text-base text-gray-900 dark:text-white\">\n"

        if isinstance(value, (str, int, float, bool)):
            code += f"            {{data.{field}}}\n"
        else:
            code += f"            {{JSON.stringify(data.{field})}}\n"

        code += f"          </dd>\n"
        code += f"        </div>\n"

    code += """      </dl>
    </div>
  );
}
"""

    return code


def _generate_simple_list_component(
    name: str,
    data: List,
    analysis: Dict[str, Any],
    use_typescript: bool
) -> str:
    """Generate a simple list component for primitive values"""

    item_type = analysis.get("item_type", "string")

    code = f"""import React from 'react';

/**
 * {name} Component
 */
export function {name}() {{
  const items = {json.dumps(data[:100], ensure_ascii=False)};

  return (
    <ul className="space-y-2">
      {{items.map((item, index) => (
        <li
          key={{index}}
          className="flex items-center gap-2 text-gray-700 dark:text-gray-300"
        >
          <span className="w-2 h-2 bg-blue-500 rounded-full" />
          {{item}}
        </li>
      ))}}
    </ul>
  );
}}
"""

    return code


def _generate_value_component(name: str, data: Any, use_typescript: bool) -> str:
    """Generate a component to display a single value"""

    code = f"""import React from 'react';

/**
 * {name} Component
 */
export function {name}() {{
  const value = {json.dumps(data, ensure_ascii=False)};

  return (
    <div className="text-lg text-gray-900 dark:text-white">
      {{value}}
    </div>
  );
}}
"""

    return code


def _detect_field(fields: List[str], patterns: List[str]) -> Optional[str]:
    """
    Detect a field that matches common patterns.

    Prioritizes exact matches, then partial matches.
    """
    # First pass: exact match (case insensitive)
    for field in fields:
        field_lower = field.lower()
        for pattern in patterns:
            if field_lower == pattern:
                return field

    # Second pass: partial match (case insensitive)
    for field in fields:
        field_lower = field.lower()
        for pattern in patterns:
            if pattern in field_lower:
                return field

    return None


def _infer_typescript_type(value: Any) -> str:
    """Infer TypeScript type from a value"""
    if value is None:
        return "string | null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "number"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        if value:
            item_type = _infer_typescript_type(value[0])
            return f"{item_type}[]"
        return "any[]"
    elif isinstance(value, dict):
        return "object"
    else:
        return "any"


def extract_design_tokens_from_style_summary(style_summary: dict) -> Dict[str, Any]:
    """
    Extract design tokens from style_summary section of JSON.

    Returns:
        Dict with:
        - colors: color palette
        - typography: font families and sizes
        - spacing: spacing scale
        - tailwind_config: generated Tailwind config
        - css_variables: CSS custom properties
    """
    tokens = {
        "colors": {},
        "typography": {},
        "spacing": {},
        "tailwind_config": {},
        "css_variables": {}
    }

    # Extract colors
    colors = style_summary.get("colors", {})
    if colors:
        # Primary colors
        primary_colors = colors.get("by_frequency", [])[:5] if isinstance(colors.get("by_frequency"), list) else []
        if primary_colors:
            tokens["colors"]["primary"] = primary_colors[0] if primary_colors else "#3b82f6"
            if len(primary_colors) > 1:
                tokens["colors"]["secondary"] = primary_colors[1]
            if len(primary_colors) > 2:
                tokens["colors"]["accent"] = primary_colors[2]

        # Background colors
        bg_colors = colors.get("backgrounds", [])
        if bg_colors:
            tokens["colors"]["background"] = bg_colors[0] if isinstance(bg_colors, list) else bg_colors

        # Text colors
        text_colors = colors.get("text", [])
        if text_colors:
            tokens["colors"]["foreground"] = text_colors[0] if isinstance(text_colors, list) else text_colors

    # Extract typography
    fonts = style_summary.get("fonts", {})
    if fonts:
        font_families = fonts.get("families", [])
        if font_families:
            tokens["typography"]["fontFamily"] = {
                "sans": font_families[0] if isinstance(font_families, list) else font_families,
            }

        font_sizes = fonts.get("sizes", [])
        if font_sizes:
            tokens["typography"]["fontSize"] = {}
            size_mapping = {
                "xs": "0.75rem",
                "sm": "0.875rem",
                "base": "1rem",
                "lg": "1.125rem",
                "xl": "1.25rem",
                "2xl": "1.5rem",
                "3xl": "1.875rem",
                "4xl": "2.25rem",
            }
            # Map extracted sizes to Tailwind sizes
            for i, size in enumerate(font_sizes[:8]):
                if isinstance(size, (int, float)):
                    size = f"{size}px"
                size_name = list(size_mapping.keys())[i] if i < len(size_mapping) else f"custom-{i}"
                tokens["typography"]["fontSize"][size_name] = size

    # Extract spacing
    spacing = style_summary.get("spacing", {})
    if spacing:
        margins = spacing.get("margins", [])
        paddings = spacing.get("paddings", [])

        all_spacing = set()
        if isinstance(margins, list):
            all_spacing.update(margins)
        if isinstance(paddings, list):
            all_spacing.update(paddings)

        if all_spacing:
            sorted_spacing = sorted([s for s in all_spacing if isinstance(s, (int, float))])[:10]
            tokens["spacing"] = {
                str(i): f"{val}px" for i, val in enumerate(sorted_spacing)
            }

    # Generate Tailwind config
    tailwind_config = {
        "theme": {
            "extend": {}
        }
    }

    if tokens["colors"]:
        tailwind_config["theme"]["extend"]["colors"] = tokens["colors"]

    if tokens["typography"]:
        if "fontFamily" in tokens["typography"]:
            tailwind_config["theme"]["extend"]["fontFamily"] = tokens["typography"]["fontFamily"]
        if "fontSize" in tokens["typography"]:
            tailwind_config["theme"]["extend"]["fontSize"] = tokens["typography"]["fontSize"]

    if tokens["spacing"]:
        tailwind_config["theme"]["extend"]["spacing"] = tokens["spacing"]

    tokens["tailwind_config"] = tailwind_config

    # Generate CSS variables
    css_vars = []
    if tokens["colors"]:
        css_vars.append("/* Color Variables */")
        for name, value in tokens["colors"].items():
            css_vars.append(f"--color-{name}: {value};")

    if tokens["typography"].get("fontFamily"):
        css_vars.append("\n/* Typography Variables */")
        for name, value in tokens["typography"]["fontFamily"].items():
            css_vars.append(f"--font-{name}: {value};")

    tokens["css_variables"] = "\n".join(css_vars)

    return tokens


# ============================================
# Code Generation Tools
# ============================================

def generate_component_from_json(
    source_id: str,
    jsonpath: str,
    component_name: str = "GeneratedComponent",
    use_typescript: bool = True,
    user_id: Optional[str] = None,
    selected_source_id: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Generate a React component from JSON data at the specified path.

    This tool intelligently analyzes the data structure and generates appropriate
    React component code with REAL data from the JSON, not hardcoded placeholders.

    **Use this instead of manually writing hardcoded data arrays!**

    Examples:
    - generate_component_from_json(source_id, "$.dom_tree.children", "HeroSection")
      → Generates a component that renders the hero section children

    - generate_component_from_json(source_id, "$.activities", "ActivityList")
      → Generates a list component displaying all activities with proper fields

    - generate_component_from_json(source_id, "$.metadata", "PageMetadata")
      → Generates a component displaying page metadata

    Args:
        source_id: The source ID from list_saved_sources()
        jsonpath: JSONPath to the data (e.g., "$.activities" or "$.dom_tree.children")
        component_name: Name for the generated component (default: "GeneratedComponent")
        use_typescript: Generate TypeScript code (default: True)
        user_id: User ID (ignored in open-source version)
        selected_source_id: If set, this source is pre-selected in UI

    Returns:
        ToolResult with generated React component code
    """
    if not source_id:
        return ToolResult(
            success=False,
            result="source_id is required. Use list_saved_sources() to get available IDs."
        )

    if not jsonpath:
        return ToolResult(
            success=False,
            result="jsonpath is required. Example: '$.activities' or '$.dom_tree.children'"
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
        page_title = item.get("page_title", "Untitled")

        # Query the data using JSONPath
        try:
            from jsonpath_ng import parse as jsonpath_parse
        except ImportError:
            return ToolResult(
                success=False,
                result="jsonpath_ng library not installed. Please install it: pip install jsonpath-ng"
            )

        expr = jsonpath_parse(jsonpath)
        matches = [match.value for match in expr.find(raw_json)]

        if not matches:
            return ToolResult(
                success=False,
                result=f"No data found at path: {jsonpath}\n\nUse get_source_overview('{source_id}') to see available paths."
            )

        # Use first match for component generation
        data = matches[0]

        # Analyze data structure
        analysis = analyze_data_structure(data)

        # Generate component code
        component_code = generate_react_component_code(
            component_name,
            data,
            analysis,
            use_typescript
        )

        # Build response
        ext = "tsx" if use_typescript else "jsx"
        lines = [
            f"## Generated Component: {component_name}.{ext}\n",
            f"**Source**: {page_title} ({source_url})",
            f"**Data Path**: {jsonpath}",
            f"**Data Type**: {analysis.get('data_type')}",
        ]

        if analysis.get("item_count"):
            lines.append(f"**Item Count**: {analysis['item_count']}")

        if analysis.get("fields"):
            lines.append(f"**Fields**: {', '.join(analysis['fields'][:10])}")

        lines.append(f"\n### Component Code\n")
        lines.append("```" + ("typescript" if use_typescript else "javascript"))
        lines.append(component_code)
        lines.append("```\n")

        lines.append("### Usage")
        lines.append("```tsx")
        lines.append(f"import {{ {component_name} }} from './{component_name}';")
        lines.append("")
        lines.append(f"<{component_name} />")
        lines.append("```\n")

        lines.append("---")
        lines.append(f"**Next Steps**:")
        lines.append(f"1. Use write_file() to save this component to `src/components/{component_name}.{ext}`")
        lines.append(f"2. Import and use it in your app")
        lines.append(f"3. Customize styles and layout as needed")

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        logger.error(f"generate_component_from_json error: {e}")
        return ToolResult(
            success=False,
            result=f"Component generation failed: {str(e)}"
        )


def extract_design_tokens(
    source_id: str,
    output_format: str = "tailwind",
    user_id: Optional[str] = None,
    selected_source_id: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Extract design tokens (colors, fonts, spacing) from a saved website source.

    This tool analyzes the style_summary section and generates a design system
    that you can use in your Tailwind config or CSS variables.

    **Use this to match the original website's look and feel!**

    Output formats:
    - "tailwind": Generate Tailwind config (default)
    - "css": Generate CSS custom properties
    - "both": Generate both Tailwind config and CSS variables

    Args:
        source_id: The source ID from list_saved_sources()
        output_format: Output format - "tailwind", "css", or "both" (default: "tailwind")
        user_id: User ID (injected by tool_node)
        selected_source_id: If set, this source is pre-selected in UI

    Returns:
        ToolResult with extracted design tokens
    """
    if not source_id:
        return ToolResult(
            success=False,
            result="source_id is required. Use list_saved_sources() to get available IDs."
        )

    if output_format not in ["tailwind", "css", "both"]:
        return ToolResult(
            success=False,
            result="output_format must be 'tailwind', 'css', or 'both'"
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
        page_title = item.get("page_title", "Untitled")

        # Get style_summary
        style_summary = raw_json.get("style_summary", {})
        if not style_summary:
            return ToolResult(
                success=False,
                result=f"No style_summary found in source. This source may not have style data extracted."
            )

        # Extract design tokens
        tokens = extract_design_tokens_from_style_summary(style_summary)

        # Build response
        lines = [
            f"## Design Tokens Extracted from: {page_title}\n",
            f"**Source**: {source_url}",
            f"**Source ID**: `{source_id}`\n",
        ]

        # Show color palette
        if tokens["colors"]:
            lines.append("### Color Palette\n")
            for name, value in tokens["colors"].items():
                lines.append(f"- **{name}**: `{value}`")
            lines.append("")

        # Show typography
        if tokens["typography"]:
            lines.append("### Typography\n")
            if "fontFamily" in tokens["typography"]:
                lines.append("**Font Families:**")
                for name, value in tokens["typography"]["fontFamily"].items():
                    lines.append(f"- **{name}**: `{value}`")
            if "fontSize" in tokens["typography"]:
                lines.append("\n**Font Sizes:**")
                for name, value in list(tokens["typography"]["fontSize"].items())[:8]:
                    lines.append(f"- **{name}**: `{value}`")
            lines.append("")

        # Show spacing
        if tokens["spacing"]:
            lines.append("### Spacing Scale\n")
            for name, value in list(tokens["spacing"].items())[:8]:
                lines.append(f"- **{name}**: `{value}`")
            lines.append("")

        # Output Tailwind config
        if output_format in ["tailwind", "both"]:
            lines.append("### Tailwind Config\n")
            lines.append("Add this to your `tailwind.config.js` or `tailwind.config.ts`:\n")
            lines.append("```javascript")
            lines.append(json.dumps(tokens["tailwind_config"], indent=2))
            lines.append("```\n")

        # Output CSS variables
        if output_format in ["css", "both"]:
            lines.append("### CSS Variables\n")
            lines.append("Add this to your global CSS file:\n")
            lines.append("```css")
            lines.append(":root {")
            lines.append("  " + tokens["css_variables"].replace("\n", "\n  "))
            lines.append("}")
            lines.append("```\n")

        lines.append("---")
        lines.append("**Next Steps**:")
        lines.append("1. Copy the config/variables above to your project")
        lines.append("2. Use these tokens in your components (e.g., `text-primary`, `bg-secondary`)")
        lines.append("3. Adjust values as needed to match your design exactly")

        return ToolResult(
            success=True,
            result="\n".join(lines)
        )

    except Exception as e:
        logger.error(f"extract_design_tokens error: {e}")
        return ToolResult(
            success=False,
            result=f"Design token extraction failed: {str(e)}"
        )


# ============================================
# Tool Registry
# ============================================

CODE_GENERATION_TOOLS = {
    "generate_component_from_json": generate_component_from_json,
    "extract_design_tokens": extract_design_tokens,
}


def get_code_generation_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for code generation tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "generate_component_from_json",
            "description": """Generate a React component from JSON data.

**CRITICAL**: Use this tool to generate components with REAL data from the JSON instead
of writing hardcoded placeholder arrays!

This tool:
1. Queries the specified JSON path
2. Analyzes the data structure (array, object, fields, types)
3. Generates appropriate React/TypeScript code with the actual data
4. Handles lists, objects, and primitive values intelligently

**When to use:**
- After querying JSON data and deciding to create a component
- When you need to display a list of items (activities, products, posts, etc.)
- When building any UI that should use real extracted data

**Example workflow:**
1. query_source_json(source_id, "$.activities") → see the data
2. generate_component_from_json(source_id, "$.activities", "ActivityList") → get component code
3. write_file("src/components/ActivityList.tsx", component_code) → save it

The generated code will include:
- TypeScript interfaces (if enabled)
- Proper data mapping and rendering
- Responsive Tailwind CSS classes
- Real data embedded in the component""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "The source ID from list_saved_sources()"
                    },
                    "jsonpath": {
                        "type": "string",
                        "description": "JSONPath to the data (e.g., '$.activities' or '$.dom_tree.children')"
                    },
                    "component_name": {
                        "type": "string",
                        "description": "Name for the component (e.g., 'ActivityList', 'HeroSection')",
                        "default": "GeneratedComponent"
                    },
                    "use_typescript": {
                        "type": "boolean",
                        "description": "Generate TypeScript code with types (default: true)",
                        "default": True
                    }
                },
                "required": ["source_id", "jsonpath"]
            }
        },
        {
            "name": "extract_design_tokens",
            "description": """Extract design tokens (colors, fonts, spacing) from a website source.

**CRITICAL**: Use this tool to extract the ACTUAL design system from the original website
instead of guessing colors and fonts!

This tool analyzes the style_summary section and generates:
- Color palette (primary, secondary, accent, background, text colors)
- Typography (font families, font size scale)
- Spacing scale (margins, paddings)
- Tailwind config ready to use
- CSS custom properties

**When to use:**
- At the start of cloning a website, before writing any CSS
- When you need to match the original website's look and feel
- Before creating components, to know what colors/fonts to use

**Example workflow:**
1. list_saved_sources() → get source_id
2. extract_design_tokens(source_id, "both") → get Tailwind config + CSS vars
3. write_file("tailwind.config.ts", tailwind_config) → save config
4. Use the extracted tokens in your components

Output formats:
- "tailwind": Generates Tailwind config object (default)
- "css": Generates CSS custom properties
- "both": Generates both Tailwind config and CSS variables""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "The source ID from list_saved_sources()"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["tailwind", "css", "both"],
                        "description": "Output format: 'tailwind', 'css', or 'both' (default: 'tailwind')",
                        "default": "tailwind"
                    }
                },
                "required": ["source_id"]
            }
        }
    ]
