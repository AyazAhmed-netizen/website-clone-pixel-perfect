/**
 * BoxLite State Adapter
 *
 * Converts BoxLiteSandboxState to WebContainerState format
 * so that NextingAgentChatPanel can work with both sandbox types.
 */

import type { BoxLiteSandboxState, TerminalSession as BoxLiteTerminal } from "@/types/boxlite";
import type {
  WebContainerState,
  TerminalSession as WebContainerTerminal,
  PreviewState,
  ConsoleMessage,
  FileDiffState,
} from "@/types/agent";

/**
 * Map BoxLite status to WebContainer status
 */
function mapStatus(
  status: BoxLiteSandboxState["status"]
): WebContainerState["status"] {
  switch (status) {
    case "creating":
    case "booting":
      return "booting";
    case "ready":
    case "running":
      return "ready";
    case "stopped":
      return "idle";
    case "error":
      return "error";
    default:
      return "idle";
  }
}

/**
 * Adapt BoxLite terminal to WebContainer terminal format
 */
function adaptTerminal(terminal: BoxLiteTerminal): WebContainerTerminal {
  return {
    id: terminal.id,
    name: terminal.name,
    cwd: "/",  // BoxLite doesn't track cwd per terminal
    isRunning: terminal.is_running,
    history: [],  // BoxLite tracks output differently
    command: terminal.command,
    exitCode: terminal.exit_code,
    createdAt: new Date(terminal.created_at).getTime(),
  };
}

/**
 * Adapt BoxLite console messages to WebContainer format
 */
function adaptConsoleMessages(
  messages: BoxLiteSandboxState["console_messages"]
): ConsoleMessage[] {
  return messages.map((msg, index) => ({
    id: `console-${index}-${msg.timestamp}`,
    type: msg.type,
    args: msg.args,
    timestamp: new Date(msg.timestamp).getTime(),
    stack: msg.stack,
  }));
}

/**
 * Adapt BoxLite preview state to WebContainer preview format
 */
function adaptPreview(
  preview: BoxLiteSandboxState["preview"],
  previewUrl?: string,
  consoleMessages: ConsoleMessage[] = []
): PreviewState {
  return {
    url: previewUrl || preview.url || null,
    isLoading: preview.is_loading,
    hasError: preview.has_error,
    errorMessage: preview.error_message,
    consoleMessages,
    viewport: {
      width: 1280,
      height: 720,
    },
  };
}

/**
 * Adapt BoxLite state to WebContainer state format
 *
 * This allows NextingAgentChatPanel to work with BoxLite sandbox
 * without any modifications to the chat panel code.
 *
 * @param state - BoxLite sandbox state
 * @param fileDiffs - Optional file diffs (tracked separately in BoxLite)
 * @returns WebContainerState compatible object
 */
export function adaptBoxLiteState(
  state: BoxLiteSandboxState | null,
  fileDiffs: Record<string, FileDiffState> = {}
): WebContainerState {
  if (!state) {
    return {
      status: "idle",
      files: {},
      activeFile: null,
      terminals: [],
      activeTerminalId: null,
      previewUrl: null,
      preview: {
        url: null,
        isLoading: false,
        hasError: false,
        consoleMessages: [],
        viewport: { width: 1280, height: 720 },
      },
      error: null,
      fileDiffs: {},
    };
  }

  const consoleMessages = adaptConsoleMessages(state.console_messages || []);

  return {
    status: mapStatus(state.status),
    files: state.files || {},
    activeFile: state.active_file || null,
    terminals: (state.terminals || []).map(adaptTerminal),
    activeTerminalId: state.active_terminal_id || null,
    previewUrl: state.preview_url || null,
    preview: adaptPreview(state.preview, state.preview_url, consoleMessages),
    error: state.error || null,
    fileDiffs,
  };
}

/**
 * Adapt WebContainer state back to BoxLite format (for sending to backend)
 *
 * Used when the chat panel needs to send state to the BoxLite backend.
 */
export function adaptWebContainerStateToBoxLite(
  state: WebContainerState
): Partial<BoxLiteSandboxState> {
  return {
    status: state.status === "ready" ? "running" : state.status === "booting" ? "booting" : "ready",
    files: state.files,
    active_file: state.activeFile || undefined,
    preview_url: state.previewUrl || undefined,
    preview: {
      url: state.preview.url || undefined,
      is_loading: state.preview.isLoading,
      has_error: state.preview.hasError,
      error_message: state.preview.errorMessage,
    },
    error: state.error || undefined,
  };
}

/**
 * Type guard to check if state is BoxLiteSandboxState
 */
export function isBoxLiteState(
  state: unknown
): state is BoxLiteSandboxState {
  return (
    typeof state === "object" &&
    state !== null &&
    "sandbox_id" in state &&
    typeof (state as BoxLiteSandboxState).sandbox_id === "string"
  );
}

/**
 * Type guard to check if state is WebContainerState
 */
export function isWebContainerState(
  state: unknown
): state is WebContainerState {
  return (
    typeof state === "object" &&
    state !== null &&
    "status" in state &&
    "preview" in state &&
    !("sandbox_id" in state)
  );
}
