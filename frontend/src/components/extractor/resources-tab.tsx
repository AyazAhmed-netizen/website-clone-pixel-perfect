"use client";

import React, { useState, useMemo } from "react";
import {
  Image as ImageIcon,
  FileCode,
  Type,
  Download,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Sun,
  Moon,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DownloadedResources, ResourceContent, ThemeMode } from "@/types/playwright";

/**
 * Resources Tab Props
 */
interface ResourcesTabProps {
  resources: DownloadedResources | null;
  currentTheme?: ThemeMode; // 当前预览主题
  hasDualTheme?: boolean;   // 是否支持双主题
}

/**
 * 检测资源的主题类型
 */
type ResourceThemeType = "light" | "dark" | "common";

function detectResourceTheme(resource: ResourceContent): ResourceThemeType {
  const lowerUrl = (resource.url || "").toLowerCase();
  const lowerFilename = (resource.filename || "").toLowerCase();
  const combined = lowerUrl + lowerFilename;

  // 检测 dark 主题标识
  const darkPatterns = [
    "-dark.", "_dark.", "/dark/", "-dark-", "_dark_",
    "dark-mode", "darkmode", "dark_mode",
  ];
  const hasDark = darkPatterns.some(p => combined.includes(p));

  // 检测 light 主题标识
  const lightPatterns = [
    "-light.", "_light.", "/light/", "-light-", "_light_",
    "light-mode", "lightmode", "light_mode",
  ];
  const hasLight = lightPatterns.some(p => combined.includes(p));

  // 如果同时包含 dark 和 light，视为通用
  if (hasDark && hasLight) return "common";
  if (hasDark) return "dark";
  if (hasLight) return "light";
  return "common";
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

/**
 * Collapsible Section Component
 * 可折叠区域组件
 */
function CollapsibleSection({
  title,
  icon: Icon,
  count,
  totalSize,
  children,
  defaultOpen = true,
  color,
}: {
  title: string;
  icon: React.ElementType;
  count: number;
  totalSize: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
  color: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div
      className={cn(
        "rounded-lg border",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full flex items-center justify-between p-3",
          "hover:bg-neutral-50 dark:hover:bg-neutral-800/50",
          "transition-colors"
        )}
      >
        <div className="flex items-center gap-2">
          <Icon className={cn("h-4 w-4", color)} />
          <span className="font-medium text-neutral-900 dark:text-neutral-100">
            {title}
          </span>
          <span
            className={cn(
              "px-2 py-0.5 text-xs rounded-full",
              "bg-neutral-100 dark:bg-neutral-800",
              "text-neutral-600 dark:text-neutral-400"
            )}
          >
            {count} files
          </span>
          <span className="text-xs text-neutral-400">
            ({formatBytes(totalSize)})
          </span>
        </div>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-neutral-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-neutral-400" />
        )}
      </button>
      {isOpen && (
        <div className="p-3 pt-0 border-t border-neutral-200 dark:border-neutral-700">
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * Image Resource Card Component
 * 图片资源卡片组件
 */
function ImageResourceCard({ resource }: { resource: ResourceContent }) {
  const [showPreview, setShowPreview] = useState(false);

  const handleDownload = () => {
    if (resource.content) {
      const link = document.createElement("a");
      link.href = `data:${resource.mime_type || "image/png"};base64,${resource.content}`;
      link.download = resource.filename || "image";
      link.click();
    }
  };

  return (
    <div
      className={cn(
        "rounded-lg border overflow-hidden",
        "bg-neutral-50 dark:bg-neutral-800/50",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      {/* Preview */}
      {showPreview && resource.content && (
        <div className="p-2 bg-checkerboard">
          <img
            src={`data:${resource.mime_type || "image/png"};base64,${resource.content}`}
            alt={resource.filename || "Image"}
            className="max-h-40 mx-auto object-contain"
          />
        </div>
      )}

      {/* Info */}
      <div className="p-2 flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-mono truncate text-neutral-700 dark:text-neutral-300">
            {resource.filename || "unknown"}
          </p>
          <p className="text-[10px] text-neutral-400">
            {formatBytes(resource.size)} • {resource.mime_type || "unknown"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className={cn(
              "p-1.5 rounded hover:bg-neutral-200 dark:hover:bg-neutral-700",
              showPreview && "bg-blue-100 dark:bg-blue-900/30"
            )}
            title={showPreview ? "Hide preview" : "Show preview"}
          >
            <ImageIcon className="h-3.5 w-3.5 text-neutral-500" />
          </button>
          <button
            onClick={handleDownload}
            className="p-1.5 rounded hover:bg-neutral-200 dark:hover:bg-neutral-700"
            title="Download"
          >
            <Download className="h-3.5 w-3.5 text-neutral-500" />
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Font Resource Card Component
 * 字体资源卡片组件
 */
function FontResourceCard({ resource }: { resource: ResourceContent }) {
  const handleDownload = () => {
    if (resource.content) {
      const link = document.createElement("a");
      link.href = `data:${resource.mime_type || "font/woff2"};base64,${resource.content}`;
      link.download = resource.filename || "font";
      link.click();
    }
  };

  // Determine font format
  const format = resource.filename?.split(".").pop()?.toUpperCase() || "FONT";

  return (
    <div
      className={cn(
        "p-3 rounded-lg border flex items-center justify-between",
        "bg-neutral-50 dark:bg-neutral-800/50",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={cn(
            "p-2 rounded-lg",
            "bg-cyan-100 dark:bg-cyan-900/30"
          )}
        >
          <Type className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate text-neutral-700 dark:text-neutral-300">
            {resource.filename || "font"}
          </p>
          <p className="text-[10px] text-neutral-400">
            {formatBytes(resource.size)} • {format}
          </p>
        </div>
      </div>
      <button
        onClick={handleDownload}
        className="p-2 rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700"
        title="Download font"
      >
        <Download className="h-4 w-4 text-neutral-500" />
      </button>
    </div>
  );
}

/**
 * Script Resource Card Component
 * 脚本资源卡片组件
 */
function ScriptResourceCard({ resource }: { resource: ResourceContent }) {
  const [expanded, setExpanded] = useState(false);

  const handleDownload = () => {
    if (resource.content) {
      // Decode base64 for text files
      const text = atob(resource.content);
      const blob = new Blob([text], { type: "text/javascript" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = resource.filename || "script.js";
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  // Get preview of script content
  let preview = "";
  if (resource.content) {
    try {
      preview = atob(resource.content).slice(0, 500);
    } catch {
      preview = "Unable to decode content";
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border overflow-hidden",
        "bg-neutral-50 dark:bg-neutral-800/50",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="p-3 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={cn(
              "p-2 rounded-lg",
              "bg-yellow-100 dark:bg-yellow-900/30"
            )}
          >
            <FileCode className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium truncate text-neutral-700 dark:text-neutral-300">
              {resource.filename || "script.js"}
            </p>
            <p className="text-[10px] text-neutral-400">
              {formatBytes(resource.size)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setExpanded(!expanded)}
            className={cn(
              "px-2 py-1 text-xs rounded hover:bg-neutral-200 dark:hover:bg-neutral-700",
              expanded && "bg-blue-100 dark:bg-blue-900/30 text-blue-600"
            )}
          >
            {expanded ? "Hide" : "Preview"}
          </button>
          <button
            onClick={handleDownload}
            className="p-2 rounded hover:bg-neutral-200 dark:hover:bg-neutral-700"
            title="Download"
          >
            <Download className="h-4 w-4 text-neutral-500" />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-neutral-200 dark:border-neutral-700">
          <pre className="p-3 text-[11px] font-mono overflow-auto max-h-48 text-neutral-600 dark:text-neutral-400">
            {preview}
            {preview.length >= 500 && "\n\n... (truncated)"}
          </pre>
        </div>
      )}

      {/* URL */}
      <div className="px-3 pb-2">
        <a
          href={resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-blue-500 hover:underline flex items-center gap-1 truncate"
        >
          <ExternalLink className="h-3 w-3 flex-shrink-0" />
          {resource.url}
        </a>
      </div>
    </div>
  );
}

/**
 * Resources Tab Component
 * 已下载资源 Tab 组件
 */
export function ResourcesTab({ resources, currentTheme = "light", hasDualTheme = false }: ResourcesTabProps) {
  // 资源过滤模式
  const [filterMode, setFilterMode] = useState<"all" | "themed">("themed");

  // 根据主题过滤资源
  const filteredResources = useMemo(() => {
    if (!resources) return null;

    // 如果不支持双主题或选择显示全部，返回原始数据
    if (!hasDualTheme || filterMode === "all") {
      return resources;
    }

    // 过滤函数：保留通用资源 + 当前主题资源
    const filterByTheme = (items: ResourceContent[]): ResourceContent[] => {
      return items.filter(item => {
        const theme = detectResourceTheme(item);
        return theme === "common" || theme === currentTheme;
      });
    };

    return {
      images: filterByTheme(resources.images),
      fonts: filterByTheme(resources.fonts),
      scripts: filterByTheme(resources.scripts),
    };
  }, [resources, currentTheme, hasDualTheme, filterMode]);

  if (!filteredResources) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No downloaded resources available
      </div>
    );
  }

  const totalImages = filteredResources.images.reduce((acc, r) => acc + r.size, 0);
  const totalFonts = filteredResources.fonts.reduce((acc, r) => acc + r.size, 0);
  const totalScripts = filteredResources.scripts.reduce((acc, r) => acc + r.size, 0);
  const totalAll = totalImages + totalFonts + totalScripts;

  // 原始总数
  const originalTotalCount = resources ?
    resources.images.length + resources.fonts.length + resources.scripts.length : 0;
  const currentTotalCount = filteredResources.images.length + filteredResources.fonts.length + filteredResources.scripts.length;

  const hasAnyResources =
    filteredResources.images.length > 0 ||
    filteredResources.fonts.length > 0 ||
    filteredResources.scripts.length > 0;

  if (!hasAnyResources) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-neutral-500">
        <Download className="h-8 w-8 mb-2 text-neutral-400" />
        <p>No resources downloaded</p>
        <p className="text-xs text-neutral-400 mt-1">
          Resources may not have been downloaded due to size limits or errors
        </p>
      </div>
    );
  }

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
            {filterMode === "themed" && currentTotalCount !== originalTotalCount && (
              <span className="text-xs text-neutral-400">
                (Showing {currentTotalCount} of {originalTotalCount})
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
            >
              <Layers className="h-3 w-3" />
              All
            </button>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-gradient-to-br from-pink-50 to-pink-100 dark:from-pink-900/20 dark:to-pink-900/10 border border-pink-200 dark:border-pink-800">
          <div className="flex items-center gap-2">
            <ImageIcon className="h-4 w-4 text-pink-500" />
            <p className="text-xl font-bold text-pink-600 dark:text-pink-400">
              {filteredResources.images.length}
            </p>
          </div>
          <p className="text-xs text-pink-700 dark:text-pink-500">
            Images ({formatBytes(totalImages)})
          </p>
        </div>

        <div className="p-3 rounded-lg bg-gradient-to-br from-cyan-50 to-cyan-100 dark:from-cyan-900/20 dark:to-cyan-900/10 border border-cyan-200 dark:border-cyan-800">
          <div className="flex items-center gap-2">
            <Type className="h-4 w-4 text-cyan-500" />
            <p className="text-xl font-bold text-cyan-600 dark:text-cyan-400">
              {filteredResources.fonts.length}
            </p>
          </div>
          <p className="text-xs text-cyan-700 dark:text-cyan-500">
            Fonts ({formatBytes(totalFonts)})
          </p>
        </div>

        <div className="p-3 rounded-lg bg-gradient-to-br from-yellow-50 to-yellow-100 dark:from-yellow-900/20 dark:to-yellow-900/10 border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-center gap-2">
            <FileCode className="h-4 w-4 text-yellow-500" />
            <p className="text-xl font-bold text-yellow-600 dark:text-yellow-400">
              {filteredResources.scripts.length}
            </p>
          </div>
          <p className="text-xs text-yellow-700 dark:text-yellow-500">
            Scripts ({formatBytes(totalScripts)})
          </p>
        </div>
      </div>

      {/* Images */}
      {filteredResources.images.length > 0 && (
        <CollapsibleSection
          title="Images"
          icon={ImageIcon}
          count={filteredResources.images.length}
          totalSize={totalImages}
          color="text-pink-500"
        >
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 mt-3">
            {filteredResources.images.map((img, idx) => (
              <ImageResourceCard key={idx} resource={img} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Fonts */}
      {filteredResources.fonts.length > 0 && (
        <CollapsibleSection
          title="Fonts"
          icon={Type}
          count={filteredResources.fonts.length}
          totalSize={totalFonts}
          color="text-cyan-500"
        >
          <div className="space-y-2 mt-3">
            {filteredResources.fonts.map((font, idx) => (
              <FontResourceCard key={idx} resource={font} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Scripts */}
      {filteredResources.scripts.length > 0 && (
        <CollapsibleSection
          title="Scripts"
          icon={FileCode}
          count={filteredResources.scripts.length}
          totalSize={totalScripts}
          color="text-yellow-500"
        >
          <div className="space-y-2 mt-3">
            {filteredResources.scripts.map((script, idx) => (
              <ScriptResourceCard key={idx} resource={script} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Total */}
      <div className="text-center text-xs text-neutral-400">
        Total downloaded: {formatBytes(totalAll)}
      </div>
    </div>
  );
}
