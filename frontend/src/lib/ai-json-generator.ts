/**
 * AI JSON Generator - RAG 友好的模块化数据格式
 *
 * 将 Playwright 提取的数据转换成：
 * 1. 模块化组件 - 每个组件独立，可单独检索
 * 2. 设计系统 - 全局样式变量
 * 3. 布局层级 - 组件间关系
 * 4. Embedding Text - 每个组件的向量化描述
 */

import type {
  ExtractionResult,
  ElementInfo,
  StyleSummary,
  PageAssets,
  PageMetadata,
} from "@/types/playwright";

// ==================== AI JSON Types ====================

/**
 * AI JSON 根结构
 */
export interface AIJson {
  version: string;
  generated_at: string;
  metadata: AIMetadata;
  design_system: AIDesignSystem;
  components: AIComponent[];
  layout: AILayout;
  assets: AIAssetMap;
}

/**
 * 页面元数据
 */
export interface AIMetadata {
  title: string;
  url: string;
  viewport: { width: number; height: number };
  page_size: { width: number; height: number };
  total_components: number;
}

/**
 * 设计系统
 */
export interface AIDesignSystem {
  colors: {
    primary: string[];
    background: string[];
    text: string[];
  };
  typography: {
    families: string[];
    sizes: string[];
    weights: string[];
  };
  spacing: {
    margins: string[];
    paddings: string[];
    gaps: string[];
  };
  borders: {
    radii: string[];
    styles: string[];
  };
}

/**
 * 单个组件
 */
export interface AIComponent {
  id: string;
  name: string;
  type: ComponentType;
  tag: string;
  selector: string;

  // 描述（用于 RAG 检索）
  description: string;
  embedding_text: string;

  // 结构
  html_structure: string;
  depth: number;
  parent_id: string | null;
  children_ids: string[];

  // 尺寸和位置
  dimensions: {
    width: number;
    height: number;
    x: number;
    y: number;
  };

  // 样式
  styles: ComponentStyles;

  // 内容
  content: {
    texts: string[];
    images: string[];
    links: string[];
  };

  // 交互
  is_interactive: boolean;
  is_visible: boolean;
}

/**
 * 组件类型
 */
export type ComponentType =
  | "page"
  | "header"
  | "navigation"
  | "hero"
  | "section"
  | "footer"
  | "card"
  | "form"
  | "button"
  | "image"
  | "text"
  | "list"
  | "container"
  | "grid"
  | "flex"
  | "other";

/**
 * 组件样式
 */
export interface ComponentStyles {
  layout: {
    display?: string;
    position?: string;
    flex_direction?: string;
    justify_content?: string;
    align_items?: string;
    gap?: string;
    grid_template?: string;
  };
  spacing: {
    margin?: string;
    padding?: string;
  };
  sizing: {
    width?: string;
    height?: string;
    max_width?: string;
    min_height?: string;
  };
  visual: {
    background?: string;
    border?: string;
    border_radius?: string;
    box_shadow?: string;
    opacity?: string;
  };
  typography?: {
    font_family?: string;
    font_size?: string;
    font_weight?: string;
    line_height?: string;
    color?: string;
    text_align?: string;
  };
  positioning?: {
    top?: string;
    right?: string;
    bottom?: string;
    left?: string;
    z_index?: string;
  };
}

/**
 * 布局信息
 */
export interface AILayout {
  hierarchy: string[];  // 组件 ID 按层级排序
  sections: {
    id: string;
    name: string;
    y_start: number;
    y_end: number;
  }[];
  landmarks: {
    header?: string;
    nav?: string;
    main?: string;
    footer?: string;
  };
}

/**
 * 资源映射
 */
export interface AIAssetMap {
  images: { url: string; used_in: string[] }[];
  fonts: string[];
  icons: string[];
}

// ==================== Generator ====================

let componentCounter = 0;

/**
 * 生成 AI JSON
 */
export function generateAIJson(result: ExtractionResult): AIJson {
  if (!result.success || !result.dom_tree || !result.metadata) {
    throw new Error("Invalid extraction result");
  }

  componentCounter = 0;

  const components: AIComponent[] = [];
  const hierarchy: string[] = [];

  // 递归提取组件
  extractComponents(result.dom_tree, null, 0, components, hierarchy);

  // 生成设计系统
  const designSystem = generateDesignSystem(result.style_summary);

  // 生成布局信息
  const layout = generateLayout(components, result.dom_tree);

  // 生成资源映射
  const assets = generateAssetMap(result.dom_tree, result.assets);

  return {
    version: "1.0.0",
    generated_at: new Date().toISOString(),
    metadata: {
      title: result.metadata.title || "Untitled",
      url: result.metadata.url,
      viewport: {
        width: result.metadata.viewport_width,
        height: result.metadata.viewport_height,
      },
      page_size: {
        width: result.metadata.page_width,
        height: result.metadata.page_height,
      },
      total_components: components.length,
    },
    design_system: designSystem,
    components,
    layout: {
      ...layout,
      hierarchy,
    },
    assets,
  };
}

/**
 * 递归提取组件
 */
function extractComponents(
  el: ElementInfo,
  parentId: string | null,
  depth: number,
  components: AIComponent[],
  hierarchy: string[]
): string | null {
  // 跳过不重要的元素
  if (shouldSkip(el)) return null;
  if (el.rect.width < 10 || el.rect.height < 10) return null;

  const id = `comp_${String(++componentCounter).padStart(4, "0")}`;
  const type = detectComponentType(el);
  const name = generateComponentName(el, type);

  // 收集子组件
  const childrenIds: string[] = [];
  for (const child of el.children) {
    const childId = extractComponents(child, id, depth + 1, components, hierarchy);
    if (childId) {
      childrenIds.push(childId);
    }
  }

  // 生成组件
  const component: AIComponent = {
    id,
    name,
    type,
    tag: el.tag.toLowerCase(),
    selector: buildSelector(el),
    description: generateDescription(el, type, name),
    embedding_text: generateEmbeddingText(el, type, name, childrenIds.length),
    html_structure: generateHtmlStructure(el, depth),
    depth,
    parent_id: parentId,
    children_ids: childrenIds,
    dimensions: {
      width: Math.round(el.rect.width),
      height: Math.round(el.rect.height),
      x: Math.round(el.rect.x),
      y: Math.round(el.rect.y),
    },
    styles: extractStyles(el),
    content: extractContent(el),
    is_interactive: el.is_interactive,
    is_visible: el.is_visible,
  };

  components.push(component);
  hierarchy.push(id);

  return id;
}

/**
 * 检测组件类型
 */
function detectComponentType(el: ElementInfo): ComponentType {
  const tag = el.tag.toLowerCase();
  const classes = el.classes.join(" ").toLowerCase();
  const id = (el.id || "").toLowerCase();

  // 语义标签
  if (tag === "header") return "header";
  if (tag === "nav") return "navigation";
  if (tag === "main") return "section";
  if (tag === "footer") return "footer";
  if (tag === "section" || tag === "article") return "section";
  if (tag === "form") return "form";
  if (tag === "button" || tag === "a" && el.styles.display?.includes("inline")) return "button";
  if (tag === "img" || tag === "picture" || tag === "svg") return "image";
  if (tag === "ul" || tag === "ol") return "list";
  if (["h1", "h2", "h3", "h4", "h5", "h6", "p"].includes(tag)) return "text";

  // 类名检测
  if (classes.includes("hero") || classes.includes("banner")) return "hero";
  if (classes.includes("card")) return "card";
  if (classes.includes("nav") || classes.includes("menu")) return "navigation";
  if (classes.includes("header")) return "header";
  if (classes.includes("footer")) return "footer";
  if (classes.includes("btn") || classes.includes("button")) return "button";
  if (classes.includes("form")) return "form";

  // ID 检测
  if (id.includes("header")) return "header";
  if (id.includes("nav")) return "navigation";
  if (id.includes("footer")) return "footer";
  if (id.includes("hero")) return "hero";

  // 布局检测
  const display = el.styles.display;
  if (display === "grid" || display === "inline-grid") return "grid";
  if (display === "flex" || display === "inline-flex") return "flex";

  // 容器检测
  if (tag === "div" && el.children.length > 0) return "container";

  return "other";
}

/**
 * 生成组件名称
 */
function generateComponentName(el: ElementInfo, type: ComponentType): string {
  // 优先使用 ID
  if (el.id) {
    return formatName(el.id);
  }

  // 使用有意义的类名
  const meaningfulClass = el.classes.find(c =>
    !c.match(/^(w-|h-|p-|m-|flex|grid|text-|bg-|border-)/)
  );
  if (meaningfulClass) {
    return formatName(meaningfulClass);
  }

  // 使用类型 + 序号
  return `${type}_${componentCounter}`;
}

/**
 * 格式化名称
 */
function formatName(str: string): string {
  return str
    .replace(/[-_]/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .split(" ")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * 生成描述（用于 RAG 检索）
 */
function generateDescription(el: ElementInfo, type: ComponentType, name: string): string {
  const parts: string[] = [];

  parts.push(`${name} - ${type} component`);

  // 尺寸
  parts.push(`Size: ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px`);

  // 布局
  if (el.styles.display) {
    parts.push(`Layout: ${el.styles.display}`);
  }

  // 位置
  if (el.styles.position && el.styles.position !== "static") {
    parts.push(`Position: ${el.styles.position}`);
  }

  // 子元素数量
  if (el.children.length > 0) {
    parts.push(`Contains ${el.children.length} child elements`);
  }

  // 文本内容预览
  if (el.text_content) {
    parts.push(`Text: "${el.text_content.slice(0, 50)}..."`);
  }

  return parts.join(". ");
}

/**
 * 生成 Embedding 文本（用于向量化）
 */
function generateEmbeddingText(
  el: ElementInfo,
  type: ComponentType,
  name: string,
  childCount: number
): string {
  const parts: string[] = [];

  // 组件身份
  parts.push(`Component: ${name}`);
  parts.push(`Type: ${type}`);
  parts.push(`HTML Tag: ${el.tag}`);

  // 选择器
  if (el.id) parts.push(`ID: ${el.id}`);
  if (el.classes.length > 0) parts.push(`Classes: ${el.classes.join(", ")}`);

  // 尺寸
  parts.push(`Width: ${Math.round(el.rect.width)}px`);
  parts.push(`Height: ${Math.round(el.rect.height)}px`);

  // 关键样式
  const s = el.styles;
  if (s.display) parts.push(`Display: ${s.display}`);
  if (s.position && s.position !== "static") parts.push(`Position: ${s.position}`);
  if (s.flex_direction) parts.push(`Flex Direction: ${s.flex_direction}`);
  if (s.justify_content) parts.push(`Justify: ${s.justify_content}`);
  if (s.align_items) parts.push(`Align: ${s.align_items}`);
  if (s.grid_template_columns) parts.push(`Grid Columns: ${s.grid_template_columns}`);
  if (s.background_color && !isTransparent(s.background_color)) {
    parts.push(`Background: ${simplifyColor(s.background_color)}`);
  }
  if (s.border_radius) parts.push(`Border Radius: ${s.border_radius}`);

  // 结构
  parts.push(`Children: ${childCount}`);
  if (el.is_interactive) parts.push(`Interactive: yes`);

  // 内容
  if (el.text_content) {
    parts.push(`Content: ${el.text_content.slice(0, 100)}`);
  }

  return parts.join("\n");
}

/**
 * 生成 HTML 结构
 */
function generateHtmlStructure(el: ElementInfo, maxDepth: number = 2): string {
  function render(e: ElementInfo, depth: number): string {
    const indent = "  ".repeat(depth);
    let tag = `<${e.tag}`;
    if (e.id) tag += ` id="${e.id}"`;
    if (e.classes.length > 0) tag += ` class="${e.classes.slice(0, 3).join(" ")}"`;
    tag += ">";

    if (depth >= maxDepth || e.children.length === 0) {
      if (e.text_content) {
        return `${indent}${tag}${e.text_content.slice(0, 30)}...</${e.tag}>`;
      }
      return `${indent}${tag}...</${e.tag}>`;
    }

    const children = e.children
      .slice(0, 5)
      .map(c => render(c, depth + 1))
      .join("\n");

    return `${indent}${tag}\n${children}\n${indent}</${e.tag}>`;
  }

  return render(el, 0);
}

/**
 * 提取样式
 */
function extractStyles(el: ElementInfo): ComponentStyles {
  const s = el.styles;

  return {
    layout: {
      display: s.display || undefined,
      position: s.position !== "static" ? s.position : undefined,
      flex_direction: s.flex_direction || undefined,
      justify_content: s.justify_content || undefined,
      align_items: s.align_items || undefined,
      gap: s.gap || undefined,
      grid_template: s.grid_template_columns || undefined,
    },
    spacing: {
      margin: s.margin !== "0px" ? s.margin : undefined,
      padding: s.padding !== "0px" ? s.padding : undefined,
    },
    sizing: {
      width: s.width || undefined,
      height: s.height || undefined,
      max_width: s.max_width || undefined,
      min_height: s.min_height || undefined,
    },
    visual: {
      background: s.background_color && !isTransparent(s.background_color)
        ? simplifyColor(s.background_color)
        : undefined,
      border: s.border && s.border !== "none" ? s.border : undefined,
      border_radius: s.border_radius !== "0px" ? s.border_radius : undefined,
      box_shadow: s.box_shadow !== "none" ? s.box_shadow : undefined,
      opacity: s.opacity !== "1" ? s.opacity : undefined,
    },
    typography: isTextElement(el.tag) ? {
      font_family: s.font_family ? simplifyFontFamily(s.font_family) : undefined,
      font_size: s.font_size || undefined,
      font_weight: s.font_weight || undefined,
      line_height: s.line_height || undefined,
      color: s.color ? simplifyColor(s.color) : undefined,
      text_align: s.text_align || undefined,
    } : undefined,
    positioning: s.position && s.position !== "static" ? {
      top: s.top !== "auto" ? s.top : undefined,
      right: s.right !== "auto" ? s.right : undefined,
      bottom: s.bottom !== "auto" ? s.bottom : undefined,
      left: s.left !== "auto" ? s.left : undefined,
      z_index: s.z_index !== "auto" ? s.z_index : undefined,
    } : undefined,
  };
}

/**
 * 提取内容
 */
function extractContent(el: ElementInfo): AIComponent["content"] {
  const texts: string[] = [];
  const images: string[] = [];
  const links: string[] = [];

  function collect(e: ElementInfo) {
    if (e.text_content) {
      texts.push(e.text_content.trim());
    }
    if (e.tag.toLowerCase() === "img" && e.attributes.src) {
      images.push(e.attributes.src);
    }
    if (e.tag.toLowerCase() === "a" && e.attributes.href) {
      links.push(e.attributes.href);
    }
    e.children.forEach(collect);
  }

  collect(el);

  return {
    texts: texts.filter(t => t.length > 0).slice(0, 10),
    images: images.slice(0, 10),
    links: links.slice(0, 10),
  };
}

/**
 * 生成设计系统
 */
function generateDesignSystem(summary: StyleSummary | null | undefined): AIDesignSystem {
  if (!summary) {
    return {
      colors: { primary: [], background: [], text: [] },
      typography: { families: [], sizes: [], weights: [] },
      spacing: { margins: [], paddings: [], gaps: [] },
      borders: { radii: [], styles: [] },
    };
  }

  // 提取颜色
  const bgColors = Object.entries(summary.background_colors)
    .filter(([c]) => !isTransparent(c))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([c]) => simplifyColor(c));

  const textColors = Object.entries(summary.colors)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([c]) => simplifyColor(c));

  // 提取字体
  const families = Object.entries(summary.font_families)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([f]) => simplifyFontFamily(f));

  const sizes = Object.entries(summary.font_sizes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([s]) => s);

  // 提取间距
  const margins = Object.entries(summary.margins)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([m]) => m);

  const paddings = Object.entries(summary.paddings)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([p]) => p);

  return {
    colors: {
      primary: bgColors.slice(0, 3),
      background: bgColors,
      text: textColors,
    },
    typography: {
      families,
      sizes,
      weights: ["400", "500", "600", "700"],
    },
    spacing: {
      margins,
      paddings,
      gaps: [],
    },
    borders: {
      radii: [],
      styles: [],
    },
  };
}

/**
 * 生成布局信息
 */
function generateLayout(
  components: AIComponent[],
  domTree: ElementInfo
): Omit<AILayout, "hierarchy"> {
  // 按 Y 坐标分组识别 sections
  const sections: AILayout["sections"] = [];
  const topLevel = components.filter(c => c.depth <= 2 && c.dimensions.height > 100);

  topLevel
    .sort((a, b) => a.dimensions.y - b.dimensions.y)
    .forEach((c, i) => {
      sections.push({
        id: c.id,
        name: c.name,
        y_start: c.dimensions.y,
        y_end: c.dimensions.y + c.dimensions.height,
      });
    });

  // 识别 landmarks
  const landmarks: AILayout["landmarks"] = {};
  components.forEach(c => {
    if (c.type === "header" && !landmarks.header) landmarks.header = c.id;
    if (c.type === "navigation" && !landmarks.nav) landmarks.nav = c.id;
    if (c.type === "footer" && !landmarks.footer) landmarks.footer = c.id;
    if (c.tag === "main" && !landmarks.main) landmarks.main = c.id;
  });

  return { sections, landmarks };
}

/**
 * 生成资源映射
 */
function generateAssetMap(
  domTree: ElementInfo,
  assets: PageAssets | null | undefined
): AIAssetMap {
  const imageUsage: Map<string, string[]> = new Map();

  function collect(el: ElementInfo, componentId: string) {
    if (el.tag.toLowerCase() === "img" && el.attributes.src) {
      const url = el.attributes.src;
      if (!imageUsage.has(url)) {
        imageUsage.set(url, []);
      }
      imageUsage.get(url)!.push(componentId);
    }
    el.children.forEach(c => collect(c, componentId));
  }

  collect(domTree, "root");

  return {
    images: Array.from(imageUsage.entries()).map(([url, used_in]) => ({
      url,
      used_in,
    })),
    fonts: assets?.fonts.map(f => f.url) || [],
    icons: [],
  };
}

// ==================== Helper Functions ====================

function shouldSkip(el: ElementInfo): boolean {
  const skipTags = ["script", "style", "noscript", "meta", "link", "br", "hr", "svg", "path"];
  return skipTags.includes(el.tag.toLowerCase());
}

function isTextElement(tag: string): boolean {
  return ["p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "a", "li", "label", "button"].includes(
    tag.toLowerCase()
  );
}

function isTransparent(color: string): boolean {
  return color.includes("rgba(0, 0, 0, 0)") || color === "transparent";
}

function simplifyColor(color: string): string {
  const rgbMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (rgbMatch) {
    const [, r, g, b] = rgbMatch;
    return `#${parseInt(r).toString(16).padStart(2, "0")}${parseInt(g)
      .toString(16)
      .padStart(2, "0")}${parseInt(b).toString(16).padStart(2, "0")}`.toUpperCase();
  }
  return color;
}

function simplifyFontFamily(font: string): string {
  return font.split(",")[0].trim().replace(/["']/g, "");
}

function buildSelector(el: ElementInfo): string {
  let s = el.tag;
  if (el.id) s += `#${el.id}`;
  else if (el.classes.length > 0) s += `.${el.classes[0]}`;
  return s;
}
