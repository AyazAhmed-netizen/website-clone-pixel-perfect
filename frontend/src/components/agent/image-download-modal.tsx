"use client";

import React, { useState, useCallback, useMemo } from "react";
import { cn } from "@/lib/utils";
import {
  X,
  Image as ImageIcon,
  Download,
  Loader2,
  Check,
  AlertCircle,
  Globe,
  Sun,
  Moon,
} from "lucide-react";
import type { WebContainer as WebContainerInstance } from "@webcontainer/api";

// ============================================
// Types
// ============================================

interface SelectedSource {
  id: string;
  title: string;
  url: string;
  theme: "light" | "dark";
}

interface ImageDownloadModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Files from WebContainer (path -> content) */
  files: Record<string, string>;
  /** WebContainer instance ref for writing files */
  webcontainerRef: React.RefObject<WebContainerInstance | null>;
  /** Callback when files are updated after image download */
  onFilesUpdated?: (updates: Record<string, string>) => void;
  /** Sync files from WebContainer (refresh file tree after download) */
  syncFilesFromContainer?: () => Promise<Record<string, string>>;
  /** Selected source for fetching images */
  selectedSource?: SelectedSource | null;
}

interface FetchedImage {
  url: string;
  content: string;  // Base64
  mime_type: string;
  filename: string;
  size: number;
}

type DownloadStatus = "idle" | "fetching" | "writing" | "replacing" | "done" | "error";

// Code file extensions for URL replacement
const CODE_EXTENSIONS = [".jsx", ".tsx", ".js", ".ts", ".html", ".css", ".vue", ".svelte"];

// ============================================
// Helper Functions
// ============================================

/**
 * Check if a file is a code file
 */
function isCodeFile(path: string): boolean {
  const ext = path.substring(path.lastIndexOf(".")).toLowerCase();
  return CODE_EXTENSIONS.includes(ext);
}

/**
 * Generate a safe filename from URL
 */
function generateFilename(url: string, index: number, mimeType: string): string {
  try {
    const urlObj = new URL(url);
    const pathParts = urlObj.pathname.split("/");
    const originalName = pathParts[pathParts.length - 1];

    // Get extension from original name or mime type
    let ext = "";
    if (originalName && originalName.includes(".")) {
      ext = originalName.substring(originalName.lastIndexOf("."));
    } else if (mimeType) {
      const mimeExt = mimeType.split("/")[1];
      if (mimeExt) {
        ext = `.${mimeExt.split(";")[0]}`;  // Handle "image/png; charset=utf-8"
      }
    }

    // Sanitize and limit length
    const baseName = originalName
      ? originalName.replace(/[^a-zA-Z0-9.-]/g, "_").substring(0, 50)
      : `image_${index}`;

    return baseName.endsWith(ext) ? baseName : `${baseName}${ext}`;
  } catch {
    return `image_${index}.png`;
  }
}

// ============================================
// Main Component
// ============================================

export function ImageDownloadModal({
  isOpen,
  onClose,
  files,
  webcontainerRef,
  onFilesUpdated,
  syncFilesFromContainer,
  selectedSource,
}: ImageDownloadModalProps) {
  // State
  const [status, setStatus] = useState<DownloadStatus>("idle");
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [fetchedImages, setFetchedImages] = useState<FetchedImage[]>([]);
  const [successCount, setSuccessCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Reset state when modal opens
  React.useEffect(() => {
    if (isOpen) {
      setStatus("idle");
      setProgress({ current: 0, total: 0 });
      setFetchedImages([]);
      setSuccessCount(0);
      setErrorMessage(null);
    }
  }, [isOpen]);

  // Status message
  const statusMessage = useMemo(() => {
    switch (status) {
      case "idle":
        return "Ready to fetch images";
      case "fetching":
        return "Fetching images from source...";
      case "writing":
        return `Writing images (${progress.current}/${progress.total})...`;
      case "replacing":
        return "Updating code references...";
      case "done":
        return `Complete! ${successCount} images downloaded`;
      case "error":
        return errorMessage || "An error occurred";
      default:
        return "";
    }
  }, [status, progress, successCount, errorMessage]);

  // Progress percentage
  const progressPercent = useMemo(() => {
    if (status === "idle") return 0;
    if (status === "fetching") return 20;
    if (status === "writing") {
      return 20 + (progress.total > 0 ? (progress.current / progress.total) * 60 : 0);
    }
    if (status === "replacing") return 90;
    if (status === "done") return 100;
    return 0;
  }, [status, progress]);

  // Main fetch and download function
  const handleFetchImages = useCallback(async () => {
    if (!selectedSource?.url) {
      setErrorMessage("No source selected");
      setStatus("error");
      return;
    }

    const container = webcontainerRef.current;
    if (!container) {
      setErrorMessage("WebContainer not available");
      setStatus("error");
      return;
    }

    try {
      // Step 1: Fetch images from Playwright API
      setStatus("fetching");
      setErrorMessage(null);

      console.log(`[ImageDownload] Fetching from: ${selectedSource.url}, theme: ${selectedSource.theme}`);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001"}/api/playwright/resources`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: selectedSource.url,
            theme: selectedSource.theme,
            viewport_width: 1920,
            viewport_height: 1080,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error || "Failed to fetch images");
      }

      const images: FetchedImage[] = result.images || [];
      setFetchedImages(images);

      if (images.length === 0) {
        setStatus("done");
        setSuccessCount(0);
        return;
      }

      // Step 2: Write images to WebContainer
      setStatus("writing");
      setProgress({ current: 0, total: images.length });

      // Ensure output directory exists
      try {
        await container.fs.mkdir("/public/images", { recursive: true });
      } catch {
        // Directory might already exist
      }

      const urlMapping: Record<string, string> = {};
      let writeSuccess = 0;

      for (let i = 0; i < images.length; i++) {
        const img = images[i];
        try {
          // Generate safe filename
          const filename = generateFilename(img.url, i, img.mime_type);
          const localPath = `/public/images/${filename}`;

          // Convert base64 to binary and write
          const binaryData = Uint8Array.from(atob(img.content), (c) => c.charCodeAt(0));
          await container.fs.writeFile(localPath, binaryData);

          // Map original URL to local path (without /public prefix for src)
          urlMapping[img.url] = `/images/${filename}`;
          writeSuccess++;

          setProgress({ current: i + 1, total: images.length });
        } catch (writeError) {
          console.error(`[ImageDownload] Failed to write: ${img.url}`, writeError);
        }
      }

      // Step 3: Replace URLs in code files
      setStatus("replacing");

      if (Object.keys(urlMapping).length > 0) {
        const fileUpdates: Record<string, string> = {};

        for (const [path, content] of Object.entries(files)) {
          if (!isCodeFile(path) || !content) continue;

          let newContent = content;
          let hasChanges = false;

          for (const [originalUrl, localPath] of Object.entries(urlMapping)) {
            if (newContent.includes(originalUrl)) {
              newContent = newContent.split(originalUrl).join(localPath);
              hasChanges = true;
            }
          }

          if (hasChanges) {
            const normalizedPath = path.startsWith("/") ? path : `/${path}`;
            await container.fs.writeFile(normalizedPath, newContent);
            fileUpdates[path] = newContent;
          }
        }

        // Notify parent about file updates
        if (onFilesUpdated && Object.keys(fileUpdates).length > 0) {
          onFilesUpdated(fileUpdates);
        }
      }

      // Step 4: Sync files
      if (syncFilesFromContainer && writeSuccess > 0) {
        try {
          await syncFilesFromContainer();
        } catch (syncError) {
          console.error("[ImageDownload] Sync error:", syncError);
        }
      }

      // Done!
      setSuccessCount(writeSuccess);
      setStatus("done");

      console.log(`[ImageDownload] Complete: ${writeSuccess}/${images.length} images`);

    } catch (error) {
      console.error("[ImageDownload] Error:", error);
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
      setStatus("error");
    }
  }, [selectedSource, webcontainerRef, files, onFilesUpdated, syncFilesFromContainer]);

  if (!isOpen) return null;

  // Extract domain from URL for display
  const sourceDomain = selectedSource?.url
    ? (() => {
        try {
          return new URL(selectedSource.url).hostname;
        } catch {
          return selectedSource.url;
        }
      })()
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5 text-violet-500" />
            <h2 className="text-base font-semibold text-neutral-900 dark:text-white">
              Download Images
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <X className="h-4 w-4 text-neutral-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Source Info */}
          {selectedSource ? (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-700">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-violet-100 dark:bg-violet-900/40 flex items-center justify-center">
                <Globe className="h-4 w-4 text-violet-600 dark:text-violet-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">
                  {selectedSource.title}
                </p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">
                  {sourceDomain}
                </p>
              </div>
              <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-neutral-200 dark:bg-neutral-700">
                {selectedSource.theme === "dark" ? (
                  <Moon className="h-3 w-3 text-neutral-600 dark:text-neutral-300" />
                ) : (
                  <Sun className="h-3 w-3 text-neutral-600 dark:text-neutral-300" />
                )}
                <span className="text-xs text-neutral-600 dark:text-neutral-300 capitalize">
                  {selectedSource.theme}
                </span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center p-6 rounded-lg bg-neutral-50 dark:bg-neutral-800/50 border border-dashed border-neutral-300 dark:border-neutral-600">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                No source selected. Select a source from the Sources panel.
              </p>
            </div>
          )}

          {/* Progress Section */}
          {status !== "idle" && (
            <div className="space-y-2">
              {/* Progress Bar */}
              <div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-300",
                    status === "error"
                      ? "bg-red-500"
                      : status === "done"
                      ? "bg-green-500"
                      : "bg-violet-500"
                  )}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              {/* Status Message */}
              <div className="flex items-center gap-2">
                {status === "fetching" || status === "writing" || status === "replacing" ? (
                  <Loader2 className="h-4 w-4 text-violet-500 animate-spin" />
                ) : status === "done" ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : status === "error" ? (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                ) : null}
                <span
                  className={cn(
                    "text-sm",
                    status === "error"
                      ? "text-red-500"
                      : status === "done"
                      ? "text-green-600 dark:text-green-400"
                      : "text-neutral-600 dark:text-neutral-400"
                  )}
                >
                  {statusMessage}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50">
          {status === "done" || status === "error" ? (
            <button
              onClick={onClose}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                "bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-200",
                "hover:bg-neutral-300 dark:hover:bg-neutral-600"
              )}
            >
              Close
            </button>
          ) : (
            <>
              <button
                onClick={onClose}
                disabled={status !== "idle"}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  "text-neutral-600 dark:text-neutral-400",
                  "hover:bg-neutral-100 dark:hover:bg-neutral-800",
                  status !== "idle" && "opacity-50 cursor-not-allowed"
                )}
              >
                Cancel
              </button>
              <button
                onClick={handleFetchImages}
                disabled={!selectedSource || status !== "idle"}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  "bg-violet-600 hover:bg-violet-700 text-white",
                  (!selectedSource || status !== "idle") && "opacity-50 cursor-not-allowed"
                )}
              >
                {status === "idle" ? (
                  <>
                    <Download className="h-4 w-4" />
                    Fetch Images
                  </>
                ) : (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Processing...
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
