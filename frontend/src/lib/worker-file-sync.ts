/**
 * Worker File Sync Utility
 *
 * Handles syncing file writes from worker agents to WebContainer
 */

import type { WebContainerAction } from "@/types/agent";

export interface FileSyncOptions {
  onAction: (action: WebContainerAction) => Promise<string>;
  onFileWritten?: (path: string) => void;
  onError?: (path: string, error: Error) => void;
}

/**
 * Sync a worker's file write operation to WebContainer
 * Handles write_file and edit_file tool calls
 */
export async function syncWorkerFileWrite(
  toolName: string,
  toolInput: Record<string, unknown>,
  options: FileSyncOptions
): Promise<void> {
  const { onAction, onFileWritten, onError } = options;

  // Only handle file write operations
  if (toolName !== "write_file" && toolName !== "edit_file") {
    return;
  }

  const path = toolInput.path as string;
  if (!path) {
    return;
  }

  try {
    if (toolName === "write_file") {
      const content = toolInput.content as string;
      if (content !== undefined) {
        await onAction({
          type: "write_file",
          payload: { path, content },
        });
        onFileWritten?.(path);
      }
    } else if (toolName === "edit_file") {
      const oldText = toolInput.oldText as string;
      const newText = toolInput.newText as string;
      const replaceAll = toolInput.replaceAll as boolean | undefined;

      if (oldText !== undefined && newText !== undefined) {
        await onAction({
          type: "edit_file",
          payload: { path, oldText, newText, replaceAll },
        });
        onFileWritten?.(path);
      }
    }
  } catch (error) {
    onError?.(path, error instanceof Error ? error : new Error(String(error)));
  }
}
