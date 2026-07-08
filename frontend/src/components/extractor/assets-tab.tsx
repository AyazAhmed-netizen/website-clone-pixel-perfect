"use client";

import React, { useState, useMemo } from "react";
import {
  Image as ImageIcon,
  FileCode,
  FileText,
  Type,
  ExternalLink,
  Copy,
  Check,
  Sun,
  Moon,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { PageAssets, AssetInfo, ThemeMode } from "@/types/playwright";
import { getDomain } from "@/lib/api/playwright";

/**
 * Assets Tab Props
 */
interface AssetsTabProps {
  assets: PageAssets | null;
  currentTheme?: ThemeMode; // 当前预览主题
  hasDualTheme?: boolean;   // 是否支持双主题
}

/**
 * Asset Category Type
 */
type AssetCategory = "images" | "scripts" | "stylesheets" | "fonts";

/**
 * Category Config
 */
const CATEGORIES: Record<
  AssetCategory,
  { label: string; icon: React.ElementType; color: string }
> = {
  images: {
    label: "Images",
    icon: ImageIcon,
    color: "text-blue-500",
  },
  scripts: {
    label: "Scripts",
    icon: FileCode,
    color: "text-yellow-500",
  },
  stylesheets: {
    label: "Stylesheets",
    icon: FileText,
    color: "text-green-500",
  },
  fonts: {
    label: "Fonts",
    icon: Type,
    color: "text-purple-500",
  },
};

/**
 * Asset Item Component
 * 资源项组件
 */
function AssetItem({ asset, category }: { asset: AssetInfo; category: AssetCategory }) {
  const [copied, setCopied] = useState(false);
  const [imageError, setImageError] = useState(false);

  const Icon = CATEGORIES[category].icon;
  const color = CATEGORIES[category].color;

  /**
   * 复制 URL 到剪贴板
   */
  const handleCopy = async () => {
    await navigator.clipboard.writeText(asset.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /**
   * 在新标签页打开
   */
  const handleOpen = () => {
    window.open(asset.url, "_blank", "noopener,noreferrer");
  };

  // 获取文件名
  const fileName = asset.url.split("/").pop()?.split("?")[0] || asset.url;

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 rounded-lg",
        "bg-neutral-50 dark:bg-neutral-800",
        "hover:bg-neutral-100 dark:hover:bg-neutral-700",
        "transition-colors"
      )}
    >
      {/* Icon or Thumbnail */}
      <div className="flex-shrink-0">
        {category === "images" && !imageError ? (
          <div className="w-12 h-12 rounded border border-neutral-200 dark:border-neutral-600 overflow-hidden bg-white">
            <img
              src={asset.url}
              alt=""
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          </div>
        ) : (
          <div
            className={cn(
              "w-12 h-12 rounded border border-neutral-200 dark:border-neutral-600",
              "flex items-center justify-center",
              "bg-white dark:bg-neutral-900"
            )}
          >
            <Icon className={cn("h-6 w-6", color)} />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 truncate">
          {fileName}
        </p>
        <p className="text-xs text-neutral-400 truncate mt-0.5">{asset.url}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-neutral-400">{asset.type}</span>
          <span className="text-xs text-neutral-400">•</span>
          <span className="text-xs text-neutral-400">{getDomain(asset.url)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <button
          onClick={handleCopy}
          className={cn(
            "p-1.5 rounded hover:bg-neutral-200 dark:hover:bg-neutral-600",
            "text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300",
            "transition-colors"
          )}
          title="Copy URL"
        >
          {copied ? (
            <Check className="h-4 w-4 text-green-500" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
        </button>
        <button
          onClick={handleOpen}
          className={cn(
            "p-1.5 rounded hover:bg-neutral-200 dark:hover:bg-neutral-600",
            "text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300",
            "transition-colors"
          )}
          title="Open in new tab"
        >
          <ExternalLink className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

/**
 * 检测资源的主题类型
 * 通过 URL 或文件名中的关键词判断
 */
type AssetThemeType = "light" | "dark" | "common";

function detectAssetTheme(url: string): AssetThemeType {
  const lowerUrl = url.toLowerCase();

  // 检测 dark 主题标识
  const darkPatterns = [
    "-dark.", "_dark.", "/dark/", "-dark-", "_dark_",
    "dark-mode", "darkmode", "dark_mode",
  ];
  const hasDark = darkPatterns.some(p => lowerUrl.includes(p));

  // 检测 light 主题标识
  const lightPatterns = [
    "-light.", "_light.", "/light/", "-light-", "_light_",
    "light-mode", "lightmode", "light_mode",
  ];
  const hasLight = lightPatterns.some(p => lowerUrl.includes(p));

  // 如果同时包含 dark 和 light（比如 logo-dark-and-light.svg），视为通用
  if (hasDark && hasLight) return "common";
  if (hasDark) return "dark";
  if (hasLight) return "light";
  return "common";
}

/**
 * Assets Tab Component
 * 资源 Tab 组件
 *
 * 展示：
 * - 图片资源列表
 * - 脚本资源列表
 * - 样式表资源列表
 * - 字体资源列表
 *
 * 支持根据当前主题过滤显示资源
 */
export function AssetsTab({ assets, currentTheme = "light", hasDualTheme = false }: AssetsTabProps) {
  // 当前选中的分类
  const [activeCategory, setActiveCategory] = useState<AssetCategory>("images");
  // 资源过滤模式: all (显示全部), themed (根据主题过滤)
  const [filterMode, setFilterMode] = useState<"all" | "themed">("themed");

  // 根据主题过滤资源
  const filteredAssets = useMemo(() => {
    if (!assets) return null;

    // 如果不支持双主题或选择显示全部，返回原始数据
    if (!hasDualTheme || filterMode === "all") {
      return assets;
    }

    // 过滤函数：保留通用资源 + 当前主题资源
    const filterByTheme = (items: AssetInfo[]): AssetInfo[] => {
      return items.filter(item => {
        const theme = detectAssetTheme(item.url);
        return theme === "common" || theme === currentTheme;
      });
    };

    const filteredImages = filterByTheme(assets.images);
    const filteredScripts = filterByTheme(assets.scripts);
    const filteredStylesheets = filterByTheme(assets.stylesheets);
    const filteredFonts = filterByTheme(assets.fonts);

    return {
      images: filteredImages,
      scripts: filteredScripts,
      stylesheets: filteredStylesheets,
      fonts: filteredFonts,
      total_images: filteredImages.length,
      total_scripts: filteredScripts.length,
      total_stylesheets: filteredStylesheets.length,
      total_fonts: filteredFonts.length,
    };
  }, [assets, currentTheme, hasDualTheme, filterMode]);

  if (!filteredAssets) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No assets data available
      </div>
    );
  }

  // 当前分类的资源列表
  const currentAssets = filteredAssets[activeCategory];
  const totalCount =
    filteredAssets.total_images +
    filteredAssets.total_scripts +
    filteredAssets.total_stylesheets +
    filteredAssets.total_fonts;

  // 原始总数（用于显示过滤信息）
  const originalTotalCount = assets ?
    assets.total_images + assets.total_scripts + assets.total_stylesheets + assets.total_fonts : 0;

  return (
    <div className="space-y-4">
      {/* Filter Toggle (only show when dual theme is supported) */}
      {hasDualTheme && (
        <div className={cn(
          "flex items-center justify-between p-2 rounded-lg border",
          "bg-neutral-50 dark:bg-neutral-800",
          "border-neutral-200 dark:border-neutral-700"
        )}>
          <div className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
            {currentTheme === "light" ? (
              <Sun className="h-4 w-4 text-amber-500" />
            ) : (
              <Moon className="h-4 w-4 text-indigo-500" />
            )}
            <span>Theme: <strong className="text-neutral-900 dark:text-neutral-100">{currentTheme.toUpperCase()}</strong></span>
            {filterMode === "themed" && totalCount !== originalTotalCount && (
              <span className="text-xs text-neutral-400">
                (Showing {totalCount} of {originalTotalCount})
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 p-1 bg-neutral-200 dark:bg-neutral-700 rounded-lg">
            <button
              onClick={() => setFilterMode("themed")}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                filterMode === "themed"
                  ? "bg-white dark:bg-neutral-600 text-neutral-900 dark:text-neutral-100 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
              )}
              title="Show only assets matching current theme"
            >
              {currentTheme === "light" ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />}
              Themed
            </button>
            <button
              onClick={() => setFilterMode("all")}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                filterMode === "all"
                  ? "bg-white dark:bg-neutral-600 text-neutral-900 dark:text-neutral-100 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
              )}
              title="Show all assets"
            >
              <Layers className="h-3 w-3" />
              All
            </button>
          </div>
        </div>
      )}

      {/* Category Tabs */}
      <div
        className={cn(
          "flex items-center gap-2 p-2 rounded-lg border",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        {(Object.keys(CATEGORIES) as AssetCategory[]).map((category) => {
          const config = CATEGORIES[category];
          const count =
            category === "images"
              ? filteredAssets.total_images
              : category === "scripts"
              ? filteredAssets.total_scripts
              : category === "stylesheets"
              ? filteredAssets.total_stylesheets
              : filteredAssets.total_fonts;

          return (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
                activeCategory === category
                  ? "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400"
                  : "hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              )}
            >
              <config.icon className={cn("h-4 w-4", config.color)} />
              <span className="text-sm font-medium">{config.label}</span>
              <span
                className={cn(
                  "px-1.5 py-0.5 rounded text-xs",
                  activeCategory === category
                    ? "bg-purple-200 dark:bg-purple-800 text-purple-700 dark:text-purple-300"
                    : "bg-neutral-200 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400"
                )}
              >
                {count}
              </span>
            </button>
          );
        })}

        {/* Total */}
        <div className="ml-auto text-sm text-neutral-400">
          Total: {totalCount} assets
        </div>
      </div>

      {/* Assets List */}
      <div
        className={cn(
          "rounded-lg border overflow-hidden",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        {currentAssets.length > 0 ? (
          <div className="divide-y divide-neutral-200 dark:divide-neutral-700 max-h-[500px] overflow-auto">
            {currentAssets.map((asset, index) => (
              <AssetItem key={index} asset={asset} category={activeCategory} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-48 text-neutral-400">
            {React.createElement(CATEGORIES[activeCategory].icon, {
              className: "h-8 w-8 mb-2",
            })}
            <p className="text-sm">No {CATEGORIES[activeCategory].label.toLowerCase()} found</p>
          </div>
        )}
      </div>

      {/* Summary */}
      <div
        className={cn(
          "grid grid-cols-4 gap-4 p-4 rounded-lg border",
          "bg-white dark:bg-neutral-900",
          "border-neutral-200 dark:border-neutral-700"
        )}
      >
        {(Object.keys(CATEGORIES) as AssetCategory[]).map((category) => {
          const config = CATEGORIES[category];
          const count =
            category === "images"
              ? filteredAssets.total_images
              : category === "scripts"
              ? filteredAssets.total_scripts
              : category === "stylesheets"
              ? filteredAssets.total_stylesheets
              : filteredAssets.total_fonts;

          return (
            <div
              key={category}
              className={cn(
                "text-center p-3 rounded-lg",
                "bg-neutral-50 dark:bg-neutral-800"
              )}
            >
              <config.icon className={cn("h-6 w-6 mx-auto mb-2", config.color)} />
              <p className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">
                {count}
              </p>
              <p className="text-xs text-neutral-500">{config.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
