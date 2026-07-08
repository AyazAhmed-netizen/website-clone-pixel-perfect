"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ChevronDown,
  ChevronRight,
  Info,
  Code,
  Copy,
  Check,
  FileCode,
  Hash,
  Ruler,
  Box,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ComponentAnalysisData, ComponentInfo } from "@/types/playwright";

/**
 * Components Tab Props
 */
interface ComponentsTabProps {
  components: ComponentAnalysisData | null;
  selectedComponentId?: string | null;
}

/**
 * Format number with locale separators
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Get token size display
 * All sections should be < 20K (backend ensures this)
 */
function getTokenDisplay(tokens: number | undefined): {
  label: string;
  colorClass: string;
} {
  if (!tokens) return { label: "N/A", colorClass: "text-neutral-400" };

  const label = tokens >= 1000
    ? `~${Math.round(tokens / 1000)}K`
    : `~${tokens}`;

  // All sections should be < 20K, use neutral color
  return { label, colorClass: "text-neutral-600 dark:text-neutral-400" };
}

/**
 * Component Type Badge
 * Simplified - all sections use unified purple style
 */
function ComponentTypeBadge({ type }: { type: string }) {
  // All sections use the same purple style
  const style = { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-300" };

  return (
    <span className={cn("px-2 py-0.5 rounded text-xs font-medium", style.bg, style.text)}>
      {type}
    </span>
  );
}

/**
 * Copy Button Component
 */
function CopyButton({
  text,
  label = "Copy",
  size = "sm"
}: {
  text: string;
  label?: string;
  size?: "sm" | "xs";
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "flex items-center gap-1 rounded transition-colors",
        size === "sm" ? "px-2 py-1 text-xs" : "px-1.5 py-0.5 text-[10px]",
        copied
          ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
          : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-700"
      )}
      title={`Copy ${label}`}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied!" : label}
    </button>
  );
}

/**
 * Component Card - Focused on code location display
 */
function ComponentCard({
  component,
  index,
  isSelected = false,
}: {
  component: ComponentInfo;
  index: number;
  isSelected?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(isSelected);
  const [showHtml, setShowHtml] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // Auto-expand and scroll when selected
  useEffect(() => {
    if (isSelected) {
      setIsExpanded(true);
      setTimeout(() => {
        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }, [isSelected]);

  const codeLocation = component.code_location;
  const hasCodeLocation = codeLocation && (codeLocation.char_start > 0 || codeLocation.char_end > 0);
  const tokenInfo = getTokenDisplay(codeLocation?.estimated_tokens);

  // Calculate character length
  const charLength = hasCodeLocation
    ? codeLocation.char_end - codeLocation.char_start
    : 0;

  return (
    <div
      ref={cardRef}
      className={cn(
        "border rounded-lg overflow-hidden transition-all",
        "bg-white dark:bg-neutral-900",
        isSelected
          ? "border-purple-500 ring-2 ring-purple-500/30"
          : "border-neutral-200 dark:border-neutral-700"
      )}
    >
      {/* Header - Always visible */}
      <div
        className={cn(
          "p-3 cursor-pointer transition-colors",
          isSelected
            ? "bg-purple-50 dark:bg-purple-900/20"
            : "hover:bg-neutral-50 dark:hover:bg-neutral-800"
        )}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between gap-3">
          {/* Left: Index + Name + Type */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-neutral-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-neutral-400 flex-shrink-0" />
            )}

            {/* Index Badge */}
            <span className="flex-shrink-0 w-6 h-6 rounded bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center text-xs font-mono font-bold text-neutral-600 dark:text-neutral-400">
              {index + 1}
            </span>

            {/* Name */}
            <span className="font-medium text-sm text-neutral-900 dark:text-neutral-100 truncate">
              {component.name}
            </span>

            <ComponentTypeBadge type={component.type} />
          </div>

          {/* Right: Key metrics */}
          <div className="flex items-center gap-3 flex-shrink-0 text-xs">
            {/* Character Range - Most important */}
            {hasCodeLocation && (
              <span className="font-mono px-2 py-1 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300">
                {formatNumber(codeLocation.char_start)} - {formatNumber(codeLocation.char_end)}
              </span>
            )}

            {/* Token count */}
            <span className={cn("font-mono font-medium", tokenInfo.colorClass)}>
              {tokenInfo.label}
            </span>
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-neutral-200 dark:border-neutral-700">
          {/* Code Location Section - Primary focus */}
          <div className="p-4 bg-neutral-50 dark:bg-neutral-800/50">
            <h4 className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-3 flex items-center gap-2">
              <FileCode className="h-4 w-4" />
              Code Location in Raw HTML
            </h4>

            {hasCodeLocation ? (
              <div className="space-y-3">
                {/* Character Position Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {/* Start Position */}
                  <div className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Hash className="h-3 w-3 text-green-500" />
                      <span className="text-[10px] uppercase tracking-wide text-neutral-500">Start Char</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-lg font-bold text-green-600 dark:text-green-400">
                        {formatNumber(codeLocation.char_start)}
                      </span>
                      <CopyButton text={String(codeLocation.char_start)} label="Copy" size="xs" />
                    </div>
                  </div>

                  {/* End Position */}
                  <div className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Hash className="h-3 w-3 text-red-500" />
                      <span className="text-[10px] uppercase tracking-wide text-neutral-500">End Char</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-lg font-bold text-red-600 dark:text-red-400">
                        {formatNumber(codeLocation.char_end)}
                      </span>
                      <CopyButton text={String(codeLocation.char_end)} label="Copy" size="xs" />
                    </div>
                  </div>

                  {/* Length */}
                  <div className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Ruler className="h-3 w-3 text-blue-500" />
                      <span className="text-[10px] uppercase tracking-wide text-neutral-500">Length</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-lg font-bold text-blue-600 dark:text-blue-400">
                        {formatNumber(charLength)}
                      </span>
                      <span className="text-[10px] text-neutral-400">chars</span>
                    </div>
                  </div>

                  {/* Estimated Tokens */}
                  <div className="p-3 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Code className="h-3 w-3 text-purple-500" />
                      <span className="text-[10px] uppercase tracking-wide text-neutral-500">Tokens</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={cn("font-mono text-lg font-bold", tokenInfo.colorClass)}>
                        {codeLocation.estimated_tokens ? formatNumber(codeLocation.estimated_tokens) : "N/A"}
                      </span>
                      <span className="text-[10px] text-neutral-400">est.</span>
                    </div>
                  </div>
                </div>

                {/* Copy Range Button */}
                <div className="flex items-center gap-2">
                  <CopyButton
                    text={`${codeLocation.char_start}-${codeLocation.char_end}`}
                    label="Copy Range"
                  />
                  <CopyButton
                    text={`rawHtml.substring(${codeLocation.char_start}, ${codeLocation.char_end})`}
                    label="Copy JS Slice"
                  />
                  <span className="text-xs text-neutral-400 ml-2">
                    Use these values to extract this component from raw HTML
                  </span>
                </div>

                {/* HTML Preview */}
                {codeLocation.html_snippet && (
                  <div className="mt-3">
                    <button
                      onClick={() => setShowHtml(!showHtml)}
                      className="flex items-center gap-1 text-xs text-purple-600 dark:text-purple-400 hover:underline mb-2"
                    >
                      {showHtml ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      {showHtml ? "Hide" : "Show"} HTML Preview
                    </button>

                    {showHtml && (
                      <div className="relative">
                        <pre className="text-xs font-mono bg-neutral-900 text-green-400 p-3 rounded-lg overflow-x-auto max-h-64 overflow-y-auto">
                          {codeLocation.html_snippet}
                        </pre>
                        <div className="absolute top-2 right-2">
                          <CopyButton text={codeLocation.html_snippet} label="Copy HTML" size="xs" />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-neutral-400 dark:text-neutral-500">
                <Code className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No code location data available</p>
              </div>
            )}
          </div>

          {/* Additional Info Section - Secondary */}
          <div className="p-4 border-t border-neutral-200 dark:border-neutral-700">
            <h4 className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-3 flex items-center gap-2">
              <Box className="h-4 w-4" />
              Component Details
            </h4>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              {/* Selector */}
              <div>
                <span className="text-neutral-500 block mb-1">Selector</span>
                <code className="text-neutral-800 dark:text-neutral-200 bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 rounded text-[11px] break-all">
                  {component.selector}
                </code>
              </div>

              {/* Dimensions */}
              <div>
                <span className="text-neutral-500 block mb-1">Dimensions</span>
                <span className="text-neutral-800 dark:text-neutral-200">
                  {component.rect.width.toFixed(0)} × {component.rect.height.toFixed(0)} px
                </span>
              </div>

              {/* Position */}
              <div>
                <span className="text-neutral-500 block mb-1">Position</span>
                <span className="text-neutral-800 dark:text-neutral-200">
                  ({component.rect.x.toFixed(0)}, {component.rect.y.toFixed(0)})
                </span>
              </div>

              {/* ID */}
              <div>
                <span className="text-neutral-500 block mb-1">ID</span>
                <span className="text-neutral-800 dark:text-neutral-200 font-mono text-[11px]">
                  {component.id}
                </span>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="flex items-center gap-4 mt-3 pt-3 border-t border-neutral-100 dark:border-neutral-800 text-xs text-neutral-500">
              <span>Images: {component.images?.length ?? 0}</span>
              <span>Internal Links: {component.internal_links?.length ?? 0}</span>
              <span>External Links: {component.external_links?.length ?? 0}</span>
              <span>Headings: {component.text_summary?.headings?.length ?? 0}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Components Tab Component
 *
 * Displays page components with focus on code location (character positions in raw HTML)
 */
export function ComponentsTab({ components, selectedComponentId }: ComponentsTabProps) {
  if (!components) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Info className="h-12 w-12 text-neutral-300 dark:text-neutral-600 mb-3" />
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Component analysis not available
        </p>
        <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
          Data may still be loading or analysis failed
        </p>
      </div>
    );
  }

  // Calculate total tokens
  const totalTokens = components.components.reduce(
    (sum, c) => sum + (c.code_location?.estimated_tokens || 0),
    0
  );

  // Calculate total characters
  const totalChars = components.components.reduce(
    (sum, c) => {
      const loc = c.code_location;
      if (loc && loc.char_start > 0 && loc.char_end > 0) {
        return sum + (loc.char_end - loc.char_start);
      }
      return sum;
    },
    0
  );

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div className={cn(
        "p-4 rounded-lg border",
        "bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30",
        "border-blue-200 dark:border-blue-800"
      )}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <FileCode className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h3 className="font-semibold text-blue-900 dark:text-blue-100">
              Component Code Locations
            </h3>
          </div>
          <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 px-2 py-1 rounded">
            {components.components.length} components
          </span>
        </div>

        <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
          Character positions for extracting components from raw HTML
        </p>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white/60 dark:bg-neutral-800/60 rounded-lg p-2">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 block">Total Components</span>
            <span className="font-mono font-bold text-lg text-neutral-900 dark:text-neutral-100">
              {components.stats.total_components}
            </span>
          </div>
          <div className="bg-white/60 dark:bg-neutral-800/60 rounded-lg p-2">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 block">Total Characters</span>
            <span className="font-mono font-bold text-lg text-blue-600 dark:text-blue-400">
              {formatNumber(totalChars)}
            </span>
          </div>
          <div className="bg-white/60 dark:bg-neutral-800/60 rounded-lg p-2">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 block">Total Tokens (Est.)</span>
            <span className="font-mono font-bold text-lg text-purple-600 dark:text-purple-400">
              {formatNumber(totalTokens)}
            </span>
          </div>
          <div className="bg-white/60 dark:bg-neutral-800/60 rounded-lg p-2">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 block">By Type</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {Object.entries(components.stats.by_type).map(([type, count]) => (
                <span key={type} className="text-[10px] text-neutral-600 dark:text-neutral-400">
                  {type}: {count}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Reference Table */}
      <div className={cn(
        "p-3 rounded-lg border overflow-x-auto",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700"
      )}>
        <h4 className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-2">
          Quick Reference - Character Ranges
        </h4>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-neutral-500 border-b border-neutral-200 dark:border-neutral-700">
              <th className="pb-2 pr-4 font-medium">#</th>
              <th className="pb-2 pr-4 font-medium">Name</th>
              <th className="pb-2 pr-4 font-medium">Type</th>
              <th className="pb-2 pr-4 font-medium text-right">Start</th>
              <th className="pb-2 pr-4 font-medium text-right">End</th>
              <th className="pb-2 pr-4 font-medium text-right">Length</th>
              <th className="pb-2 font-medium text-right">Tokens</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {components.components.map((comp, idx) => {
              const loc = comp.code_location;
              const hasLoc = loc && loc.char_start > 0;
              const len = hasLoc ? loc.char_end - loc.char_start : 0;
              const tokens = getTokenDisplay(loc?.estimated_tokens);

              return (
                <tr
                  key={comp.id}
                  className={cn(
                    "border-b border-neutral-100 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-800/50",
                    selectedComponentId === comp.id && "bg-purple-50 dark:bg-purple-900/20"
                  )}
                >
                  <td className="py-2 pr-4 text-neutral-400">{idx + 1}</td>
                  <td className="py-2 pr-4 text-neutral-900 dark:text-neutral-100 truncate max-w-[150px]">{comp.name}</td>
                  <td className="py-2 pr-4"><ComponentTypeBadge type={comp.type} /></td>
                  <td className="py-2 pr-4 text-right text-green-600 dark:text-green-400">
                    {hasLoc ? formatNumber(loc.char_start) : "-"}
                  </td>
                  <td className="py-2 pr-4 text-right text-red-600 dark:text-red-400">
                    {hasLoc ? formatNumber(loc.char_end) : "-"}
                  </td>
                  <td className="py-2 pr-4 text-right text-blue-600 dark:text-blue-400">
                    {hasLoc ? formatNumber(len) : "-"}
                  </td>
                  <td className={cn("py-2 text-right", tokens.colorClass)}>
                    {tokens.label}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Component Cards */}
      <div className="space-y-3">
        {components.components.map((component, idx) => (
          <ComponentCard
            key={component.id || idx}
            component={component}
            index={idx}
            isSelected={selectedComponentId === component.id}
          />
        ))}
      </div>

      {/* Empty State */}
      {components.components.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-neutral-400 dark:text-neutral-500">
          <Box className="h-10 w-10 mb-3" />
          <p className="text-sm">No components detected</p>
        </div>
      )}
    </div>
  );
}
