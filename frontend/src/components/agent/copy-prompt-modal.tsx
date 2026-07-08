"use client";

import React, { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  X,
  ChevronDown,
  Check,
  Plus,
  Copy,
  ExternalLink,
} from "lucide-react";
import {
  PLATFORMS,
  type PlatformType,
  generatePrompt,
  copyToClipboard,
} from "@/lib/prompt-templates";
import type { ExportableFile } from "@/lib/code-export-utils";
import { PlatformIcon } from "./platform-icons";

// ============================================
// Types
// ============================================

interface CopyPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  files: ExportableFile[];
  projectName?: string;
}

// ============================================
// Platform URL Map
// ============================================

const PLATFORM_URLS: Record<PlatformType, string> = {
  bolt: "https://bolt.new",
  "claude-code": "https://claude.ai",
  cursor: "https://cursor.com",
  lovable: "https://lovable.dev",
  replit: "https://replit.com",
  v0: "https://v0.dev",
};

// ============================================
// Main Component
// ============================================

export function CopyPromptModal({
  isOpen,
  onClose,
  files,
  projectName = "Nexting Project",
}: CopyPromptModalProps) {
  const [selectedPlatform, setSelectedPlatform] =
    useState<PlatformType>("claude-code");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [additionalContext, setAdditionalContext] = useState("");
  const [showContextInput, setShowContextInput] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  // Get selected platform info
  const selectedPlatformInfo = PLATFORMS.find((p) => p.id === selectedPlatform);

  // Handle copy prompt
  const handleCopyPrompt = useCallback(async () => {
    const prompt = generatePrompt({
      files,
      platform: selectedPlatform,
      additionalContext: additionalContext.trim() || undefined,
      projectName,
    });

    const success = await copyToClipboard(prompt);

    if (success) {
      setIsCopied(true);
      setTimeout(() => {
        setIsCopied(false);
        onClose();
      }, 1500);
    }
  }, [files, selectedPlatform, additionalContext, projectName, onClose]);

  // Handle platform select
  const handleSelectPlatform = useCallback((platform: PlatformType) => {
    setSelectedPlatform(platform);
    setIsDropdownOpen(false);
  }, []);

  // Handle open platform
  const handleOpenPlatform = useCallback(() => {
    const url = PLATFORM_URLS[selectedPlatform];
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [selectedPlatform]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className={cn(
          "fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
          "w-full max-w-[340px]",
          "bg-neutral-900 rounded-xl shadow-2xl",
          "border border-neutral-800/80"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-0.5">
          <h2 className="text-sm font-semibold text-white">Copy Prompt</h2>
          <button
            onClick={onClose}
            className={cn(
              "p-1 rounded-md transition-colors",
              "text-neutral-500 hover:text-white",
              "hover:bg-neutral-800"
            )}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="px-4 py-3 space-y-3.5">
          {/* Prompt Type */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-neutral-400">
              Prompt Type
            </label>

            {/* Custom Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className={cn(
                  "w-full flex items-center justify-between",
                  "px-3 py-2.5 rounded-lg",
                  "bg-neutral-800/80 border border-neutral-700/60",
                  "text-white text-xs font-medium",
                  "hover:border-neutral-600 transition-all duration-200",
                  isDropdownOpen && "border-neutral-600 ring-1 ring-neutral-600"
                )}
              >
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 flex items-center justify-center">
                    <PlatformIcon platform={selectedPlatform} size={16} />
                  </div>
                  <span>{selectedPlatformInfo?.name}</span>
                </div>
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 text-neutral-500 transition-transform duration-200",
                    isDropdownOpen && "rotate-180"
                  )}
                />
              </button>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setIsDropdownOpen(false)}
                  />
                  <div
                    className={cn(
                      "absolute z-20 w-full mt-1.5",
                      "bg-neutral-800 rounded-lg",
                      "border border-neutral-700/60",
                      "shadow-xl shadow-black/30 overflow-hidden",
                      "animate-in fade-in-0 zoom-in-95 duration-150"
                    )}
                  >
                    {PLATFORMS.map((platform) => (
                      <button
                        key={platform.id}
                        onClick={() => handleSelectPlatform(platform.id)}
                        className={cn(
                          "w-full flex items-center gap-2 px-3 py-2.5",
                          "text-xs text-left transition-all duration-150",
                          selectedPlatform === platform.id
                            ? "bg-neutral-700/70 text-white"
                            : "text-neutral-300 hover:bg-neutral-700/40 hover:text-white"
                        )}
                      >
                        <div className="w-4 h-4 flex items-center justify-center">
                          <PlatformIcon platform={platform.id} size={16} />
                        </div>
                        <span className="flex-1 font-medium">{platform.name}</span>
                        {selectedPlatform === platform.id && (
                          <Check className="h-3.5 w-3.5 text-blue-400" />
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Platform Description & Link */}
            <div className="flex items-start justify-between gap-1.5">
              <p className="text-[11px] text-neutral-500 leading-relaxed">
                {selectedPlatformInfo?.description}
              </p>
              <button
                onClick={handleOpenPlatform}
                className={cn(
                  "flex-shrink-0 p-1 rounded-md transition-colors",
                  "text-neutral-500 hover:text-blue-400",
                  "hover:bg-neutral-800"
                )}
                title={`Open ${selectedPlatformInfo?.name}`}
              >
                <ExternalLink className="h-3 w-3" />
              </button>
            </div>
          </div>

          {/* Additional Context */}
          <div>
            {!showContextInput ? (
              <button
                onClick={() => setShowContextInput(true)}
                className={cn(
                  "flex items-center gap-1.5 text-xs",
                  "text-neutral-400 hover:text-white transition-colors duration-200",
                  "px-2 py-1.5 -mx-2 rounded-md hover:bg-neutral-800/50"
                )}
              >
                <Plus className="h-3.5 w-3.5" />
                Add additional context
              </button>
            ) : (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-neutral-400">
                    Additional Context
                  </label>
                  <button
                    onClick={() => {
                      setShowContextInput(false);
                      setAdditionalContext("");
                    }}
                    className="text-[10px] text-neutral-500 hover:text-red-400 transition-colors"
                  >
                    Remove
                  </button>
                </div>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  placeholder="Add any additional instructions..."
                  className={cn(
                    "w-full h-20 px-3 py-2 rounded-lg resize-none",
                    "bg-neutral-800/80 border border-neutral-700/60",
                    "text-white text-xs placeholder:text-neutral-500",
                    "focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/60",
                    "transition-all duration-200"
                  )}
                  autoFocus
                />
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="px-4 pb-4 pt-0.5 space-y-2">
          {/* Copy Prompt Button */}
          <button
            onClick={handleCopyPrompt}
            disabled={isCopied}
            className={cn(
              "w-full flex items-center justify-center gap-1.5",
              "px-3 py-2.5 rounded-lg font-medium text-xs",
              "transition-all duration-200",
              isCopied
                ? "bg-green-600 text-white shadow-md shadow-green-600/20"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20 hover:shadow-blue-500/30"
            )}
          >
            {isCopied ? (
              <>
                <Check className="h-3.5 w-3.5" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy Prompt
              </>
            )}
          </button>

          {/* File Count Info */}
          <p className="text-[10px] text-neutral-500 text-center">
            {files.length} file{files.length !== 1 ? "s" : ""} included
          </p>
        </div>
      </div>
    </>
  );
}
