"use client";

/**
 * XTerm Terminal Component
 *
 * A fully interactive terminal using xterm.js connected to WebContainer's jsh shell.
 * Features:
 * - Full terminal emulation (cursor, colors, escape sequences)
 * - Interactive input (type commands directly)
 * - Ctrl+C to interrupt processes
 * - Auto-resize to container
 * - Persists across tab switches (when kept mounted)
 */

import React, { useEffect, useRef, useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { Loader2, TerminalIcon, Trash2 } from "lucide-react";

/**
 * Agent log entry for displaying in terminal
 */
export interface AgentLogEntry {
  type: "command" | "output" | "error" | "info" | "file";
  content: string;
  timestamp?: number;
}

interface XTermTerminalProps {
  /** WebContainer status */
  webcontainerStatus: "idle" | "booting" | "ready" | "error";
  /** Function to spawn shell - returns the shell process */
  onSpawnShell: () => Promise<{
    output: ReadableStream<string>;
    input: WritableStream<string>;
    exit: Promise<number>;
    resize?: (dimensions: { cols: number; rows: number }) => void;
  } | null>;
  /** Whether the terminal is currently visible */
  isVisible?: boolean;
  /** Custom class name */
  className?: string;
  /** Agent log entries to display */
  agentLogs?: AgentLogEntry[];
  /** Callback when agent logs are consumed (to clear them) */
  onAgentLogsConsumed?: () => void;
}

export function XTermTerminal({
  webcontainerStatus,
  onSpawnShell,
  isVisible = true,
  className,
  agentLogs = [],
  onAgentLogsConsumed,
}: XTermTerminalProps) {
  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<import("@xterm/xterm").Terminal | null>(null);
  const fitAddonRef = useRef<import("@xterm/addon-fit").FitAddon | null>(null);
  const shellRef = useRef<{
    output: ReadableStream<string>;
    input: WritableStream<string>;
    exit: Promise<number>;
    resize?: (dimensions: { cols: number; rows: number }) => void;
  } | null>(null);
  const writerRef = useRef<WritableStreamDefaultWriter<string> | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<string> | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "waiting">("waiting");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const initCompletedRef = useRef(false);
  const isDisposedRef = useRef(false);

  // Store callback in ref to avoid dependency issues
  const onSpawnShellRef = useRef(onSpawnShell);
  useEffect(() => {
    onSpawnShellRef.current = onSpawnShell;
  }, [onSpawnShell]);

  // Initialize terminal when conditions are met
  // This effect ONLY handles initialization, not cleanup on visibility change
  useEffect(() => {
    const container = terminalContainerRef.current;
    if (!container) return;

    // Wait for WebContainer to be ready
    if (webcontainerStatus !== "ready") {
      setStatus("waiting");
      return;
    }

    // Initialize terminal even when not visible
    // This ensures Agent commands can be processed in the background
    // Fit operation will be done when terminal becomes visible

    // Already initialized
    if (initCompletedRef.current || xtermRef.current) {
      return;
    }

    // Mark as initializing
    isDisposedRef.current = false;

    const init = async () => {
      try {
        setStatus("loading");
        console.log("[XTermTerminal] Starting initialization...");

        // Dynamic import xterm
        const [{ Terminal }, { FitAddon }] = await Promise.all([
          import("@xterm/xterm"),
          import("@xterm/addon-fit"),
        ]);

        // Import CSS
        await import("@xterm/xterm/css/xterm.css");

        if (isDisposedRef.current) return;

        // Create terminal
        const terminal = new Terminal({
          cursorBlink: true,
          cursorStyle: "block",
          fontSize: 13,
          fontFamily: 'Menlo, Monaco, "Courier New", monospace',
          theme: {
            background: "#171717",
            foreground: "#f5f5f5",
            cursor: "#22c55e",
            cursorAccent: "#171717",
            selectionBackground: "#404040",
            black: "#171717",
            red: "#ef4444",
            green: "#22c55e",
            yellow: "#eab308",
            blue: "#3b82f6",
            magenta: "#a855f7",
            cyan: "#06b6d4",
            white: "#f5f5f5",
            brightBlack: "#525252",
            brightRed: "#f87171",
            brightGreen: "#4ade80",
            brightYellow: "#facc15",
            brightBlue: "#60a5fa",
            brightMagenta: "#c084fc",
            brightCyan: "#22d3ee",
            brightWhite: "#fafafa",
          },
          scrollback: 1000,
          convertEol: true,
        });

        const fitAddon = new FitAddon();
        terminal.loadAddon(fitAddon);

        // Open terminal
        terminal.open(container);
        xtermRef.current = terminal;
        fitAddonRef.current = fitAddon;

        console.log("[XTermTerminal] Terminal opened");

        // Wait for DOM to settle
        await new Promise(resolve => setTimeout(resolve, 150));

        if (isDisposedRef.current) {
          terminal.dispose();
          xtermRef.current = null;
          fitAddonRef.current = null;
          return;
        }

        // Fit terminal - check dimensions
        const rect = container.getBoundingClientRect();
        console.log("[XTermTerminal] Container dimensions:", rect.width, rect.height);

        if (rect.width > 0 && rect.height > 0) {
          try {
            fitAddon.fit();
            console.log("[XTermTerminal] Terminal fitted:", terminal.cols, "x", terminal.rows);
          } catch (e) {
            console.warn("[XTermTerminal] Fit failed:", e);
          }
        }

        // Show welcome message
        terminal.writeln("\x1b[32m$ WebContainer Terminal\x1b[0m");
        terminal.writeln("\x1b[90mConnecting to shell...\x1b[0m");
        terminal.writeln("");

        // Spawn shell
        console.log("[XTermTerminal] Spawning shell...");
        let shell;
        try {
          shell = await onSpawnShellRef.current();
        } catch (spawnError) {
          console.error("[XTermTerminal] Shell spawn error:", spawnError);
          throw new Error(`Failed to spawn shell: ${spawnError}`);
        }

        if (!shell) {
          throw new Error("Failed to spawn shell - returned null");
        }

        if (isDisposedRef.current) {
          terminal.dispose();
          xtermRef.current = null;
          fitAddonRef.current = null;
          return;
        }

        console.log("[XTermTerminal] Shell spawned successfully");
        shellRef.current = shell;

        // Get writer for shell input
        const writer = shell.input.getWriter();
        writerRef.current = writer;

        // Handle user input -> shell
        terminal.onData((data) => {
          if (writerRef.current) {
            writerRef.current.write(data).catch((err) => {
              console.error("[XTermTerminal] Write error:", err);
            });
          }
        });

        // Handle resize
        terminal.onResize(({ cols, rows }) => {
          console.log("[XTermTerminal] Terminal resized:", cols, "x", rows);
          shellRef.current?.resize?.({ cols, rows });
        });

        // Initial resize
        if (shell.resize && terminal.cols > 0 && terminal.rows > 0) {
          shell.resize({ cols: terminal.cols, rows: terminal.rows });
        }

        // Read shell output -> terminal
        const reader = shell.output.getReader();
        readerRef.current = reader;

        const readLoop = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                console.log("[XTermTerminal] Shell output stream ended");
                break;
              }
              if (xtermRef.current && value) {
                xtermRef.current.write(value);
              }
            }
          } catch (e) {
            // Don't log if disposed
            if (!isDisposedRef.current && xtermRef.current) {
              console.error("[XTermTerminal] Read error:", e);
            }
          }
        };
        readLoop();

        // Handle shell exit
        shell.exit.then((code) => {
          console.log("[XTermTerminal] Shell exited with code:", code);
          if (xtermRef.current) {
            xtermRef.current.writeln(`\r\n\x1b[90mShell exited with code ${code}\x1b[0m`);
          }
        }).catch((err) => {
          // Ignore exit errors when disposed
          if (!isDisposedRef.current) {
            console.error("[XTermTerminal] Shell exit error:", err);
          }
        });

        initCompletedRef.current = true;
        setStatus("ready");
        terminal.writeln("\x1b[32mShell ready. Type commands here.\x1b[0m");
        terminal.writeln("");
        terminal.focus();

        console.log("[XTermTerminal] Initialization complete");

      } catch (err) {
        console.error("[XTermTerminal] Init error:", err);
        if (!isDisposedRef.current) {
          setStatus("error");
          setErrorMsg(err instanceof Error ? err.message : "Unknown error");
          if (xtermRef.current) {
            xtermRef.current.writeln(`\r\n\x1b[31mError: ${err instanceof Error ? err.message : "Unknown error"}\x1b[0m`);
          }
        }
      }
    };

    init();

    // Note: No cleanup here - we want terminal to persist
    // Removed isVisible from dependencies - terminal initializes in background
  }, [webcontainerStatus]);

  // Cleanup ONLY on unmount
  useEffect(() => {
    return () => {
      console.log("[XTermTerminal] Unmounting - cleaning up...");
      isDisposedRef.current = true;

      // Release reader
      if (readerRef.current) {
        try {
          readerRef.current.cancel().catch(() => {});
        } catch (e) {
          // Ignore
        }
        readerRef.current = null;
      }

      // Release writer
      if (writerRef.current) {
        try {
          writerRef.current.releaseLock();
        } catch (e) {
          // Ignore
        }
        writerRef.current = null;
      }

      // Dispose terminal
      if (xtermRef.current) {
        xtermRef.current.dispose();
        xtermRef.current = null;
      }

      fitAddonRef.current = null;
      shellRef.current = null;
      initCompletedRef.current = false;
    };
  }, []);

  // Handle container resize
  useEffect(() => {
    const container = terminalContainerRef.current;
    if (!container) return;

    let resizeTimeout: NodeJS.Timeout;

    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        const fitAddon = fitAddonRef.current;
        const terminal = xtermRef.current;
        if (!fitAddon || !terminal) return;

        const rect = container.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;

        try {
          fitAddon.fit();
        } catch (e) {
          // Ignore
        }
      }, 100);
    };

    window.addEventListener("resize", handleResize);
    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    return () => {
      clearTimeout(resizeTimeout);
      window.removeEventListener("resize", handleResize);
      observer.disconnect();
    };
  }, []);

  // Refit and focus terminal when becoming visible
  useEffect(() => {
    if (!isVisible) return;

    const container = terminalContainerRef.current;
    const fitAddon = fitAddonRef.current;
    const terminal = xtermRef.current;

    if (!container || !fitAddon || !terminal) return;

    // Small delay to ensure container has proper dimensions
    const timeout = setTimeout(() => {
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        try {
          fitAddon.fit();
          terminal.focus();
        } catch (e) {
          // Ignore
        }
      }
    }, 50);

    return () => clearTimeout(timeout);
  }, [isVisible]);

  // Track last written lines to prevent duplicates
  const lastWrittenLinesRef = useRef<string[]>([]);

  // Process Agent logs and display them in terminal
  useEffect(() => {
    const terminal = xtermRef.current;
    if (!terminal || agentLogs.length === 0) return;

    // Format and write each log entry
    agentLogs.forEach((log) => {
      // 去重：检查是否已经显示过相同内容
      const contentHash = log.content.slice(0, 200);
      if (lastWrittenLinesRef.current.includes(contentHash)) {
        return; // 跳过重复内容
      }
      // 保留最近50条记录用于去重
      lastWrittenLinesRef.current.push(contentHash);
      if (lastWrittenLinesRef.current.length > 50) {
        lastWrittenLinesRef.current.shift();
      }
      const timestamp = log.timestamp
        ? new Date(log.timestamp).toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })
        : "";

      // Different formatting based on log type
      switch (log.type) {
        case "command":
          // Command: cyan color with "▶ Agent:" prefix
          terminal.writeln("");
          terminal.writeln(
            `\x1b[90m${timestamp}\x1b[0m \x1b[36m▶ Agent:\x1b[0m \x1b[1m${log.content}\x1b[0m`
          );
          break;

        case "output":
          // Output: normal text with slight indent
          const outputLines = log.content.split("\n");
          outputLines.forEach((line) => {
            if (line.trim()) {
              terminal.writeln(`  ${line}`);
            }
          });
          break;

        case "error":
          // Error: red color with "✗" prefix
          terminal.writeln(
            `\x1b[90m${timestamp}\x1b[0m \x1b[31m✗ Error:\x1b[0m ${log.content}`
          );
          break;

        case "info":
          // Info: yellow/dim color with "ℹ" prefix
          terminal.writeln(
            `\x1b[90m${timestamp}\x1b[0m \x1b[33mℹ\x1b[0m \x1b[90m${log.content}\x1b[0m`
          );
          break;

        case "file":
          // File operation: green color with "📄" prefix
          terminal.writeln(
            `\x1b[90m${timestamp}\x1b[0m \x1b[32m📄 File:\x1b[0m ${log.content}`
          );
          break;

        default:
          terminal.writeln(log.content);
      }
    });

    // Notify parent that logs have been consumed
    onAgentLogsConsumed?.();
  }, [agentLogs, onAgentLogsConsumed]);

  // Clear terminal (keeps shell running)
  const handleClear = useCallback(() => {
    xtermRef.current?.clear();
  }, []);

  // Get status message
  const getStatusMessage = () => {
    if (webcontainerStatus === "booting") return "WebContainer booting...";
    if (webcontainerStatus === "error") return "WebContainer error";
    if (status === "loading") return "Loading terminal...";
    if (status === "waiting") return "Waiting for WebContainer...";
    if (status === "error") return errorMsg || "Error";
    return null;
  };

  const statusMessage = getStatusMessage();

  return (
    <div className={cn("flex flex-col h-full bg-neutral-100 dark:bg-neutral-900", className)}>
      {/* Header */}
      <div
        className={cn(
          "flex items-center justify-between px-3 py-2 flex-shrink-0",
          "border-b border-neutral-200 dark:border-neutral-700",
          "bg-neutral-50 dark:bg-neutral-800"
        )}
      >
        <div className="flex items-center gap-2">
          <TerminalIcon className="h-4 w-4 text-neutral-500 dark:text-neutral-400" />
          <span className="text-xs text-neutral-700 dark:text-neutral-300 font-medium">Terminal</span>
          {statusMessage && (
            <span className="flex items-center gap-1 text-yellow-600 dark:text-yellow-400 text-xs">
              {(status === "loading" || status === "waiting" || webcontainerStatus === "booting") && (
                <Loader2 className="h-3 w-3 animate-spin" />
              )}
              {statusMessage}
            </span>
          )}
          {status === "ready" && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/50 text-green-600 dark:text-green-400 text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 dark:bg-green-400" />
              Connected
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handleClear}
            className="p-1.5 rounded hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-500 dark:text-neutral-400 transition-colors"
            title="Clear terminal"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Terminal Container - Terminal itself stays dark */}
      <div
        ref={terminalContainerRef}
        className="flex-1 overflow-hidden bg-[#171717]"
        style={{
          minHeight: "200px",
          padding: "8px",
        }}
      />
    </div>
  );
}

export default XTermTerminal;
