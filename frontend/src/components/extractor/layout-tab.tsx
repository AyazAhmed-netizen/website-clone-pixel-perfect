"use client";

import React, { useState, useCallback, useMemo, useRef } from "react";
import { ZoomIn, ZoomOut, Maximize2, Move, Layers, X, MousePointer, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ElementInfo, PageMetadata, ComponentInfo, ComponentAnalysisData } from "@/types/playwright";

/**
 * Layout Tab Props
 */
interface LayoutTabProps {
  domTree: ElementInfo | null;
  metadata: PageMetadata | null;
  components?: ComponentAnalysisData | null;
  rawHtml?: string | null;
  onSelectElement?: (element: ElementInfo) => void;
  onSelectComponent?: (component: ComponentInfo) => void;
}

/**
 * Find element's position in raw HTML by searching for its selector/tag pattern
 * Returns line numbers and character positions
 */
function findElementInRawHtml(
  element: ElementInfo,
  rawHtml: string | null | undefined
): { startLine: number; endLine: number; charStart: number; charEnd: number } | null {
  if (!rawHtml || !element) return null;

  try {
    // Build search pattern based on element's characteristics
    let searchPattern = `<${element.tag}`;

    // Add id if exists
    if (element.id) {
      searchPattern = `<${element.tag}[^>]*id=["']${element.id}["']`;
    } else if (element.classes && element.classes.length > 0) {
      // Search for first class
      searchPattern = `<${element.tag}[^>]*class=["'][^"']*${element.classes[0]}[^"']*["']`;
    }

    const regex = new RegExp(searchPattern, 'i');
    const match = rawHtml.match(regex);

    if (!match || match.index === undefined) {
      // Fallback: just search for the tag
      const simpleMatch = rawHtml.indexOf(`<${element.tag}`);
      if (simpleMatch === -1) return null;

      const charStart = simpleMatch;
      const lines = rawHtml.substring(0, charStart).split('\n');
      const startLine = lines.length;

      return {
        startLine,
        endLine: startLine,
        charStart,
        charEnd: charStart + 100,
      };
    }

    const charStart = match.index;

    // Find closing tag or estimate end
    const closingTag = `</${element.tag}>`;
    let charEnd = rawHtml.indexOf(closingTag, charStart);
    if (charEnd === -1) {
      charEnd = charStart + 500; // Estimate
    } else {
      charEnd += closingTag.length;
    }

    // Calculate line numbers
    const beforeStart = rawHtml.substring(0, charStart);
    const startLine = beforeStart.split('\n').length;

    const beforeEnd = rawHtml.substring(0, charEnd);
    const endLine = beforeEnd.split('\n').length;

    return { startLine, endLine, charStart, charEnd };
  } catch {
    return null;
  }
}

/**
 * Collect all elements from DOM tree into a flat array
 */
function collectAllElements(element: ElementInfo | null): ElementInfo[] {
  if (!element) return [];

  const elements: ElementInfo[] = [element];

  if (element.children) {
    for (const child of element.children) {
      elements.push(...collectAllElements(child));
    }
  }

  return elements;
}

/**
 * Find all elements that contain a given point
 */
function findElementsAtPoint(
  x: number,
  y: number,
  allElements: ElementInfo[]
): ElementInfo[] {
  return allElements.filter(el => {
    const rect = el.rect;
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      x >= rect.x &&
      x <= rect.x + rect.width &&
      y >= rect.y &&
      y <= rect.y + rect.height
    );
  }).sort((a, b) => {
    // Sort by area (smallest first = most nested)
    const areaA = a.rect.width * a.rect.height;
    const areaB = b.rect.width * b.rect.height;
    return areaA - areaB;
  });
}

/**
 * Component Type Colors
 * Simplified - all sections use the same color palette cycling
 * No more semantic types (header, footer, testimonial, etc.)
 */
const COMPONENT_TYPE_COLORS: Record<string, { border: string; text: string; dot: string }> = {
  // All sections use this as fallback
  section: { border: "border-purple-400", text: "text-purple-400", dot: "bg-purple-400" },
};

/**
 * Section Color Palette
 * Different colors for each section to improve visual distinction
 * Cycles through these colors for section_1, section_2, etc.
 */
const SECTION_COLOR_PALETTE = [
  { border: "border-purple-400", text: "text-purple-400", dot: "bg-purple-400" },
  { border: "border-teal-400", text: "text-teal-400", dot: "bg-teal-400" },
  { border: "border-indigo-400", text: "text-indigo-400", dot: "bg-indigo-400" },
  { border: "border-emerald-400", text: "text-emerald-400", dot: "bg-emerald-400" },
  { border: "border-violet-400", text: "text-violet-400", dot: "bg-violet-400" },
  { border: "border-lime-400", text: "text-lime-400", dot: "bg-lime-400" },
  { border: "border-sky-400", text: "text-sky-400", dot: "bg-sky-400" },
  { border: "border-fuchsia-400", text: "text-fuchsia-400", dot: "bg-fuchsia-400" },
  { border: "border-rose-400", text: "text-rose-400", dot: "bg-rose-400" },
  { border: "border-amber-400", text: "text-amber-400", dot: "bg-amber-400" },
];

/**
 * Get section color by index
 * Cycles through the palette for visual distinction
 */
function getSectionColor(sectionIndex: number) {
  return SECTION_COLOR_PALETTE[sectionIndex % SECTION_COLOR_PALETTE.length];
}

/**
 * Extract section number from component name
 * e.g., "section_1" -> 1, "section_2" -> 2, "section_10" -> 10
 * Returns the actual section number (1-based)
 */
function extractSectionIndex(name: string): number {
  const match = name.match(/section_(\d+)/);
  if (match) {
    return parseInt(match[1], 10);  // Return 1-based number directly
  }
  return 0;  // 0 means not matched
}

/**
 * DOM Tag Colors (existing logic)
 */
const TAG_COLORS: Record<string, string> = {
  header: "bg-blue-500/30 border-blue-500",
  nav: "bg-cyan-500/30 border-cyan-500",
  main: "bg-green-500/30 border-green-500",
  section: "bg-purple-500/30 border-purple-500",
  article: "bg-indigo-500/30 border-indigo-500",
  aside: "bg-orange-500/30 border-orange-500",
  footer: "bg-pink-500/30 border-pink-500",
  div: "bg-neutral-500/20 border-neutral-400",
  form: "bg-yellow-500/30 border-yellow-500",
  button: "bg-red-500/30 border-red-500",
  a: "bg-blue-400/30 border-blue-400",
  img: "bg-emerald-500/30 border-emerald-500",
  default: "bg-neutral-400/20 border-neutral-300",
};

/**
 * Get element color class
 */
function getElementColor(tag: string): string {
  return TAG_COLORS[tag.toLowerCase()] || TAG_COLORS.default;
}

/**
 * Layout Box Component
 * Recursively render DOM layout boxes
 */
function LayoutBox({
  element,
  scale,
  offset,
  minSize,
  onSelect,
  selectedElement,
  canvasRef,
}: {
  element: ElementInfo;
  scale: number;
  offset: { x: number; y: number };
  minSize: number;
  onSelect: (el: ElementInfo, clickX?: number, clickY?: number) => void;
  selectedElement: ElementInfo | null;
  canvasRef: React.RefObject<HTMLDivElement | null>;
}) {
  const { rect, tag, children, id, classes } = element;

  // Calculate scaled position and size
  const x = (rect.x + offset.x) * scale;
  const y = (rect.y + offset.y) * scale;
  const width = Math.max(rect.width * scale, minSize);
  const height = Math.max(rect.height * scale, minSize);

  // Only render elements with size
  if (rect.width <= 0 || rect.height <= 0) {
    return null;
  }

  // Ignore very small elements
  if (width < 2 || height < 2) {
    return null;
  }

  const isSelected = selectedElement?.xpath === element.xpath;
  const colorClass = getElementColor(tag);

  // Generate label text
  const label =
    tag +
    (id ? `#${id}` : "") +
    (classes.length > 0 ? `.${classes[0]}` : "");

  return (
    <>
      {/* Current element box */}
      <div
        className={cn(
          "absolute border cursor-pointer transition-all duration-150",
          colorClass,
          isSelected && "ring-2 ring-purple-500 z-50"
        )}
        style={{
          left: x,
          top: y,
          width,
          height,
        }}
        onClick={(e) => {
          e.stopPropagation();

          // Calculate actual mouse position in original page coordinates
          const canvas = canvasRef?.current;
          if (canvas) {
            const canvasRect = canvas.getBoundingClientRect();
            const scrollLeft = canvas.scrollLeft;
            const scrollTop = canvas.scrollTop;

            // Mouse position relative to canvas (including scroll)
            const mouseX = e.clientX - canvasRect.left + scrollLeft;
            const mouseY = e.clientY - canvasRect.top + scrollTop;

            // Convert to original page coordinates (reverse scale and offset)
            const originalX = (mouseX / scale) - offset.x;
            const originalY = (mouseY / scale) - offset.y;

            onSelect(element, originalX, originalY);
          } else {
            // Fallback to element center if canvas ref not available
            onSelect(element, rect.x + rect.width / 2, rect.y + rect.height / 2);
          }
        }}
        title={label}
      >
        {/* Label (only show on large enough elements) */}
        {width > 60 && height > 20 && (
          <span
            className={cn(
              "absolute top-0 left-0 px-1 text-xs truncate",
              "bg-black/50 text-white rounded-br",
              "max-w-full"
            )}
            style={{ fontSize: Math.min(10, height / 2) }}
          >
            {label.substring(0, Math.floor(width / 6))}
          </span>
        )}
      </div>

      {/* Recursively render children */}
      {children.map((child, index) => (
        <LayoutBox
          key={child.xpath || index}
          element={child}
          scale={scale}
          offset={offset}
          minSize={minSize}
          onSelect={onSelect}
          selectedElement={selectedElement}
          canvasRef={canvasRef}
        />
      ))}
    </>
  );
}

/**
 * Component Overlay Box
 * Render semantic component regions as dashed border overlay (no fill)
 */
function ComponentOverlay({
  component,
  scale,
  offset,
  isSelected,
  onClick,
}: {
  component: ComponentInfo;
  scale: number;
  offset: { x: number; y: number };
  isSelected: boolean;
  onClick?: (component: ComponentInfo) => void;
}) {
  const { rect, type, name } = component;

  // Calculate scaled position and size
  const x = (rect.x + offset.x) * scale;
  const y = (rect.y + offset.y) * scale;
  const width = Math.max(rect.width * scale, 20);
  const height = Math.max(rect.height * scale, 20);

  // Get colors - all sections use color palette cycling
  const sectionNum = extractSectionIndex(name);  // 1-based section number
  const colors = getSectionColor(sectionNum > 0 ? sectionNum - 1 : 0);  // Convert to 0-based for color palette

  // Display name - unified section naming
  const displayName = `Section ${sectionNum > 0 ? sectionNum : 1}`;

  // Get token estimate - show exact number if < 1K, otherwise show ~XK
  const estimatedTokens = component.code_location?.estimated_tokens;
  const tokenLabel = estimatedTokens
    ? estimatedTokens >= 1000
      ? `~${Math.round(estimatedTokens / 1000)}K`
      : `~${estimatedTokens}`
    : null;

  return (
    <div
      className={cn(
        "absolute border-2 border-dashed transition-all duration-200",
        onClick ? "cursor-pointer hover:border-[3px] pointer-events-auto" : "pointer-events-none",
        colors.border,
        isSelected && "border-solid border-[3px] z-50"
      )}
      style={{
        left: x,
        top: y,
        width,
        height,
      }}
      onClick={(e) => {
        if (onClick) {
          e.stopPropagation();
          onClick(component);
        }
      }}
      title={`${displayName} - ${Math.round(rect.width)}×${Math.round(rect.height)}px${tokenLabel ? ` - ${tokenLabel} tokens` : ''} - Click to view in Components tab`}
    >
      {/* Component label - small tag at top-left corner */}
      <div
        className={cn(
          "absolute -top-3 left-2 px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap flex items-center gap-1",
          "bg-neutral-900/90 dark:bg-neutral-800/90",
          colors.text
        )}
      >
        {displayName}
        {tokenLabel && (
          <span className="px-1 py-0.5 rounded text-[8px] bg-neutral-700/50 text-neutral-400">
            {tokenLabel}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Layout Tab Component
 * Visual layout representation with component overlay
 *
 * Features:
 * - Visualize page layout
 * - Zoom and pan controls
 * - Click to select elements
 * - Color-coded element types
 * - Component overlay with filtering
 */
export function LayoutTab({
  domTree,
  metadata,
  components,
  rawHtml,
  onSelectElement,
  onSelectComponent,
}: LayoutTabProps) {
  // Zoom level
  const [scale, setScale] = useState(0.3);
  // Selected element
  const [selectedElement, setSelectedElement] = useState<ElementInfo | null>(null);
  // Selected component
  const [selectedComponent, setSelectedComponent] = useState<ComponentInfo | null>(null);
  // View offset
  const [viewOffset, setViewOffset] = useState({ x: 20, y: 20 });
  // Show component overlay
  const [showComponentOverlay, setShowComponentOverlay] = useState(true);
  // Component filters - simplified, all sections use individual filters
  const [componentFilters, setComponentFilters] = useState<Record<string, boolean>>({
    section: true,  // Default filter for all sections
  });

  // State for cycling through overlapping elements
  const [elementsAtClick, setElementsAtClick] = useState<ElementInfo[]>([]);
  const [cycleIndex, setCycleIndex] = useState(0);
  const lastClickPosition = useRef<{ x: number; y: number } | null>(null);

  // Canvas reference for coordinate calculation
  const canvasRef = useRef<HTMLDivElement>(null);

  // Collect all elements for click detection
  const allElements = useMemo(() => collectAllElements(domTree), [domTree]);

  // Find element position in raw HTML
  const elementSourceLocation = useMemo(() => {
    if (!selectedElement || !rawHtml) return null;
    return findElementInRawHtml(selectedElement, rawHtml);
  }, [selectedElement, rawHtml]);

  // Calculate content area
  const containerWidth = metadata?.page_width || 1920;
  const containerHeight = metadata?.page_height || 1080;

  /**
   * Get filtered components
   * All sections are filtered individually by their unique id
   */
  const filteredComponents = useMemo(() => {
    if (!components?.components) return [];
    return components.components.filter(comp => {
      // All sections are filtered individually by their unique key
      const filterKey = `section-${comp.id}`;
      return componentFilters[filterKey] !== false;
    });
  }, [components, componentFilters]);

  /**
   * Handle element selection with cycling support for overlapping elements
   */
  const handleSelectElement = useCallback(
    (element: ElementInfo, clickX?: number, clickY?: number) => {
      // If we have click coordinates, check for cycling
      if (clickX !== undefined && clickY !== undefined) {
        const lastPos = lastClickPosition.current;
        const isSamePosition = lastPos &&
          Math.abs(lastPos.x - clickX) < 10 &&
          Math.abs(lastPos.y - clickY) < 10;

        if (isSamePosition && elementsAtClick.length > 1) {
          // Same position - cycle to next element
          const nextIndex = (cycleIndex + 1) % elementsAtClick.length;
          setCycleIndex(nextIndex);
          const nextElement = elementsAtClick[nextIndex];
          setSelectedElement(nextElement);
          setSelectedComponent(null);
          onSelectElement?.(nextElement);
          return;
        }

        // New position - find all elements at this point
        const elements = findElementsAtPoint(clickX, clickY, allElements);
        setElementsAtClick(elements);
        setCycleIndex(0);
        lastClickPosition.current = { x: clickX, y: clickY };

        if (elements.length > 0) {
          setSelectedElement(elements[0]);
          setSelectedComponent(null);
          onSelectElement?.(elements[0]);
        }
      } else {
        // Direct selection without coordinates
        setSelectedElement(element);
        setSelectedComponent(null);
        setElementsAtClick([element]);
        setCycleIndex(0);
        lastClickPosition.current = null;
        onSelectElement?.(element);
      }
    },
    [onSelectElement, allElements, elementsAtClick, cycleIndex]
  );

  /**
   * Clear all selections
   */
  const handleClearSelection = useCallback(() => {
    setSelectedElement(null);
    setSelectedComponent(null);
    setElementsAtClick([]);
    setCycleIndex(0);
    lastClickPosition.current = null;
  }, []);

  // Copy feedback state
  const [copySuccess, setCopySuccess] = useState(false);

  /**
   * Copy selected element info to clipboard
   */
  const handleCopyElementInfo = useCallback(() => {
    if (!selectedElement) return;

    const info: string[] = [];
    info.push(`Tag: <${selectedElement.tag}>`);
    if (selectedElement.id) info.push(`ID: #${selectedElement.id}`);
    if (selectedElement.classes?.length) info.push(`Classes: ${selectedElement.classes.map(c => '.' + c).join(' ')}`);
    info.push(`Size: ${Math.round(selectedElement.rect.width)}×${Math.round(selectedElement.rect.height)}`);
    info.push(`Position: (${Math.round(selectedElement.rect.x)}, ${Math.round(selectedElement.rect.y)})`);
    if (selectedElement.selector) info.push(`Selector: ${selectedElement.selector}`);
    if (selectedElement.xpath) info.push(`XPath: ${selectedElement.xpath}`);
    if (elementSourceLocation) {
      info.push(`Source Lines: ${elementSourceLocation.startLine}-${elementSourceLocation.endLine}`);
      info.push(`Source Chars: ${elementSourceLocation.charStart}-${elementSourceLocation.charEnd}`);
    }

    navigator.clipboard.writeText(info.join('\n')).then(() => {
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    });
  }, [selectedElement, elementSourceLocation]);

  /**
   * Toggle component filter
   */
  const toggleFilter = (type: string) => {
    setComponentFilters(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  /**
   * Zoom controls
   */
  const handleZoomIn = () => setScale((s) => Math.min(s * 1.2, 2));
  const handleZoomOut = () => setScale((s) => Math.max(s / 1.2, 0.1));
  const handleResetZoom = () => {
    setScale(0.3);
    setViewOffset({ x: 20, y: 20 });
  };

  if (!domTree || !metadata) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No layout data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Control Bar */}
      <div
        className={cn(
          "flex flex-col gap-3 p-3 rounded-lg border",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        {/* Top row: Zoom controls and info */}
        <div className="flex items-center justify-between">
          {/* Zoom Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleZoomOut}
              className={cn(
                "p-2 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800",
                "text-neutral-600 dark:text-neutral-400"
              )}
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="text-sm text-neutral-600 dark:text-neutral-400 w-16 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className={cn(
                "p-2 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800",
                "text-neutral-600 dark:text-neutral-400"
              )}
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              onClick={handleResetZoom}
              className={cn(
                "p-2 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800",
                "text-neutral-600 dark:text-neutral-400"
              )}
              title="Reset View"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>

          {/* Component Overlay Toggle */}
          {components && (
            <button
              onClick={() => setShowComponentOverlay(!showComponentOverlay)}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                showComponentOverlay
                  ? "bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300"
                  : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              )}
            >
              <Layers className="h-4 w-4" />
              Components
            </button>
          )}

          {/* Info */}
          <div className="text-sm text-neutral-500">
            <Move className="h-4 w-4 inline mr-1" />
            Click to select
          </div>
        </div>

        {/* Component Filters (when overlay is enabled) */}
        {showComponentOverlay && components && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-700">
            <span className="text-xs text-neutral-500 mr-1">Show:</span>

            {/* Select All / Deselect All buttons */}
            <button
              onClick={() => {
                const newFilters: Record<string, boolean> = {};
                // Enable all section filters
                components.components?.forEach(comp => {
                  newFilters[`section-${comp.id}`] = true;
                });
                setComponentFilters(prev => ({ ...prev, ...newFilters }));
              }}
              className="px-1.5 py-0.5 rounded text-[10px] font-medium text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              title="Select All"
            >
              All
            </button>
            <button
              onClick={() => {
                const newFilters: Record<string, boolean> = {};
                // Disable all section filters
                components.components?.forEach(comp => {
                  newFilters[`section-${comp.id}`] = false;
                });
                setComponentFilters(prev => ({ ...prev, ...newFilters }));
              }}
              className="px-1.5 py-0.5 rounded text-[10px] font-medium text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              title="Deselect All"
            >
              None
            </button>

            <span className="w-px h-4 bg-neutral-300 dark:bg-neutral-600 mx-1" />

            {/* All sections shown as individual buttons */}
            {components.components?.map((sectionComp, index) => {
              const sectionNum = extractSectionIndex(sectionComp.name);  // 1-based number
              const colors = getSectionColor(index);  // Use index for color cycling
              const filterKey = `section-${sectionComp.id}`;
              const isActive = componentFilters[filterKey] !== false;

              // Token info for this specific section
              const tokens = sectionComp.code_location?.estimated_tokens || 0;
              const tokenLabel = tokens >= 1000
                ? `${Math.round(tokens / 1000)}K`
                : `${tokens}`;

              return (
                <button
                  key={sectionComp.id}
                  onClick={() => {
                    setComponentFilters(prev => ({
                      ...prev,
                      [filterKey]: !prev[filterKey]
                    }));
                  }}
                  className={cn(
                    "flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all border",
                    isActive
                      ? `${colors.border} border-dashed ${colors.text}`
                      : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 border-transparent"
                  )}
                  title={`${sectionComp.name}: ${tokens.toLocaleString()} tokens`}
                >
                  <span
                    className={cn(
                      "w-2 h-2 rounded-sm",
                      isActive ? colors.dot : "bg-neutral-400"
                    )}
                  />
                  S{sectionNum > 0 ? sectionNum : index + 1}
                  <span className="opacity-50 text-[10px]">{tokenLabel}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* DOM Tag Legend (when overlay is disabled) */}
        {!showComponentOverlay && (
          <div className="flex items-center gap-3 text-xs pt-2 border-t border-neutral-200 dark:border-neutral-700">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-blue-500/30 border border-blue-500" />
              header
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-green-500/30 border border-green-500" />
              main
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-purple-500/30 border border-purple-500" />
              section
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-pink-500/30 border border-pink-500" />
              footer
            </span>
          </div>
        )}
      </div>

      {/* Layout Canvas */}
      <div
        ref={canvasRef}
        className={cn(
          "relative overflow-auto rounded-lg border",
          "bg-neutral-100 dark:bg-neutral-950",
          "border-neutral-200 dark:border-neutral-700"
        )}
        style={{ height: "calc(100vh - 200px)", minHeight: "500px" }}
        onClick={(e) => {
          // Clear selection when clicking on canvas background (not on elements)
          if (e.target === e.currentTarget || (e.target as HTMLElement).classList.contains('relative')) {
            handleClearSelection();
          }
        }}
      >
        {/* Content Area */}
        <div
          className="relative"
          style={{
            width: containerWidth * scale + 40,
            height: containerHeight * scale + 40,
            minWidth: "100%",
            minHeight: "100%",
          }}
        >
          {/* Page Background */}
          <div
            className="absolute bg-white dark:bg-neutral-900 shadow-lg"
            style={{
              left: viewOffset.x,
              top: viewOffset.y,
              width: containerWidth * scale,
              height: containerHeight * scale,
            }}
          />

          {/* Layout Boxes (DOM tree) */}
          <LayoutBox
            element={domTree}
            scale={scale}
            offset={viewOffset}
            minSize={2}
            onSelect={handleSelectElement}
            selectedElement={selectedElement}
            canvasRef={canvasRef}
          />

          {/* Component Overlay Layer */}
          {showComponentOverlay && filteredComponents.length > 0 && (
            <div className="absolute inset-0">
              {filteredComponents.map((component) => (
                <ComponentOverlay
                  key={component.id}
                  component={component}
                  scale={scale}
                  offset={viewOffset}
                  isSelected={selectedComponent?.id === component.id}
                  onClick={onSelectComponent}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Selected Element Info */}
      {selectedElement && !selectedComponent && (
        <div
          className={cn(
            "p-4 rounded-lg border",
            "bg-white dark:bg-neutral-900",
            "border-neutral-200 dark:border-neutral-700"
          )}
        >
          {/* Header with title and clear button */}
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
              Selected Element
            </h4>
            <div className="flex items-center gap-2">
              {/* Cycling indicator */}
              {elementsAtClick.length > 1 && (
                <span className="flex items-center gap-1 px-2 py-1 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 text-xs">
                  <MousePointer className="h-3 w-3" />
                  {cycleIndex + 1}/{elementsAtClick.length}
                  <span className="text-purple-400 dark:text-purple-500 ml-1">(click to cycle)</span>
                </span>
              )}
              {/* Copy button */}
              <button
                onClick={handleCopyElementInfo}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                  copySuccess
                    ? "bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400"
                    : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400"
                )}
                title="Copy Element Info"
              >
                {copySuccess ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copySuccess ? "Copied!" : "Copy"}
              </button>
              {/* Clear button */}
              <button
                onClick={handleClearSelection}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                  "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
                  "hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 dark:hover:text-red-400"
                )}
                title="Clear Selection"
              >
                <X className="h-3 w-3" />
                Clear
              </button>
            </div>
          </div>

          {/* Basic info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-neutral-500">Tag:</span>
              <span className="ml-2 font-mono text-purple-600 dark:text-purple-400">
                &lt;{selectedElement.tag}&gt;
              </span>
            </div>
            {selectedElement.id && (
              <div>
                <span className="text-neutral-500">ID:</span>
                <span className="ml-2 font-mono">#{selectedElement.id}</span>
              </div>
            )}
            <div>
              <span className="text-neutral-500">Size:</span>
              <span className="ml-2">
                {Math.round(selectedElement.rect.width)}×
                {Math.round(selectedElement.rect.height)}
              </span>
            </div>
            <div>
              <span className="text-neutral-500">Position:</span>
              <span className="ml-2">
                ({Math.round(selectedElement.rect.x)},{" "}
                {Math.round(selectedElement.rect.y)})
              </span>
            </div>
          </div>

          {/* Additional info row */}
          <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {/* Selector */}
            {selectedElement.selector && (
              <div className="col-span-2">
                <span className="text-neutral-500">Selector:</span>
                <span className="ml-2 font-mono text-xs text-neutral-700 dark:text-neutral-300 break-all">
                  {selectedElement.selector}
                </span>
              </div>
            )}

            {/* XPath */}
            {selectedElement.xpath && (
              <div className="col-span-2">
                <span className="text-neutral-500">XPath:</span>
                <span className="ml-2 font-mono text-xs text-neutral-700 dark:text-neutral-300 break-all">
                  {selectedElement.xpath}
                </span>
              </div>
            )}
          </div>

          {/* Source location info */}
          {elementSourceLocation && (
            <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-neutral-500">Source Location</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-neutral-500">Lines:</span>
                  <span className="ml-2 font-mono text-green-600 dark:text-green-400">
                    {elementSourceLocation.startLine}
                    {elementSourceLocation.endLine !== elementSourceLocation.startLine &&
                      `-${elementSourceLocation.endLine}`}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500">Chars:</span>
                  <span className="ml-2 font-mono text-xs text-neutral-600 dark:text-neutral-400">
                    {elementSourceLocation.charStart.toLocaleString()}-{elementSourceLocation.charEnd.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Classes info */}
          {selectedElement.classes && selectedElement.classes.length > 0 && (
            <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700">
              <span className="text-xs text-neutral-500">Classes:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {selectedElement.classes.map((cls, i) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 rounded text-xs font-mono bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
                  >
                    .{cls}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Selected Component Info */}
      {selectedComponent && (
        <div
          className={cn(
            "p-4 rounded-lg border-2 border-dashed",
            "bg-white dark:bg-neutral-900",
            COMPONENT_TYPE_COLORS[selectedComponent.type]?.border || "border-neutral-400"
          )}
        >
          {/* Header with title and clear button */}
          <div className="flex items-center justify-between mb-3">
            <h4 className={cn(
              "text-sm font-medium",
              COMPONENT_TYPE_COLORS[selectedComponent.type]?.text || "text-neutral-400"
            )}>
              Selected Component
            </h4>
            <button
              onClick={handleClearSelection}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
                "hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 dark:hover:text-red-400"
              )}
              title="Clear Selection"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-neutral-500">Type:</span>
              <span className={cn(
                "ml-2 px-2 py-0.5 rounded text-xs font-medium border border-dashed",
                COMPONENT_TYPE_COLORS[selectedComponent.type]?.border || "border-neutral-400",
                COMPONENT_TYPE_COLORS[selectedComponent.type]?.text || "text-neutral-400"
              )}>
                {selectedComponent.type}
              </span>
            </div>
            <div>
              <span className="text-neutral-500">Name:</span>
              <span className="ml-2 font-medium text-neutral-800 dark:text-neutral-200">
                {selectedComponent.name}
              </span>
            </div>
            <div>
              <span className="text-neutral-500">Size:</span>
              <span className="ml-2">
                {Math.round(selectedComponent.rect.width)}×
                {Math.round(selectedComponent.rect.height)}px
              </span>
            </div>
            <div>
              <span className="text-neutral-500">Position:</span>
              <span className="ml-2">
                ({Math.round(selectedComponent.rect.x)},{" "}
                {Math.round(selectedComponent.rect.y)})
              </span>
            </div>
          </div>
          {/* Additional component info */}
          <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-neutral-500">Links:</span>
              <span className="ml-2">{selectedComponent.internal_links?.length || 0} internal</span>
            </div>
            <div>
              <span className="text-neutral-500">Images:</span>
              <span className="ml-2">{selectedComponent.images?.length || 0}</span>
            </div>
            {selectedComponent.code_location && selectedComponent.code_location.char_start > 0 && selectedComponent.code_location.char_end > 0 && (
              <div>
                <span className="text-neutral-500">Chars:</span>
                <span className="ml-2 font-mono text-xs">
                  {selectedComponent.code_location.char_start.toLocaleString()}-{selectedComponent.code_location.char_end.toLocaleString()}
                </span>
              </div>
            )}
            {selectedComponent.code_location?.estimated_tokens != null && (
              <div>
                <span className="text-neutral-500">Tokens:</span>
                <span className="ml-2 px-1.5 py-0.5 rounded text-xs font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300">
                  {selectedComponent.code_location.estimated_tokens >= 1000
                    ? `~${Math.round(selectedComponent.code_location.estimated_tokens / 1000)}K`
                    : `~${selectedComponent.code_location.estimated_tokens}`}
                </span>
              </div>
            )}
          </div>
          {/* Split part indicator */}
          {selectedComponent.code_location?.is_split_part && (
            <div className="mt-2 px-2 py-1 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs">
              ℹ️ This is part {selectedComponent.code_location.part_index} of a split component (parent: {selectedComponent.code_location.parent_id})
            </div>
          )}
        </div>
      )}
    </div>
  );
}
