/**
 * Nexting Agent API Client
 *
 * WebSocket-based API for communicating with Claude Agent SDK backend.
 */

import type { ChatMessage, WebContainerState } from "@/types/nexting-agent";

// ============================================
// Configuration
// ============================================

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";
const WS_URL = BACKEND_URL.replace(/^http/, "ws");
const API_BASE = `${BACKEND_URL}/api/nexting-agent`;

// ============================================
// Types
// ============================================

// Client -> Server messages
export type ClientMessageType = "chat" | "action_result" | "state_update" | "state_refresh_response" | "file_changed" | "ping";

export interface ClientMessage {
  type: ClientMessageType;
  payload: Record<string, unknown>;
}

// Server -> Client messages
export type ServerMessageType =
  | "text"
  | "text_delta"
  | "tool_call"
  | "tool_result"
  | "execute_action"
  | "error"
  | "done"
  | "pong"
  // State sync events
  | "request_state_refresh"
  // Worker Agent events (Multi-Agent)
  | "worker_spawned"
  | "worker_started"
  | "worker_tool_call"
  | "worker_tool_result"
  | "worker_completed"
  | "worker_error"
  | "worker_iteration"
  | "worker_text_delta";

export interface ServerMessage {
  type: ServerMessageType;
  payload: Record<string, unknown>;
}

// Worker event payloads
export interface WorkerSpawnedPayload {
  worker_id: string;
  section_name: string;
  display_name?: string;  // Human-friendly name (e.g., "Navigation", "Section 1")
  task_description: string;
  input_data: {
    section_data_keys: string[];
    target_files: string[];
    has_layout_context: boolean;
    has_style_context: boolean;
    // Data size info for UI display
    html_lines?: number;
    html_chars?: number;
    html_range?: { start: number; end: number } | null;
    char_start?: number;
    char_end?: number;
    estimated_tokens?: number;
    images_count?: number;
    links_count?: number;
  };
  total_workers: number;
}

export interface WorkerToolCallPayload {
  worker_id: string;
  section_name: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface WorkerToolResultPayload {
  worker_id: string;
  section_name: string;
  tool_name: string;
  result: string;
  success: boolean;
}

export interface WorkerCompletedPayload {
  worker_id: string;
  section_name: string;
  success: boolean;
  files: string[];
  file_count: number;
  summary: string;
  error?: string;
}

export interface WorkerErrorPayload {
  worker_id: string;
  section_name: string;
  error: string;
}

export interface WorkerIterationPayload {
  worker_id: string;
  section_name: string;
  iteration: number;
  max_iterations: number;
}

export interface WorkerTextDeltaPayload {
  worker_id: string;
  section_name: string;
  text: string;
  iteration: number;
}

// Action execution request from backend
export interface ExecuteActionRequest {
  action_id: string;
  action_type: string;
  payload: Record<string, unknown>;
}

// WebSocket connection options
export interface WebSocketOptions {
  sessionId?: string;
  token?: string;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onText?: (content: string) => void;
  onTextDelta?: (delta: string) => void;
  onToolCall?: (toolCall: { id: string; name: string; input: Record<string, unknown> }) => void;
  onToolResult?: (result: { id: string; success: boolean; result: string }) => void;
  onExecuteAction?: (request: ExecuteActionRequest) => Promise<{ success: boolean; result: string; error?: string }>;
  onDone?: () => void;
  // Worker Agent event callbacks (Multi-Agent)
  onWorkerSpawned?: (payload: WorkerSpawnedPayload) => void;
  onWorkerStarted?: (payload: { worker_id: string; section_name: string }) => void;
  onWorkerToolCall?: (payload: WorkerToolCallPayload) => void;
  onWorkerToolResult?: (payload: WorkerToolResultPayload) => void;
  onWorkerCompleted?: (payload: WorkerCompletedPayload) => void;
  onWorkerError?: (payload: WorkerErrorPayload) => void;
  onWorkerIteration?: (payload: WorkerIterationPayload) => void;
  onWorkerTextDelta?: (payload: WorkerTextDeltaPayload) => void;
  // State sync callback
  onRequestStateRefresh?: (requestId: string) => void;
}

// ============================================
// WebSocket Client Class
// ============================================

export class NextingAgentClient {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private options: WebSocketOptions;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private pingInterval: NodeJS.Timeout | null = null;

  constructor(options: WebSocketOptions = {}) {
    this.options = options;
  }

  // ============================================
  // Connection Management
  // ============================================

  /**
   * Connect to WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const params = new URLSearchParams();

      if (this.options.sessionId) {
        params.set("session_id", this.options.sessionId);
      }

      if (this.options.token) {
        params.set("token", this.options.token);
      }

      const url = `${WS_URL}/api/nexting-agent/ws?${params.toString()}`;

      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log("[NextingAgent] WebSocket connected");
          this.reconnectAttempts = 0;
          this.startPing();
          this.options.onOpen?.();
          resolve();
        };

        this.ws.onclose = (event) => {
          console.log("[NextingAgent] WebSocket closed:", event.code, event.reason);
          this.stopPing();
          this.options.onClose?.();

          // Auto-reconnect on unexpected close
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[NextingAgent] Reconnecting... (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), 1000 * this.reconnectAttempts);
          }
        };

        this.ws.onerror = (error) => {
          // Only log if not already connected (avoid duplicate errors during reconnect)
          // Use warn instead of error to avoid red console messages
          if (this.ws?.readyState !== WebSocket.OPEN) {
            console.warn("[NextingAgent] WebSocket connection failed - is backend running?");
            this.options.onError?.(error);
            reject(error);
          }
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // ============================================
  // Message Sending
  // ============================================

  /**
   * Send message to server
   */
  private send(message: ClientMessage): void {
    if (!this.isConnected()) {
      console.error("[NextingAgent] Not connected");
      return;
    }

    this.ws!.send(JSON.stringify(message));
  }

  /**
   * Send chat message
   * @param message - User's message
   * @param webcontainerState - Current WebContainer state
   * @param selectedSourceId - Selected source ID for context
   * @param recentErrors - Recent preview/build errors to include as context for Agent
   * @param images - Base64 encoded images to include with message
   */
  sendChat(
    message: string,
    webcontainerState?: WebContainerState,
    selectedSourceId?: string | null,
    recentErrors?: string[],
    images?: string[]
  ): void {
    this.send({
      type: "chat",
      payload: {
        message,
        webcontainer_state: webcontainerState ? this.formatState(webcontainerState) : undefined,
        selected_source_id: selectedSourceId || undefined,
        // Include recent errors so Agent can be aware of build/preview issues
        recent_errors: recentErrors && recentErrors.length > 0 ? recentErrors : undefined,
        // Include images if provided (base64 encoded)
        images: images && images.length > 0 ? images : undefined,
      },
    });
  }

  /**
   * Send action result
   */
  sendActionResult(actionId: string, success: boolean, result: string, error?: string): void {
    this.send({
      type: "action_result",
      payload: {
        action_id: actionId,
        success,
        result,
        error,
      },
    });
  }

  /**
   * Send state update
   */
  sendStateUpdate(state: WebContainerState): void {
    this.send({
      type: "state_update",
      payload: this.formatState(state),
    });
  }

  /**
   * Send state refresh response (in response to request_state_refresh)
   */
  sendStateRefreshResponse(requestId: string, state: WebContainerState): void {
    console.log(`[NextingAgent] Sending state refresh response, version: ${state.version || 0}`);
    this.send({
      type: "state_refresh_response" as ClientMessageType,
      payload: {
        request_id: requestId,
        state: {
          ...this.formatState(state),
          version: state.version || 0,
        },
      },
    });
  }

  /**
   * Send file changed notification (marks backend state as stale)
   */
  sendFileChanged(event: "write" | "delete" | "rename", filename: string): void {
    if (!this.isConnected()) return;
    this.send({
      type: "file_changed" as ClientMessageType,
      payload: {
        event,
        filename,
        timestamp: Date.now(),
      },
    });
  }

  // ============================================
  // Message Handling
  // ============================================

  /**
   * Handle incoming message
   */
  private async handleMessage(data: string): Promise<void> {
    try {
      const message: ServerMessage = JSON.parse(data);
      const { type, payload } = message;

      switch (type) {
        case "text":
          this.options.onText?.(payload.content as string);
          break;

        case "text_delta":
          this.options.onTextDelta?.(payload.delta as string);
          break;

        case "tool_call":
          this.options.onToolCall?.({
            id: payload.id as string,
            name: payload.name as string,
            input: payload.input as Record<string, unknown>,
          });
          break;

        case "tool_result":
          this.options.onToolResult?.({
            id: payload.id as string,
            success: payload.success as boolean,
            result: payload.result as string,
          });
          break;

        case "execute_action":
          await this.handleExecuteAction(payload as unknown as ExecuteActionRequest);
          break;

        case "error":
          console.error("[NextingAgent] Server error:", payload.error);
          break;

        case "done":
          this.options.onDone?.();
          break;

        case "pong":
          // Heartbeat response
          break;

        case "request_state_refresh":
          // Backend requests fresh WebContainer state
          console.log("[NextingAgent] State refresh requested");
          this.options.onRequestStateRefresh?.(payload.request_id as string);
          break;

        // Worker Agent events (Multi-Agent)
        case "worker_spawned":
          this.options.onWorkerSpawned?.(payload as unknown as WorkerSpawnedPayload);
          break;

        case "worker_started":
          this.options.onWorkerStarted?.(payload as { worker_id: string; section_name: string });
          break;

        case "worker_tool_call":
          this.options.onWorkerToolCall?.(payload as unknown as WorkerToolCallPayload);
          break;

        case "worker_tool_result":
          this.options.onWorkerToolResult?.(payload as unknown as WorkerToolResultPayload);
          break;

        case "worker_completed":
          this.options.onWorkerCompleted?.(payload as unknown as WorkerCompletedPayload);
          break;

        case "worker_error":
          this.options.onWorkerError?.(payload as unknown as WorkerErrorPayload);
          break;

        case "worker_iteration":
          this.options.onWorkerIteration?.(payload as unknown as WorkerIterationPayload);
          break;

        case "worker_text_delta":
          this.options.onWorkerTextDelta?.(payload as unknown as WorkerTextDeltaPayload);
          break;

        default:
          console.log("[NextingAgent] Unknown message type:", type);
      }
    } catch (error) {
      console.error("[NextingAgent] Failed to parse message:", error);
    }
  }

  /**
   * Handle execute_action request from backend
   */
  private async handleExecuteAction(request: ExecuteActionRequest): Promise<void> {
    console.log("[NextingAgent] Received execute_action:", {
      action_id: request.action_id,
      action_type: request.action_type,
      payload: request.payload,
    });

    if (!this.options.onExecuteAction) {
      console.warn("[NextingAgent] No onExecuteAction handler registered!");
      this.sendActionResult(request.action_id, false, "", "No handler");
      return;
    }

    try {
      console.log("[NextingAgent] Calling onExecuteAction handler...");
      const result = await this.options.onExecuteAction(request);
      console.log("[NextingAgent] Handler returned:", {
        success: result.success,
        resultLength: result.result?.length || 0,
        error: result.error,
      });
      this.sendActionResult(
        request.action_id,
        result.success,
        result.result,
        result.error
      );
      console.log("[NextingAgent] Action result sent successfully");
    } catch (error) {
      console.error("[NextingAgent] Handler threw error:", error);
      this.sendActionResult(
        request.action_id,
        false,
        "",
        error instanceof Error ? error.message : "Unknown error"
      );
    }
  }

  // ============================================
  // Heartbeat
  // ============================================

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send({ type: "ping", payload: {} });
      }
    }, 30000); // 30 seconds
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  // ============================================
  // Helper Methods
  // ============================================

  /**
   * Format WebContainer state for backend
   */
  private formatState(state: WebContainerState): Record<string, unknown> {
    const terminalsData = state.terminals.map((t) => ({
      id: t.id,
      name: t.name,
      cwd: t.cwd,
      is_running: t.isRunning,
      command: t.command,
      exit_code: t.exitCode,
      last_output: t.history.slice(-50).map((h) => h.data),
    }));

    const previewData = {
      url: state.preview?.url || state.previewUrl,
      is_loading: state.preview?.isLoading || false,
      has_error: state.preview?.hasError || false,
      error_message: state.preview?.errorMessage,
      console_messages: state.preview?.consoleMessages?.slice(-50) || [],
      viewport: state.preview?.viewport || { width: 1280, height: 720 },
      // Vite error overlay - detailed build error info from iframe
      error_overlay: state.preview?.errorOverlay ? {
        message: state.preview.errorOverlay.message,
        file: state.preview.errorOverlay.file,
        line: state.preview.errorOverlay.line,
        column: state.preview.errorOverlay.column,
        stack: state.preview.errorOverlay.stack,
        plugin: state.preview.errorOverlay.plugin,
        frame: state.preview.errorOverlay.frame,
        timestamp: state.preview.errorOverlay.timestamp,
      } : null,
    };

    return {
      status: state.status,
      files: state.files,
      active_file: state.activeFile,
      cwd: "/",
      terminals: terminalsData,
      active_terminal_id: state.activeTerminalId,
      preview_url: state.previewUrl,
      preview: previewData,
      error: state.error,
    };
  }

  /**
   * Get session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }
}

// ============================================
// Singleton Instance
// ============================================

let _client: NextingAgentClient | null = null;

/**
 * Get or create WebSocket client
 */
export function getClient(options?: WebSocketOptions): NextingAgentClient {
  if (!_client) {
    _client = new NextingAgentClient(options);
  }
  return _client;
}

/**
 * Create new WebSocket client (replaces existing)
 */
export function createClient(options: WebSocketOptions): NextingAgentClient {
  if (_client) {
    _client.disconnect();
  }
  _client = new NextingAgentClient(options);
  return _client;
}

// ============================================
// Legacy API Functions (HTTP fallback)
// ============================================

/**
 * Check API health
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get available tools
 */
export async function getTools(): Promise<Array<{ name: string; description: string }>> {
  const response = await fetch(`${API_BASE}/tools`);
  if (!response.ok) {
    throw new Error(`Failed to get tools: ${response.status}`);
  }
  return response.json();
}

/**
 * Send action result via HTTP (fallback)
 */
export async function sendActionResultHTTP(
  sessionId: string,
  actionId: string,
  success: boolean,
  result: string,
  error?: string
): Promise<void> {
  const response = await fetch(`${API_BASE}/action-result?session_id=${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_id: actionId,
      success,
      result,
      error,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send action result: ${response.status}`);
  }
}
