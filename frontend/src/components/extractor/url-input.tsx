"use client";

import React, { useState, useEffect, KeyboardEvent } from "react";
import { Search, Loader2, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * URL Input Props
 */
interface UrlInputProps {
  onSubmit: (url: string, options: ExtractOptions) => void;
  isLoading: boolean;
  disabled?: boolean;
  /** Initial URL value (e.g., from URL params) */
  initialUrl?: string;
}

/**
 * Extract Options
 * 提取选项配置
 */
export interface ExtractOptions {
  viewportWidth: number;
  viewportHeight: number;
  includeHidden: boolean;
  maxDepth: number;
}

/**
 * Viewport Presets
 * 预设视口尺寸
 */
const VIEWPORT_PRESETS = [
  { label: "Desktop", width: 1920, height: 1080 },
  { label: "Laptop", width: 1440, height: 900 },
  { label: "Tablet", width: 768, height: 1024 },
  { label: "Mobile", width: 375, height: 812 },
] as const;

/**
 * URL Input Component
 * URL 输入组件
 *
 * 功能：
 * - URL 输入框
 * - 提取选项配置（视口尺寸、是否包含隐藏元素等）
 * - 提交按钮
 */
export function UrlInput({ onSubmit, isLoading, disabled, initialUrl = "" }: UrlInputProps) {
  // URL 状态
  const [url, setUrl] = useState(initialUrl);

  // Sync URL state when initialUrl changes
  useEffect(() => {
    if (initialUrl) {
      setUrl(initialUrl);
    }
  }, [initialUrl]);

  // 选项展开状态
  const [showOptions, setShowOptions] = useState(false);

  // 提取选项
  const [options, setOptions] = useState<ExtractOptions>({
    viewportWidth: 1920,
    viewportHeight: 1080,
    includeHidden: false,
    maxDepth: 50,
  });

  /**
   * 处理提交
   */
  const handleSubmit = () => {
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;

    // 自动添加协议
    let finalUrl = trimmedUrl;
    if (!trimmedUrl.startsWith("http://") && !trimmedUrl.startsWith("https://")) {
      finalUrl = "https://" + trimmedUrl;
    }

    onSubmit(finalUrl, options);
  };

  /**
   * 处理键盘事件
   */
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !isLoading && !disabled) {
      handleSubmit();
    }
  };

  /**
   * 选择视口预设
   */
  const selectPreset = (width: number, height: number) => {
    setOptions((prev) => ({
      ...prev,
      viewportWidth: width,
      viewportHeight: height,
    }));
  };

  return (
    <div className="space-y-3">
      {/* URL Input Row */}
      <div className="flex gap-2">
        {/* Input Field */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter website URL (e.g., example.com)"
            disabled={isLoading || disabled}
            className={cn(
              "w-full pl-10 pr-4 py-2.5 rounded-lg border",
              "bg-white dark:bg-neutral-900",
              "border-neutral-200 dark:border-neutral-700",
              "text-neutral-900 dark:text-neutral-100",
              "placeholder:text-neutral-400 dark:placeholder:text-neutral-500",
              "focus:outline-none focus:ring-2 focus:ring-purple-500/50",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-all duration-200"
            )}
          />
        </div>

        {/* Options Toggle */}
        <button
          onClick={() => setShowOptions(!showOptions)}
          className={cn(
            "px-3 py-2.5 rounded-lg border transition-all duration-200",
            "border-neutral-200 dark:border-neutral-700",
            "hover:bg-neutral-100 dark:hover:bg-neutral-800",
            showOptions && "bg-neutral-100 dark:bg-neutral-800"
          )}
          title="Options"
        >
          <Settings2 className="h-4 w-4 text-neutral-600 dark:text-neutral-400" />
        </button>

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={isLoading || disabled || !url.trim()}
          className={cn(
            "px-6 py-2.5 rounded-lg font-medium transition-all duration-200",
            "bg-purple-600 hover:bg-purple-700 text-white",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "flex items-center gap-2"
          )}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Analyzing...</span>
            </>
          ) : (
            <span>Analyze</span>
          )}
        </button>
      </div>

      {/* Options Panel */}
      {showOptions && (
        <div
          className={cn(
            "p-4 rounded-lg border",
            "bg-neutral-50 dark:bg-neutral-900",
            "border-neutral-200 dark:border-neutral-700"
          )}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Viewport Selection */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                Viewport Size
              </label>
              <div className="flex flex-wrap gap-2">
                {VIEWPORT_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => selectPreset(preset.width, preset.height)}
                    className={cn(
                      "px-3 py-1.5 rounded text-sm transition-all",
                      options.viewportWidth === preset.width &&
                        options.viewportHeight === preset.height
                        ? "bg-purple-600 text-white"
                        : "bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-300 dark:hover:bg-neutral-600"
                    )}
                  >
                    {preset.label}
                    <span className="text-xs opacity-70 ml-1">
                      {preset.width}×{preset.height}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Max Depth */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                Max DOM Depth: {options.maxDepth}
              </label>
              <input
                type="range"
                min="10"
                max="100"
                value={options.maxDepth}
                onChange={(e) =>
                  setOptions((prev) => ({
                    ...prev,
                    maxDepth: parseInt(e.target.value),
                  }))
                }
                className="w-full accent-purple-600"
              />
            </div>

            {/* Include Hidden */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="includeHidden"
                checked={options.includeHidden}
                onChange={(e) =>
                  setOptions((prev) => ({
                    ...prev,
                    includeHidden: e.target.checked,
                  }))
                }
                className="rounded border-neutral-300 text-purple-600 focus:ring-purple-500"
              />
              <label
                htmlFor="includeHidden"
                className="text-sm text-neutral-700 dark:text-neutral-300"
              >
                Include hidden elements
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
