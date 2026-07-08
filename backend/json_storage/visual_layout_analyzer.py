"""
Visual Layout Analyzer
视觉布局分析器

Analyzes DOM tree structure and generates visual representations.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def analyze_visual_layout(
    dom_tree: Dict[str, Any],
    page_width: int = 1920,
    page_height: int = 1080,
) -> Dict[str, Any]:
    """
    Analyze DOM tree and generate visual layout representation.

    Args:
        dom_tree: DOM tree structure from extraction
        page_width: Page width in pixels
        page_height: Page height in pixels

    Returns:
        Dict with layout analysis including:
        - ascii_layout: ASCII diagram of page structure
        - sections: List of identified sections
        - stats: Layout statistics
    """
    if not dom_tree:
        return {
            "ascii_layout": "No DOM tree available",
            "sections": [],
            "stats": {},
        }

    # Generate ASCII layout representation
    ascii_lines = []
    ascii_lines.append("+" + "-" * 60 + "+")
    ascii_lines.append("|" + " " * 20 + "PAGE LAYOUT" + " " * 29 + "|")
    ascii_lines.append("+" + "-" * 60 + "+")

    # Analyze children for main sections
    children = dom_tree.get("children", [])
    sections = []

    for i, child in enumerate(children[:10]):  # Limit to first 10 children
        tag = child.get("tag", "div")
        class_names = child.get("class", "")
        if isinstance(class_names, list):
            class_names = " ".join(class_names)

        # Determine section type based on tag and class
        section_type = _infer_section_type(tag, class_names, i, len(children))

        sections.append({
            "index": i,
            "tag": tag,
            "class": class_names,
            "type": section_type,
        })

        # Add to ASCII diagram
        section_label = f"{section_type.upper()}"
        padding = (58 - len(section_label)) // 2
        ascii_lines.append("|" + " " * padding + section_label + " " * (58 - padding - len(section_label)) + "|")
        ascii_lines.append("+" + "-" * 60 + "+")

    return {
        "ascii_layout": "\n".join(ascii_lines),
        "sections": sections,
        "stats": {
            "total_sections": len(sections),
            "page_width": page_width,
            "page_height": page_height,
        },
    }


def _infer_section_type(tag: str, class_names: str, index: int, total: int) -> str:
    """Infer section type from tag, class names, and position."""
    class_lower = class_names.lower()
    tag_lower = tag.lower()

    # Check common patterns
    if tag_lower == "header" or "header" in class_lower or "nav" in class_lower:
        return "header"
    if tag_lower == "footer" or "footer" in class_lower:
        return "footer"
    if tag_lower == "nav" or "navigation" in class_lower:
        return "navigation"
    if "hero" in class_lower or "banner" in class_lower:
        return "hero"
    if "feature" in class_lower:
        return "features"
    if "pricing" in class_lower:
        return "pricing"
    if "testimonial" in class_lower or "review" in class_lower:
        return "testimonials"
    if "faq" in class_lower:
        return "faq"
    if "contact" in class_lower:
        return "contact"
    if "cta" in class_lower or "call-to-action" in class_lower:
        return "cta"

    # Position-based inference
    if index == 0:
        return "header"
    if index == total - 1:
        return "footer"

    return f"section_{index}"


def generate_layout_prompt(layout: Dict[str, Any]) -> str:
    """Generate a prompt describing the layout for AI."""
    sections = layout.get("sections", [])

    lines = ["## Page Layout Structure", ""]

    for section in sections:
        lines.append(f"- **{section.get('type', 'section')}**: <{section.get('tag')}> with class=\"{section.get('class', '')}\"")

    return "\n".join(lines)


def generate_compact_layout_tree(
    dom_tree: Dict[str, Any],
    min_width: int = 50,
    min_height: int = 30,
    max_depth: int = 15,
    include_all_tags: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Generate a compact layout tree with essential information only.

    Args:
        dom_tree: Full DOM tree
        min_width: Minimum width to include element
        min_height: Minimum height to include element
        max_depth: Maximum tree depth
        include_all_tags: Whether to include all tags or just containers

    Returns:
        Compact layout tree
    """
    if not dom_tree:
        return None

    def process_node(node: Dict[str, Any], depth: int) -> Optional[Dict[str, Any]]:
        if depth > max_depth:
            return None

        tag = node.get("tag", "div")
        bounds = node.get("bounds", {})
        width = bounds.get("width", 0)
        height = bounds.get("height", 0)

        # Skip small elements unless we want all tags
        if not include_all_tags:
            if width < min_width or height < min_height:
                return None

            # Only include container-like tags
            container_tags = {"div", "section", "header", "footer", "nav", "main", "article", "aside"}
            if tag.lower() not in container_tags:
                return None

        # Build compact node
        compact = {
            "tag": tag,
            "class": node.get("class", ""),
            "bounds": {
                "x": bounds.get("x", 0),
                "y": bounds.get("y", 0),
                "w": width,
                "h": height,
            },
        }

        # Process children
        children = node.get("children", [])
        if children:
            compact_children = []
            for child in children:
                compact_child = process_node(child, depth + 1)
                if compact_child:
                    compact_children.append(compact_child)
            if compact_children:
                compact["children"] = compact_children

        return compact

    return process_node(dom_tree, 0)


def format_compact_layout_for_agent(
    compact_layout: Dict[str, Any],
    max_lines: int = 300,
) -> str:
    """
    Format compact layout tree as text for AI agent.

    Args:
        compact_layout: Compact layout tree
        max_lines: Maximum number of lines

    Returns:
        Formatted text representation
    """
    if not compact_layout:
        return "No layout available"

    lines = []

    def format_node(node: Dict[str, Any], indent: int = 0):
        if len(lines) >= max_lines:
            return

        prefix = "  " * indent
        tag = node.get("tag", "div")
        class_name = node.get("class", "")
        bounds = node.get("bounds", {})

        # Format class names
        if isinstance(class_name, list):
            class_name = " ".join(class_name)
        class_str = f".{class_name.replace(' ', '.')}" if class_name else ""

        # Format bounds
        w = bounds.get("w", 0)
        h = bounds.get("h", 0)
        bounds_str = f"[{w}x{h}]" if w and h else ""

        lines.append(f"{prefix}<{tag}{class_str}> {bounds_str}")

        # Process children
        children = node.get("children", [])
        for child in children:
            format_node(child, indent + 1)

    format_node(compact_layout)

    if len(lines) >= max_lines:
        lines.append("... (truncated)")

    return "\n".join(lines)


def get_layout_tree_stats(compact_layout: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get statistics about the compact layout tree.

    Args:
        compact_layout: Compact layout tree

    Returns:
        Statistics dict
    """
    if not compact_layout:
        return {
            "node_count": 0,
            "max_depth": 0,
            "json_size_kb": 0,
        }

    import json

    node_count = 0
    max_depth = 0

    def count_nodes(node: Dict[str, Any], depth: int):
        nonlocal node_count, max_depth
        node_count += 1
        max_depth = max(max_depth, depth)

        for child in node.get("children", []):
            count_nodes(child, depth + 1)

    count_nodes(compact_layout, 0)

    json_str = json.dumps(compact_layout, ensure_ascii=False)
    json_size_kb = len(json_str) / 1024

    return {
        "node_count": node_count,
        "max_depth": max_depth,
        "json_size_kb": round(json_size_kb, 2),
    }
