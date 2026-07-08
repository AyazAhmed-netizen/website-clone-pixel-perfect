/**
 * Independent Image Downloader Hook
 *
 * Automatically scans code files for external image URLs and downloads them.
 * Completely independent from Agent/Worker flow.
 *
 * Features:
 * - Debounced scanning (waits for file writes to settle)
 * - Batch downloading of all external images
 * - Automatic URL replacement in code files
 * - Manual trigger support
 *
 * @module use-image-downloader
 */

import { useCallback, useRef, useEffect } from "react";
import type { WebContainer as WebContainerInstance } from "@webcontainer/api";

// ============================================
// Types
// ============================================

export interface ImageDownloadConfig {
  enabled: boolean;
  maxSizeKB: number;
  quality: number;
  maxWidth: number;
  maxHeight: number;
  maxImages: number;
  outputFormat: "webp" | "jpeg" | "png";
  outputDir: string;
  debounceMs: number;
}

export interface DownloadedImage {
  originalUrl: string;
  localPath: string;
  width: number;
  height: number;
  sizeKB: number;
}

export interface ScanResult {
  totalFiles: number;
  filesWithImages: number;
  totalUrls: number;
  uniqueUrls: string[];
}

export interface DownloadResult {
  success: boolean;
  downloaded: number;
  failed: number;
  images: DownloadedImage[];
  updatedFiles: string[];
}

// ============================================
// Constants
// ============================================

const DEFAULT_CONFIG: ImageDownloadConfig = {
  enabled: true,
  maxSizeKB: 500,
  quality: 80,
  maxWidth: 1200,
  maxHeight: 1200,
  maxImages: 50,
  outputFormat: "webp",
  outputDir: "/public/images",
  debounceMs: 2000,
};

// Code file extensions to scan
const CODE_EXTENSIONS = [".jsx", ".tsx", ".js", ".ts", ".html", ".css", ".vue", ".svelte"];

// Template/config files to exclude from scanning (contain example URLs)
const EXCLUDED_FILES = [
  "_image-proxy-plugin.js",
  "vite.config.js",
  "vite.config.ts",
  "next.config.js",
  "next.config.ts",
  "webpack.config.js",
  "tailwind.config.js",
  "postcss.config.js",
];

// Common image file extensions
const IMAGE_EXTENSIONS = "jpg|jpeg|png|gif|webp|svg|ico|avif|heic|heif|bmp|tiff?";

// Regex to match external image URLs with file extensions
// Matches: src="https://...", srcSet="https://...", url("https://..."), etc.
const IMAGE_URL_REGEX = new RegExp(
  `(?:src=["']|srcSet=["']|url\\(["']?|background(?:-image)?:\\s*url\\(["']?)(https?:\\/\\/[^"'\\s\\),]+\\.(?:${IMAGE_EXTENSIONS}))(?:["'\\)]|[\\s,])`,
  "gi"
);

// Match image URLs in JSX expressions like src={`...`} or src={"..."}
const JSX_IMAGE_URL_REGEX = new RegExp(
  `src=\\{[\`"'](https?:\\/\\/[^\`"'\\s\\),]+\\.(?:${IMAGE_EXTENSIONS}))[\`"']\\}`,
  "gi"
);

// Match URLs from common image CDNs (even without extensions)
// Extended list: Unsplash, Cloudinary, imgix, Imgur, Pexels, Shopify, CloudFront, GCS, Vercel, GitHub, Firebase, Picsum, etc.
const CDN_IMAGE_URL_REGEX = /(?:src=["']|srcSet=["']|url\(["']?)(https?:\/\/(?:images\.unsplash\.com|res\.cloudinary\.com|[a-z0-9-]+\.imgix\.net|i\.imgur\.com|images\.pexels\.com|cdn\.shopify\.com|[a-z0-9-]+\.cloudfront\.net|storage\.googleapis\.com|firebasestorage\.googleapis\.com|[a-z0-9-]+\.supabase\.co|vercel\.app|raw\.githubusercontent\.com|avatars\.githubusercontent\.com|user-images\.githubusercontent\.com|cdn\.sanity\.io|media\.graphassets\.com|cdn\.dribbble\.com|cdn\.pixabay\.com|picsum\.photos|loremflickr\.com|placekitten\.com|placehold\.co|via\.placeholder\.com)[^"'\s\),]+)(?:["'\)]|[\s,])/gi;

// Match srcSet URLs with size descriptors (e.g., "url 2x" or "url 800w")
const SRCSET_URL_REGEX = new RegExp(
  `(https?:\\/\\/[^"'\\s,]+\\.(?:${IMAGE_EXTENSIONS}))(?:\\s+[0-9.]+[wx])`,
  "gi"
);

// Match srcSet URLs from CDNs without extensions (e.g., picsum.photos)
const SRCSET_CDN_REGEX = /(https?:\/\/(?:picsum\.photos|loremflickr\.com|placekitten\.com|placehold\.co|via\.placeholder\.com)[^"'\s,]+)(?:\s+[0-9.]+[wx])/gi;

// Match image URLs in object properties like { image: "https://..." } or { src: "https://..." }
const OBJECT_PROPERTY_REGEX = new RegExp(
  `(?:image|src|url|poster|thumbnail|avatar|logo|icon|cover|banner|background|photo|picture)["']?\\s*:\\s*["'](https?:\\/\\/[^"'\\s]+\\.(?:${IMAGE_EXTENSIONS}))["']`,
  "gi"
);

// Match image URLs in arrays like ["https://example.com/1.jpg", "https://example.com/2.jpg"]
const ARRAY_URL_REGEX = new RegExp(
  `["'](https?:\\/\\/[^"'\\s]+\\.(?:${IMAGE_EXTENSIONS}))["']\\s*[,\\]]`,
  "gi"
);

// Match generic CDN patterns (cdn., images., img., media., assets.)
const GENERIC_CDN_REGEX = /(?:src=["']|srcSet=["']|url\(["']?|["'])(https?:\/\/(?:cdn|images?|img|media|assets?|static)\.[a-z0-9-]+\.[a-z]{2,}[^"'\s\),]*)(?:["'\)]|[\s,])/gi;

// Match data-src for lazy loading
const LAZY_LOAD_REGEX = new RegExp(
  `data-src=["'](https?:\\/\\/[^"'\\s]+\\.(?:${IMAGE_EXTENSIONS}))["']`,
  "gi"
);

// Match poster attribute for videos
const VIDEO_POSTER_REGEX = new RegExp(
  `poster=["'](https?:\\/\\/[^"'\\s]+\\.(?:${IMAGE_EXTENSIONS}))["']`,
  "gi"
);

// All regex patterns for scanning
const ALL_IMAGE_REGEXES = [
  IMAGE_URL_REGEX,
  JSX_IMAGE_URL_REGEX,
  CDN_IMAGE_URL_REGEX,
  LAZY_LOAD_REGEX,
  VIDEO_POSTER_REGEX,
  OBJECT_PROPERTY_REGEX,
  ARRAY_URL_REGEX,
  GENERIC_CDN_REGEX,
  SRCSET_URL_REGEX,
  SRCSET_CDN_REGEX,
];

// ============================================
// Hook
// ============================================

export function useImageDownloader(
  webcontainerRef: React.RefObject<WebContainerInstance | null>,
  filesState: Record<string, { content: string; version: number }>,
  onFileUpdate?: (path: string, content: string) => Promise<void>,
  logAgent?: (type: string, message: string) => void
) {
  // Configuration
  const configRef = useRef<ImageDownloadConfig>({ ...DEFAULT_CONFIG });

  // Debounce timer
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Processing flag to prevent concurrent runs
  const isProcessingRef = useRef(false);

  // Track processed URLs to avoid re-downloading
  const processedUrlsRef = useRef<Set<string>>(new Set());

  // ============================================
  // Utility Functions
  // ============================================

  const log = useCallback((level: "info" | "warn" | "error", message: string) => {
    const prefix = "[ImageDownloader]";
    if (level === "error") {
      console.error(`${prefix} ${message}`);
    } else if (level === "warn") {
      console.warn(`${prefix} ${message}`);
    } else {
      console.log(`${prefix} ${message}`);
    }

    if (logAgent) {
      if (level === "error") {
        logAgent("error", message);
      } else {
        logAgent("info", message);
      }
    }
  }, [logAgent]);

  const isCodeFile = useCallback((path: string): boolean => {
    const ext = path.substring(path.lastIndexOf(".")).toLowerCase();
    if (!CODE_EXTENSIONS.includes(ext)) return false;

    // Exclude template/config files that may contain example URLs
    const fileName = path.split("/").pop() || "";
    if (EXCLUDED_FILES.includes(fileName)) return false;

    return true;
  }, []);

  // ============================================
  // Core Functions
  // ============================================

  /**
   * Scan all code files for external image URLs
   */
  const scanAllFiles = useCallback((): ScanResult => {
    const result: ScanResult = {
      totalFiles: 0,
      filesWithImages: 0,
      totalUrls: 0,
      uniqueUrls: [],
    };

    const allUrls = new Set<string>();

    for (const [path, file] of Object.entries(filesState)) {
      if (!isCodeFile(path)) continue;

      result.totalFiles++;

      const content = file.content;
      if (!content || typeof content !== "string") continue;

      // Find all image URLs using all regex patterns
      const matchesInFile: string[] = [];

      for (const regexPattern of ALL_IMAGE_REGEXES) {
        // Create fresh regex instance to reset lastIndex
        const regex = new RegExp(regexPattern.source, regexPattern.flags);
        let match;

        while ((match = regex.exec(content)) !== null) {
          const url = match[1];
          // Skip already processed URLs and non-http URLs
          if (url && url.startsWith("http") && !processedUrlsRef.current.has(url)) {
            if (!allUrls.has(url)) {
              matchesInFile.push(url);
              allUrls.add(url);
            }
          }
        }
      }

      if (matchesInFile.length > 0) {
        result.filesWithImages++;
        result.totalUrls += matchesInFile.length;
      }
    }

    result.uniqueUrls = Array.from(allUrls);
    return result;
  }, [filesState, isCodeFile]);

  /**
   * Download images from URLs via backend API
   */
  const downloadImages = useCallback(async (urls: string[]): Promise<{
    success: boolean;
    urlMapping: Record<string, string>;
    downloadedImages: DownloadedImage[];
  }> => {
    if (urls.length === 0) {
      return { success: true, urlMapping: {}, downloadedImages: [] };
    }

    const config = configRef.current;

    try {
      log("info", `Downloading ${urls.length} images...`);

      const response = await fetch("http://localhost:5001/api/image-downloader/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          urls: urls.slice(0, config.maxImages),
          max_size_kb: config.maxSizeKB,
          quality: config.quality,
          max_width: config.maxWidth,
          max_height: config.maxHeight,
          max_images: config.maxImages,
          output_format: config.outputFormat,
          output_dir: config.outputDir,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        log("error", `API error: ${response.status} - ${errorText}`);
        return { success: false, urlMapping: {}, downloadedImages: [] };
      }

      const result = await response.json();
      log("info", `API returned: ${result.total_success}/${result.total_requested} images`);

      const container = webcontainerRef.current;
      if (!container) {
        log("error", "WebContainer not available");
        return { success: false, urlMapping: {}, downloadedImages: [] };
      }

      // Ensure output directory exists
      try {
        await container.fs.mkdir(config.outputDir, { recursive: true });
      } catch {
        // Directory might already exist
      }

      // Write images to WebContainer filesystem
      const urlMapping: Record<string, string> = {};
      const downloadedImages: DownloadedImage[] = [];

      for (const img of result.images) {
        if (img.success && img.base64_data) {
          try {
            const binaryData = Uint8Array.from(atob(img.base64_data), c => c.charCodeAt(0));
            const imgPath = img.local_path;

            await container.fs.writeFile(imgPath, binaryData);

            // Local path for src attribute
            const srcPath = imgPath.replace("/public", "");
            urlMapping[img.original_url] = srcPath;

            downloadedImages.push({
              originalUrl: img.original_url,
              localPath: srcPath,
              width: img.width,
              height: img.height,
              sizeKB: Math.round(img.compressed_size / 1024),
            });

            // Mark as processed
            processedUrlsRef.current.add(img.original_url);

            log("info", `✓ Saved: ${img.original_url.substring(0, 40)}... -> ${srcPath}`);
          } catch (writeError) {
            log("error", `Failed to write: ${img.local_path}`);
          }
        }
      }

      return { success: true, urlMapping, downloadedImages };
    } catch (error) {
      log("error", `Download error: ${error instanceof Error ? error.message : "Unknown"}`);
      return { success: false, urlMapping: {}, downloadedImages: [] };
    }
  }, [webcontainerRef, log]);

  /**
   * Update file contents to replace external URLs with local paths
   */
  const updateFileContents = useCallback(async (
    urlMapping: Record<string, string>
  ): Promise<string[]> => {
    const container = webcontainerRef.current;
    if (!container || Object.keys(urlMapping).length === 0) {
      return [];
    }

    const updatedFiles: string[] = [];

    for (const [path, file] of Object.entries(filesState)) {
      if (!isCodeFile(path)) continue;

      let content = file.content;
      if (!content || typeof content !== "string") continue;

      let hasChanges = false;

      // Replace all URLs in content
      for (const [originalUrl, localPath] of Object.entries(urlMapping)) {
        if (content.includes(originalUrl)) {
          content = content.split(originalUrl).join(localPath);
          hasChanges = true;
        }
      }

      if (hasChanges) {
        try {
          // Write updated content to WebContainer
          const normalizedPath = path.startsWith("/") ? path : `/${path}`;
          await container.fs.writeFile(normalizedPath, content);

          // Notify parent to update state
          if (onFileUpdate) {
            await onFileUpdate(path, content);
          }

          updatedFiles.push(path);
          log("info", `Updated: ${path}`);
        } catch (error) {
          log("error", `Failed to update: ${path}`);
        }
      }
    }

    return updatedFiles;
  }, [filesState, webcontainerRef, isCodeFile, onFileUpdate, log]);

  /**
   * Main function: Scan, download, and replace
   */
  const processImages = useCallback(async (): Promise<DownloadResult> => {
    if (!configRef.current.enabled) {
      return { success: true, downloaded: 0, failed: 0, images: [], updatedFiles: [] };
    }

    if (isProcessingRef.current) {
      log("warn", "Already processing, skipping...");
      return { success: false, downloaded: 0, failed: 0, images: [], updatedFiles: [] };
    }

    isProcessingRef.current = true;
    log("info", "=== Starting image scan and download ===");

    try {
      // Step 1: Scan all files
      const scanResult = scanAllFiles();
      log("info", `Scanned ${scanResult.totalFiles} files, found ${scanResult.uniqueUrls.length} new external images`);

      if (scanResult.uniqueUrls.length === 0) {
        log("info", "No new external images to download");
        return { success: true, downloaded: 0, failed: 0, images: [], updatedFiles: [] };
      }

      // Step 2: Download images
      const { success, urlMapping, downloadedImages } = await downloadImages(scanResult.uniqueUrls);

      if (!success || downloadedImages.length === 0) {
        return {
          success: false,
          downloaded: 0,
          failed: scanResult.uniqueUrls.length,
          images: [],
          updatedFiles: []
        };
      }

      // Step 3: Update file contents
      const updatedFiles = await updateFileContents(urlMapping);

      const result: DownloadResult = {
        success: true,
        downloaded: downloadedImages.length,
        failed: scanResult.uniqueUrls.length - downloadedImages.length,
        images: downloadedImages,
        updatedFiles,
      };

      log("info", `=== Complete: ${result.downloaded} images downloaded, ${result.updatedFiles.length} files updated ===`);

      return result;
    } finally {
      isProcessingRef.current = false;
    }
  }, [scanAllFiles, downloadImages, updateFileContents, log]);

  /**
   * Schedule a debounced processing run
   */
  const scheduleProcessing = useCallback(() => {
    if (!configRef.current.enabled) return;

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer
    debounceTimerRef.current = setTimeout(() => {
      processImages();
    }, configRef.current.debounceMs);

    log("info", `Scheduled image processing in ${configRef.current.debounceMs}ms`);
  }, [processImages, log]);

  /**
   * Cancel scheduled processing
   */
  const cancelScheduled = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
      log("info", "Cancelled scheduled processing");
    }
  }, [log]);

  /**
   * Update configuration
   */
  const setConfig = useCallback((config: Partial<ImageDownloadConfig>) => {
    configRef.current = { ...configRef.current, ...config };
  }, []);

  /**
   * Clear processed URLs cache (for re-scanning)
   */
  const clearCache = useCallback(() => {
    processedUrlsRef.current.clear();
    log("info", "Cleared processed URLs cache");
  }, [log]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return {
    // Core functions
    processImages,      // Manual trigger - scan, download, replace
    scheduleProcessing, // Debounced trigger
    cancelScheduled,    // Cancel pending processing

    // Utility functions
    scanAllFiles,       // Just scan, don't download
    clearCache,         // Clear processed URLs cache
    setConfig,          // Update config

    // State
    config: configRef.current,
    isProcessing: isProcessingRef.current,
  };
}
