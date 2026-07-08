"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronRight,
  ChevronDown,
  Search,
  Filter,
  Eye,
  EyeOff,
  MousePointer2,
  Box,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ElementInfo, ElementFilterType } from "@/types/playwright";
import { ELEMENT_FILTERS } from "@/types/playwright";

/**
 * Elements Tab Props
 */
interface ElementsTabProps {
  domTree: ElementInfo | null;
  onSelectElement?: (element: ElementInfo) => void;
  selectedElement?: ElementInfo | null;
}

/**
 * Tree Node Component
 * DOM 树节点组件
 */
function TreeNode({
  element,
  depth,
  onSelect,
  selectedElement,
  expandedNodes,
  toggleExpand,
  filterTags,
}: {
  element: ElementInfo;
  depth: number;
  onSelect: (el: ElementInfo) => void;
  selectedElement: ElementInfo | null;
  expandedNodes: Set<string>;
  toggleExpand: (xpath: string) => void;
  filterTags: string[];
}) {
  const xpath = element.xpath || "";
  const isExpanded = expandedNodes.has(xpath);
  const isSelected = selectedElement?.xpath === xpath;
  const hasChildren = element.children.length > 0;

  // 过滤检查
  const matchesFilter =
    filterTags.length === 0 || filterTags.includes(element.tag.toLowerCase());

  // 过滤后的子元素
  const filteredChildren = useMemo(() => {
    if (filterTags.length === 0) return element.children;
    return element.children.filter(
      (child) =>
        filterTags.includes(child.tag.toLowerCase()) ||
        hasMatchingDescendant(child, filterTags)
    );
  }, [element.children, filterTags]);

  // 如果不匹配且没有匹配的后代，不渲染
  if (!matchesFilter && filteredChildren.length === 0) {
    return null;
  }

  // 生成标签显示文本
  const tagDisplay = (
    <>
      <span className="text-blue-600 dark:text-blue-400">&lt;{element.tag}</span>
      {element.id && (
        <span className="text-orange-600 dark:text-orange-400">
          {" "}
          id=&quot;{element.id}&quot;
        </span>
      )}
      {element.classes.length > 0 && (
        <span className="text-green-600 dark:text-green-400">
          {" "}
          class=&quot;{element.classes.slice(0, 3).join(" ")}
          {element.classes.length > 3 ? "..." : ""}&quot;
        </span>
      )}
      <span className="text-blue-600 dark:text-blue-400">&gt;</span>
    </>
  );

  return (
    <div className="select-none">
      {/* Node Row */}
      <div
        className={cn(
          "flex items-center gap-1 py-1 px-2 rounded cursor-pointer",
          "hover:bg-neutral-100 dark:hover:bg-neutral-800",
          isSelected && "bg-purple-100 dark:bg-purple-900/30"
        )}
        style={{ paddingLeft: depth * 16 + 8 }}
        onClick={() => onSelect(element)}
      >
        {/* Expand/Collapse Toggle */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleExpand(xpath);
            }}
            className="p-0.5 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3 text-neutral-500" />
            ) : (
              <ChevronRight className="h-3 w-3 text-neutral-500" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {/* Tag Content */}
        <code className="text-xs font-mono flex-1 truncate">{tagDisplay}</code>

        {/* Badges */}
        <div className="flex items-center gap-1">
          {/* Children Count */}
          {element.children_count > 0 && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-200 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400">
              {element.children_count}
            </span>
          )}

          {/* Visibility */}
          {!element.is_visible && (
            <EyeOff className="h-3 w-3 text-neutral-400" title="Hidden" />
          )}

          {/* Interactive */}
          {element.is_interactive && (
            <MousePointer2
              className="h-3 w-3 text-purple-500"
              title="Interactive"
            />
          )}
        </div>
      </div>

      {/* Children */}
      {isExpanded &&
        filteredChildren.map((child, index) => (
          <TreeNode
            key={child.xpath || index}
            element={child}
            depth={depth + 1}
            onSelect={onSelect}
            selectedElement={selectedElement}
            expandedNodes={expandedNodes}
            toggleExpand={toggleExpand}
            filterTags={filterTags}
          />
        ))}
    </div>
  );
}

/**
 * 检查元素是否有匹配的后代
 */
function hasMatchingDescendant(element: ElementInfo, filterTags: string[]): boolean {
  for (const child of element.children) {
    if (filterTags.includes(child.tag.toLowerCase())) {
      return true;
    }
    if (hasMatchingDescendant(child, filterTags)) {
      return true;
    }
  }
  return false;
}

/**
 * 统计元素数量
 */
function countTotalElements(element: ElementInfo | null): number {
  if (!element) return 0;
  let count = 1;
  for (const child of element.children) {
    count += countTotalElements(child);
  }
  return count;
}

/**
 * Elements Tab Component
 * DOM 树 Tab 组件
 *
 * 功能：
 * - 可展开/折叠的 DOM 树视图
 * - 元素搜索
 * - 按类型筛选
 * - 点击选择元素查看详情
 */
export function ElementsTab({
  domTree,
  onSelectElement,
  selectedElement,
}: ElementsTabProps) {
  // 搜索关键词
  const [searchQuery, setSearchQuery] = useState("");

  // 当前筛选类型
  const [filterType, setFilterType] = useState<ElementFilterType>("all");

  // 展开的节点
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(
    new Set(["/body"])
  );

  // 内部选中状态
  const [internalSelected, setInternalSelected] = useState<ElementInfo | null>(
    null
  );

  const currentSelected = selectedElement ?? internalSelected;

  // 筛选标签
  const filterTags = useMemo(() => {
    return ELEMENT_FILTERS[filterType].tags;
  }, [filterType]);

  // 总元素数
  const totalElements = useMemo(() => countTotalElements(domTree), [domTree]);

  /**
   * 切换节点展开状态
   */
  const toggleExpand = useCallback((xpath: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(xpath)) {
        next.delete(xpath);
      } else {
        next.add(xpath);
      }
      return next;
    });
  }, []);

  /**
   * 展开所有节点
   */
  const expandAll = useCallback(() => {
    if (!domTree) return;

    const allXpaths = new Set<string>();
    const collect = (el: ElementInfo) => {
      if (el.xpath) allXpaths.add(el.xpath);
      el.children.forEach(collect);
    };
    collect(domTree);
    setExpandedNodes(allXpaths);
  }, [domTree]);

  /**
   * 折叠所有节点
   */
  const collapseAll = useCallback(() => {
    setExpandedNodes(new Set(["/body"]));
  }, []);

  /**
   * 处理元素选择
   */
  const handleSelectElement = useCallback(
    (element: ElementInfo) => {
      setInternalSelected(element);
      onSelectElement?.(element);
    },
    [onSelectElement]
  );

  if (!domTree) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No DOM data available
      </div>
    );
  }

  return (
    <div className="flex h-[600px] gap-4">
      {/* Tree Panel */}
      <div
        className={cn(
          "flex-1 flex flex-col rounded-lg border overflow-hidden",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        {/* Toolbar */}
        <div className="p-3 border-b border-neutral-200 dark:border-neutral-700 space-y-2">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search elements..."
              className={cn(
                "w-full pl-9 pr-4 py-2 text-sm rounded-lg border",
                "bg-neutral-50 dark:bg-neutral-800",
                "border-neutral-200 dark:border-neutral-700",
                "focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              )}
            />
          </div>

          {/* Filters & Actions */}
          <div className="flex items-center justify-between">
            {/* Filter Dropdown */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-neutral-400" />
              <select
                value={filterType}
                onChange={(e) =>
                  setFilterType(e.target.value as ElementFilterType)
                }
                className={cn(
                  "text-sm px-2 py-1 rounded border",
                  "bg-neutral-50 dark:bg-neutral-800",
                  "border-neutral-200 dark:border-neutral-700",
                  "focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                )}
              >
                {Object.entries(ELEMENT_FILTERS).map(([key, { label }]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={expandAll}
                className="text-xs px-2 py-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              >
                Expand All
              </button>
              <button
                onClick={collapseAll}
                className="text-xs px-2 py-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              >
                Collapse
              </button>
              <span className="text-xs text-neutral-400 ml-2">
                {totalElements} elements
              </span>
            </div>
          </div>
        </div>

        {/* Tree Content */}
        <div className="flex-1 overflow-auto p-2">
          <TreeNode
            element={domTree}
            depth={0}
            onSelect={handleSelectElement}
            selectedElement={currentSelected}
            expandedNodes={expandedNodes}
            toggleExpand={toggleExpand}
            filterTags={filterTags}
          />
        </div>
      </div>

      {/* Detail Panel */}
      <div
        className={cn(
          "w-80 rounded-lg border overflow-hidden",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        <div className="p-3 border-b border-neutral-200 dark:border-neutral-700">
          <h4 className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Element Details
          </h4>
        </div>

        {currentSelected ? (
          <div className="p-3 space-y-4 overflow-auto max-h-[550px]">
            {/* Tag Info */}
            <div>
              <h5 className="text-xs font-medium text-neutral-500 mb-1">Tag</h5>
              <code className="text-sm font-mono text-purple-600 dark:text-purple-400">
                &lt;{currentSelected.tag}&gt;
              </code>
            </div>

            {/* ID */}
            {currentSelected.id && (
              <div>
                <h5 className="text-xs font-medium text-neutral-500 mb-1">ID</h5>
                <code className="text-sm font-mono">#{currentSelected.id}</code>
              </div>
            )}

            {/* Classes */}
            {currentSelected.classes.length > 0 && (
              <div>
                <h5 className="text-xs font-medium text-neutral-500 mb-1">
                  Classes
                </h5>
                <div className="flex flex-wrap gap-1">
                  {currentSelected.classes.map((cls, i) => (
                    <span
                      key={i}
                      className="text-xs px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                    >
                      .{cls}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Position & Size */}
            <div>
              <h5 className="text-xs font-medium text-neutral-500 mb-1">
                Position & Size
              </h5>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                  <span className="text-neutral-500">X:</span>
                  <span className="ml-1 font-mono">
                    {Math.round(currentSelected.rect.x)}px
                  </span>
                </div>
                <div className="p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                  <span className="text-neutral-500">Y:</span>
                  <span className="ml-1 font-mono">
                    {Math.round(currentSelected.rect.y)}px
                  </span>
                </div>
                <div className="p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                  <span className="text-neutral-500">W:</span>
                  <span className="ml-1 font-mono">
                    {Math.round(currentSelected.rect.width)}px
                  </span>
                </div>
                <div className="p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                  <span className="text-neutral-500">H:</span>
                  <span className="ml-1 font-mono">
                    {Math.round(currentSelected.rect.height)}px
                  </span>
                </div>
              </div>
            </div>

            {/* Styles */}
            <div>
              <h5 className="text-xs font-medium text-neutral-500 mb-1">
                Computed Styles
              </h5>
              <div className="space-y-1 text-xs">
                {Object.entries(currentSelected.styles).map(([key, value]) => {
                  if (!value) return null;
                  return (
                    <div
                      key={key}
                      className="flex justify-between p-1.5 rounded bg-neutral-50 dark:bg-neutral-800"
                    >
                      <span className="text-neutral-500">
                        {key.replace(/_/g, "-")}:
                      </span>
                      <span className="font-mono text-neutral-700 dark:text-neutral-300 truncate max-w-[120px]">
                        {value}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Text Content */}
            {currentSelected.text_content && (
              <div>
                <h5 className="text-xs font-medium text-neutral-500 mb-1">
                  Text Content
                </h5>
                <p className="text-xs p-2 rounded bg-neutral-50 dark:bg-neutral-800 break-words">
                  {currentSelected.text_content}
                </p>
              </div>
            )}

            {/* Attributes */}
            {Object.keys(currentSelected.attributes).length > 0 && (
              <div>
                <h5 className="text-xs font-medium text-neutral-500 mb-1">
                  Attributes
                </h5>
                <div className="space-y-1 text-xs">
                  {Object.entries(currentSelected.attributes).map(
                    ([key, value]) => (
                      <div
                        key={key}
                        className="flex justify-between p-1.5 rounded bg-neutral-50 dark:bg-neutral-800"
                      >
                        <span className="text-orange-600 dark:text-orange-400">
                          {key}:
                        </span>
                        <span className="font-mono text-neutral-700 dark:text-neutral-300 truncate max-w-[120px]">
                          {value}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-[550px] text-neutral-400">
            <Box className="h-8 w-8 mb-2" />
            <p className="text-sm">Select an element</p>
          </div>
        )}
      </div>
    </div>
  );
}
