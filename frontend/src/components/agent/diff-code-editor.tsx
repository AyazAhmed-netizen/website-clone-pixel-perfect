"use client";

import React, { useMemo, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { File, X, Plus, Minus } from "lucide-react";
import type { FileDiff, DiffLine, DiffLineType } from "@/lib/code-diff";
import { getDiffSummary } from "@/lib/code-diff";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

// ============================================
// Types
// ============================================

// ============================================
// Language Detection Utility
// ============================================

/**
 * Get Prism language from file path
 */
function getLanguageFromPath(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    js: "javascript",
    jsx: "jsx",
    ts: "typescript",
    tsx: "tsx",
    css: "css",
    scss: "scss",
    sass: "sass",
    less: "less",
    html: "html",
    htm: "html",
    json: "json",
    md: "markdown",
    py: "python",
    rb: "ruby",
    go: "go",
    rs: "rust",
    java: "java",
    c: "c",
    cpp: "cpp",
    h: "c",
    hpp: "cpp",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    yml: "yaml",
    yaml: "yaml",
    xml: "xml",
    sql: "sql",
    graphql: "graphql",
    gql: "graphql",
    vue: "vue",
    svelte: "svelte",
  };
  return languageMap[ext || ""] || "plaintext";
}

// ============================================
// Custom VSCode-like theme overrides
// ============================================

const customVscDarkPlus = {
  ...vscDarkPlus,
  'pre[class*="language-"]': {
    ...vscDarkPlus['pre[class*="language-"]'],
    background: "transparent",
    margin: 0,
    padding: 0,
  },
  'code[class*="language-"]': {
    ...vscDarkPlus['code[class*="language-"]'],
    background: "transparent",
  },
};

interface DiffCodeEditorProps {
  /** The file diff to display */
  diff: FileDiff;
  /** Whether to show the diff border/highlight */
  showDiffBorder?: boolean;
  /** Callback when user closes the diff view */
  onClose?: () => void;
  /** Additional className */
  className?: string;
}

interface DiffLineProps {
  line: DiffLine;
  index: number;
  language: string;
}

// ============================================
// Line Number Gutter
// ============================================

function LineNumberGutter({
  oldLineNumber,
  newLineNumber,
  type,
}: {
  oldLineNumber?: number;
  newLineNumber?: number;
  type: DiffLineType;
}) {
  // VSCode-like gutter colors - subtle background tint
  const gutterBg = {
    unchanged: "bg-[#1e1e1e]",
    added: "bg-[#1e3a1e]",
    removed: "bg-[#3a1e1e]",
  }[type];

  // Line number colors
  const textColor = {
    unchanged: "text-[#858585]",
    added: "text-[#6a9955]",
    removed: "text-[#f14c4c]",
  }[type];

  return (
    <div
      className={cn(
        "flex-shrink-0 flex select-none",
        "border-r border-[#333333]",
        gutterBg
      )}
    >
      {/* Single line number column - shows new line number for added, old for removed */}
      <span
        className={cn(
          "w-10 px-1.5 text-right text-xs font-mono leading-[22px]",
          textColor
        )}
      >
        {type === "removed" ? oldLineNumber || "" : newLineNumber || ""}
      </span>
    </div>
  );
}

// ============================================
// Single Diff Line Component
// ============================================

function DiffLineComponent({ line, index, language }: DiffLineProps) {
  // VSCode-like background colors for different line types
  const lineBg = {
    unchanged: "bg-[#1e1e1e] hover:bg-[#2a2d2e]",
    added: "bg-[#1e3a1e] hover:bg-[#264f26]",
    removed: "bg-[#3a1e1e] hover:bg-[#4f2626]",
  }[line.type];

  // Left border indicator (VSCode style - colored bar on left)
  const borderIndicator = {
    unchanged: "border-transparent",
    added: "border-[#4d9375]",
    removed: "border-[#f14c4c]",
  }[line.type];

  // Change indicator symbol
  const changeIndicator = {
    unchanged: " ",
    added: "+",
    removed: "-",
  }[line.type];

  const indicatorColor = {
    unchanged: "text-transparent",
    added: "text-[#4d9375]",
    removed: "text-[#f14c4c]",
  }[line.type];

  return (
    <div
      className={cn(
        "flex items-stretch min-h-[22px]",
        "border-l-2 transition-colors duration-75",
        lineBg,
        borderIndicator
      )}
    >
      {/* Line numbers gutter */}
      <LineNumberGutter
        oldLineNumber={line.oldLineNumber}
        newLineNumber={line.newLineNumber}
        type={line.type}
      />

      {/* Change indicator (+/-) */}
      <span
        className={cn(
          "w-4 flex-shrink-0 text-center font-mono text-xs leading-[22px] font-semibold",
          indicatorColor
        )}
      >
        {changeIndicator}
      </span>

      {/* Code content with syntax highlighting */}
      <div className="flex-1 min-w-0 overflow-x-auto">
        {line.content ? (
          <SyntaxHighlighter
            language={language}
            style={customVscDarkPlus}
            customStyle={{
              margin: 0,
              padding: "0 8px",
              background: "transparent",
              fontSize: "12px",
              lineHeight: "22px",
              whiteSpace: "pre",
              overflow: "visible",
            }}
            codeTagProps={{
              style: {
                background: "transparent",
              },
            }}
          >
            {line.content}
          </SyntaxHighlighter>
        ) : (
          <pre className="px-2 font-mono text-xs leading-[22px]">&nbsp;</pre>
        )}
      </div>
    </div>
  );
}

// ============================================
// Diff Header Component
// ============================================

function DiffHeader({
  diff,
  onClose,
}: {
  diff: FileDiff;
  onClose?: () => void;
}) {
  const fileName = diff.path.split("/").pop() || diff.path;

  return (
    <div
      className={cn(
        "flex items-center justify-between px-3 py-2",
        "bg-neutral-100 dark:bg-[#252526]",
        "border-b border-neutral-200 dark:border-[#3c3c3c]"
      )}
    >
      {/* File info */}
      <div className="flex items-center gap-2">
        <File className="h-4 w-4 text-blue-500 dark:text-[#75beff]" />
        <span className="text-sm font-medium text-neutral-700 dark:text-[#cccccc]">
          {fileName}
        </span>
        <span className="text-xs text-neutral-500 dark:text-[#858585]">
          {diff.path}
        </span>
        {/* Modified indicator */}
        <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-neutral-200 dark:bg-[#3c3c3c] text-neutral-700 dark:text-[#cccccc]">
          Modified
        </span>
      </div>

      {/* Stats and close */}
      <div className="flex items-center gap-3">
        {/* Change stats */}
        <div className="flex items-center gap-2 text-xs">
          {diff.addedCount > 0 && (
            <span className="flex items-center gap-0.5 text-green-600 dark:text-[#4d9375]">
              <Plus className="h-3 w-3" />
              {diff.addedCount}
            </span>
          )}
          {diff.removedCount > 0 && (
            <span className="flex items-center gap-0.5 text-red-500 dark:text-[#f14c4c]">
              <Minus className="h-3 w-3" />
              {diff.removedCount}
            </span>
          )}
        </div>

        {/* Close button */}
        {onClose && (
          <button
            onClick={onClose}
            className={cn(
              "p-1 rounded hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]",
              "text-neutral-500 dark:text-[#858585] hover:text-neutral-700 dark:hover:text-[#cccccc]"
            )}
            title="Close diff view"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================
// Main Diff Code Editor Component
// ============================================

export function DiffCodeEditor({
  diff,
  showDiffBorder = true,
  onClose,
  className,
}: DiffCodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Get language from file path
  const language = useMemo(() => getLanguageFromPath(diff.path), [diff.path]);

  // Auto-scroll to first change
  useEffect(() => {
    if (containerRef.current && diff.hasChanges) {
      const firstChange = containerRef.current.querySelector(
        '[data-change="true"]'
      );
      if (firstChange) {
        firstChange.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [diff]);

  // If no changes, show the new content with syntax highlighting
  if (!diff.hasChanges) {
    return (
      <div
        className={cn(
          "flex flex-col h-full",
          "bg-[#1e1e1e] text-[#cccccc]",
          className
        )}
      >
        <SyntaxHighlighter
          language={language}
          style={customVscDarkPlus}
          customStyle={{
            margin: 0,
            padding: "16px",
            background: "#1e1e1e",
            fontSize: "12px",
            lineHeight: "22px",
            flex: 1,
            overflow: "auto",
          }}
          showLineNumbers
          lineNumberStyle={{
            color: "#858585",
            minWidth: "3em",
            paddingRight: "1em",
            textAlign: "right",
          }}
        >
          {diff.newContent}
        </SyntaxHighlighter>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col h-full overflow-hidden",
        "bg-[#1e1e1e]",
        showDiffBorder && [
          "ring-1 ring-[#3c3c3c]",
          "rounded-md",
        ],
        className
      )}
    >
      {/* Diff Header */}
      <DiffHeader diff={diff} onClose={onClose} />

      {/* Diff Content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-[#1e1e1e]"
      >
        <div className="min-w-fit">
          {diff.lines.map((line, index) => (
            <div
              key={index}
              data-change={line.type !== "unchanged" ? "true" : "false"}
            >
              <DiffLineComponent line={line} index={index} language={language} />
            </div>
          ))}
        </div>
      </div>

      {/* Diff Footer - Summary */}
      <div
        className={cn(
          "flex items-center justify-between px-3 py-1.5",
          "bg-neutral-100 dark:bg-[#252526]",
          "border-t border-neutral-200 dark:border-[#3c3c3c]",
          "text-xs text-neutral-500 dark:text-[#858585]"
        )}
      >
        <span>
          Changes by AI Agent
        </span>
        <span>
          {diff.lines.length} lines total
        </span>
      </div>
    </div>
  );
}

// ============================================
// Multiple Files Diff View
// ============================================

interface MultiFileDiffProps {
  diffs: FileDiff[];
  activeFile?: string;
  onFileSelect?: (path: string) => void;
  onClearDiff?: (path: string) => void;
  onClearAllDiffs?: () => void;
  className?: string;
}

export function MultiFileDiff({
  diffs,
  activeFile,
  onFileSelect,
  onClearDiff,
  onClearAllDiffs,
  className,
}: MultiFileDiffProps) {
  // Filter to only files with changes
  const changedFiles = useMemo(
    () => diffs.filter((d) => d.hasChanges),
    [diffs]
  );

  const activeDiff = useMemo(
    () => changedFiles.find((d) => d.path === activeFile) || changedFiles[0],
    [changedFiles, activeFile]
  );

  if (changedFiles.length === 0) {
    return null;
  }

  return (
    <div className={cn("flex flex-col h-full bg-neutral-50 dark:bg-[#1e1e1e]", className)}>
      {/* File Tabs */}
      {changedFiles.length > 1 && (
        <div
          className={cn(
            "flex items-center gap-1 px-2 py-1",
            "bg-neutral-100 dark:bg-[#252526]",
            "border-b border-neutral-200 dark:border-[#3c3c3c]",
            "overflow-x-auto"
          )}
        >
          {changedFiles.map((diff) => (
            <button
              key={diff.path}
              onClick={() => onFileSelect?.(diff.path)}
              className={cn(
                "flex items-center gap-1.5 px-2 py-1 rounded text-xs",
                "transition-colors",
                diff.path === activeDiff?.path
                  ? "bg-white dark:bg-[#1e1e1e] text-neutral-700 dark:text-[#cccccc] shadow-sm"
                  : "text-neutral-500 dark:text-[#858585] hover:bg-neutral-200 dark:hover:bg-[#2a2d2e] hover:text-neutral-700 dark:hover:text-[#cccccc]"
              )}
            >
              <File className="h-3 w-3" />
              {diff.path.split("/").pop()}
              <span className="text-green-600 dark:text-[#4d9375]">+{diff.addedCount}</span>
              <span className="text-red-500 dark:text-[#f14c4c]">-{diff.removedCount}</span>
            </button>
          ))}

          {/* Clear all button */}
          {onClearAllDiffs && (
            <button
              onClick={onClearAllDiffs}
              className={cn(
                "ml-auto px-2 py-1 rounded text-xs",
                "text-neutral-500 dark:text-[#858585]",
                "hover:bg-red-100 dark:hover:bg-[#3a1e1e]",
                "hover:text-red-500 dark:hover:text-[#f14c4c]"
              )}
            >
              Clear All
            </button>
          )}
        </div>
      )}

      {/* Active Diff View */}
      {activeDiff && (
        <DiffCodeEditor
          diff={activeDiff}
          showDiffBorder={false}
          onClose={onClearDiff ? () => onClearDiff(activeDiff.path) : undefined}
          className="flex-1"
        />
      )}
    </div>
  );
}

export default DiffCodeEditor;
