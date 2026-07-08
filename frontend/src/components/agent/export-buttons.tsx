"use client";

import React, { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Copy, Download, Loader2, Check, Image as ImageIcon } from "lucide-react";
import { CopyPromptModal } from "./copy-prompt-modal";
import { ImageDownloadModal } from "./image-download-modal";
import {
  getExportableFiles,
  exportAsZip,
  type ExportOptions,
} from "@/lib/code-export-utils";
import type { WebContainer as WebContainerInstance } from "@webcontainer/api";

// ============================================
// Types
// ============================================

/** Selected source for image download */
interface SelectedSourceInfo {
  id: string;
  title: string;
  url: string;
  theme: "light" | "dark";
}

interface ExportButtonsProps {
  /** Files from WebContainer state (path -> content) */
  files: Record<string, string>;
  /** Image URL mapping for restoration (localPath -> originalUrl) */
  imageUrlMapping?: Record<string, string>;
  /** Project name for exports */
  projectName?: string;
  /** Whether to show the buttons */
  visible?: boolean;
  /** WebContainer instance ref for image download */
  webcontainerRef?: React.RefObject<WebContainerInstance | null>;
  /** Callback when files are updated after image download */
  onFilesUpdated?: (updates: Record<string, string>) => void;
  /** Sync files from WebContainer before export (ensures latest content) */
  syncFilesFromContainer?: () => Promise<Record<string, string>>;
  /** Selected source for image fetching */
  selectedSource?: SelectedSourceInfo | null;
  className?: string;
}

// ============================================
// Main Component
// ============================================

export function ExportButtons({
  files,
  imageUrlMapping = {},
  projectName = "nexting-project",
  visible = true,
  webcontainerRef,
  onFilesUpdated,
  syncFilesFromContainer,
  selectedSource,
  className,
}: ExportButtonsProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isImageModalOpen, setIsImageModalOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  // Store synced files for modal
  const [syncedFilesForModal, setSyncedFilesForModal] = useState<ReturnType<typeof getExportableFiles>>([]);

  // Get exportable files with URL restoration
  const getFiles = useCallback((fileSource: Record<string, string>) => {
    const options: ExportOptions = {
      files: fileSource,
      imageUrlMapping,
      restoreUrls: true,
      excludePaths: ["/public/images/"],
    };
    return getExportableFiles(options);
  }, [imageUrlMapping]);

  // Handle Copy Code (download ZIP)
  const handleDownloadZip = useCallback(async () => {
    setIsDownloading(true);
    try {
      // Sync files from WebContainer to ensure we export the latest content
      let filesToExport = files;
      if (syncFilesFromContainer) {
        console.log("[Export] Syncing files from WebContainer before download...");
        filesToExport = await syncFilesFromContainer();
      }

      const options: ExportOptions = {
        files: filesToExport,
        imageUrlMapping,
        restoreUrls: true,
        excludePaths: ["/public/images/"],
      };
      await exportAsZip(options, projectName);
      setDownloadSuccess(true);
      setTimeout(() => setDownloadSuccess(false), 2000);
    } catch (error) {
      console.error("Failed to download ZIP:", error);
    } finally {
      setIsDownloading(false);
    }
  }, [files, imageUrlMapping, projectName, syncFilesFromContainer]);

  // Handle Copy Prompt (open modal)
  const handleOpenModal = useCallback(async () => {
    // Sync files from WebContainer to ensure we export the latest content
    let filesToExport = files;
    if (syncFilesFromContainer) {
      console.log("[Export] Syncing files from WebContainer before copying prompt...");
      filesToExport = await syncFilesFromContainer();
    }
    // Store synced files for modal
    setSyncedFilesForModal(getFiles(filesToExport));
    setIsModalOpen(true);
  }, [files, syncFilesFromContainer, getFiles]);

  if (!visible) return null;

  return (
    <>
      <div className={cn("flex items-center gap-1", className)}>
        {/* Download Images Button */}
        {webcontainerRef && (
          <button
            onClick={() => setIsImageModalOpen(true)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
              "text-neutral-500 dark:text-neutral-400",
              "hover:text-neutral-700 dark:hover:text-neutral-200",
              "hover:bg-neutral-200 dark:hover:bg-neutral-700"
            )}
            title="Scan and download external images"
          >
            <ImageIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Images</span>
          </button>
        )}

        {/* Copy Prompt Button */}
        <button
          onClick={handleOpenModal}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
            "text-neutral-500 dark:text-neutral-400",
            "hover:text-neutral-700 dark:hover:text-neutral-200",
            "hover:bg-neutral-200 dark:hover:bg-neutral-700"
          )}
          title="Copy code as prompt for AI platforms"
        >
          <Copy className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Copy Prompt</span>
        </button>

        {/* Copy Code (Download ZIP) Button */}
        <button
          onClick={handleDownloadZip}
          disabled={isDownloading}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
            "text-neutral-500 dark:text-neutral-400",
            "hover:text-neutral-700 dark:hover:text-neutral-200",
            "hover:bg-neutral-200 dark:hover:bg-neutral-700",
            isDownloading && "opacity-50 cursor-not-allowed"
          )}
          title="Download code as ZIP file"
        >
          {isDownloading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : downloadSuccess ? (
            <Check className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <Download className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">
            {downloadSuccess ? "Downloaded!" : "Copy Code"}
          </span>
        </button>
      </div>

      {/* Image Download Modal */}
      {webcontainerRef && (
        <ImageDownloadModal
          isOpen={isImageModalOpen}
          onClose={() => setIsImageModalOpen(false)}
          files={files}
          webcontainerRef={webcontainerRef}
          onFilesUpdated={onFilesUpdated}
          syncFilesFromContainer={syncFilesFromContainer}
          selectedSource={selectedSource}
        />
      )}

      {/* Copy Prompt Modal */}
      <CopyPromptModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        files={syncedFilesForModal}
        projectName={projectName}
      />
    </>
  );
}
