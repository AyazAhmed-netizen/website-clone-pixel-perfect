"use client";

/**
 * Error Detail Panel Component
 *
 * Displays a collapsible list of errors with details,
 * file locations, and fix suggestions.
 */

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  FileCode,
  Terminal,
  Eye,
  AlertCircle,
  AlertTriangle,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react";
import type { AggregatedError } from "@/hooks/use-error-aggregator";

interface ErrorDetailPanelProps {
  /** List of aggregated errors */
  errors: AggregatedError[];
  /** Callback when a file link is clicked */
  onFileClick?: (path: string, line?: number) => void;
  /** Callback when an error is dismissed */
  onDismissError?: (id: string) => void;
  /** Maximum height of the panel */
  maxHeight?: string;
  /** Additional CSS classes */
  className?: string;
}

const sourceIcons = {
  preview: Eye,
  console: Terminal,
  terminal: Terminal,
  build: FileCode,
};

const severityColors = {
  critical: {
    bg: "bg-red-50 dark:bg-red-900/20",
    border: "border-red-200 dark:border-red-800",
    text: "text-red-700 dark:text-red-300",
    icon: "text-red-500",
  },
  error: {
    bg: "bg-orange-50 dark:bg-orange-900/20",
    border: "border-orange-200 dark:border-orange-800",
    text: "text-orange-700 dark:text-orange-300",
    icon: "text-orange-500",
  },
  warning: {
    bg: "bg-yellow-50 dark:bg-yellow-900/20",
    border: "border-yellow-200 dark:border-yellow-800",
    text: "text-yellow-700 dark:text-yellow-300",
    icon: "text-yellow-500",
  },
};

interface ErrorItemProps {
  error: AggregatedError;
  onFileClick?: (path: string, line?: number) => void;
  onDismiss?: (id: string) => void;
}

function ErrorItem({ error, onFileClick, onDismiss }: ErrorItemProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const Icon = sourceIcons[error.source] || FileCode;
  const colors = severityColors[error.severity];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(error.message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = error.message;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const formatCategory = (category: string) => {
    return category
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div
      className={cn(
        "border rounded-lg overflow-hidden transition-all",
        colors.border
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 text-left text-xs transition-colors",
          colors.bg,
          "hover:opacity-90"
        )}
      >
        {/* Expand/Collapse Icon */}
        {isExpanded ? (
          <ChevronDown className="h-3 w-3 flex-shrink-0 opacity-60" />
        ) : (
          <ChevronRight className="h-3 w-3 flex-shrink-0 opacity-60" />
        )}

        {/* Severity Icon */}
        {error.severity === "critical" ? (
          <AlertCircle className={cn("h-3.5 w-3.5 flex-shrink-0", colors.icon)} />
        ) : (
          <AlertTriangle className={cn("h-3.5 w-3.5 flex-shrink-0", colors.icon)} />
        )}

        {/* Source Icon */}
        <Icon className="h-3 w-3 flex-shrink-0 opacity-60" />

        {/* Category */}
        <span className={cn("font-medium", colors.text)}>
          {formatCategory(error.category)}
        </span>

        {/* Message Preview */}
        <span className="flex-1 truncate opacity-70 font-mono text-[10px]">
          {error.message.slice(0, 60)}...
        </span>

        {/* Occurrence Count */}
        {error.occurrenceCount > 1 && (
          <span className="text-[10px] opacity-50 flex-shrink-0">
            x{error.occurrenceCount}
          </span>
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-3 py-2 text-xs border-t space-y-2 bg-white dark:bg-neutral-900">
          {/* Full Message */}
          <div className="relative group">
            <pre className="font-mono text-[10px] bg-neutral-100 dark:bg-neutral-800 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap break-words">
              {error.message}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-1 right-1 p-1 rounded bg-neutral-200 dark:bg-neutral-700 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Copy error message"
            >
              {copied ? (
                <Check className="h-3 w-3 text-green-500" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          </div>

          {/* File Location */}
          {error.file && (
            <div className="flex items-center gap-1">
              <FileCode className="h-3 w-3 opacity-50" />
              <button
                onClick={() => onFileClick?.(error.file!, error.line)}
                className="text-blue-600 dark:text-blue-400 hover:underline font-mono text-[10px]"
              >
                {error.file}
                {error.line && `:${error.line}`}
                {error.column && `:${error.column}`}
              </button>
              <ExternalLink className="h-2.5 w-2.5 opacity-40" />
            </div>
          )}

          {/* Fix Suggestions */}
          {error.fixStrategy && error.fixStrategy.length > 0 && (
            <div className="mt-2 pt-2 border-t border-dashed">
              <div className="font-semibold text-[10px] uppercase tracking-wider opacity-60 mb-1">
                Suggested Fix
              </div>
              <ul className="space-y-0.5 text-[10px]">
                {error.fixStrategy.map((step, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <span className="opacity-40">{i + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Stack Trace (if available) */}
          {error.stack && (
            <details className="mt-2 pt-2 border-t border-dashed">
              <summary className="text-[10px] uppercase tracking-wider opacity-60 cursor-pointer hover:opacity-80">
                Stack Trace
              </summary>
              <pre className="mt-1 font-mono text-[9px] bg-neutral-100 dark:bg-neutral-800 p-2 rounded overflow-x-auto max-h-24 overflow-y-auto whitespace-pre-wrap">
                {error.stack}
              </pre>
            </details>
          )}

          {/* Metadata */}
          <div className="flex items-center gap-3 pt-1 text-[9px] opacity-50">
            <span>Source: {error.source}</span>
            <span>ID: {error.id.slice(0, 12)}</span>
            <span>
              {new Date(error.lastOccurrence).toLocaleTimeString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export function ErrorDetailPanel({
  errors,
  onFileClick,
  onDismissError,
  maxHeight = "300px",
  className,
}: ErrorDetailPanelProps) {
  if (errors.length === 0) {
    return (
      <div className={cn("text-center py-4 text-xs text-neutral-500", className)}>
        No errors detected
      </div>
    );
  }

  // Group errors by severity for display
  const criticalErrors = errors.filter((e) => e.severity === "critical");
  const regularErrors = errors.filter((e) => e.severity === "error");
  const warnings = errors.filter((e) => e.severity === "warning");

  const groupedErrors = [...criticalErrors, ...regularErrors, ...warnings];

  return (
    <div
      className={cn("space-y-2 overflow-y-auto", className)}
      style={{ maxHeight }}
    >
      {groupedErrors.map((error) => (
        <ErrorItem
          key={error.id}
          error={error}
          onFileClick={onFileClick}
          onDismiss={onDismissError}
        />
      ))}
    </div>
  );
}

export default ErrorDetailPanel;
