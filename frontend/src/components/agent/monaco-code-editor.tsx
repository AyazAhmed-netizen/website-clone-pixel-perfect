"use client";

/**
 * Monaco Code Editor Component
 *
 * A fully-featured code editor powered by Monaco (VSCode's core).
 *
 * Features:
 * - Full syntax highlighting for JSX/TSX/CSS/JSON/etc.
 * - Multi-cursor editing
 * - Code folding
 * - Bracket matching
 * - Auto-indentation
 * - Search & replace (Ctrl+F, Ctrl+H)
 * - VSCode keyboard shortcuts
 * - Dark theme (VS Code Dark+)
 */

import React, { useCallback, useRef, useMemo, useEffect, useState } from "react";
import Editor, { OnMount, OnChange } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { cn } from "@/lib/utils";
import { ChevronRight, Loader2, Code2 } from "lucide-react";

// ============================================
// Theme Detection Hook
// ============================================

/**
 * Hook to detect system dark mode preference
 */
function useSystemTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    // Check if dark mode class is present on html element
    const checkTheme = () => {
      const isDark = document.documentElement.classList.contains("dark");
      setTheme(isDark ? "dark" : "light");
    };

    // Initial check
    checkTheme();

    // Observe changes to the html class
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  return theme;
}

// ============================================
// Types
// ============================================

interface MonacoCodeEditorProps {
  /** File content to display */
  content: string;
  /** Callback when content changes */
  onChange: (content: string) => void;
  /** Current file path (for language detection) */
  filePath: string | null;
  /** Callback when user saves (Ctrl+S) */
  onSave?: (content: string) => void;
  /** Additional className */
  className?: string;
}

// ============================================
// Language Detection
// ============================================

/**
 * Get Monaco language ID from file path
 */
function getLanguageFromPath(filePath: string | null): string {
  if (!filePath) return "plaintext";
  const ext = filePath.split(".").pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    js: "javascript",
    jsx: "javascript", // Monaco handles JSX in javascript mode
    ts: "typescript",
    tsx: "typescript", // Monaco handles TSX in typescript mode
    css: "css",
    scss: "scss",
    sass: "scss",
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
    sh: "shell",
    bash: "shell",
    zsh: "shell",
    yml: "yaml",
    yaml: "yaml",
    xml: "xml",
    sql: "sql",
    graphql: "graphql",
    gql: "graphql",
    vue: "vue",
    svelte: "svelte",
    svg: "xml",
  };
  return languageMap[ext || ""] || "plaintext";
}

/**
 * Get file icon color based on extension - works in both light/dark modes
 */
function getFileIconColor(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase();
  const colorMap: Record<string, string> = {
    js: "text-yellow-500",
    jsx: "text-yellow-500",
    ts: "text-blue-500",
    tsx: "text-blue-500",
    css: "text-purple-500",
    scss: "text-pink-500",
    html: "text-orange-500",
    json: "text-yellow-600",
    md: "text-sky-500",
  };
  return colorMap[ext || ""] || "text-neutral-500 dark:text-[#cccccc]";
}

/**
 * Get file type label
 */
function getFileTypeLabel(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase();
  const labelMap: Record<string, string> = {
    js: "JS",
    jsx: "JSX",
    ts: "TS",
    tsx: "TSX",
    css: "CSS",
    scss: "SCSS",
    html: "HTML",
    json: "JSON",
    md: "MD",
    py: "PY",
  };
  return labelMap[ext || ""] || ext?.toUpperCase() || "";
}

// ============================================
// Monaco Editor Component
// ============================================

export function MonacoCodeEditor({
  content,
  onChange,
  filePath,
  onSave,
  className,
}: MonacoCodeEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  // Detect system theme for Monaco
  const systemTheme = useSystemTheme();
  const monacoTheme = systemTheme === "dark" ? "vs-dark" : "light";

  // Derived values
  const language = useMemo(() => getLanguageFromPath(filePath), [filePath]);
  const fileName = filePath?.split("/").pop() || "";
  const fileTypeLabel = filePath ? getFileTypeLabel(filePath) : "";
  const fileIconColor = filePath ? getFileIconColor(filePath) : "";

  // Build breadcrumb path
  const breadcrumbParts = useMemo(() => {
    if (!filePath) return [];
    const parts = filePath.split("/").filter(Boolean);
    return parts.slice(0, -1); // Exclude filename
  }, [filePath]);

  // Handle editor mount
  const handleEditorMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    // Configure editor options for VSCode-like experience
    editor.updateOptions({
      // Font settings
      fontFamily: "'Menlo', 'Monaco', 'Courier New', monospace",
      fontSize: 13,
      lineHeight: 22,
      fontLigatures: true,

      // UI settings
      minimap: { enabled: true, scale: 1 },
      scrollBeyondLastLine: false,
      smoothScrolling: true,
      cursorBlinking: "smooth",
      cursorSmoothCaretAnimation: "on",

      // Editor behavior
      wordWrap: "off",
      tabSize: 2,
      insertSpaces: true,
      autoIndent: "full",
      formatOnPaste: true,
      formatOnType: true,

      // Features
      folding: true,
      foldingStrategy: "indentation",
      showFoldingControls: "mouseover",
      bracketPairColorization: { enabled: true },
      guides: {
        bracketPairs: true,
        indentation: true,
      },

      // Line numbers
      lineNumbers: "on",
      lineDecorationsWidth: 10,
      lineNumbersMinChars: 4,

      // Scrollbar
      scrollbar: {
        vertical: "auto",
        horizontal: "auto",
        verticalScrollbarSize: 10,
        horizontalScrollbarSize: 10,
      },

      // Highlighting
      renderWhitespace: "selection",
      renderLineHighlight: "all",
      occurrencesHighlight: "singleFile",
      selectionHighlight: true,

      // Suggestions
      quickSuggestions: true,
      suggestOnTriggerCharacters: true,
      acceptSuggestionOnEnter: "on",

      // Context menu
      contextmenu: true,
    });

    // Register Ctrl+S / Cmd+S for save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      const currentContent = editor.getValue();
      onSave?.(currentContent);
    });

    // Focus editor
    editor.focus();
  }, [onSave]);

  // Handle content change
  const handleChange: OnChange = useCallback((value) => {
    onChange(value || "");
  }, [onChange]);

  // Loading component
  const LoadingComponent = () => (
    <div className="flex items-center justify-center h-full bg-neutral-50 dark:bg-[#1e1e1e]">
      <Loader2 className="h-6 w-6 animate-spin text-neutral-500 dark:text-[#858585] mr-2" />
      <span className="text-neutral-500 dark:text-[#858585] text-sm">Loading editor...</span>
    </div>
  );

  // Empty state when no file selected
  if (!filePath) {
    return (
      <div className={cn("flex flex-col h-full bg-neutral-50 dark:bg-[#1e1e1e]", className)}>
        <div className="flex items-center justify-center h-full text-neutral-500 dark:text-[#858585]">
          <div className="text-center">
            <Code2 className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">Select a file to edit</p>
            <p className="text-xs mt-1 opacity-70">
              Use the file explorer on the left
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col h-full bg-neutral-50 dark:bg-[#1e1e1e]", className)}>
      {/* Breadcrumb - file path navigation */}
      <div
        className={cn(
          "flex items-center gap-1 px-3 py-1.5 flex-shrink-0",
          "bg-neutral-50 dark:bg-[#1e1e1e]",
          "border-b border-neutral-200 dark:border-[#3c3c3c]",
          "text-xs text-neutral-500 dark:text-[#858585]"
        )}
      >
        {breadcrumbParts.map((part, index) => (
          <React.Fragment key={index}>
            <span className="hover:text-neutral-700 dark:hover:text-[#cccccc] cursor-pointer">{part}</span>
            <ChevronRight className="h-3 w-3 text-neutral-500 dark:text-[#858585]" />
          </React.Fragment>
        ))}
        <span className={cn("font-medium", fileIconColor)}>{fileTypeLabel}</span>
        <span className="text-neutral-700 dark:text-[#cccccc]">{fileName}</span>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          language={language}
          value={content}
          theme={monacoTheme}
          onChange={handleChange}
          onMount={handleEditorMount}
          loading={<LoadingComponent />}
          options={{
            readOnly: false,
          }}
        />
      </div>
    </div>
  );
}

export default MonacoCodeEditor;
