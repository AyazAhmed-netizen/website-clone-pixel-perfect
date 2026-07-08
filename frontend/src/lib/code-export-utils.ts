/**
 * Code Export Utilities
 *
 * Provides utilities for exporting code from WebContainer:
 * - ZIP file generation
 * - URL restoration (local paths -> original URLs)
 * - File filtering (exclude /public/images/)
 */

// JSZip is dynamically imported to avoid build errors if not installed

// ============================================
// Types
// ============================================

export interface ExportableFile {
  path: string;
  content: string;
}

export interface ExportOptions {
  /** Files to export (path -> content) */
  files: Record<string, string>;
  /** URL mapping for restoration (localPath -> originalUrl) */
  imageUrlMapping?: Record<string, string>;
  /** Whether to restore original image URLs (default: true) */
  restoreUrls?: boolean;
  /** Paths to exclude (default: ["/public/images/"]) */
  excludePaths?: string[];
}

// ============================================
// Constants
// ============================================

/** Default paths to exclude from export */
const DEFAULT_EXCLUDE_PATHS = ["/public/images/"];

/** File extensions that may contain image URLs */
const CODE_FILE_EXTENSIONS = [
  ".jsx",
  ".tsx",
  ".js",
  ".ts",
  ".html",
  ".css",
  ".vue",
  ".svelte",
  ".scss",
  ".less",
];

// ============================================
// URL Restoration
// ============================================

/**
 * Restore original URLs in content
 *
 * Replaces local image paths with their original external URLs.
 *
 * @param content - File content with local paths
 * @param urlMapping - Map of localPath -> originalUrl
 * @returns Content with restored URLs
 */
export function restoreOriginalUrls(
  content: string,
  urlMapping: Record<string, string>
): string {
  let result = content;

  // Sort by path length (longest first) to avoid partial replacements
  const sortedEntries = Object.entries(urlMapping).sort(
    ([a], [b]) => b.length - a.length
  );

  for (const [localPath, originalUrl] of sortedEntries) {
    // Replace all occurrences of this local path
    result = result.split(localPath).join(originalUrl);
  }

  return result;
}

/**
 * Check if a file should have URLs restored
 */
function shouldRestoreUrls(filePath: string): boolean {
  const ext = filePath.substring(filePath.lastIndexOf(".")).toLowerCase();
  return CODE_FILE_EXTENSIONS.includes(ext);
}

// ============================================
// File Filtering
// ============================================

/**
 * Check if a path should be excluded from export
 */
function shouldExclude(path: string, excludePaths: string[]): boolean {
  return excludePaths.some(
    (excludePath) =>
      path.startsWith(excludePath) || path.includes(excludePath)
  );
}

/**
 * Get exportable files with URL restoration
 *
 * Filters out excluded paths and optionally restores original image URLs.
 */
export function getExportableFiles(options: ExportOptions): ExportableFile[] {
  const {
    files,
    imageUrlMapping = {},
    restoreUrls = true,
    excludePaths = DEFAULT_EXCLUDE_PATHS,
  } = options;

  const exportableFiles: ExportableFile[] = [];

  for (const [path, content] of Object.entries(files)) {
    // Skip excluded paths
    if (shouldExclude(path, excludePaths)) {
      continue;
    }

    // Skip binary file placeholders
    if (content.startsWith("[Binary")) {
      continue;
    }

    // Restore URLs if needed
    let finalContent = content;
    if (
      restoreUrls &&
      shouldRestoreUrls(path) &&
      Object.keys(imageUrlMapping).length > 0
    ) {
      finalContent = restoreOriginalUrls(content, imageUrlMapping);
    }

    exportableFiles.push({
      path: path.startsWith("/") ? path.slice(1) : path, // Remove leading slash
      content: finalContent,
    });
  }

  return exportableFiles;
}

// ============================================
// ZIP Generation
// ============================================

/**
 * Generate ZIP file from exportable files
 *
 * Uses dynamic import for JSZip to avoid build errors.
 *
 * @param files - Files to include in ZIP
 * @param projectName - Name for the ZIP file (default: "project")
 * @returns Blob of the ZIP file
 */
export async function generateZip(
  files: ExportableFile[],
  projectName: string = "project"
): Promise<Blob> {
  // Dynamic import JSZip
  const JSZip = (await import("jszip")).default;
  const zip = new JSZip();

  for (const file of files) {
    zip.file(file.path, file.content);
  }

  return await zip.generateAsync({
    type: "blob",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
  });
}

/**
 * Download ZIP file
 *
 * Creates a download link and triggers download.
 */
export function downloadZip(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export code as ZIP file
 *
 * Convenience function that combines all steps.
 */
export async function exportAsZip(
  options: ExportOptions,
  projectName: string = "nexting-project"
): Promise<void> {
  const files = getExportableFiles(options);
  const blob = await generateZip(files, projectName);
  const timestamp = new Date().toISOString().slice(0, 10);
  downloadZip(blob, `${projectName}-${timestamp}.zip`);
}

// ============================================
// File Structure Generation
// ============================================

/**
 * Generate file structure tree as string
 *
 * Creates a visual tree representation of the file structure.
 */
export function generateFileTree(files: ExportableFile[]): string {
  // Sort files by path
  const sortedFiles = [...files].sort((a, b) => a.path.localeCompare(b.path));

  // Build tree structure
  const tree: string[] = [];
  const seenDirs = new Set<string>();

  for (const file of sortedFiles) {
    const parts = file.path.split("/");
    let currentPath = "";

    // Add directories
    for (let i = 0; i < parts.length - 1; i++) {
      currentPath = currentPath ? `${currentPath}/${parts[i]}` : parts[i];
      if (!seenDirs.has(currentPath)) {
        seenDirs.add(currentPath);
        const indent = "  ".repeat(i);
        const prefix = i === 0 ? "" : "├── ";
        tree.push(`${indent}${prefix}${parts[i]}/`);
      }
    }

    // Add file
    const indent = "  ".repeat(parts.length - 1);
    const prefix = parts.length === 1 ? "" : "├── ";
    tree.push(`${indent}${prefix}${parts[parts.length - 1]}`);
  }

  return tree.join("\n");
}

/**
 * Generate simple file list
 */
export function generateFileList(files: ExportableFile[]): string {
  return files.map((f) => f.path).join("\n");
}
