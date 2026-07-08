/**
 * Nexting Agent Types
 *
 * Type definitions for the Nexting Agent feature
 * including WebContainer integration and LangGraph communication
 */

// ============================================
// WebContainer Types
// ============================================

/**
 * WebContainer file system entry
 */
export interface FileSystemEntry {
  path: string;
  type: "file" | "directory";
  content?: string;
  children?: FileSystemEntry[];
}

/**
 * WebContainer process output
 */
export interface ProcessOutput {
  type: "stdout" | "stderr";
  data: string;
  timestamp: number;
}

/**
 * Console message from preview iframe
 */
export interface ConsoleMessage {
  id: string;
  type: "log" | "warn" | "error" | "info" | "debug";
  args: unknown[];
  timestamp: number;
  stack?: string;
}

/**
 * WebContainer terminal session (enhanced)
 */
export interface TerminalSession {
  id: string;
  name: string;
  cwd: string;
  isRunning: boolean;
  history: ProcessOutput[];
  command?: string; // Current/last command
  exitCode?: number; // Exit code if process completed
  createdAt: number;
}

/**
 * Vite error overlay information extracted from preview iframe
 * Contains detailed build/compile error info from Vite
 */
export interface ViteErrorOverlay {
  message: string;        // Main error message
  file?: string;          // File path where error occurred
  line?: number;          // Line number
  column?: number;        // Column number
  stack?: string;         // Full stack trace
  plugin?: string;        // Vite plugin name (e.g., "vite:react-babel")
  frame?: string;         // Code frame showing error context
  timestamp: number;      // When the error was captured
}

/**
 * Preview state for tracking iframe status
 */
export interface PreviewState {
  url: string | null;
  isLoading: boolean;
  hasError: boolean;
  errorMessage?: string;
  lastScreenshot?: string; // Base64 encoded
  consoleMessages: ConsoleMessage[];
  viewport: {
    width: number;
    height: number;
  };
  /** Vite build error overlay - captured from iframe when compilation fails */
  errorOverlay?: ViteErrorOverlay;
}

/**
 * File diff tracking for Agent-made changes
 * Used to highlight code changes in the IDE
 */
export interface FileDiffState {
  path: string;
  oldContent: string;
  newContent: string;
  timestamp: number;
}

/**
 * WebContainer state (enhanced)
 */
export interface WebContainerState {
  status: "booting" | "ready" | "error" | "idle";
  files: Record<string, string>;
  activeFile: string | null;
  terminals: TerminalSession[];
  activeTerminalId: string | null;
  previewUrl: string | null;
  preview: PreviewState;
  error: string | null;
  /** Track file diffs made by Agent (path -> diff info) */
  fileDiffs: Record<string, FileDiffState>;
  /** State version number for sync tracking (auto-increments on file changes) */
  version?: number;
  /**
   * Image URL mapping for export (local path -> original URL)
   * Used to restore original external URLs when exporting code
   */
  imageUrlMapping?: Record<string, string>;
}

// ============================================
// Chat Types
// ============================================

/**
 * Chat message role
 */
export type MessageRole = "user" | "assistant" | "system";

/**
 * Tool call status
 */
export type ToolCallStatus = "pending" | "executing" | "success" | "error";

/**
 * Tool call definition
 */
export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
  status: ToolCallStatus;
  result?: string;
  error?: string;
  startTime?: number;  // Timestamp when tool started
  endTime?: number;    // Timestamp when tool completed
}

/**
 * Content block for streaming responses
 */
export type ContentBlock =
  | { type: "text"; content: string }
  | { type: "tool_call"; toolCall: ToolCall };

/**
 * Chat message
 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  toolCalls?: ToolCall[];
  contentBlocks?: ContentBlock[];
  isThinking?: boolean;
  images?: string[]; // Base64 encoded images attached to message
}

// ============================================
// WebContainer Action Types (for Agent tools)
// ============================================

/**
 * WebContainer action type (enhanced with new capabilities)
 */
export type WebContainerActionType =
  // File operations
  | "write_file"
  | "read_file"
  | "delete_file"
  | "create_directory"
  | "rename_file"
  | "edit_file"
  | "list_files"
  // Terminal operations
  | "shell"
  | "run_command"
  | "install_dependencies"
  | "start_dev_server"
  | "stop_process"
  | "create_terminal"
  | "kill_terminal"
  | "send_terminal_input"
  | "switch_terminal"
  // Preview inspection operations
  | "take_screenshot"
  | "get_preview_dom"
  | "get_visual_summary"
  | "get_build_errors"
  | "get_console_messages"
  | "clear_console";

/**
 * WebContainer action payload
 */
export interface WebContainerAction {
  type: WebContainerActionType;
  payload: Record<string, unknown>;
}

/**
 * File write action
 */
export interface WriteFileAction extends WebContainerAction {
  type: "write_file";
  payload: {
    path: string;
    content: string;
  };
}

/**
 * Run command action
 */
export interface RunCommandAction extends WebContainerAction {
  type: "run_command";
  payload: {
    command: string;
    args?: string[];
    cwd?: string;
  };
}

/**
 * Install dependencies action
 */
export interface InstallDepsAction extends WebContainerAction {
  type: "install_dependencies";
  payload: {
    packages: string[];
    isDev?: boolean;
  };
}

/**
 * Edit file action (partial edit)
 */
export interface EditFileAction extends WebContainerAction {
  type: "edit_file";
  payload: {
    path: string;
    oldText: string;
    newText: string;
    replaceAll?: boolean;
  };
}

/**
 * Rename file action
 */
export interface RenameFileAction extends WebContainerAction {
  type: "rename_file";
  payload: {
    oldPath: string;
    newPath: string;
  };
}

/**
 * Create terminal action
 */
export interface CreateTerminalAction extends WebContainerAction {
  type: "create_terminal";
  payload: {
    name?: string;
  };
}

/**
 * Kill terminal action
 */
export interface KillTerminalAction extends WebContainerAction {
  type: "kill_terminal";
  payload: {
    terminalId: string;
  };
}

/**
 * Send terminal input action
 */
export interface SendTerminalInputAction extends WebContainerAction {
  type: "send_terminal_input";
  payload: {
    terminalId: string;
    input: string;
  };
}

/**
 * Take screenshot action
 */
export interface TakeScreenshotAction extends WebContainerAction {
  type: "take_screenshot";
  payload: {
    selector?: string;
    fullPage?: boolean;
  };
}

/**
 * Get preview DOM action
 */
export interface GetPreviewDOMAction extends WebContainerAction {
  type: "get_preview_dom";
  payload: {
    selector?: string;
    depth?: number;
  };
}

/**
 * Get visual summary action
 */
export interface GetVisualSummaryAction extends WebContainerAction {
  type: "get_visual_summary";
  payload: Record<string, never>;
}

/**
 * Shell command action (universal command execution)
 */
export interface ShellAction extends WebContainerAction {
  type: "shell";
  payload: {
    command: string;
    args?: string[];
    raw_command?: string;
    background?: boolean;
  };
}

// ============================================
// Preview Visual Summary Response
// ============================================

/**
 * Visual summary response from Nexting Bridge
 */
export interface VisualSummary {
  success: boolean;
  viewport: {
    width: number;
    height: number;
  };
  bodySize: {
    width: number;
    height: number;
    scrollHeight: number;
  };
  backgroundColor: string;
  visibleElementCount: number;
  hasContent: boolean;
  textPreview: string;
  title: string;
  url: string;
}

/**
 * DOM snapshot response from Nexting Bridge
 */
export interface DOMSnapshotResponse {
  success: boolean;
  summary: VisualSummary;
  dom: string;
  elementCount: number;
}

// ============================================
// SSE Event Types
// ============================================

/**
 * SSE event types from backend
 */
export type SSEEventType =
  | "text"
  | "tool_call"
  | "tool_executing"
  | "tool_result"
  | "webcontainer_action"
  | "iteration"
  | "loop_complete"
  | "error"
  | "done";

/**
 * SSE event data
 */
export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

// ============================================
// Worker Agent Event Types (Multi-Agent)
// ============================================

/**
 * WebSocket message types for Worker events
 */
export type WorkerEventType =
  | "worker_spawned"
  | "worker_started"
  | "worker_tool_call"
  | "worker_tool_result"
  | "worker_completed"
  | "worker_error";

/**
 * Worker spawned event payload
 */
export interface WorkerSpawnedPayload {
  worker_id: string;
  section_name: string;
  task_description: string;
  input_data: {
    section_data_keys: string[];
    target_files: string[];
    has_layout_context: boolean;
    has_style_context: boolean;
  };
  total_workers: number;
}

/**
 * Worker started event payload
 */
export interface WorkerStartedPayload {
  worker_id: string;
  section_name: string;
}

/**
 * Worker tool call event payload
 */
export interface WorkerToolCallPayload {
  worker_id: string;
  section_name: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

/**
 * Worker tool result event payload
 */
export interface WorkerToolResultPayload {
  worker_id: string;
  section_name: string;
  tool_name: string;
  result: string;
  success: boolean;
}

/**
 * Worker completed event payload
 */
export interface WorkerCompletedPayload {
  worker_id: string;
  section_name: string;
  success: boolean;
  files: string[];
  file_count: number;
  summary: string;
  error?: string;
}

/**
 * Worker error event payload
 */
export interface WorkerErrorPayload {
  worker_id: string;
  section_name: string;
  error: string;
}

/**
 * Worker event (union type)
 */
export type WorkerEvent =
  | { type: "worker_spawned"; payload: WorkerSpawnedPayload }
  | { type: "worker_started"; payload: WorkerStartedPayload }
  | { type: "worker_tool_call"; payload: WorkerToolCallPayload }
  | { type: "worker_tool_result"; payload: WorkerToolResultPayload }
  | { type: "worker_completed"; payload: WorkerCompletedPayload }
  | { type: "worker_error"; payload: WorkerErrorPayload };

// ============================================
// API Types
// ============================================

/**
 * Chat request payload
 */
export interface ChatRequest {
  message: string;
  history: ChatMessage[];
  webcontainer_state: {
    files: Record<string, string>;
    active_file: string | null;
    cwd: string;
  };
}

/**
 * Agent API response
 */
export interface AgentResponse {
  success: boolean;
  message?: string;
  error?: string;
}

// ============================================
// Component Props Types
// ============================================

/**
 * WebContainer IDE props
 */
export interface WebContainerIDEProps {
  onFileChange?: (path: string, content: string) => void;
  onCommandRun?: (command: string) => void;
  className?: string;
}

/**
 * Chat panel props for Nexting Agent
 */
export interface NextingAgentChatPanelProps {
  onWebContainerAction?: (action: WebContainerAction) => Promise<string>;
  getWebContainerState?: () => WebContainerState;
  className?: string;
}

/**
 * Terminal component props
 */
export interface TerminalProps {
  onCommand?: (command: string) => Promise<string>;
  history?: ProcessOutput[];
  className?: string;
}

/**
 * File explorer props
 */
export interface FileExplorerProps {
  files: FileSystemEntry[];
  activeFile?: string;
  onFileSelect?: (path: string) => void;
  onFileCreate?: (path: string, type: "file" | "directory") => void;
  onFileDelete?: (path: string) => void;
  onFileRename?: (oldPath: string, newPath: string) => void;
  className?: string;
}
