/**
 * Code Diff Utilities
 *
 * Utilities for computing and displaying code differences
 * Similar to Claude Code's diff visualization
 */

// ============================================
// Types
// ============================================

/**
 * Type of line change in diff
 */
export type DiffLineType = "unchanged" | "added" | "removed";

/**
 * Single line in a diff
 */
export interface DiffLine {
  type: DiffLineType;
  content: string;
  oldLineNumber?: number; // Line number in old file (for removed/unchanged)
  newLineNumber?: number; // Line number in new file (for added/unchanged)
}

/**
 * Complete diff result for a file
 */
export interface FileDiff {
  path: string;
  oldContent: string;
  newContent: string;
  lines: DiffLine[];
  hasChanges: boolean;
  addedCount: number;
  removedCount: number;
  timestamp: number;
}

/**
 * Tracked file changes for the current session
 */
export interface FileChanges {
  [path: string]: FileDiff;
}

// ============================================
// Diff Algorithm (Simple Line-by-Line)
// ============================================

/**
 * Compute diff between two strings using line-by-line comparison
 * Uses a simplified LCS (Longest Common Subsequence) approach
 */
export function computeDiff(oldContent: string, newContent: string): DiffLine[] {
  const oldLines = oldContent.split("\n");
  const newLines = newContent.split("\n");

  // Use Myers diff algorithm (simplified)
  const result: DiffLine[] = [];

  // Build LCS matrix
  const m = oldLines.length;
  const n = newLines.length;

  // For very large files, use a simpler approach
  if (m > 1000 || n > 1000) {
    return computeSimpleDiff(oldLines, newLines);
  }

  // LCS dynamic programming
  const dp: number[][] = Array(m + 1)
    .fill(null)
    .map(() => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff
  let i = m;
  let j = n;
  const diffReverse: DiffLine[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      // Unchanged line
      diffReverse.push({
        type: "unchanged",
        content: oldLines[i - 1],
        oldLineNumber: i,
        newLineNumber: j,
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      // Added line
      diffReverse.push({
        type: "added",
        content: newLines[j - 1],
        newLineNumber: j,
      });
      j--;
    } else if (i > 0) {
      // Removed line
      diffReverse.push({
        type: "removed",
        content: oldLines[i - 1],
        oldLineNumber: i,
      });
      i--;
    }
  }

  // Reverse to get correct order
  return diffReverse.reverse();
}

/**
 * Simple diff for large files (line-by-line comparison)
 */
function computeSimpleDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  const result: DiffLine[] = [];
  const maxLen = Math.max(oldLines.length, newLines.length);

  let oldIdx = 0;
  let newIdx = 0;

  while (oldIdx < oldLines.length || newIdx < newLines.length) {
    const oldLine = oldLines[oldIdx];
    const newLine = newLines[newIdx];

    if (oldIdx >= oldLines.length) {
      // All remaining are added
      result.push({
        type: "added",
        content: newLine,
        newLineNumber: newIdx + 1,
      });
      newIdx++;
    } else if (newIdx >= newLines.length) {
      // All remaining are removed
      result.push({
        type: "removed",
        content: oldLine,
        oldLineNumber: oldIdx + 1,
      });
      oldIdx++;
    } else if (oldLine === newLine) {
      // Unchanged
      result.push({
        type: "unchanged",
        content: oldLine,
        oldLineNumber: oldIdx + 1,
        newLineNumber: newIdx + 1,
      });
      oldIdx++;
      newIdx++;
    } else {
      // Look ahead to find if lines were inserted or removed
      const lookAheadNew = newLines.slice(newIdx, newIdx + 10).indexOf(oldLine);
      const lookAheadOld = oldLines.slice(oldIdx, oldIdx + 10).indexOf(newLine);

      if (lookAheadNew !== -1 && (lookAheadOld === -1 || lookAheadNew <= lookAheadOld)) {
        // Lines were inserted
        for (let i = 0; i < lookAheadNew; i++) {
          result.push({
            type: "added",
            content: newLines[newIdx],
            newLineNumber: newIdx + 1,
          });
          newIdx++;
        }
      } else if (lookAheadOld !== -1) {
        // Lines were removed
        for (let i = 0; i < lookAheadOld; i++) {
          result.push({
            type: "removed",
            content: oldLines[oldIdx],
            oldLineNumber: oldIdx + 1,
          });
          oldIdx++;
        }
      } else {
        // Both changed - show as remove then add
        result.push({
          type: "removed",
          content: oldLine,
          oldLineNumber: oldIdx + 1,
        });
        result.push({
          type: "added",
          content: newLine,
          newLineNumber: newIdx + 1,
        });
        oldIdx++;
        newIdx++;
      }
    }
  }

  return result;
}

/**
 * Create a FileDiff object from old and new content
 */
export function createFileDiff(
  path: string,
  oldContent: string,
  newContent: string
): FileDiff {
  const lines = computeDiff(oldContent, newContent);

  let addedCount = 0;
  let removedCount = 0;

  for (const line of lines) {
    if (line.type === "added") addedCount++;
    if (line.type === "removed") removedCount++;
  }

  return {
    path,
    oldContent,
    newContent,
    lines,
    hasChanges: addedCount > 0 || removedCount > 0,
    addedCount,
    removedCount,
    timestamp: Date.now(),
  };
}

/**
 * Check if a file diff has meaningful changes
 */
export function hasMeaningfulChanges(diff: FileDiff): boolean {
  // Filter out whitespace-only changes
  for (const line of diff.lines) {
    if (line.type !== "unchanged" && line.content.trim().length > 0) {
      return true;
    }
  }
  return false;
}

/**
 * Get summary of changes
 */
export function getDiffSummary(diff: FileDiff): string {
  if (!diff.hasChanges) {
    return "No changes";
  }

  const parts: string[] = [];
  if (diff.addedCount > 0) {
    parts.push(`+${diff.addedCount}`);
  }
  if (diff.removedCount > 0) {
    parts.push(`-${diff.removedCount}`);
  }

  return parts.join(" ");
}

/**
 * Merge multiple file changes, keeping only the latest for each path
 */
export function mergeFileChanges(
  existing: FileChanges,
  newChanges: FileChanges
): FileChanges {
  return {
    ...existing,
    ...newChanges,
  };
}

/**
 * Get the display line number for a diff line
 * Returns the line number that should be shown (prefers new line number)
 */
export function getDisplayLineNumber(line: DiffLine): number {
  return line.newLineNumber ?? line.oldLineNumber ?? 0;
}
