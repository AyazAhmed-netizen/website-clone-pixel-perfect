"use client";

import React, { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Bot, Database, History, Settings, X } from "lucide-react";
import { LLMProviderPanel } from "../agent/llm-provider-panel";

interface ProjectHeaderProps {
  projectName: string;
  showChatPanel: boolean;
  onToggleChatPanel: () => void;
  showSourcePanel: boolean;
  onToggleSourcePanel: () => void;
  showCheckpointPanel: boolean;
  onToggleCheckpointPanel: () => void;
  status?: "idle" | "ready" | "booting" | "error";
}

export function ProjectHeader({
  projectName,
  showChatPanel,
  onToggleChatPanel,
  showSourcePanel,
  onToggleSourcePanel,
  showCheckpointPanel,
  onToggleCheckpointPanel,
  status = "idle",
}: ProjectHeaderProps) {
  const [showProviderPanel, setShowProviderPanel] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!showProviderPanel) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowProviderPanel(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showProviderPanel]);

  const statusColors: Record<string, string> = {
    booting: "bg-yellow-500",
    ready: "bg-green-500",
    error: "bg-red-500",
    idle: "bg-neutral-400",
  };

  const statusLabels: Record<string, string> = {
    booting: "Starting...",
    ready: "Ready",
    error: "Error",
    idle: "Idle",
  };

  return (
    <div className="flex-shrink-0 relative z-40" ref={panelRef}>
      {/* Header bar */}
      <div className={cn(
        "flex items-center justify-between px-4 py-1.5",
        "border-b border-neutral-200 dark:border-neutral-700",
        "bg-white dark:bg-neutral-900"
      )}>
        {/* Left */}
        <div className="flex items-center gap-3">
          {projectName && (
            <span className="px-2 py-1 text-sm font-medium text-neutral-900 dark:text-white">
              {projectName}
            </span>
          )}
          <div className="flex items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400">
            <span className={cn("w-2 h-2 rounded-full", statusColors[status])} />
            <span>{statusLabels[status]}</span>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleSourcePanel}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              showSourcePanel
                ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            )}
          >
            <Database className="h-4 w-4" />
            Sources
          </button>

          <button
            onClick={onToggleCheckpointPanel}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              showCheckpointPanel
                ? "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            )}
          >
            <History className="h-4 w-4" />
            Checkpoints
          </button>

          <button
            onClick={onToggleChatPanel}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              showChatPanel
                ? "bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            )}
          >
            <Bot className="h-4 w-4" />
            AI Assistant
          </button>

          {/* Settings / Provider toggle */}
          <button
            onClick={() => setShowProviderPanel((v) => !v)}
            title="AI Provider Settings"
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              showProviderPanel
                ? "bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-400"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            )}
          >
            {showProviderPanel ? <X className="h-4 w-4" /> : <Settings className="h-4 w-4" />}
            {showProviderPanel ? "Close" : "Provider"}
          </button>
        </div>
      </div>

      {/* Dropdown provider panel */}
      {showProviderPanel && (
        <div className="absolute right-0 top-full w-96 shadow-xl border border-neutral-200 dark:border-neutral-700 rounded-b-xl overflow-hidden bg-white dark:bg-neutral-900">
          <LLMProviderPanel />
        </div>
      )}
    </div>
  );
}
