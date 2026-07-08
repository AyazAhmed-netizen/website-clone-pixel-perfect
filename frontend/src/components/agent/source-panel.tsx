"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  Database,
  Globe,
  RefreshCw,
  Loader2,
  ExternalLink,
  Clock,
  Layers,
  X,
  Trash2,
} from "lucide-react";
import { getCacheList, deleteCacheItem, type CachedExtraction } from "@/lib/api/cache";

// ============================================
// Types
// ============================================

interface SavedSource {
  id: string;
  source_url: string;
  page_title: string | null;
  json_size: number;
  top_keys: string[];
  metadata: {
    viewport?: { width: number; height: number };
    extracted_at?: string;
    theme?: "light" | "dark";  // Theme mode when saved
  };
  created_at: string;
  updated_at: string;
}

interface SourcePanelProps {
  /**
   * Callback when a source is selected for reference
   */
  onSelectSource?: (source: SavedSource) => void;
  /**
   * Currently selected source ID (single select)
   */
  selectedSourceId?: string | null;
  /**
   * Whether source selection is disabled (e.g., when Agent is running)
   */
  disabled?: boolean;
  className?: string;
}

// ============================================
// Helper Functions
// ============================================

/**
 * Convert CachedExtraction to SavedSource format
 */
function convertToSavedSource(item: CachedExtraction): SavedSource {
  // Calculate approximate JSON size - handle missing data field
  // Note: /api/cache/list returns summary only (no data field)
  // Use size_bytes from summary if available, otherwise estimate
  const jsonSize = item.size_bytes || (item.data ? JSON.stringify(item.data).length : 0);

  // Get top-level keys from data or top_keys summary
  const topKeys = item.top_keys || (item.data ? Object.keys(item.data).slice(0, 10) : []);

  // Extract theme from data if available
  const dataObj = item.data as Record<string, unknown> | undefined;
  const metadataObj = dataObj?.metadata as Record<string, unknown> | undefined;
  const theme = metadataObj?.theme as "light" | "dark" || "light";

  // Convert timestamp to ISO string if it's a number (Unix timestamp)
  const getISOTimestamp = (): string => {
    if (item.created_at) return item.created_at;
    if (typeof item.timestamp === "number") {
      return new Date(item.timestamp * 1000).toISOString();
    }
    if (typeof item.timestamp === "string") return item.timestamp;
    return new Date().toISOString();
  };

  const isoTimestamp = getISOTimestamp();

  return {
    id: item.id,
    source_url: item.url,
    page_title: item.title || null,
    json_size: jsonSize,
    top_keys: topKeys,
    metadata: {
      extracted_at: isoTimestamp,
      theme: theme,
    },
    created_at: isoTimestamp,
    updated_at: isoTimestamp,
  };
}

// ============================================
// Source Card Component
// ============================================

function SourceCard({
  source,
  isSelected,
  onSelect,
  onDelete,
  disabled = false,
  isDeleting = false,
}: {
  source: SavedSource;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  disabled?: boolean;
  isDeleting?: boolean;
}) {
  // Format URL for display
  const displayUrl = (() => {
    try {
      const url = new URL(source.source_url);
      return url.hostname + (url.pathname !== "/" ? url.pathname : "");
    } catch {
      return source.source_url;
    }
  })();

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return "Today";
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  // Format size
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Handle delete click with confirmation
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card selection
    if (window.confirm(`Delete "${source.page_title || "Untitled"}"?\n\nThis will remove this source from the cache.`)) {
      onDelete();
    }
  };

  return (
    <div
      className={cn(
        "relative w-full text-left p-3 rounded-lg transition-all group",
        "border",
        // Disabled/deleting state
        (disabled || isDeleting) && "opacity-50 cursor-not-allowed",
        // Selected state
        isSelected
          ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
          : "border-neutral-200 dark:border-neutral-700",
        // Hover state (only when not disabled)
        !disabled && !isDeleting && !isSelected && "hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-sm"
      )}
    >
      {/* Delete button - top right, visible on hover */}
      {!disabled && !isDeleting && (
        <button
          onClick={handleDelete}
          className={cn(
            "absolute top-2 right-2 p-1.5 rounded-md transition-all",
            "opacity-0 group-hover:opacity-100",
            "text-neutral-400 hover:text-red-500",
            "hover:bg-red-50 dark:hover:bg-red-900/20",
            "z-10"
          )}
          title="Delete source"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      )}

      {/* Deleting indicator */}
      {isDeleting && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-black/50 rounded-lg z-10">
          <Loader2 className="h-5 w-5 animate-spin text-red-500" />
        </div>
      )}

      {/* Clickable area for selection */}
      <button
        onClick={onSelect}
        disabled={disabled || isDeleting}
        className="w-full text-left"
      >
        {/* Header with Checkbox */}
        <div className="flex items-start gap-3">
          {/* Checkbox */}
          <div className="flex-shrink-0 pt-0.5">
            <div
              className={cn(
                "w-5 h-5 rounded border-2 flex items-center justify-center transition-all",
                isSelected
                  ? "bg-violet-600 border-violet-600"
                  : "border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800"
              )}
            >
              {isSelected && (
                <svg
                  className="w-3 h-3 text-white"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path d="M5 13l4 4L19 7"></path>
                </svg>
              )}
            </div>
          </div>

          {/* Icon and Content */}
          <div
            className={cn(
              "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
              isSelected
                ? "bg-violet-100 dark:bg-violet-900/40"
                : "bg-neutral-100 dark:bg-neutral-800"
            )}
          >
            <Globe
              className={cn(
                "h-4 w-4",
                isSelected
                  ? "text-violet-600 dark:text-violet-400"
                  : "text-neutral-500 dark:text-neutral-400"
              )}
            />
          </div>
          <div className="flex-1 min-w-0 pr-6">
            <h4 className="text-sm font-medium text-neutral-900 dark:text-white truncate">
              {source.page_title || "Untitled"}
            </h4>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">
              {displayUrl}
            </p>
          </div>
        </div>

        {/* Meta info */}
        <div className="flex items-center gap-3 mt-2 text-xs text-neutral-500 dark:text-neutral-400">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(source.created_at)}
          </span>
          <span className="flex items-center gap-1">
            <Layers className="h-3 w-3" />
            {formatSize(source.json_size)}
          </span>
        </div>

        {/* Available data preview */}
        <div className="flex flex-wrap gap-1 mt-2">
          {source.top_keys.slice(0, 4).map((key) => (
            <span
              key={key}
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px]",
                "bg-neutral-100 dark:bg-neutral-800",
                "text-neutral-600 dark:text-neutral-400"
              )}
            >
              {key}
            </span>
          ))}
          {source.top_keys.length > 4 && (
            <span className="px-1.5 py-0.5 text-[10px] text-neutral-400">
              +{source.top_keys.length - 4} more
            </span>
          )}
        </div>
      </button>
    </div>
  );
}

// ============================================
// Main Source Panel Component
// ============================================

export function SourcePanel({
  onSelectSource,
  selectedSourceId = null,
  disabled = false,
  className,
}: SourcePanelProps) {
  const [sources, setSources] = useState<SavedSource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingSourceId, setDeletingSourceId] = useState<string | null>(null);

  // Fetch sources from cache API
  const fetchSources = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getCacheList();

      if (data.success && data.items) {
        const savedSources = data.items.map(convertToSavedSource);
        setSources(savedSources);
      } else {
        throw new Error(data.error || "Failed to fetch sources");
      }
    } catch (err) {
      console.error("Failed to fetch sources:", err);
      setError(err instanceof Error ? err.message : "Failed to load sources");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load sources on mount
  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // Handle source selection
  const handleSelectSource = (source: SavedSource) => {
    onSelectSource?.(source);
  };

  // Handle source deletion
  const handleDeleteSource = useCallback(async (sourceId: string) => {
    setDeletingSourceId(sourceId);

    try {
      const result = await deleteCacheItem(sourceId);

      if (result) {
        // Remove from local state
        setSources(prev => prev.filter(s => s.id !== sourceId));

        // If deleted source was selected, clear selection
        if (selectedSourceId === sourceId) {
          onSelectSource?.(null as unknown as SavedSource);
        }
      } else {
        throw new Error("Failed to delete source");
      }
    } catch (err) {
      console.error("Failed to delete source:", err);
      alert(err instanceof Error ? err.message : "Failed to delete source");
    } finally {
      setDeletingSourceId(null);
    }
  }, [selectedSourceId, onSelectSource]);

  return (
    <div
      className={cn(
        "flex flex-col h-full",
        "bg-white dark:bg-neutral-900",
        "border-r border-neutral-200 dark:border-neutral-700",
        className
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "flex items-center justify-between px-4 py-3 flex-shrink-0",
          "border-b border-neutral-200 dark:border-neutral-700"
        )}
      >
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center">
            <Database className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-white">
              Cached Sources
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {sources.length} website{sources.length !== 1 ? "s" : ""} available
            </p>
          </div>
        </div>
        <button
          onClick={fetchSources}
          disabled={isLoading}
          className={cn(
            "p-2 rounded-lg transition-colors",
            "text-neutral-500 dark:text-neutral-400",
            "hover:bg-neutral-100 dark:hover:bg-neutral-800",
            "disabled:opacity-50"
          )}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {isLoading && sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Loader2 className="h-8 w-8 animate-spin text-neutral-400 mb-2" />
            <p className="text-sm text-neutral-500 dark:text-neutral-400">
              Loading sources...
            </p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center mb-3">
              <X className="h-6 w-6 text-red-500" />
            </div>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-3">
              {error}
            </p>
            <button
              onClick={fetchSources}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                "bg-neutral-100 dark:bg-neutral-800",
                "text-neutral-700 dark:text-neutral-300",
                "hover:bg-neutral-200 dark:hover:bg-neutral-700"
              )}
            >
              Try Again
            </button>
          </div>
        ) : sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <div className="w-12 h-12 rounded-full bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center mb-3">
              <Database className="h-6 w-6 text-neutral-400" />
            </div>
            <h3 className="text-sm font-medium text-neutral-900 dark:text-white mb-1">
              No cached sources
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">
              Extract website data using the Extractor page, then click "Save to
              Cache" to make it available here.
            </p>
            <Link
              href="/extractor"
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                "bg-violet-600 text-white",
                "hover:bg-violet-700"
              )}
            >
              <ExternalLink className="h-4 w-4" />
              Go to Extractor
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {sources.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                isSelected={selectedSourceId === source.id}
                onSelect={() => handleSelectSource(source)}
                onDelete={() => handleDeleteSource(source.id)}
                disabled={disabled}
                isDeleting={deletingSourceId === source.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer hint */}
      {sources.length > 0 && (
        <div
          className={cn(
            "flex-shrink-0 px-4 py-2",
            "border-t border-neutral-200 dark:border-neutral-700",
            selectedSourceId
              ? "bg-violet-50 dark:bg-violet-900/20"
              : "bg-neutral-50 dark:bg-neutral-800/50"
          )}
        >
          {disabled ? (
            <p className="text-xs text-neutral-400 dark:text-neutral-500">
              Source selection disabled while Agent is running.
            </p>
          ) : selectedSourceId ? (
            <p className="text-xs text-violet-700 dark:text-violet-400 font-medium">
              Source selected. Agent can now access this data.
            </p>
          ) : (
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Click a source to make it available to the Agent.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
