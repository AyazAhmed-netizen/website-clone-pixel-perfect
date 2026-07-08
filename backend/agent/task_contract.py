"""
Task Contract System

Defines the contract between Main Agent and Worker Agents for
strict task isolation and clear deliverables.

Features:
- File path isolation (namespace-based)
- Clear input/output specifications
- Acceptance criteria validation
- Integration plan generation
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# Enums and Types
# ============================================

class SectionType(str, Enum):
    """Section types for classification"""
    HEADER = "header"
    HERO = "hero"
    NAVIGATION = "navigation"
    FEATURES = "features"
    CONTENT = "content"
    TESTIMONIALS = "testimonials"
    GALLERY = "gallery"
    PRICING = "pricing"
    CTA = "cta"
    FOOTER = "footer"
    SIDEBAR = "sidebar"
    GENERIC = "section"


class ImageRole(str, Enum):
    """Role of image in section"""
    LOGO = "logo"
    ICON = "icon"
    PHOTO = "photo"
    AVATAR = "avatar"
    BACKGROUND = "background"
    DECORATION = "decoration"
    PRODUCT = "product"


class LinkType(str, Enum):
    """Type of link"""
    NAVIGATION = "navigation"
    SOCIAL = "social"
    CTA = "cta"
    INTERNAL = "internal"
    EXTERNAL = "external"
    ANCHOR = "anchor"


# ============================================
# Enhanced Section Data
# ============================================

@dataclass
class ImageData:
    """Enhanced image data with role and context"""
    url: str
    alt: str = ""
    role: ImageRole = ImageRole.PHOTO
    width: Optional[int] = None
    height: Optional[int] = None
    css_classes: List[str] = field(default_factory=list)
    parent_element: str = ""
    is_background: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "alt": self.alt,
            "role": self.role.value,
            "width": self.width,
            "height": self.height,
            "css_classes": self.css_classes,
            "parent_element": self.parent_element,
            "is_background": self.is_background,
        }


@dataclass
class LinkData:
    """Enhanced link data with type and context"""
    url: str
    text: str = ""
    link_type: LinkType = LinkType.INTERNAL
    position: str = ""  # left, center, right
    has_icon: bool = False
    icon_url: Optional[str] = None
    css_classes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "text": self.text,
            "type": self.link_type.value,
            "position": self.position,
            "has_icon": self.has_icon,
            "icon_url": self.icon_url,
            "css_classes": self.css_classes,
        }


@dataclass
class VisualProperties:
    """Visual layout properties"""
    rect: Dict[str, float] = field(default_factory=dict)  # x, y, width, height
    estimated_height: str = "auto"
    position_type: str = "relative"  # fixed, sticky, relative, absolute
    z_index: int = 0
    background_type: str = "solid"  # solid, gradient, image, transparent
    has_shadow: bool = False
    border_radius: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rect": self.rect,
            "estimated_height": self.estimated_height,
            "position_type": self.position_type,
            "z_index": self.z_index,
            "background_type": self.background_type,
            "has_shadow": self.has_shadow,
            "border_radius": self.border_radius,
        }


@dataclass
class StyleProperties:
    """Style properties extracted from section"""
    background_colors: List[str] = field(default_factory=list)
    text_colors: List[str] = field(default_factory=list)
    accent_colors: List[str] = field(default_factory=list)
    font_family: str = "inherit"
    heading_sizes: List[str] = field(default_factory=list)
    body_size: str = "16px"
    padding: str = "0"
    gap: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "colors": {
                "background": self.background_colors,
                "text": self.text_colors,
                "accent": self.accent_colors,
            },
            "typography": {
                "font_family": self.font_family,
                "heading_sizes": self.heading_sizes,
                "body_size": self.body_size,
            },
            "spacing": {
                "padding": self.padding,
                "gap": self.gap,
            },
        }


@dataclass
class TextContent:
    """Text content extracted from section"""
    headings: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    button_labels: List[str] = field(default_factory=list)
    nav_items: List[str] = field(default_factory=list)
    list_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headings": self.headings,
            "paragraphs": self.paragraphs,
            "button_labels": self.button_labels,
            "nav_items": self.nav_items,
            "list_items": self.list_items,
        }


@dataclass
class LayoutProperties:
    """Layout structure properties"""
    flex_direction: str = "column"
    justify_content: str = "flex-start"
    align_items: str = "stretch"
    child_count: int = 0
    has_container: bool = True
    container_max_width: str = "1200px"
    display: str = "flex"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flex_direction": self.flex_direction,
            "justify_content": self.justify_content,
            "align_items": self.align_items,
            "child_count": self.child_count,
            "has_container": self.has_container,
            "container_max_width": self.container_max_width,
            "display": self.display,
        }


@dataclass
class EnhancedSectionData:
    """Complete enhanced section data for Worker"""
    # Identity
    section_id: str
    section_type: SectionType
    display_name: str

    # Visual
    visual: VisualProperties = field(default_factory=VisualProperties)

    # Content
    images: List[ImageData] = field(default_factory=list)
    links: List[LinkData] = field(default_factory=list)
    text_content: TextContent = field(default_factory=TextContent)

    # Style
    styles: StyleProperties = field(default_factory=StyleProperties)

    # Layout
    layout: LayoutProperties = field(default_factory=LayoutProperties)

    # Raw reference
    raw_html: str = ""

    # CSS 规则 - 组件使用的所有 CSS 类定义
    css_rules: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_type": self.section_type.value,
            "display_name": self.display_name,
            "visual": self.visual.to_dict(),
            "images": [img.to_dict() for img in self.images],
            "links": [link.to_dict() for link in self.links],
            "text_content": self.text_content.to_dict(),
            "styles": self.styles.to_dict(),
            "layout": self.layout.to_dict(),
            "raw_html": self.raw_html,
            "css_rules": self.css_rules,
        }


# ============================================
# Task Contract
# ============================================

@dataclass
class FileDeliverable:
    """Required file deliverable"""
    path: str  # Relative path within namespace
    file_type: str  # "component", "styles", "utils"
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "type": self.file_type,
            "required": self.required,
        }


@dataclass
class AcceptanceCriteria:
    """Acceptance criteria for task completion"""
    min_images: int = 0
    min_links: int = 0
    required_colors: List[str] = field(default_factory=list)
    required_exports: List[str] = field(default_factory=list)
    layout_constraints: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_images": self.min_images,
            "min_links": self.min_links,
            "required_colors": self.required_colors,
            "required_exports": self.required_exports,
            "layout_constraints": self.layout_constraints,
        }

    def validate(self, result: Dict[str, Any]) -> List[str]:
        """Validate result against criteria, return warnings"""
        warnings = []

        # Check image count (from code analysis)
        # This is a simple heuristic - count img tags or image URLs in code
        files_content = "".join(result.get("files", {}).values())

        image_count = files_content.count('src="http') + files_content.count("src='http")
        if image_count < self.min_images:
            warnings.append(f"Expected {self.min_images} images, found ~{image_count}")

        link_count = files_content.count('href="') + files_content.count("href='")
        if link_count < self.min_links:
            warnings.append(f"Expected {self.min_links} links, found ~{link_count}")

        # Check required exports
        for export_name in self.required_exports:
            if f"export default {export_name}" not in files_content and \
               f"export {{ {export_name}" not in files_content and \
               f"export function {export_name}" not in files_content:
                warnings.append(f"Missing required export: {export_name}")

        return warnings


@dataclass
class TaskContract:
    """
    Complete task contract for Worker Agent

    Defines:
    - Identity and namespace (file isolation)
    - Scope (allowed/forbidden paths)
    - Input data
    - Required deliverables
    - Acceptance criteria
    """
    # Identity
    contract_id: str
    worker_namespace: str  # e.g., "header", "hero", "footer"
    priority: int = 1

    # Scope - File isolation
    base_path: str = "/src/components/sections"
    allowed_extensions: List[str] = field(default_factory=lambda: [".jsx", ".css", ".js"])
    forbidden_paths: List[str] = field(default_factory=lambda: [
        "/src/App.jsx",
        "/src/main.jsx",
        "/src/index.css",
        "/package.json",
    ])
    can_create_subdirs: bool = True

    # Input
    section_data: EnhancedSectionData = None
    shared_imports: List[str] = field(default_factory=lambda: [
        "import React from 'react'",
    ])
    style_tokens: Dict[str, str] = field(default_factory=dict)  # CSS variables

    # Deliverables
    deliverables: List[FileDeliverable] = field(default_factory=list)

    # Acceptance
    acceptance: AcceptanceCriteria = field(default_factory=AcceptanceCriteria)

    def __post_init__(self):
        """Set default deliverables based on namespace"""
        if not self.deliverables:
            component_name = self._namespace_to_component_name()
            self.deliverables = [
                FileDeliverable(
                    path=f"{component_name}.jsx",
                    file_type="component",
                    required=True,
                ),
                FileDeliverable(
                    path=f"{component_name}.css",
                    file_type="styles",
                    required=False,
                ),
            ]

        # Set acceptance criteria from section data
        if self.section_data and not self.acceptance.required_exports:
            self.acceptance.required_exports = [self._namespace_to_component_name()]
            self.acceptance.min_images = len(self.section_data.images)
            self.acceptance.min_links = len(self.section_data.links)

    def _namespace_to_component_name(self) -> str:
        """Convert namespace to component name"""
        # header -> HeaderSection
        # hero-0 -> Hero0Section
        # section-1 -> Section1Section
        parts = self.worker_namespace.replace("-", "_").split("_")
        pascal = "".join(p.capitalize() for p in parts)
        if not pascal.endswith("Section"):
            pascal += "Section"
        return pascal

    def get_allowed_path(self, filename: str) -> str:
        """Get full allowed path for a file"""
        return f"{self.base_path}/{self.worker_namespace}/{filename}"

    def is_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed for this worker"""
        # Check forbidden
        for forbidden in self.forbidden_paths:
            if path == forbidden or path.endswith(forbidden):
                return False

        # Check namespace
        expected_prefix = f"{self.base_path}/{self.worker_namespace}/"
        if not path.startswith(expected_prefix):
            # Also allow without leading slash
            alt_prefix = expected_prefix.lstrip("/")
            if not path.startswith(alt_prefix) and not path.lstrip("/").startswith(alt_prefix):
                return False

        # Check extension
        has_valid_ext = any(path.endswith(ext) for ext in self.allowed_extensions)
        return has_valid_ext

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "worker_namespace": self.worker_namespace,
            "priority": self.priority,
            "scope": {
                "base_path": self.base_path,
                "full_path": f"{self.base_path}/{self.worker_namespace}/",
                "allowed_extensions": self.allowed_extensions,
                "forbidden_paths": self.forbidden_paths,
            },
            "section_data": self.section_data.to_dict() if self.section_data else None,
            "shared_imports": self.shared_imports,
            "style_tokens": self.style_tokens,
            "deliverables": [d.to_dict() for d in self.deliverables],
            "acceptance": self.acceptance.to_dict(),
        }

    def generate_worker_prompt(self) -> str:
        """Generate the task prompt for Worker Agent"""
        component_name = self._namespace_to_component_name()
        full_path = f"{self.base_path}/{self.worker_namespace}/{component_name}.jsx"

        # Build images summary
        images_summary = ""
        if self.section_data and self.section_data.images:
            images = self.section_data.images
            images_summary = f"""
### Images ({len(images)} total) - USE THESE EXACT URLs
```json
{self._format_images_preview(images)}
```
Use `query_section_data(jsonpath="$.images")` to get all images.
"""

        # Build links summary
        links_summary = ""
        if self.section_data and self.section_data.links:
            links = self.section_data.links
            links_summary = f"""
### Links ({len(links)} total) - USE THESE EXACT URLs
```json
{self._format_links_preview(links)}
```
Use `query_section_data(jsonpath="$.links")` to get all links.
"""

        # Build colors - with explicit instructions for each color type
        colors_str = ""
        colors_section = ""
        if self.section_data and self.section_data.styles:
            colors = self.section_data.styles
            bg_colors = colors.background_colors[:3] if colors.background_colors else []
            text_colors = colors.text_colors[:3] if colors.text_colors else []
            accent_colors = colors.accent_colors[:2] if colors.accent_colors else []

            if bg_colors or text_colors or accent_colors:
                colors_lines = ["### Color Palette - MUST USE THESE EXACT COLORS"]
                colors_lines.append("Apply these colors using inline styles or Tailwind classes:")
                if bg_colors:
                    colors_lines.append(f"- **Background colors**: `{', '.join(bg_colors)}`")
                if text_colors:
                    colors_lines.append(f"- **Text colors**: `{', '.join(text_colors)}`")
                if accent_colors:
                    colors_lines.append(f"- **Accent colors** (buttons, links): `{', '.join(accent_colors)}`")
                colors_lines.append("")
                colors_lines.append("Example usage:")
                colors_lines.append("```jsx")
                if bg_colors:
                    colors_lines.append(f'<div style={{{{ backgroundColor: "{bg_colors[0]}" }}}}>')
                if text_colors:
                    colors_lines.append(f'<p style={{{{ color: "{text_colors[0]}" }}}}>')
                colors_lines.append("```")
                colors_section = "\n".join(colors_lines)
                colors_str = f"- **IMPORTANT**: Apply the exact colors from the Color Palette section"

        # Build raw HTML preview
        html_preview = ""
        if self.section_data and self.section_data.raw_html:
            html = self.section_data.raw_html[:1500]
            html_preview = f"""
### Reference HTML (first 1500 chars)
```html
{html}{"..." if len(self.section_data.raw_html) > 1500 else ""}
```
"""

        # Build CSS rules section
        css_rules_section = ""
        has_css_rules = self.section_data and self.section_data.css_rules
        if has_css_rules:
            css_preview = self.section_data.css_rules[:2000]
            css_rules_section = f"""
### Extracted CSS Rules - USE THESE EXACT STYLES
The following CSS rules are extracted from the original page. You MUST include these in your component's CSS file:
```css
{css_preview}{"..." if len(self.section_data.css_rules) > 2000 else ""}
```
Use `query_section_data(jsonpath="$.css_rules")` to get all CSS rules.
"""

        # Determine if CSS file is required
        css_required = "Yes" if has_css_rules else "Optional"

        return f"""## Task Contract: {self.contract_id}

### Your Identity
- **Namespace**: `{self.worker_namespace}`
- **Component Name**: `{component_name}`
- **You can ONLY write to**: `{self.base_path}/{self.worker_namespace}/*`

### Required Deliverables
| File | Type | Required |
|------|------|----------|
| `{full_path}` | React Component | Yes |
| `{self.base_path}/{self.worker_namespace}/{component_name}.css` | Styles | {css_required} |

### Acceptance Criteria
- [ ] Include **{self.acceptance.min_images}** images (use provided URLs)
- [ ] Include **{self.acceptance.min_links}** links (use provided URLs)
- [ ] Export component as `{component_name}`
{f"- [ ] Include CSS file with provided CSS rules" if has_css_rules else ""}
{colors_str}
{images_summary}
{links_summary}
{colors_section}
{css_rules_section}
{html_preview}
### Workflow
1. Query data: `query_section_data(jsonpath="$")` to see full structure
2. Get all images: `query_section_data(jsonpath="$.images")`
3. Get all links: `query_section_data(jsonpath="$.links")`
{f'4. Get CSS rules: `query_section_data(jsonpath="$.css_rules")`' if has_css_rules else ""}
{f'5' if has_css_rules else '4'}. Write component: `write_code(path="{full_path}", content="...")`
{f'6. Write CSS file: `write_code(path="{self.base_path}/{self.worker_namespace}/{component_name}.css", content="...")`' if has_css_rules else ""}
{f'7' if has_css_rules else '5'}. Complete: `complete_task(summary="...")`

**IMPORTANT**:
- Use REAL URLs from the data, never placeholder URLs
- Include ALL images and ALL links
- Export the component as `{component_name}`
{f"- Include the extracted CSS rules in {component_name}.css and import it in your component" if has_css_rules else ""}
- **MUST apply colors from Color Palette section** - use inline styles like `style={{{{ backgroundColor: "rgb(...)" }}}}`
"""

    def _format_images_preview(self, images: List[ImageData], max_items: int = 3) -> str:
        """Format images preview for prompt"""
        import json
        preview = [img.to_dict() for img in images[:max_items]]
        result = json.dumps(preview, ensure_ascii=False, indent=2)
        if len(images) > max_items:
            result += f"\n// ... and {len(images) - max_items} more images"
        return result

    def _format_links_preview(self, links: List[LinkData], max_items: int = 3) -> str:
        """Format links preview for prompt"""
        import json
        preview = [link.to_dict() for link in links[:max_items]]
        result = json.dumps(preview, ensure_ascii=False, indent=2)
        if len(links) > max_items:
            result += f"\n// ... and {len(links) - max_items} more links"
        return result


# ============================================
# Integration Plan
# ============================================

@dataclass
class ComponentEntry:
    """Entry in the integration plan"""
    namespace: str
    import_name: str
    import_path: str
    position: str  # "top", "after:header", "bottom"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "import_name": self.import_name,
            "import_path": self.import_path,
            "position": self.position,
        }


@dataclass
class IntegrationPlan:
    """
    Integration plan for Main Agent

    Provides:
    - Component import order
    - App.jsx template
    - Shared styles
    """
    # Project setup
    framework: str = "react-vite"
    entry_file: str = "/src/main.jsx"
    root_component: str = "/src/App.jsx"
    global_styles: str = "/src/index.css"

    # Component order
    components: List[ComponentEntry] = field(default_factory=list)

    # Shared styles
    css_variables: Dict[str, str] = field(default_factory=dict)
    base_font: str = "system-ui, -apple-system, sans-serif"

    # Page metadata
    page_title: str = ""
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_setup": {
                "framework": self.framework,
                "entry_file": self.entry_file,
                "root_component": self.root_component,
                "global_styles": self.global_styles,
            },
            "component_order": [c.to_dict() for c in self.components],
            "shared_styles": {
                "css_variables": self.css_variables,
                "base_font": self.base_font,
            },
            "metadata": {
                "page_title": self.page_title,
                "source_url": self.source_url,
            },
        }

    def generate_app_jsx(self) -> str:
        """Generate App.jsx content"""
        # Generate imports
        imports = ["import React from 'react'", "import './index.css'"]
        for comp in self.components:
            imports.append(f"import {comp.import_name} from '{comp.import_path}'")

        # Generate component JSX
        component_jsx = []
        for comp in self.components:
            component_jsx.append(f"      <{comp.import_name} />")

        imports_str = "\n".join(imports)
        components_str = "\n".join(component_jsx)

        return f"""{imports_str}

function App() {{
  return (
    <div className="app">
{components_str}
    </div>
  )
}}

export default App
"""

    def generate_index_css(self) -> str:
        """Generate index.css content with CSS variables"""
        variables = []
        for name, value in self.css_variables.items():
            variables.append(f"  {name}: {value};")

        variables_str = "\n".join(variables) if variables else "  /* No variables extracted */"

        return f"""/* Global styles - Auto-generated */
:root {{
{variables_str}
}}

* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}

body {{
  font-family: {self.base_font};
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

.app {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}}

img {{
  max-width: 100%;
  height: auto;
}}

a {{
  text-decoration: none;
  color: inherit;
}}
"""

    def generate_main_jsx(self) -> str:
        """Generate main.jsx content"""
        return """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
"""

    def generate_package_json(self) -> str:
        """Generate package.json content"""
        import json
        return json.dumps({
            "name": "cloned-website",
            "private": True,
            "version": "0.0.1",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.0.0",
                "vite": "^5.0.0"
            }
        }, indent=2)

    def generate_vite_config(self) -> str:
        """Generate vite.config.js content"""
        return """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
"""


# ============================================
# Factory Functions
# ============================================

def create_task_contract(
    section_id: str,
    section_type: str,
    display_name: str,
    section_data: Dict[str, Any],
    priority: int = 1,
) -> TaskContract:
    """
    Create a TaskContract from raw section data

    Args:
        section_id: Section identifier (e.g., "header-0")
        section_type: Type of section (e.g., "header")
        display_name: Display name (e.g., "Header Navigation")
        section_data: Raw section data dict
        priority: Execution priority

    Returns:
        Configured TaskContract
    """
    # Parse section type
    try:
        sec_type = SectionType(section_type.lower())
    except ValueError:
        sec_type = SectionType.GENERIC

    # Build enhanced section data
    enhanced = EnhancedSectionData(
        section_id=section_id,
        section_type=sec_type,
        display_name=display_name,
    )

    # Parse images
    for img_data in section_data.get("images", []):
        if isinstance(img_data, dict):
            role = ImageRole.PHOTO
            role_str = img_data.get("role", "").lower()
            if role_str in [r.value for r in ImageRole]:
                role = ImageRole(role_str)

            enhanced.images.append(ImageData(
                url=img_data.get("url", img_data.get("src", "")),
                alt=img_data.get("alt", ""),
                role=role,
                width=img_data.get("width"),
                height=img_data.get("height"),
                css_classes=img_data.get("css_classes", img_data.get("classes", [])),
                parent_element=img_data.get("parent_element", ""),
                is_background=img_data.get("is_background", False),
            ))
        elif isinstance(img_data, str):
            enhanced.images.append(ImageData(url=img_data))

    # Parse links
    for link_data in section_data.get("links", []):
        if isinstance(link_data, dict):
            link_type = LinkType.INTERNAL
            type_str = link_data.get("type", "").lower()
            if type_str in [t.value for t in LinkType]:
                link_type = LinkType(type_str)

            enhanced.links.append(LinkData(
                url=link_data.get("url", link_data.get("href", "")),
                text=link_data.get("text", ""),
                link_type=link_type,
                position=link_data.get("position", ""),
                has_icon=link_data.get("has_icon", False),
                icon_url=link_data.get("icon_url"),
                css_classes=link_data.get("css_classes", link_data.get("classes", [])),
            ))
        elif isinstance(link_data, str):
            enhanced.links.append(LinkData(url=link_data))

    # Parse visual properties
    rect = section_data.get("rect", {})
    enhanced.visual = VisualProperties(
        rect=rect,
        estimated_height=section_data.get("estimated_height", "auto"),
        position_type=section_data.get("position_type", "relative"),
        z_index=section_data.get("z_index", 0),
        background_type=section_data.get("background_type", "solid"),
        has_shadow=section_data.get("has_shadow", False),
        border_radius=section_data.get("border_radius", "0"),
    )

    # Parse styles
    styles = section_data.get("styles", {})
    colors = styles.get("colors", {}) if isinstance(styles, dict) else {}
    enhanced.styles = StyleProperties(
        background_colors=colors.get("background", []),
        text_colors=colors.get("text", []),
        accent_colors=colors.get("accent", []),
        font_family=styles.get("font_family", "inherit") if isinstance(styles, dict) else "inherit",
    )

    # Parse text content
    text = section_data.get("text_content", {})
    if isinstance(text, dict):
        enhanced.text_content = TextContent(
            headings=text.get("headings", []),
            paragraphs=text.get("paragraphs", []),
            button_labels=text.get("button_labels", []),
            nav_items=text.get("nav_items", []),
        )

    # Raw HTML
    enhanced.raw_html = section_data.get("raw_html", "")

    # CSS rules - extracted from original page
    enhanced.css_rules = section_data.get("css_rules", "")

    # Create contract
    # Use section_id as namespace, sanitized
    namespace = section_id.replace(".", "-").replace(" ", "-").lower()

    contract = TaskContract(
        contract_id=f"{namespace}_contract",
        worker_namespace=namespace,
        priority=priority,
        section_data=enhanced,
    )

    return contract


def create_integration_plan(
    contracts: List[TaskContract],
    page_title: str = "",
    source_url: str = "",
    css_variables: Dict[str, str] = None,
) -> IntegrationPlan:
    """
    Create an IntegrationPlan from TaskContracts

    Args:
        contracts: List of TaskContracts
        page_title: Page title
        source_url: Source URL
        css_variables: CSS variables to include

    Returns:
        Configured IntegrationPlan
    """
    plan = IntegrationPlan(
        page_title=page_title,
        source_url=source_url,
        css_variables=css_variables or {},
    )

    # Sort contracts by priority and type
    type_order = {
        SectionType.HEADER: 0,
        SectionType.NAVIGATION: 1,
        SectionType.HERO: 2,
        SectionType.FEATURES: 3,
        SectionType.CONTENT: 4,
        SectionType.TESTIMONIALS: 5,
        SectionType.GALLERY: 6,
        SectionType.PRICING: 7,
        SectionType.CTA: 8,
        SectionType.SIDEBAR: 9,
        SectionType.FOOTER: 10,
        SectionType.GENERIC: 5,  # Middle
    }

    sorted_contracts = sorted(
        contracts,
        key=lambda c: (
            type_order.get(c.section_data.section_type if c.section_data else SectionType.GENERIC, 5),
            c.priority,
        )
    )

    # Build component entries
    prev_namespace = None
    for contract in sorted_contracts:
        component_name = contract._namespace_to_component_name()
        import_path = f"./components/sections/{contract.worker_namespace}/{component_name}"

        # Determine position
        if contract.section_data:
            sec_type = contract.section_data.section_type
            if sec_type == SectionType.HEADER:
                position = "top"
            elif sec_type == SectionType.FOOTER:
                position = "bottom"
            elif prev_namespace:
                position = f"after:{prev_namespace}"
            else:
                position = "top"
        else:
            position = f"after:{prev_namespace}" if prev_namespace else "top"

        plan.components.append(ComponentEntry(
            namespace=contract.worker_namespace,
            import_name=component_name,
            import_path=import_path,
            position=position,
        ))

        prev_namespace = contract.worker_namespace

    return plan
