/**
 * BoxLite Components
 *
 * Components for the BoxLite backend sandbox environment.
 * These are independent from the WebContainer-based components.
 */

export { BoxLiteAgentPage } from "./boxlite-agent-page";
export { BoxLiteIDE } from "./boxlite-ide";

// Re-export types
export type {
  BoxLiteSandboxState,
  FileEntry,
  TerminalSession,
  ProcessOutput,
  CommandResult,
  PreviewState,
  ConsoleMessage,
  BuildError,
  VisualSummary,
  ToolRequest,
  ToolResponse,
  ChatMessage,
  ToolCall,
  ToolResult,
  FileDiff,
  FileDiffState,
  AgentLogEntry,
} from "@/types/boxlite";
