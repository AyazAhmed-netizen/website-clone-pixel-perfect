"use client";

import React, { useMemo } from "react";
import { Palette, Type, Layout, Box } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StyleSummary } from "@/types/playwright";

/**
 * Styles Tab Props
 */
interface StylesTabProps {
  styleSummary: StyleSummary | null;
}

/**
 * Color Swatch Component
 * 颜色色块组件
 */
function ColorSwatch({ color, count }: { color: string; count: number }) {
  // 检测是否是有效的颜色值
  const isValidColor = /^(#|rgb|hsl|transparent|inherit)/.test(color);

  return (
    <div
      className={cn(
        "flex items-center gap-2 p-2 rounded-lg",
        "bg-neutral-50 dark:bg-neutral-800"
      )}
    >
      {/* Color Preview */}
      <div
        className={cn(
          "w-8 h-8 rounded border border-neutral-300 dark:border-neutral-600",
          "flex-shrink-0"
        )}
        style={{
          backgroundColor: isValidColor ? color : "transparent",
          backgroundImage: !isValidColor
            ? "linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc)"
            : undefined,
          backgroundSize: "8px 8px",
          backgroundPosition: "0 0, 4px 4px",
        }}
      />
      {/* Color Value */}
      <div className="flex-1 min-w-0">
        <code className="text-xs font-mono text-neutral-700 dark:text-neutral-300 block truncate">
          {color}
        </code>
        <span className="text-xs text-neutral-400">{count} uses</span>
      </div>
    </div>
  );
}

/**
 * Stat Item Component
 * 统计项组件
 */
function StatItem({
  label,
  value,
  count,
}: {
  label: string;
  value: string;
  count: number;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between p-2 rounded-lg",
        "bg-neutral-50 dark:bg-neutral-800"
      )}
    >
      <code className="text-xs font-mono text-neutral-700 dark:text-neutral-300 truncate max-w-[200px]">
        {value}
      </code>
      <span className="text-xs text-neutral-400 ml-2 flex-shrink-0">
        {count}×
      </span>
    </div>
  );
}

/**
 * Section Component
 * 分区组件
 */
function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "p-4 rounded-lg border",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex items-center gap-2 mb-4">
        <Icon className="h-5 w-5 text-neutral-600 dark:text-neutral-400" />
        <h4 className="font-medium text-neutral-700 dark:text-neutral-300">
          {title}
        </h4>
      </div>
      {children}
    </div>
  );
}

/**
 * Styles Tab Component
 * 样式统计 Tab 组件
 *
 * 展示：
 * - 颜色使用统计
 * - 字体使用统计
 * - 间距使用统计
 * - 布局类型统计
 */
export function StylesTab({ styleSummary }: StylesTabProps) {
  // 排序后的数据
  const sortedData = useMemo(() => {
    if (!styleSummary) return null;

    const sortByCount = (obj: Record<string, number>) =>
      Object.entries(obj).sort((a, b) => b[1] - a[1]);

    return {
      colors: sortByCount(styleSummary.colors),
      backgroundColors: sortByCount(styleSummary.background_colors),
      fontFamilies: sortByCount(styleSummary.font_families),
      fontSizes: sortByCount(styleSummary.font_sizes),
      margins: sortByCount(styleSummary.margins),
      paddings: sortByCount(styleSummary.paddings),
      displayTypes: sortByCount(styleSummary.display_types),
      positionTypes: sortByCount(styleSummary.position_types),
    };
  }, [styleSummary]);

  if (!styleSummary || !sortedData) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No style data available
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Colors */}
      <Section icon={Palette} title="Text Colors">
        {sortedData.colors.length > 0 ? (
          <div className="grid grid-cols-2 gap-2">
            {sortedData.colors.slice(0, 12).map(([color, count]) => (
              <ColorSwatch key={color} color={color} count={count} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No colors found</p>
        )}
      </Section>

      {/* Background Colors */}
      <Section icon={Palette} title="Background Colors">
        {sortedData.backgroundColors.length > 0 ? (
          <div className="grid grid-cols-2 gap-2">
            {sortedData.backgroundColors.slice(0, 12).map(([color, count]) => (
              <ColorSwatch key={color} color={color} count={count} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No background colors found</p>
        )}
      </Section>

      {/* Font Families */}
      <Section icon={Type} title="Font Families">
        {sortedData.fontFamilies.length > 0 ? (
          <div className="space-y-2">
            {sortedData.fontFamilies.slice(0, 8).map(([font, count]) => (
              <div
                key={font}
                className={cn(
                  "p-3 rounded-lg",
                  "bg-neutral-50 dark:bg-neutral-800"
                )}
              >
                <p
                  className="text-sm text-neutral-700 dark:text-neutral-300 mb-1"
                  style={{ fontFamily: font }}
                >
                  The quick brown fox jumps over the lazy dog
                </p>
                <div className="flex items-center justify-between">
                  <code className="text-xs font-mono text-neutral-500 truncate max-w-[250px]">
                    {font}
                  </code>
                  <span className="text-xs text-neutral-400">{count} uses</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No fonts found</p>
        )}
      </Section>

      {/* Font Sizes */}
      <Section icon={Type} title="Font Sizes">
        {sortedData.fontSizes.length > 0 ? (
          <div className="space-y-2">
            {sortedData.fontSizes.slice(0, 10).map(([size, count]) => (
              <StatItem key={size} label="size" value={size} count={count} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No font sizes found</p>
        )}
      </Section>

      {/* Layout Types */}
      <Section icon={Layout} title="Display Types">
        {sortedData.displayTypes.length > 0 ? (
          <div className="space-y-2">
            {sortedData.displayTypes.map(([type, count]) => (
              <div
                key={type}
                className={cn(
                  "flex items-center justify-between p-2 rounded-lg",
                  "bg-neutral-50 dark:bg-neutral-800"
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-xs font-medium",
                      type === "flex" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                      type === "grid" && "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
                      type === "block" && "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                      type === "inline" && "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
                      type === "none" && "bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400",
                      !["flex", "grid", "block", "inline", "none"].includes(type) &&
                        "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
                    )}
                  >
                    {type}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div
                    className="h-2 bg-neutral-400 dark:bg-neutral-500 rounded"
                    style={{
                      width: Math.max(
                        4,
                        (count / sortedData.displayTypes[0][1]) * 100
                      ),
                    }}
                  />
                  <span className="text-xs text-neutral-400 w-12 text-right">
                    {count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No display types found</p>
        )}
      </Section>

      {/* Position Types */}
      <Section icon={Box} title="Position Types">
        {sortedData.positionTypes.length > 0 ? (
          <div className="space-y-2">
            {sortedData.positionTypes.map(([type, count]) => (
              <div
                key={type}
                className={cn(
                  "flex items-center justify-between p-2 rounded-lg",
                  "bg-neutral-50 dark:bg-neutral-800"
                )}
              >
                <span
                  className={cn(
                    "px-2 py-0.5 rounded text-xs font-medium",
                    type === "relative" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                    type === "absolute" && "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
                    type === "fixed" && "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
                    type === "sticky" && "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
                    type === "static" && "bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400"
                  )}
                >
                  {type}
                </span>
                <div className="flex items-center gap-2">
                  <div
                    className="h-2 bg-neutral-400 dark:bg-neutral-500 rounded"
                    style={{
                      width: Math.max(
                        4,
                        (count / sortedData.positionTypes[0][1]) * 100
                      ),
                    }}
                  />
                  <span className="text-xs text-neutral-400 w-12 text-right">
                    {count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No position types found</p>
        )}
      </Section>

      {/* Margins */}
      <Section icon={Box} title="Common Margins">
        {sortedData.margins.length > 0 ? (
          <div className="space-y-2">
            {sortedData.margins.slice(0, 10).map(([margin, count]) => (
              <StatItem key={margin} label="margin" value={margin} count={count} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No margins found</p>
        )}
      </Section>

      {/* Paddings */}
      <Section icon={Box} title="Common Paddings">
        {sortedData.paddings.length > 0 ? (
          <div className="space-y-2">
            {sortedData.paddings.slice(0, 10).map(([padding, count]) => (
              <StatItem key={padding} label="padding" value={padding} count={count} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">No paddings found</p>
        )}
      </Section>
    </div>
  );
}
