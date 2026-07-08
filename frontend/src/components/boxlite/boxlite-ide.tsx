"use client";

import React, { useState, useCallback, useMemo, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import {
  Folder,
  FolderOpen,
  File,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Code2,
  Terminal as TerminalIcon,
  Eye,
  FilePlus,
  FolderPlus,
  ChevronsDownUp,
  RotateCcw,
  Maximize2,
  Monitor,
  Smartphone,
  Tablet,
  Loader2,
  X,
  Copy,
  Check,
  AlertTriangle,
  ScrollText,
  Globe,
  Hammer,
  Search,
  Wrench,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type {
  BoxLiteSandboxState,
  AgentLogEntry,
  FileDiffState,
} from "@/types/boxlite";
import { ExportButtons } from "@/components/agent/export-buttons";

// Dynamic import Monaco editor to avoid SSR issues
const MonacoCodeEditor = dynamic(
  () => import("@/components/agent/monaco-code-editor").then((mod) => mod.MonacoCodeEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full bg-neutral-100 dark:bg-[#1e1e1e] text-neutral-500 dark:text-[#858585]">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading editor...</span>
      </div>
    ),
  }
);

// ============================================
// Types
// ============================================

type IDEViewTab = "preview" | "code" | "terminal" | "logs";
type DeviceType = "desktop" | "mobile" | "tablet";

interface DevicePreset {
  width: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const DEVICE_PRESETS: Record<DeviceType, DevicePreset> = {
  desktop: { width: "100%", label: "Desktop", icon: Monitor },
  mobile: { width: "375px", label: "Mobile", icon: Smartphone },
  tablet: { width: "768px", label: "Tablet", icon: Tablet },
};

// ============================================
// Props Types
// ============================================

/** Selected source info for image download */
interface SelectedSourceInfo {
  id: string;
  title: string;
  url: string;
  theme: "light" | "dark";
}

interface BoxLiteIDEProps {
  state: BoxLiteSandboxState | null;
  isConnected: boolean;
  agentLogs: AgentLogEntry[];
  fileDiffs: FileDiffState;

  // File operations
  onFileSelect: (path: string) => void;
  onFileCreate: (path: string, content: string) => void;
  onFileDelete: (path: string) => void;
  onDiffClear: (path: string) => void;
  /** Write file to backend (for real-time sync) */
  onWriteFile: (path: string, content: string) => Promise<boolean>;

  // Terminal operations
  onTerminalInput: (input: string) => void;
  getTerminalOutput: (terminalId?: string, lines?: number) => string[];

  // Editor
  selectedFile: string | null;
  fileContent: string;
  onContentChange: (content: string) => void;
  onSaveFile: () => void;

  /** Whether the parent is currently being resized (disables iframe pointer events) */
  isResizing?: boolean;
  /** Selected source for image fetching */
  selectedSource?: SelectedSourceInfo | null;
  /** Project name for exports */
  projectName?: string;
}

// ============================================
// File Tree Types
// ============================================

interface FileSystemEntry {
  path: string;
  type: "file" | "directory";
  children?: FileSystemEntry[];
}

// ============================================
// File Explorer Component (VSCode Style)
// ============================================

interface FileExplorerProps {
  files: Record<string, string>;
  fileDiffs: Record<string, any>;
  activeFile: string | null;
  onFileSelect: (path: string) => void;
  onCreateFile?: (path: string, content: string) => void;
  onRefresh?: () => void;
}

function FileExplorer({
  files,
  fileDiffs,
  activeFile,
  onFileSelect,
  onCreateFile,
  onRefresh,
}: FileExplorerProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set(["/", "/src"])
  );
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState<"file" | "folder" | null>(null);
  const [newItemName, setNewItemName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isCreating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isCreating]);

  const getCreateParentPath = useCallback(() => {
    if (!selectedPath) return "/src";
    const isDir = !files[selectedPath];
    if (isDir) return selectedPath;
    const parts = selectedPath.split("/");
    parts.pop();
    return parts.join("/") || "/";
  }, [selectedPath, files]);

  const handleCreateFileClick = useCallback(() => {
    const parentPath = getCreateParentPath();
    setExpandedFolders(prev => new Set([...prev, parentPath]));
    setIsCreating("file");
    setNewItemName("");
  }, [getCreateParentPath]);

  const handleCreateFolderClick = useCallback(() => {
    const parentPath = getCreateParentPath();
    setExpandedFolders(prev => new Set([...prev, parentPath]));
    setIsCreating("folder");
    setNewItemName("");
  }, [getCreateParentPath]);

  const handleConfirmCreate = useCallback(() => {
    if (!newItemName.trim()) {
      setIsCreating(null);
      return;
    }
    const parentPath = getCreateParentPath();
    // Fix: avoid double slash when parent is root "/"
    const newPath = parentPath === "/"
      ? `/${newItemName.trim()}`
      : `${parentPath}/${newItemName.trim()}`;

    if (isCreating === "file") {
      onCreateFile?.(newPath, "");
      onFileSelect(newPath);
    } else if (isCreating === "folder") {
      onCreateFile?.(`${newPath}/.gitkeep`, "");
      setExpandedFolders(prev => new Set([...prev, newPath]));
    }
    setIsCreating(null);
    setNewItemName("");
  }, [isCreating, newItemName, getCreateParentPath, onCreateFile, onFileSelect]);

  const handleCancelCreate = useCallback(() => {
    setIsCreating(null);
    setNewItemName("");
  }, []);

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleConfirmCreate();
    } else if (e.key === "Escape") {
      handleCancelCreate();
    }
  }, [handleConfirmCreate, handleCancelCreate]);

  const handleCollapseAll = useCallback(() => {
    setExpandedFolders(new Set());
  }, []);

  const handleFolderToggle = useCallback((path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Build tree structure from flat files
  const buildFileTree = useCallback(
    (files: Record<string, string>): FileSystemEntry[] => {
      const root: Map<string, FileSystemEntry> = new Map();
      const sortedPaths = Object.keys(files).sort();

      for (const filePath of sortedPaths) {
        const parts = filePath.split("/").filter(Boolean);
        let currentPath = "";

        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          const parentPath = currentPath;
          currentPath = currentPath ? `${currentPath}/${part}` : `/${part}`;

          if (!root.has(currentPath)) {
            const isFile = i === parts.length - 1;
            const entry: FileSystemEntry = {
              path: currentPath,
              type: isFile ? "file" : "directory",
              children: isFile ? undefined : [],
            };
            root.set(currentPath, entry);

            if (parentPath) {
              const parent = root.get(parentPath);
              if (parent && parent.children) {
                parent.children.push(entry);
              }
            }
          }
        }
      }

      const rootEntries: FileSystemEntry[] = [];
      root.forEach((entry) => {
        const parts = entry.path.split("/").filter(Boolean);
        if (parts.length === 1) {
          rootEntries.push(entry);
        }
      });

      return rootEntries;
    },
    []
  );

  const fileTree = buildFileTree(files);
  const diffCount = Object.keys(fileDiffs).length;
  const createParentPath = isCreating ? getCreateParentPath() : null;

  // Get file icon based on extension
  const getFileIcon = (path: string) => {
    const ext = path.split(".").pop()?.toLowerCase();
    const iconClass = "h-4 w-4";
    switch (ext) {
      case "js":
      case "jsx":
        return <File className={cn(iconClass, "text-yellow-500")} />;
      case "ts":
      case "tsx":
        return <File className={cn(iconClass, "text-blue-500")} />;
      case "css":
      case "scss":
        return <File className={cn(iconClass, "text-purple-500")} />;
      case "html":
        return <File className={cn(iconClass, "text-orange-500")} />;
      case "json":
        return <File className={cn(iconClass, "text-yellow-600")} />;
      case "md":
        return <File className={cn(iconClass, "text-sky-500")} />;
      default:
        return <File className={cn(iconClass, "text-neutral-500 dark:text-[#858585]")} />;
    }
  };

  // Render file tree item
  const renderTreeItem = (entry: FileSystemEntry, depth: number): React.ReactNode => {
    const isExpanded = expandedFolders.has(entry.path);
    const isActive = activeFile === entry.path;
    const isSelected = selectedPath === entry.path;
    const hasDiff = entry.type === "file" && fileDiffs[entry.path];
    const shouldShowInput = isCreating && createParentPath === entry.path;

    if (entry.type === "directory") {
      const hasChildDiff = entry.children?.some((child) => {
        if (child.type === "file") return !!fileDiffs[child.path];
        const checkNested = (c: FileSystemEntry): boolean => {
          if (c.type === "file") return !!fileDiffs[c.path];
          return c.children?.some(checkNested) || false;
        };
        return checkNested(child);
      });

      return (
        <div key={entry.path}>
          <button
            onClick={(e) => {
              const target = e.target as HTMLElement;
              if (target.closest('[data-chevron]')) {
                handleFolderToggle(entry.path);
              } else {
                setSelectedPath(entry.path);
                if (!isExpanded) handleFolderToggle(entry.path);
              }
            }}
            className={cn(
              "flex items-center gap-1.5 w-full px-2 py-0.5 text-[13px] text-left",
              "hover:bg-neutral-200 dark:hover:bg-[#2a2d2e]",
              isSelected && "bg-blue-100 dark:bg-[#094771] ring-1 ring-blue-300 dark:ring-[#094771]",
              "text-neutral-700 dark:text-[#cccccc]"
            )}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
          >
            <span data-chevron>
              {isExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-neutral-500 dark:text-[#858585]" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-neutral-500 dark:text-[#858585]" />
              )}
            </span>
            {isExpanded ? (
              <FolderOpen className="h-4 w-4 text-amber-600 dark:text-[#dcb67a]" />
            ) : (
              <Folder className="h-4 w-4 text-amber-600 dark:text-[#dcb67a]" />
            )}
            <span className="truncate">{entry.path.split("/").pop()}</span>
            {hasChildDiff && (
              <span className="ml-auto w-2 h-2 rounded-full bg-blue-500 dark:bg-[#75beff] animate-pulse" />
            )}
          </button>
          {isExpanded && (
            <div>
              {shouldShowInput && (
                <div
                  className="flex items-center gap-1.5 px-2 py-0.5"
                  style={{ paddingLeft: `${(depth + 1) * 12 + 24}px` }}
                >
                  {isCreating === "folder" ? (
                    <Folder className="h-4 w-4 text-amber-600 dark:text-[#dcb67a]" />
                  ) : (
                    <File className="h-4 w-4 text-neutral-500 dark:text-[#858585]" />
                  )}
                  <input
                    ref={inputRef}
                    type="text"
                    value={newItemName}
                    onChange={(e) => setNewItemName(e.target.value)}
                    onKeyDown={handleInputKeyDown}
                    onBlur={handleCancelCreate}
                    placeholder={isCreating === "folder" ? "folder name" : "file name"}
                    className={cn(
                      "flex-1 px-1.5 py-0.5 text-[13px] rounded",
                      "bg-white dark:bg-[#3c3c3c]",
                      "border border-blue-400 dark:border-[#007acc]",
                      "text-neutral-900 dark:text-white",
                      "placeholder:text-neutral-400 dark:placeholder:text-[#858585]",
                      "focus:outline-none focus:ring-1 focus:ring-blue-400 dark:focus:ring-[#007acc]"
                    )}
                    autoFocus
                  />
                </div>
              )}
              {entry.children?.map((child) => renderTreeItem(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    return (
      <button
        key={entry.path}
        onClick={() => {
          setSelectedPath(entry.path);
          onFileSelect(entry.path);
        }}
        className={cn(
          "flex items-center gap-1.5 w-full px-2 py-0.5 text-[13px] text-left",
          "hover:bg-neutral-200 dark:hover:bg-[#2a2d2e]",
          isActive
            ? "bg-blue-100 dark:bg-[#094771] text-blue-900 dark:text-white"
            : isSelected
              ? "bg-blue-50 dark:bg-[#094771]/50 ring-1 ring-blue-200 dark:ring-[#094771]"
              : "text-neutral-700 dark:text-[#cccccc]",
          hasDiff && !isActive && !isSelected && "bg-blue-50 dark:bg-[#1e3a5f]/40"
        )}
        style={{ paddingLeft: `${depth * 12 + 24}px` }}
      >
        {getFileIcon(entry.path)}
        <span className="truncate">{entry.path.split("/").pop()}</span>
        {hasDiff && (
          <span
            className={cn(
              "ml-auto flex items-center gap-0.5 text-[10px] font-medium",
              "px-1.5 py-0.5 rounded",
              "bg-blue-100 dark:bg-[#264f78]",
              "text-blue-600 dark:text-[#75beff]"
            )}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 dark:bg-[#75beff]" />
            Modified
          </span>
        )}
      </button>
    );
  };

  return (
    <div
      className={cn(
        "flex flex-col h-full",
        "border-r border-neutral-200 dark:border-[#3c3c3c]",
        "bg-neutral-50 dark:bg-[#252526]"
      )}
    >
      {/* Toolbar */}
      <div
        className={cn(
          "flex items-center justify-between px-2 py-1",
          "border-b border-neutral-200 dark:border-[#3c3c3c]",
          "bg-neutral-50 dark:bg-[#252526]"
        )}
      >
        <div className="flex items-center gap-1">
          {diffCount > 0 && (
            <span
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-medium",
                "bg-blue-100 dark:bg-[#264f78]",
                "text-blue-600 dark:text-[#75beff]"
              )}
            >
              {diffCount} changed
            </span>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          <button
            onClick={handleCreateFileClick}
            className={cn(
              "p-1 rounded hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]",
              "text-neutral-500 dark:text-[#858585] hover:text-neutral-700 dark:hover:text-[#cccccc]"
            )}
            title="New File"
          >
            <FilePlus className="h-4 w-4" />
          </button>
          <button
            onClick={handleCreateFolderClick}
            className={cn(
              "p-1 rounded hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]",
              "text-neutral-500 dark:text-[#858585] hover:text-neutral-700 dark:hover:text-[#cccccc]"
            )}
            title="New Folder"
          >
            <FolderPlus className="h-4 w-4" />
          </button>
          <button
            onClick={onRefresh}
            className={cn(
              "p-1 rounded hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]",
              "text-neutral-500 dark:text-[#858585] hover:text-neutral-700 dark:hover:text-[#cccccc]"
            )}
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={handleCollapseAll}
            className={cn(
              "p-1 rounded hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]",
              "text-neutral-500 dark:text-[#858585] hover:text-neutral-700 dark:hover:text-[#cccccc]"
            )}
            title="Collapse All"
          >
            <ChevronsDownUp className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto py-1 bg-neutral-50 dark:bg-[#252526]">
        {fileTree.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-neutral-500 dark:text-[#858585] text-sm">
            <Folder className="h-8 w-8 mb-2 opacity-50" />
            <span>No files yet</span>
          </div>
        ) : (
          <>
            {isCreating && createParentPath === "/" && (
              <div
                className="flex items-center gap-1.5 px-2 py-0.5"
                style={{ paddingLeft: "24px" }}
              >
                {isCreating === "folder" ? (
                  <Folder className="h-4 w-4 text-amber-600 dark:text-[#dcb67a]" />
                ) : (
                  <File className="h-4 w-4 text-neutral-500 dark:text-[#858585]" />
                )}
                <input
                  ref={inputRef}
                  type="text"
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  onKeyDown={handleInputKeyDown}
                  onBlur={handleCancelCreate}
                  placeholder={isCreating === "folder" ? "folder name" : "file name"}
                  className={cn(
                    "flex-1 px-1.5 py-0.5 text-[13px] rounded",
                    "bg-white dark:bg-[#3c3c3c]",
                    "border border-blue-400 dark:border-[#007acc]",
                    "text-neutral-900 dark:text-white",
                    "placeholder:text-neutral-400 dark:placeholder:text-[#858585]",
                    "focus:outline-none focus:ring-1 focus:ring-blue-400 dark:focus:ring-[#007acc]"
                  )}
                  autoFocus
                />
              </div>
            )}
            {fileTree.map((entry) => renderTreeItem(entry, 0))}
          </>
        )}
      </div>
    </div>
  );
}

// ============================================
// Debounce Hook for Auto-Save
// ============================================

function useDebounce<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedFn = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay]
  ) as T;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return debouncedFn;
}

// ============================================
// Terminal Component
// ============================================

interface TerminalProps {
  output: string[];
  agentLogs: AgentLogEntry[];
  onInput: (input: string) => void;
}

function Terminal({ output, agentLogs, onInput }: TerminalProps) {
  const [inputValue, setInputValue] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output, agentLogs]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (inputValue.trim()) {
        onInput(inputValue + "\n");
        setInputValue("");
      }
    },
    [inputValue, onInput]
  );

  return (
    <div className="flex flex-col h-full bg-neutral-900 dark:bg-[#1e1e1e]">
      <div
        ref={outputRef}
        className="flex-1 overflow-y-auto p-4 font-mono text-sm"
      >
        {/* Agent logs */}
        {agentLogs.map((log, i) => (
          <div
            key={i}
            className={cn(
              log.type === "error"
                ? "text-red-400"
                : log.type === "command"
                  ? "text-green-400"
                  : log.type === "file"
                    ? "text-blue-400"
                    : "text-neutral-300 dark:text-[#d4d4d4]"
            )}
          >
            {log.type === "command" ? (
              <span className="text-green-500">$ </span>
            ) : null}
            {log.content}
          </div>
        ))}
        {/* Terminal output */}
        {output.map((line, i) => (
          <div key={`output-${i}`} className="text-neutral-300 dark:text-[#d4d4d4] whitespace-pre-wrap">
            {line}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="flex border-t border-neutral-700 dark:border-[#3c3c3c]">
        <span className="px-4 py-2 text-green-500 bg-neutral-800 dark:bg-[#252526]">$</span>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="flex-1 px-2 py-2 bg-neutral-800 dark:bg-[#252526] text-neutral-100 dark:text-[#d4d4d4] font-mono text-sm focus:outline-none"
          placeholder="Enter command..."
        />
      </form>
    </div>
  );
}

// ============================================
// Preview Component
// ============================================

interface PreviewViewProps {
  url: string | null;
  isLoading: boolean;
  hasError: boolean;
  errorMessage: string | null;
  device: DeviceType;
  onDeviceChange: (device: DeviceType) => void;
  isFullscreen: boolean;
  onFullscreenChange: (fullscreen: boolean) => void;
  showDeviceMenu: boolean;
  onShowDeviceMenuChange: (show: boolean) => void;
  onRefresh: () => void;
  previewKey: number;  // For forcing iframe refresh
  agentLogs?: AgentLogEntry[];  // For deriving current activity status
}

/**
 * Derive a human-readable status message from recent agent logs.
 * Returns null when the preview should just show the iframe normally.
 */
function deriveAgentActivity(agentLogs?: AgentLogEntry[]): {
  message: string;
  phase: "crawling" | "building" | "checking" | "fixing" | null;
} | null {
  if (!agentLogs || agentLogs.length === 0) return null;

  // Check the most recent 20 logs for activity keywords
  const recent = agentLogs.slice(-20);
  const lastLog = recent[recent.length - 1];
  const lastContent = (lastLog?.content || "").toLowerCase();

  // Crawling phase
  if (lastContent.includes("crawl") || lastContent.includes("extract") || lastContent.includes("scraping")) {
    return { message: "Crawling website...", phase: "crawling" };
  }

  // Building phase
  if (
    lastContent.includes('wrote file') || lastContent.includes('write_file') ||
    lastContent.includes('creating') || lastContent.includes('building') ||
    lastContent.includes('wrote 1 file') || lastContent.includes('wrote 2 file')
  ) {
    return { message: "Building components...", phase: "building" };
  }

  // Checking phase
  if (lastContent.includes("build error") || lastContent.includes("get_build_errors")) {
    return { message: "Checking for errors...", phase: "checking" };
  }

  // Fixing phase
  if (lastContent.includes("fix") || lastContent.includes("edit_file")) {
    return { message: "Fixing errors...", phase: "fixing" };
  }

  // If the last log was more than 3 seconds ago, don't show activity
  if (Date.now() - lastLog.timestamp > 3000) return null;

  return null;
}

/** Phase-specific icon/animation for the overlay */
function PhaseIndicator({ phase }: { phase: string }) {
  switch (phase) {
    case "crawling":
      return (
        <div className="relative">
          <Globe className="h-10 w-10 text-violet-400 animate-pulse" />
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-violet-500 rounded-full animate-ping" />
        </div>
      );
    case "building":
      return <Hammer className="h-10 w-10 text-blue-400 animate-bounce" />;
    case "checking":
      return <Search className="h-10 w-10 text-yellow-400 animate-pulse" />;
    case "fixing":
      return <Wrench className="h-10 w-10 text-orange-400 animate-spin" style={{ animationDuration: '2s' }} />;
    default:
      return <Loader2 className="h-10 w-10 text-neutral-400 animate-spin" />;
  }
}

function PreviewView({
  url,
  isLoading,
  hasError,
  errorMessage,
  device,
  onDeviceChange,
  isFullscreen,
  onFullscreenChange,
  showDeviceMenu,
  onShowDeviceMenuChange,
  onRefresh,
  previewKey,
  agentLogs,
}: PreviewViewProps) {
  const [copied, setCopied] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const currentDevice = DEVICE_PRESETS[device];

  // Derive current agent activity for the overlay
  const agentActivity = deriveAgentActivity(agentLogs);

  const handleRefresh = useCallback(() => {
    const iframe = iframeRef.current;
    if (iframe && iframe.contentWindow) {
      try {
        iframe.contentWindow.location.reload();
      } catch {
        const currentSrc = iframe.src;
        iframe.src = '';
        setTimeout(() => { iframe.src = currentSrc; }, 50);
      }
    } else if (iframe) {
      const currentSrc = iframe.src;
      iframe.src = '';
      setTimeout(() => { iframe.src = currentSrc; }, 50);
    }
    onRefresh();
  }, [onRefresh]);

  const handleCopyError = useCallback(async () => {
    if (errorMessage) {
      try {
        await navigator.clipboard.writeText(errorMessage);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error("Failed to copy error:", err);
      }
    }
  }, [errorMessage]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        onFullscreenChange(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, onFullscreenChange]);

  if (!url) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400">
        <Loader2 className="h-8 w-8 mb-3 animate-spin opacity-50" />
        <p className="text-sm">Preparing development environment...</p>
        <p className="text-xs mt-1 opacity-70">
          Installing dependencies and starting server
        </p>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="flex items-center justify-center h-full bg-neutral-100 dark:bg-neutral-800">
        <div className="bg-neutral-900 border border-red-500/50 rounded-lg max-w-2xl w-full max-h-[80%] flex flex-col shadow-2xl mx-4">
          <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-700">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <span className="font-semibold text-white">Preview Error</span>
            </div>
            <button
              onClick={handleCopyError}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                copied
                  ? "bg-green-500/20 text-green-400"
                  : "bg-neutral-700 hover:bg-neutral-600 text-white"
              )}
            >
              {copied ? (
                <>
                  <Check className="h-4 w-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy Error
                </>
              )}
            </button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <pre className="text-sm text-red-400 font-mono whitespace-pre-wrap break-words">
              {errorMessage || "Unknown error"}
            </pre>
          </div>
        </div>
      </div>
    );
  }

  // Fullscreen mode
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-black">
        <div
          className={cn(
            "absolute top-0 left-0 right-0 z-10",
            "flex items-center justify-between px-4 py-2",
            "bg-black/80 backdrop-blur-sm"
          )}
        >
          <div className="flex items-center gap-2">
            <span className="text-white text-sm font-medium">Preview</span>
            <span className="text-neutral-400 text-xs truncate max-w-[300px]">
              {url}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={() => onShowDeviceMenuChange(!showDeviceMenu)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
                  "text-neutral-300 hover:text-white hover:bg-white/10"
                )}
              >
                {React.createElement(currentDevice.icon, { className: "h-3.5 w-3.5" })}
                {currentDevice.label}
              </button>

              {showDeviceMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => onShowDeviceMenuChange(false)} />
                  <div
                    className={cn(
                      "absolute right-0 top-full mt-1 z-20 min-w-[120px]",
                      "bg-neutral-800 rounded-lg shadow-lg border border-neutral-700 py-1"
                    )}
                  >
                    {(Object.keys(DEVICE_PRESETS) as DeviceType[]).map((key) => {
                      const preset = DEVICE_PRESETS[key];
                      const Icon = preset.icon;
                      return (
                        <button
                          key={key}
                          onClick={() => {
                            onDeviceChange(key);
                            onShowDeviceMenuChange(false);
                          }}
                          className={cn(
                            "flex items-center gap-2 w-full px-3 py-1.5 text-sm text-left hover:bg-neutral-700",
                            device === key ? "text-[#75beff]" : "text-neutral-300"
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {preset.label}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            <button
              onClick={handleRefresh}
              className="p-1.5 rounded-lg transition-colors text-neutral-300 hover:text-white hover:bg-white/10"
              title="Refresh"
            >
              <RotateCcw className="h-4 w-4" />
            </button>

            <button
              onClick={() => onFullscreenChange(false)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors text-neutral-300 hover:text-white hover:bg-white/10"
              title="Exit Fullscreen (ESC)"
            >
              <X className="h-4 w-4" />
              Exit
            </button>
          </div>
        </div>

        <div
          className={cn(
            "h-full pt-12 relative",
            device !== "desktop" && "flex items-center justify-center bg-neutral-900"
          )}
        >
          <iframe
            key={previewKey}
            ref={iframeRef}
            src={url}
            className={cn(
              "bg-white",
              device === "desktop" ? "w-full h-full" : "rounded-lg shadow-2xl"
            )}
            style={{
              width: device === "desktop" ? "100%" : currentDevice.width,
              height: device === "desktop" ? "100%" : "calc(100vh - 80px)",
            }}
            title="Preview (Fullscreen)"
          />
          {/* Activity overlay for fullscreen mode */}
          {agentActivity && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
              <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex items-center gap-3 shadow-2xl">
                <PhaseIndicator phase={agentActivity.phase || ''} />
                <div>
                  <p className="text-sm font-medium text-white">{agentActivity.message}</p>
                  <p className="text-xs text-neutral-300">Working...</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div
        className={cn(
          "flex-1 min-h-0 overflow-hidden relative",
          device === "desktop"
            ? ""
            : "bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center p-4"
        )}
      >
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full bg-neutral-100 dark:bg-neutral-800 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-neutral-400" />
            <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading preview...</p>
          </div>
        ) : !url ? (
          /* No URL yet - dev server starting or no content */
          <div className="flex flex-col items-center justify-center h-full bg-neutral-100 dark:bg-neutral-800 gap-4">
            <div className="relative">
              <Code2 className="h-12 w-12 text-neutral-300 dark:text-neutral-600" />
              {agentActivity && (
                <div className="absolute -bottom-1 -right-1">
                  <Loader2 className="h-5 w-5 animate-spin text-violet-500" />
                </div>
              )}
            </div>
            {agentActivity ? (
              <div className="text-center">
                <div className="flex items-center gap-2 mb-1">
                  <PhaseIndicator phase={agentActivity.phase || ''} />
                  <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                    {agentActivity.message}
                  </p>
                </div>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  Preview will appear when dev server is ready
                </p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-sm text-neutral-500 dark:text-neutral-400">Starting dev server...</p>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">Preview will appear shortly</p>
              </div>
            )}
          </div>
        ) : (
          /* Normal preview with iframe */
          <div className="relative h-full">
            <iframe
              key={previewKey}
              ref={iframeRef}
              src={url}
              className={cn(
                "bg-white",
                device === "desktop" ? "w-full h-full" : "rounded-lg shadow-lg h-full"
              )}
              style={{
                width: device === "desktop" ? "100%" : currentDevice.width,
                maxHeight: device === "desktop" ? undefined : "600px",
              }}
              title="Preview"
            />
            {/* Activity overlay - shows on top of iframe when agent is actively working */}
            {agentActivity && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                <div className="bg-black/60 backdrop-blur-sm rounded-xl px-6 py-4 flex items-center gap-3 shadow-2xl">
                  <PhaseIndicator phase={agentActivity.phase || ''} />
                  <div>
                    <p className="text-sm font-medium text-white">{agentActivity.message}</p>
                    <p className="text-xs text-neutral-300">Working...</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// Logs View Component
// ============================================

function LogsView({ agentLogs }: { agentLogs: AgentLogEntry[] }) {
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [agentLogs]);

  const getLogIcon = (type: AgentLogEntry["type"]) => {
    switch (type) {
      case "error": return <span className="text-red-500">\u2717</span>;
      case "command": return <span className="text-green-500">$</span>;
      case "file": return <span className="text-blue-500">\u25CB</span>;
      case "info": return <span className="text-yellow-500">\u2139</span>;
      default: return <span className="text-neutral-400">\u2022</span>;
    }
  };

  return (
    <div className="flex flex-col h-full bg-neutral-950 dark:bg-[#1a1a2e]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-neutral-800">
        <ScrollText className="h-4 w-4 text-neutral-400" />
        <span className="text-xs font-medium text-neutral-300">Agent Activity Log</span>
        <span className="text-[10px] text-neutral-500">({agentLogs.length} entries)</span>
      </div>
      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1">
        {agentLogs.length === 0 ? (
          <div className="text-neutral-500 text-center py-8">
            No logs yet. Start a conversation to see agent activity.
          </div>
        ) : (
          agentLogs.map((log, i) => (
            <div
              key={i}
              className={cn(
                "flex items-start gap-2 py-1",
                log.type === "error" && "bg-red-500/5 rounded px-2 -mx-2"
              )}
            >
              <span className="flex-shrink-0 w-4 text-center">{getLogIcon(log.type)}</span>
              <span className={cn(
                "flex-1",
                log.type === "error"
                  ? "text-red-400"
                  : log.type === "command"
                    ? "text-green-400"
                    : log.type === "file"
                      ? "text-blue-400"
                      : log.type === "info"
                        ? "text-yellow-400"
                        : "text-neutral-400 dark:text-[#969696]"
              )}>
                {log.content}
              </span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

// ============================================
// Main BoxLite IDE Component
// ============================================

export function BoxLiteIDE({
  state,
  isConnected,
  agentLogs,
  fileDiffs,
  onFileSelect,
  onFileCreate,
  onFileDelete,
  onDiffClear,
  onWriteFile,
  onTerminalInput,
  getTerminalOutput,
  selectedFile,
  fileContent,
  onContentChange,
  onSaveFile,
  isResizing,
  selectedSource,
  projectName = "nexting-project",
}: BoxLiteIDEProps) {
  const [activeTab, setActiveTab] = useState<IDEViewTab>("preview");
  const [previewDevice, setPreviewDevice] = useState<DeviceType>("desktop");
  const [isPreviewFullscreen, setIsPreviewFullscreen] = useState(false);
  const [showDeviceMenu, setShowDeviceMenu] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);  // For forcing iframe refresh
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  const currentDevice = DEVICE_PRESETS[previewDevice];
  const DeviceIcon = currentDevice.icon;

  const terminalOutput = getTerminalOutput(undefined, 100);
  const isDevServerRunning = Boolean(state?.preview_url);

  // Cleanup refresh timer on unmount
  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  // Debounced preview refresh (500ms delay)
  const triggerPreviewRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = setTimeout(() => {
      setPreviewKey(k => k + 1);
      refreshTimerRef.current = null;
    }, 500);
  }, []);

  // Manual refresh (immediate)
  const handleManualRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    setPreviewKey(k => k + 1);
  }, []);

  // Debounced auto-save function (500ms delay)
  const debouncedSave = useDebounce(
    useCallback(async (path: string, content: string) => {
      if (!path) return;
      setIsSaving(true);
      try {
        await onWriteFile(path, content);
        console.log(`[BoxLiteIDE] Auto-saved: ${path}`);
        // Trigger preview refresh after save
        triggerPreviewRefresh();
      } catch (e) {
        console.error("[BoxLiteIDE] Auto-save failed:", e);
      } finally {
        setIsSaving(false);
      }
    }, [onWriteFile, triggerPreviewRefresh]),
    500
  );

  // Handle content change with auto-save
  const handleContentChange = useCallback((content: string) => {
    onContentChange(content);
    if (selectedFile) {
      debouncedSave(selectedFile, content);
    }
  }, [onContentChange, selectedFile, debouncedSave]);

  // Handle manual save (Ctrl+S)
  const handleManualSave = useCallback(async (content: string) => {
    if (!selectedFile) return;
    setIsSaving(true);
    try {
      await onWriteFile(selectedFile, content);
      console.log(`[BoxLiteIDE] Saved: ${selectedFile}`);
    } catch (e) {
      console.error("[BoxLiteIDE] Save failed:", e);
    } finally {
      setIsSaving(false);
    }
  }, [selectedFile, onWriteFile]);

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => setActiveTab(value as IDEViewTab)}
      className="flex flex-col h-full overflow-hidden bg-neutral-50 dark:bg-[#1e1e1e] gap-0"
    >
      {/* View Tabs - Shadcn Style */}
      <div
        className={cn(
          "flex items-center justify-between px-2 py-1 flex-shrink-0",
          "border-b border-neutral-200 dark:border-[#3c3c3c]",
          "bg-neutral-100 dark:bg-[#252526]"
        )}
      >
        <TabsList className="bg-white dark:bg-[#1e1e1e] h-7 p-0.5 gap-0.5 rounded-md">
          {/* Preview Tab */}
          <TabsTrigger
            value="preview"
            className={cn(
              "flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded",
              "data-[state=active]:bg-neutral-200 dark:data-[state=active]:bg-[#3c3c3c] data-[state=active]:text-neutral-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm",
              "data-[state=inactive]:bg-transparent data-[state=inactive]:text-neutral-500 dark:data-[state=inactive]:text-[#969696]",
              "hover:text-neutral-700 dark:hover:text-[#cccccc] transition-all"
            )}
          >
            <Eye className="h-3.5 w-3.5" />
            Preview
          </TabsTrigger>

          {/* Code Tab */}
          <TabsTrigger
            value="code"
            className={cn(
              "flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded",
              "data-[state=active]:bg-neutral-200 dark:data-[state=active]:bg-[#3c3c3c] data-[state=active]:text-neutral-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm",
              "data-[state=inactive]:bg-transparent data-[state=inactive]:text-neutral-500 dark:data-[state=inactive]:text-[#969696]",
              "hover:text-neutral-700 dark:hover:text-[#cccccc] transition-all"
            )}
          >
            <Code2 className="h-3.5 w-3.5" />
            Code
          </TabsTrigger>

          {/* Terminal Tab */}
          <TabsTrigger
            value="terminal"
            className={cn(
              "flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded",
              "data-[state=active]:bg-neutral-200 dark:data-[state=active]:bg-[#3c3c3c] data-[state=active]:text-neutral-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm",
              "data-[state=inactive]:bg-transparent data-[state=inactive]:text-neutral-500 dark:data-[state=inactive]:text-[#969696]",
              "hover:text-neutral-700 dark:hover:text-[#cccccc] transition-all"
            )}
          >
            <TerminalIcon className="h-3.5 w-3.5" />
            Terminal
          </TabsTrigger>

          {/* Logs Tab */}
          <TabsTrigger
            value="logs"
            className={cn(
              "flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded",
              "data-[state=active]:bg-neutral-200 dark:data-[state=active]:bg-[#3c3c3c] data-[state=active]:text-neutral-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm",
              "data-[state=inactive]:bg-transparent data-[state=inactive]:text-neutral-500 dark:data-[state=inactive]:text-[#969696]",
              "hover:text-neutral-700 dark:hover:text-[#cccccc] transition-all"
            )}
          >
            <ScrollText className="h-3.5 w-3.5" />
            Logs
            {agentLogs.length > 0 && (
              <span className="ml-1 px-1 py-0 text-[10px] rounded-full bg-blue-500/20 text-blue-400">
                {agentLogs.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Right side toolbar */}
        <div className="flex items-center gap-1">
          {/* Preview Toolbar */}
          {activeTab === "preview" && (
            <>
              {/* Fullscreen */}
              <button
                onClick={() => setIsPreviewFullscreen(true)}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                  "text-neutral-500 dark:text-[#969696] hover:text-neutral-700 dark:hover:text-[#cccccc] hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]"
                )}
                title="Fullscreen"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>

              {/* Device Selector */}
              <div className="relative">
                <button
                  onClick={() => setShowDeviceMenu(!showDeviceMenu)}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                    "text-neutral-500 dark:text-[#969696] hover:text-neutral-700 dark:hover:text-[#cccccc] hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]"
                  )}
                >
                  <DeviceIcon className="h-3.5 w-3.5" />
                  {currentDevice.label}
                </button>

                {showDeviceMenu && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setShowDeviceMenu(false)} />
                    <div
                      className={cn(
                        "absolute right-0 top-full mt-1 z-20 min-w-[100px]",
                        "bg-white dark:bg-[#252526] rounded-md shadow-lg border border-neutral-200 dark:border-[#3c3c3c] py-1"
                      )}
                    >
                      {(Object.keys(DEVICE_PRESETS) as DeviceType[]).map((key) => {
                        const preset = DEVICE_PRESETS[key];
                        const Icon = preset.icon;
                        return (
                          <button
                            key={key}
                            onClick={() => {
                              setPreviewDevice(key);
                              setShowDeviceMenu(false);
                            }}
                            className={cn(
                              "flex items-center gap-2 w-full px-2.5 py-1 text-xs text-left hover:bg-neutral-100 dark:hover:bg-[#3c3c3c]",
                              previewDevice === key ? "text-blue-600 dark:text-[#75beff]" : "text-neutral-700 dark:text-[#cccccc]"
                            )}
                          >
                            <Icon className="h-3.5 w-3.5" />
                            {preset.label}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>

              {/* Refresh */}
              <button
                onClick={handleManualRefresh}
                className={cn(
                  "p-1 rounded transition-colors",
                  "text-neutral-500 dark:text-[#969696] hover:text-neutral-700 dark:hover:text-[#cccccc] hover:bg-neutral-200 dark:hover:bg-[#3c3c3c]"
                )}
                title="Refresh Preview"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </>
          )}

          {/* Terminal Status */}
          {activeTab === "terminal" && (
            <div className="flex items-center gap-1.5 px-2 py-1 text-xs">
              <span className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-green-500" : "bg-red-500")} />
              <span className="text-neutral-500 dark:text-[#969696]">
                {isDevServerRunning ? "running" : (state?.status || "...")}
              </span>
            </div>
          )}

          {/* Code Toolbar - Download & Copy Prompt */}
          {activeTab === "code" && (
            <ExportButtons
              files={state?.files || {}}
              projectName={projectName}
              visible={true}
              selectedSource={selectedSource}
            />
          )}
        </div>
      </div>

      {/* View Content */}
      <div className="flex-1 overflow-hidden min-h-0 relative">
        {/* Preview View */}
        <TabsContent value="preview" className="absolute inset-0 m-0 data-[state=active]:z-10 data-[state=inactive]:z-0 data-[state=inactive]:invisible">
          <PreviewView
            url={state?.preview_url || null}
            isLoading={state?.preview.is_loading || false}
            hasError={state?.preview.has_error || false}
            errorMessage={state?.preview.error_message || null}
            device={previewDevice}
            onDeviceChange={setPreviewDevice}
            isFullscreen={isPreviewFullscreen}
            onFullscreenChange={setIsPreviewFullscreen}
            showDeviceMenu={showDeviceMenu}
            onShowDeviceMenuChange={setShowDeviceMenu}
            onRefresh={handleManualRefresh}
            previewKey={previewKey}
            agentLogs={agentLogs}
          />
        </TabsContent>

        {/* Code View */}
        <TabsContent value="code" className="absolute inset-0 m-0 data-[state=active]:z-10 data-[state=inactive]:z-0 data-[state=inactive]:invisible" forceMount>
          <div className="flex h-full">
            {/* File Explorer */}
            <div className="w-48 flex-shrink-0">
              <FileExplorer
                files={state?.files || {}}
                fileDiffs={fileDiffs.diffs}
                activeFile={selectedFile}
                onFileSelect={onFileSelect}
                onCreateFile={onFileCreate}
              />
            </div>
            {/* Monaco Code Editor */}
            <div className="flex-1 min-w-0 relative">
              <MonacoCodeEditor
                content={fileContent}
                onChange={handleContentChange}
                filePath={selectedFile}
                onSave={handleManualSave}
              />
              {/* Saving indicator */}
              {isSaving && (
                <div className="absolute top-2 right-2 flex items-center gap-1.5 px-2 py-1 rounded bg-blue-500/90 text-white text-xs">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Saving...
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Terminal View */}
        <TabsContent value="terminal" className="absolute inset-0 m-0 data-[state=active]:z-10 data-[state=inactive]:z-0 data-[state=inactive]:invisible" forceMount>
          <Terminal
            output={terminalOutput}
            agentLogs={agentLogs}
            onInput={onTerminalInput}
          />
        </TabsContent>

        {/* Logs View */}
        <TabsContent value="logs" className="absolute inset-0 m-0 data-[state=active]:z-10 data-[state=inactive]:z-0 data-[state=inactive]:invisible" forceMount>
          <LogsView agentLogs={agentLogs} />
        </TabsContent>
      </div>
    </Tabs>
  );
}

export default BoxLiteIDE;
