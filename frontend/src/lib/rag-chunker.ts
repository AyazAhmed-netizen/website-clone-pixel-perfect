/**
 * RAG Chunker - 模块化切片处理器
 *
 * 将 Playwright 提取的原始 JSON 数据进行智能切片：
 * 1. 按语义模块切片 - header, hero, section, footer 等
 * 2. 按组件类型切片 - button, card, form, navigation 等
 * 3. 按内容关联切片 - 相关元素组合在一起
 * 4. 生成 embedding text - 方便向量检索
 */

import type {
  ExtractionResult,
  ElementInfo,
  StyleSummary,
  PageAssets,
} from "@/types/playwright";

// ==================== Chunk Types ====================

/**
 * RAG Chunk - 单个切片
 */
export interface RAGChunk {
  id: string;
  type: ChunkType;
  name: string;
  description: string;
  embedding_text: string;
  content: ChunkContent;
  metadata: ChunkMetadata;
}

/**
 * 切片类型
 */
export type ChunkType =
  | "page_overview"      // 页面概览
  | "design_system"      // 设计系统
  | "layout_structure"   // 布局结构
  | "semantic_section"   // 语义区块 (header, footer, hero, etc.)
  | "component"          // 独立组件 (card, button, form, etc.)
  | "style_collection"   // 样式集合
  | "asset_collection";  // 资源集合

/**
 * 切片内容
 */
export interface ChunkContent {
  // 原始 DOM 数据（如果适用）
  elements?: ElementInfo[];
  // 样式数据
  styles?: Record<string, unknown>;
  // HTML 结构片段
  html_structure?: string;
  // 文本内容
  texts?: string[];
  // 图片 URLs
  images?: string[];
  // 链接
  links?: string[];
  // 其他原始数据
  raw_data?: Record<string, unknown>;
}

/**
 * 切片元数据
 */
export interface ChunkMetadata {
  source_url: string;
  page_title: string;
  viewport: { width: number; height: number };
  position?: { x: number; y: number };
  dimensions?: { width: number; height: number };
  depth?: number;
  element_count?: number;
  parent_chunk_id?: string;
  child_chunk_ids?: string[];
}

/**
 * 切片结果
 */
export interface ChunkResult {
  version: string;
  generated_at: string;
  source_url: string;
  total_chunks: number;
  chunks: RAGChunk[];
}

// ==================== Chunker Class ====================

/**
 * RAG Chunker - 智能切片器
 */
export class RAGChunker {
  private chunkCounter = 0;
  private result: ExtractionResult;
  private chunks: RAGChunk[] = [];

  constructor(result: ExtractionResult) {
    if (!result.success || !result.dom_tree || !result.metadata) {
      throw new Error("Invalid extraction result");
    }
    this.result = result;
  }

  /**
   * 执行切片
   */
  public chunk(): ChunkResult {
    this.chunkCounter = 0;
    this.chunks = [];

    // 1. 页面概览切片
    this.createPageOverviewChunk();

    // 2. 设计系统切片
    this.createDesignSystemChunk();

    // 3. 布局结构切片
    this.createLayoutStructureChunk();

    // 4. 语义区块切片
    this.createSemanticSectionChunks();

    // 5. 组件切片
    this.createComponentChunks();

    // 6. 资源切片
    this.createAssetChunk();

    return {
      version: "1.0.0",
      generated_at: new Date().toISOString(),
      source_url: this.result.metadata!.url,
      total_chunks: this.chunks.length,
      chunks: this.chunks,
    };
  }

  /**
   * 创建页面概览切片
   */
  private createPageOverviewChunk(): void {
    const meta = this.result.metadata!;
    const domTree = this.result.dom_tree!;

    const chunk: RAGChunk = {
      id: this.generateId("overview"),
      type: "page_overview",
      name: "Page Overview",
      description: this.buildOverviewDescription(meta),
      embedding_text: this.buildOverviewEmbedding(meta, domTree),
      content: {
        raw_data: {
          title: meta.title,
          url: meta.url,
          viewport_width: meta.viewport_width,
          viewport_height: meta.viewport_height,
          page_width: meta.page_width,
          page_height: meta.page_height,
          total_elements: meta.total_elements,
          max_depth: meta.max_depth,
          load_time_ms: meta.load_time_ms,
        },
      },
      metadata: {
        source_url: meta.url,
        page_title: meta.title,
        viewport: { width: meta.viewport_width, height: meta.viewport_height },
        element_count: meta.total_elements,
      },
    };

    this.chunks.push(chunk);
  }

  /**
   * 创建设计系统切片
   */
  private createDesignSystemChunk(): void {
    const styleSummary = this.result.style_summary;
    if (!styleSummary) return;

    const meta = this.result.metadata!;

    const chunk: RAGChunk = {
      id: this.generateId("design"),
      type: "design_system",
      name: "Design System",
      description: "Page design tokens: colors, typography, spacing, and borders",
      embedding_text: this.buildDesignSystemEmbedding(styleSummary),
      content: {
        styles: {
          // 颜色系统
          colors: {
            background: this.extractTopValues(styleSummary.background_colors, 10),
            text: this.extractTopValues(styleSummary.colors, 10),
          },
          // 字体系统
          typography: {
            families: this.extractTopValues(styleSummary.font_families, 5),
            sizes: this.extractTopValues(styleSummary.font_sizes, 10),
          },
          // 间距系统
          spacing: {
            margins: this.extractTopValues(styleSummary.margins, 10),
            paddings: this.extractTopValues(styleSummary.paddings, 10),
          },
          // 边框系统
          borders: {
            widths: this.extractTopValues(styleSummary.border_widths, 5),
            radii: this.extractTopValues(styleSummary.border_radii, 5),
          },
        },
        raw_data: styleSummary as Record<string, unknown>,
      },
      metadata: {
        source_url: meta.url,
        page_title: meta.title,
        viewport: { width: meta.viewport_width, height: meta.viewport_height },
      },
    };

    this.chunks.push(chunk);
  }

  /**
   * 创建布局结构切片
   */
  private createLayoutStructureChunk(): void {
    const domTree = this.result.dom_tree!;
    const meta = this.result.metadata!;

    // 提取顶层布局结构
    const layoutElements = this.extractLayoutElements(domTree, 3);

    const chunk: RAGChunk = {
      id: this.generateId("layout"),
      type: "layout_structure",
      name: "Page Layout",
      description: "Page layout structure showing main sections and their arrangement",
      embedding_text: this.buildLayoutEmbedding(layoutElements),
      content: {
        elements: layoutElements,
        html_structure: this.buildLayoutHTML(domTree, 3),
      },
      metadata: {
        source_url: meta.url,
        page_title: meta.title,
        viewport: { width: meta.viewport_width, height: meta.viewport_height },
        dimensions: { width: meta.page_width, height: meta.page_height },
        element_count: layoutElements.length,
      },
    };

    this.chunks.push(chunk);
  }

  /**
   * 创建语义区块切片
   */
  private createSemanticSectionChunks(): void {
    const domTree = this.result.dom_tree!;
    const meta = this.result.metadata!;

    // 识别语义区块
    const semanticSections = this.findSemanticSections(domTree);

    for (const section of semanticSections) {
      const chunk: RAGChunk = {
        id: this.generateId("section"),
        type: "semantic_section",
        name: this.getSectionName(section),
        description: this.buildSectionDescription(section),
        embedding_text: this.buildSectionEmbedding(section),
        content: {
          elements: [section],
          html_structure: this.buildElementHTML(section, 4),
          texts: this.extractTexts(section),
          images: this.extractImages(section),
          links: this.extractLinks(section),
        },
        metadata: {
          source_url: meta.url,
          page_title: meta.title,
          viewport: { width: meta.viewport_width, height: meta.viewport_height },
          position: { x: Math.round(section.rect.x), y: Math.round(section.rect.y) },
          dimensions: {
            width: Math.round(section.rect.width),
            height: Math.round(section.rect.height),
          },
          depth: 0,
          element_count: this.countElements(section),
        },
      };

      this.chunks.push(chunk);
    }
  }

  /**
   * 创建组件切片
   */
  private createComponentChunks(): void {
    const domTree = this.result.dom_tree!;
    const meta = this.result.metadata!;

    // 识别独立组件
    const components = this.findComponents(domTree);

    for (const component of components) {
      const componentType = this.detectComponentType(component);

      const chunk: RAGChunk = {
        id: this.generateId("component"),
        type: "component",
        name: this.getComponentName(component, componentType),
        description: this.buildComponentDescription(component, componentType),
        embedding_text: this.buildComponentEmbedding(component, componentType),
        content: {
          elements: [component],
          html_structure: this.buildElementHTML(component, 3),
          texts: this.extractTexts(component),
          images: this.extractImages(component),
          links: this.extractLinks(component),
          styles: this.extractElementStyles(component),
        },
        metadata: {
          source_url: meta.url,
          page_title: meta.title,
          viewport: { width: meta.viewport_width, height: meta.viewport_height },
          position: { x: Math.round(component.rect.x), y: Math.round(component.rect.y) },
          dimensions: {
            width: Math.round(component.rect.width),
            height: Math.round(component.rect.height),
          },
          element_count: this.countElements(component),
        },
      };

      this.chunks.push(chunk);
    }
  }

  /**
   * 创建资源切片
   */
  private createAssetChunk(): void {
    const assets = this.result.assets;
    const meta = this.result.metadata!;
    if (!assets) return;

    // 安全获取数组
    const safeArray = <T>(arr: T[] | undefined | null): T[] => arr || [];

    const chunk: RAGChunk = {
      id: this.generateId("assets"),
      type: "asset_collection",
      name: "Page Assets",
      description: "All page assets including images, fonts, and external resources",
      embedding_text: this.buildAssetEmbedding(assets),
      content: {
        // AssetInfo 使用 url 而不是 src
        images: safeArray(assets.images).map((img) => img.url),
        raw_data: {
          images: safeArray(assets.images),
          fonts: safeArray(assets.fonts),
          scripts: safeArray(assets.scripts),
          stylesheets: safeArray(assets.stylesheets),
        },
      },
      metadata: {
        source_url: meta.url,
        page_title: meta.title,
        viewport: { width: meta.viewport_width, height: meta.viewport_height },
      },
    };

    this.chunks.push(chunk);
  }

  // ==================== Helper Methods ====================

  private generateId(prefix: string): string {
    return `${prefix}_${String(++this.chunkCounter).padStart(4, "0")}`;
  }

  private extractTopValues(
    obj: Record<string, number> | undefined | null,
    limit: number
  ): { value: string; count: number }[] {
    if (!obj || typeof obj !== "object") {
      return [];
    }
    return Object.entries(obj)
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([value, count]) => ({ value, count }));
  }

  private extractLayoutElements(el: ElementInfo, maxDepth: number): ElementInfo[] {
    const elements: ElementInfo[] = [];

    const traverse = (e: ElementInfo, depth: number) => {
      if (depth > maxDepth) return;
      if (this.isSignificantElement(e)) {
        elements.push(e);
      }
      e.children.forEach((c) => traverse(c, depth + 1));
    };

    traverse(el, 0);
    return elements;
  }

  private isSignificantElement(el: ElementInfo): boolean {
    // 尺寸过小的元素不重要
    if (el.rect.width < 50 || el.rect.height < 30) return false;

    // 语义标签
    const semanticTags = ["header", "nav", "main", "section", "article", "aside", "footer"];
    if (semanticTags.includes(el.tag.toLowerCase())) return true;

    // 有意义的类名
    const meaningfulClasses = ["hero", "banner", "card", "container", "wrapper", "section"];
    if (el.classes.some((c) => meaningfulClasses.some((m) => c.toLowerCase().includes(m)))) {
      return true;
    }

    // 有 ID 的元素
    if (el.id) return true;

    return false;
  }

  private findSemanticSections(domTree: ElementInfo): ElementInfo[] {
    const sections: ElementInfo[] = [];
    const semanticTags = ["header", "nav", "main", "section", "article", "aside", "footer"];

    const traverse = (el: ElementInfo) => {
      const tag = el.tag.toLowerCase();
      const classes = el.classes.join(" ").toLowerCase();
      const id = (el.id || "").toLowerCase();

      // 语义标签
      if (semanticTags.includes(tag)) {
        sections.push(el);
        return; // 不再递归子元素
      }

      // Hero 区域
      if (classes.includes("hero") || classes.includes("banner") || id.includes("hero")) {
        sections.push(el);
        return;
      }

      // 大型容器
      if (
        tag === "div" &&
        el.rect.width > 800 &&
        el.rect.height > 200 &&
        (classes.includes("section") || classes.includes("container"))
      ) {
        sections.push(el);
        return;
      }

      el.children.forEach(traverse);
    };

    traverse(domTree);
    return sections;
  }

  private findComponents(domTree: ElementInfo): ElementInfo[] {
    const components: ElementInfo[] = [];
    const componentPatterns = [
      "card",
      "button",
      "btn",
      "form",
      "input",
      "modal",
      "dropdown",
      "menu",
      "tab",
      "accordion",
      "slider",
      "carousel",
    ];

    const traverse = (el: ElementInfo, depth: number) => {
      // 限制深度
      if (depth > 8) return;

      const tag = el.tag.toLowerCase();
      const classes = el.classes.join(" ").toLowerCase();

      // 表单元素
      if (tag === "form" || tag === "button" || tag === "input" || tag === "select") {
        components.push(el);
        return;
      }

      // 卡片等组件
      if (componentPatterns.some((p) => classes.includes(p))) {
        components.push(el);
        return;
      }

      // 交互元素
      if (el.is_interactive && el.rect.width > 30 && el.rect.height > 20) {
        components.push(el);
        return;
      }

      el.children.forEach((c) => traverse(c, depth + 1));
    };

    traverse(domTree, 0);
    return components;
  }

  private detectComponentType(el: ElementInfo): string {
    const tag = el.tag.toLowerCase();
    const classes = el.classes.join(" ").toLowerCase();

    if (tag === "button" || classes.includes("btn") || classes.includes("button")) return "button";
    if (tag === "form") return "form";
    if (tag === "input" || tag === "textarea" || tag === "select") return "input";
    if (classes.includes("card")) return "card";
    if (classes.includes("modal") || classes.includes("dialog")) return "modal";
    if (classes.includes("dropdown") || classes.includes("menu")) return "dropdown";
    if (classes.includes("nav")) return "navigation";
    if (classes.includes("tab")) return "tabs";
    if (tag === "a") return "link";
    if (tag === "img") return "image";

    return "container";
  }

  private getSectionName(el: ElementInfo): string {
    const tag = el.tag.toLowerCase();
    if (el.id) return this.formatName(el.id);

    const meaningfulClass = el.classes.find(
      (c) => !c.match(/^(w-|h-|p-|m-|flex|grid|text-|bg-|border-)/)
    );
    if (meaningfulClass) return this.formatName(meaningfulClass);

    return this.formatName(tag);
  }

  private getComponentName(el: ElementInfo, type: string): string {
    if (el.id) return this.formatName(el.id);

    const meaningfulClass = el.classes.find(
      (c) => !c.match(/^(w-|h-|p-|m-|flex|grid|text-|bg-|border-)/)
    );
    if (meaningfulClass) return this.formatName(meaningfulClass);

    return `${this.formatName(type)} Component`;
  }

  private formatName(str: string): string {
    return str
      .replace(/[-_]/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .toLowerCase()
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }

  private countElements(el: ElementInfo): number {
    let count = 1;
    el.children.forEach((c) => (count += this.countElements(c)));
    return count;
  }

  private extractTexts(el: ElementInfo): string[] {
    const texts: string[] = [];
    const traverse = (e: ElementInfo) => {
      if (e.text_content && e.text_content.trim()) {
        texts.push(e.text_content.trim());
      }
      e.children.forEach(traverse);
    };
    traverse(el);
    return texts.slice(0, 20);
  }

  private extractImages(el: ElementInfo): string[] {
    const images: string[] = [];
    const traverse = (e: ElementInfo) => {
      if (e.tag.toLowerCase() === "img" && e.attributes.src) {
        images.push(e.attributes.src);
      }
      e.children.forEach(traverse);
    };
    traverse(el);
    return images.slice(0, 10);
  }

  private extractLinks(el: ElementInfo): string[] {
    const links: string[] = [];
    const traverse = (e: ElementInfo) => {
      if (e.tag.toLowerCase() === "a" && e.attributes.href) {
        links.push(e.attributes.href);
      }
      e.children.forEach(traverse);
    };
    traverse(el);
    return links.slice(0, 10);
  }

  private extractElementStyles(el: ElementInfo): Record<string, unknown> {
    return {
      display: el.styles.display,
      position: el.styles.position,
      flexDirection: el.styles.flex_direction,
      justifyContent: el.styles.justify_content,
      alignItems: el.styles.align_items,
      backgroundColor: el.styles.background_color,
      color: el.styles.color,
      fontSize: el.styles.font_size,
      fontWeight: el.styles.font_weight,
      padding: el.styles.padding,
      margin: el.styles.margin,
      borderRadius: el.styles.border_radius,
      boxShadow: el.styles.box_shadow,
    };
  }

  private buildLayoutHTML(el: ElementInfo, maxDepth: number): string {
    const render = (e: ElementInfo, depth: number): string => {
      const indent = "  ".repeat(depth);
      let tag = `<${e.tag}`;
      if (e.id) tag += ` id="${e.id}"`;
      if (e.classes.length > 0) tag += ` class="${e.classes.slice(0, 3).join(" ")}"`;
      tag += ">";

      if (depth >= maxDepth || e.children.length === 0) {
        return `${indent}${tag}...</${e.tag}>`;
      }

      const children = e.children
        .filter((c) => this.isSignificantElement(c))
        .slice(0, 5)
        .map((c) => render(c, depth + 1))
        .join("\n");

      return `${indent}${tag}\n${children}\n${indent}</${e.tag}>`;
    };

    return render(el, 0);
  }

  private buildElementHTML(el: ElementInfo, maxDepth: number): string {
    const render = (e: ElementInfo, depth: number): string => {
      const indent = "  ".repeat(depth);
      let tag = `<${e.tag}`;
      if (e.id) tag += ` id="${e.id}"`;
      if (e.classes.length > 0) tag += ` class="${e.classes.slice(0, 3).join(" ")}"`;
      tag += ">";

      if (depth >= maxDepth || e.children.length === 0) {
        if (e.text_content) {
          return `${indent}${tag}${e.text_content.slice(0, 50)}...</${e.tag}>`;
        }
        return `${indent}${tag}...</${e.tag}>`;
      }

      const children = e.children
        .slice(0, 5)
        .map((c) => render(c, depth + 1))
        .join("\n");

      return `${indent}${tag}\n${children}\n${indent}</${e.tag}>`;
    };

    return render(el, 0);
  }

  // ==================== Embedding Text Builders ====================

  private buildOverviewDescription(meta: ExtractionResult["metadata"]): string {
    return `Page: ${meta!.title}. URL: ${meta!.url}. Size: ${meta!.page_width}x${meta!.page_height}px. Elements: ${meta!.total_elements}.`;
  }

  private buildOverviewEmbedding(
    meta: ExtractionResult["metadata"],
    domTree: ElementInfo
  ): string {
    const parts: string[] = [];
    parts.push(`Page Title: ${meta!.title}`);
    parts.push(`URL: ${meta!.url}`);
    parts.push(`Viewport: ${meta!.viewport_width}x${meta!.viewport_height}`);
    parts.push(`Page Size: ${meta!.page_width}x${meta!.page_height}`);
    parts.push(`Total Elements: ${meta!.total_elements}`);
    parts.push(`Max Depth: ${meta!.max_depth}`);
    parts.push(`Load Time: ${meta!.load_time_ms}ms`);

    // 添加主要标签统计
    const tagCounts = new Map<string, number>();
    const countTags = (el: ElementInfo) => {
      const tag = el.tag.toLowerCase();
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      el.children.forEach(countTags);
    };
    countTags(domTree);

    const topTags = Array.from(tagCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([tag, count]) => `${tag}: ${count}`)
      .join(", ");
    parts.push(`Top Tags: ${topTags}`);

    return parts.join("\n");
  }

  private buildDesignSystemEmbedding(styleSummary: StyleSummary): string {
    const parts: string[] = [];
    parts.push("Design System Tokens:");

    // 安全获取对象的 keys
    const safeKeys = (obj: Record<string, unknown> | undefined | null): string[] => {
      if (!obj || typeof obj !== "object") return [];
      return Object.keys(obj);
    };

    // Colors
    const bgColors = safeKeys(styleSummary.background_colors).slice(0, 5);
    const textColors = safeKeys(styleSummary.colors).slice(0, 5);
    parts.push(`Background Colors: ${bgColors.join(", ") || "none"}`);
    parts.push(`Text Colors: ${textColors.join(", ") || "none"}`);

    // Typography
    const fonts = safeKeys(styleSummary.font_families).slice(0, 3);
    const sizes = safeKeys(styleSummary.font_sizes).slice(0, 8);
    parts.push(`Font Families: ${fonts.join(", ") || "none"}`);
    parts.push(`Font Sizes: ${sizes.join(", ") || "none"}`);

    // Spacing
    const margins = safeKeys(styleSummary.margins).slice(0, 5);
    const paddings = safeKeys(styleSummary.paddings).slice(0, 5);
    parts.push(`Margins: ${margins.join(", ") || "none"}`);
    parts.push(`Paddings: ${paddings.join(", ") || "none"}`);

    return parts.join("\n");
  }

  private buildLayoutEmbedding(elements: ElementInfo[]): string {
    const parts: string[] = [];
    parts.push("Page Layout Structure:");

    elements.forEach((el, i) => {
      const tag = el.tag.toLowerCase();
      const name = el.id || el.classes[0] || tag;
      parts.push(
        `${i + 1}. ${name} (${tag}) - ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px at y=${Math.round(el.rect.y)}`
      );
    });

    return parts.join("\n");
  }

  private buildSectionDescription(el: ElementInfo): string {
    const tag = el.tag.toLowerCase();
    const name = this.getSectionName(el);
    return `${name} - ${tag} section. Size: ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px. Position: y=${Math.round(el.rect.y)}. Elements: ${this.countElements(el)}.`;
  }

  private buildSectionEmbedding(el: ElementInfo): string {
    const parts: string[] = [];
    const name = this.getSectionName(el);

    parts.push(`Section: ${name}`);
    parts.push(`Tag: ${el.tag}`);
    if (el.id) parts.push(`ID: ${el.id}`);
    if (el.classes.length > 0) parts.push(`Classes: ${el.classes.join(", ")}`);
    parts.push(`Size: ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px`);
    parts.push(`Position: x=${Math.round(el.rect.x)}, y=${Math.round(el.rect.y)}`);

    // Layout styles
    const s = el.styles;
    if (s.display) parts.push(`Display: ${s.display}`);
    if (s.flex_direction) parts.push(`Flex Direction: ${s.flex_direction}`);
    if (s.justify_content) parts.push(`Justify: ${s.justify_content}`);
    if (s.align_items) parts.push(`Align: ${s.align_items}`);
    if (s.background_color) parts.push(`Background: ${s.background_color}`);

    // Content
    const texts = this.extractTexts(el);
    if (texts.length > 0) {
      parts.push(`Content: ${texts.slice(0, 3).join(" | ")}`);
    }

    return parts.join("\n");
  }

  private buildComponentDescription(el: ElementInfo, type: string): string {
    const name = this.getComponentName(el, type);
    return `${name} - ${type} component. Size: ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px. Interactive: ${el.is_interactive}.`;
  }

  private buildComponentEmbedding(el: ElementInfo, type: string): string {
    const parts: string[] = [];
    const name = this.getComponentName(el, type);

    parts.push(`Component: ${name}`);
    parts.push(`Type: ${type}`);
    parts.push(`Tag: ${el.tag}`);
    if (el.id) parts.push(`ID: ${el.id}`);
    if (el.classes.length > 0) parts.push(`Classes: ${el.classes.join(", ")}`);
    parts.push(`Size: ${Math.round(el.rect.width)}x${Math.round(el.rect.height)}px`);
    parts.push(`Interactive: ${el.is_interactive}`);

    // Styles
    const s = el.styles;
    if (s.display) parts.push(`Display: ${s.display}`);
    if (s.background_color) parts.push(`Background: ${s.background_color}`);
    if (s.color) parts.push(`Color: ${s.color}`);
    if (s.border_radius) parts.push(`Border Radius: ${s.border_radius}`);
    if (s.font_size) parts.push(`Font Size: ${s.font_size}`);

    // Content
    const texts = this.extractTexts(el);
    if (texts.length > 0) {
      parts.push(`Text: ${texts.slice(0, 2).join(" | ")}`);
    }

    return parts.join("\n");
  }

  private buildAssetEmbedding(assets: PageAssets): string {
    // 安全获取数组长度
    const safeLength = (arr: unknown[] | undefined | null): number => arr?.length || 0;
    const safeArray = <T>(arr: T[] | undefined | null): T[] => arr || [];

    const parts: string[] = [];
    parts.push("Page Assets:");
    parts.push(`Images: ${safeLength(assets.images)}`);
    parts.push(`Fonts: ${safeLength(assets.fonts)}`);
    parts.push(`Scripts: ${safeLength(assets.scripts)}`);
    parts.push(`Stylesheets: ${safeLength(assets.stylesheets)}`);

    // Image URLs (AssetInfo 使用 url 而不是 src)
    const images = safeArray(assets.images);
    if (images.length > 0) {
      parts.push(`Image Sources: ${images.slice(0, 5).map((i) => i.url).join(", ")}`);
    }

    // Fonts
    const fonts = safeArray(assets.fonts);
    if (fonts.length > 0) {
      parts.push(`Font URLs: ${fonts.slice(0, 3).map((f) => f.url).join(", ")}`);
    }

    return parts.join("\n");
  }
}

// ==================== Export Function ====================

/**
 * 对 Playwright 提取结果进行 RAG 切片
 *
 * @param result - Playwright 提取结果
 * @returns 切片结果
 */
export function chunkForRAG(result: ExtractionResult): ChunkResult {
  const chunker = new RAGChunker(result);
  return chunker.chunk();
}
