"""
Section Analyzer
区块分析器

Analyzes HTML content to identify page sections.
"""

from typing import Dict, Any, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


def analyze_sections(
    raw_html: str,
    dom_tree: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Analyze HTML content to identify page sections.

    Args:
        raw_html: Raw HTML content
        dom_tree: Optional DOM tree for additional context

    Returns:
        Dict with:
        - type: Layout type (single-page, multi-section, etc.)
        - sections: List of identified sections
    """
    if not raw_html and not dom_tree:
        return {
            "type": "empty",
            "sections": [],
        }

    sections = []

    # If we have DOM tree, use it primarily
    if dom_tree:
        sections = _extract_sections_from_dom(dom_tree)
    else:
        # Fallback to HTML parsing
        sections = _extract_sections_from_html(raw_html)

    # Determine layout type
    layout_type = "single-page"
    if len(sections) > 5:
        layout_type = "multi-section"
    elif len(sections) <= 2:
        layout_type = "simple"

    return {
        "type": layout_type,
        "sections": sections,
    }


def _extract_sections_from_dom(dom_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract sections from DOM tree."""
    sections = []

    # Get direct children of body/root
    children = dom_tree.get("children", [])

    for i, child in enumerate(children):
        tag = child.get("tag", "div").lower()
        class_names = child.get("class", "")
        if isinstance(class_names, list):
            class_names = " ".join(class_names)

        # Get bounds if available
        bounds = child.get("bounds", {})

        # Determine section name
        section_name = _generate_section_name(tag, class_names, i)

        # Get HTML snippet if available
        html_snippet = child.get("outerHTML", "")
        if not html_snippet:
            # Try to reconstruct basic tag
            html_snippet = f"<{tag} class=\"{class_names}\">...</{tag}>"

        section = {
            "section_name": section_name,
            "tag": tag,
            "class": class_names,
            "index": i,
            "bounds": {
                "x": bounds.get("x", 0),
                "y": bounds.get("y", 0),
                "width": bounds.get("width", 0),
                "height": bounds.get("height", 0),
            },
            "html_snippet": html_snippet[:500] if len(html_snippet) > 500 else html_snippet,
            "element_count": _count_children(child),
        }

        # Try to extract text content summary
        text_content = child.get("textContent", "")
        if text_content:
            section["text_preview"] = text_content[:200] + "..." if len(text_content) > 200 else text_content

        sections.append(section)

    return sections


def _extract_sections_from_html(raw_html: str) -> List[Dict[str, Any]]:
    """Extract sections from raw HTML using regex patterns."""
    sections = []

    # Pattern to match common section tags
    section_pattern = r'<(header|footer|nav|main|section|article|aside|div)[^>]*class=["\']([^"\']*)["\'][^>]*>'

    matches = re.finditer(section_pattern, raw_html, re.IGNORECASE)

    for i, match in enumerate(matches):
        tag = match.group(1)
        class_names = match.group(2)

        section_name = _generate_section_name(tag, class_names, i)

        sections.append({
            "section_name": section_name,
            "tag": tag,
            "class": class_names,
            "index": i,
            "html_snippet": match.group(0),
        })

        # Limit to prevent too many sections
        if i >= 20:
            break

    return sections


def _generate_section_name(tag: str, class_names: str, index: int) -> str:
    """Generate a meaningful section name."""
    tag_lower = tag.lower()
    class_lower = class_names.lower()

    # Check common patterns
    if tag_lower == "header" or "header" in class_lower:
        return "header"
    if tag_lower == "footer" or "footer" in class_lower:
        return "footer"
    if tag_lower == "nav" or "nav" in class_lower or "navigation" in class_lower:
        return "navigation"
    if "hero" in class_lower or "banner" in class_lower or "jumbotron" in class_lower:
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
    if "about" in class_lower:
        return "about"
    if "team" in class_lower:
        return "team"
    if "blog" in class_lower or "news" in class_lower:
        return "blog"
    if "gallery" in class_lower or "portfolio" in class_lower:
        return "gallery"

    # Default naming
    return f"section_{index}"


def _count_children(node: Dict[str, Any]) -> int:
    """Count total number of child elements."""
    count = 1
    for child in node.get("children", []):
        count += _count_children(child)
    return count
