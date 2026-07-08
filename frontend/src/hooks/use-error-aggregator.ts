/**
 * Error Aggregator Hook
 *
 * Aggregates errors from all sources (preview, console, terminal)
 * with deduplication, categorization, and severity assessment.
 *
 * Used for displaying error status and triggering auto-fix.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import type { WebContainerState, ConsoleMessage } from "@/types/nexting-agent";

// ============================================
// Types
// ============================================

export type ErrorSource = "preview" | "console" | "terminal" | "build";

export type ErrorSeverity = "critical" | "error" | "warning";

export type ErrorCategory =
  | "BUILD_FAILED"
  | "VITE_PLUGIN_ERROR"
  | "MISSING_IMPORT"
  | "MISSING_CSS"
  | "SYNTAX_ERROR"
  | "TYPE_ERROR"
  | "UNDEFINED_VARIABLE"
  | "REACT_HOOK_ERROR"
  | "NPM_ERROR"
  | "PROCESS_EXIT"
  | "WHITE_SCREEN"
  | "FILESYSTEM_ERROR"
  | "RUNTIME_ERROR"
  | "UNKNOWN";

export interface AggregatedError {
  id: string;
  source: ErrorSource;
  severity: ErrorSeverity;
  category: ErrorCategory;
  message: string;
  file?: string;
  line?: number;
  column?: number;
  stack?: string;
  fixStrategy?: string[];
  timestamp: number;
  occurrenceCount: number;
  lastOccurrence: number;
}

export interface UseErrorAggregatorOptions {
  webcontainerState: WebContainerState | null;
  onNewCriticalError?: (error: AggregatedError) => void;
  maxErrors?: number;
}

export interface UseErrorAggregatorReturn {
  errors: AggregatedError[];
  criticalCount: number;
  errorCount: number;
  warningCount: number;
  hasErrors: boolean;
  clearError: (id: string) => void;
  clearAll: () => void;
  getErrorById: (id: string) => AggregatedError | undefined;
}

// ============================================
// Error Pattern Matching
// ============================================

interface ErrorPattern {
  pattern: RegExp;
  category: ErrorCategory;
  severity: ErrorSeverity;
  fixStrategy: string[];
}

const ERROR_PATTERNS: ErrorPattern[] = [
  // Build/Vite errors
  {
    pattern: /\[plugin:vite:([^\]]+)\]/,
    category: "VITE_PLUGIN_ERROR",
    severity: "critical",
    fixStrategy: [
      "Check the file mentioned in the error",
      "Fix syntax or import issues",
      "Verify JSX/TSX syntax is correct",
    ],
  },
  {
    pattern: /Failed to compile/i,
    category: "BUILD_FAILED",
    severity: "critical",
    fixStrategy: [
      "Check terminal output for specific error",
      "Fix the root cause error first",
      "Run verify_changes() to confirm fix",
    ],
  },

  // Import errors
  {
    pattern: /Cannot find module ['"]([^'"]+)['"]/,
    category: "MISSING_IMPORT",
    severity: "error",
    fixStrategy: [
      "Check if the imported file exists",
      "Create the file if needed",
      "Or install the package if it's an npm module",
    ],
  },
  {
    pattern: /Module not found.*Can't resolve ['"]([^'"]+)['"]/,
    category: "MISSING_IMPORT",
    severity: "error",
    fixStrategy: [
      "Verify the import path is correct",
      "Check if file exists at the path",
      "For npm packages, run npm install",
    ],
  },

  // CSS errors
  {
    pattern: /Failed to resolve import ['"]([^'"]+\.css)['"]/,
    category: "MISSING_CSS",
    severity: "error",
    fixStrategy: [
      "Create the missing CSS file",
      "Or remove the import if not needed",
    ],
  },

  // Syntax errors
  {
    pattern: /SyntaxError:/,
    category: "SYNTAX_ERROR",
    severity: "error",
    fixStrategy: [
      "Check for missing brackets or semicolons",
      "Verify JSX syntax",
      "Look for unclosed strings",
    ],
  },
  {
    pattern: /Unexpected token/,
    category: "SYNTAX_ERROR",
    severity: "error",
    fixStrategy: [
      "Look for missing/extra punctuation",
      "Check JSX syntax (class vs className)",
      "Verify string quotes are matched",
    ],
  },

  // React errors
  {
    pattern: /Invalid hook call/,
    category: "REACT_HOOK_ERROR",
    severity: "error",
    fixStrategy: [
      "Ensure hooks are at top level of components",
      "Don't call hooks in loops or conditions",
      "Check React version compatibility",
    ],
  },

  // Runtime errors
  {
    pattern: /TypeError:/,
    category: "TYPE_ERROR",
    severity: "error",
    fixStrategy: [
      "Check if variable is defined before use",
      "Verify data types match expected",
      "Add null/undefined checks",
    ],
  },
  {
    pattern: /ReferenceError:/,
    category: "UNDEFINED_VARIABLE",
    severity: "error",
    fixStrategy: [
      "Check if variable is imported",
      "Verify variable is declared",
      "Check spelling and case",
    ],
  },

  // White screen
  {
    pattern: /WHITE_SCREEN/,
    category: "WHITE_SCREEN",
    severity: "critical",
    fixStrategy: [
      "Check if App component renders properly",
      "Verify ReactDOM.createRoot() is called",
      "Check for silent lifecycle errors",
    ],
  },

  // NPM errors
  {
    pattern: /npm ERR!/,
    category: "NPM_ERROR",
    severity: "error",
    fixStrategy: [
      "Clear node_modules and reinstall",
      "Check package.json for syntax errors",
      "Verify package version compatibility",
    ],
  },
];

// ============================================
// Helper Functions
// ============================================

function hashString(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16).slice(0, 12);
}

function categorizeError(
  message: string
): { category: ErrorCategory; severity: ErrorSeverity; fixStrategy: string[] } {
  for (const pattern of ERROR_PATTERNS) {
    if (pattern.pattern.test(message)) {
      return {
        category: pattern.category,
        severity: pattern.severity,
        fixStrategy: pattern.fixStrategy,
      };
    }
  }

  // Default categorization based on keywords
  const lowerMessage = message.toLowerCase();

  if (lowerMessage.includes("error")) {
    return {
      category: "RUNTIME_ERROR",
      severity: "error",
      fixStrategy: ["Check the error message for details", "Trace the error source"],
    };
  }

  if (lowerMessage.includes("warning") || lowerMessage.includes("warn")) {
    return {
      category: "UNKNOWN",
      severity: "warning",
      fixStrategy: ["Review the warning message"],
    };
  }

  return {
    category: "UNKNOWN",
    severity: "error",
    fixStrategy: ["Investigate the error"],
  };
}

function extractFileInfo(message: string): { file?: string; line?: number; column?: number } {
  // Match patterns like: /path/to/file.jsx:123:45
  const fileMatch = message.match(/([^\s]+\.(jsx?|tsx?|vue|svelte|css)):(\d+):(\d+)/);
  if (fileMatch) {
    return {
      file: fileMatch[1],
      line: parseInt(fileMatch[3], 10),
      column: parseInt(fileMatch[4], 10),
    };
  }

  // Match patterns like: at file.jsx:123
  const simpleMatch = message.match(/at\s+([^\s]+):(\d+)/);
  if (simpleMatch) {
    return {
      file: simpleMatch[1],
      line: parseInt(simpleMatch[2], 10),
    };
  }

  return {};
}

function shouldFilterError(message: string): boolean {
  // Filter out noise
  const filters = [
    "[HMR]",
    "[vite] connected",
    "Download the React DevTools",
    "Warning: ReactDOM.render",
    "Warning: findDOMNode",
    "[Fast Refresh]",
    "Compiled successfully",
    "VITE v",
    "ready in",
    "Local:",
    "Network:",
    "press h + enter",
  ];

  return filters.some((filter) => message.includes(filter));
}

// ============================================
// Hook Implementation
// ============================================

export function useErrorAggregator({
  webcontainerState,
  onNewCriticalError,
  maxErrors = 50,
}: UseErrorAggregatorOptions): UseErrorAggregatorReturn {
  const [errors, setErrors] = useState<Map<string, AggregatedError>>(new Map());
  const lastProcessedRef = useRef<{
    errorOverlayTimestamp?: number;
    consoleLength?: number;
  }>({});
  const onNewCriticalErrorRef = useRef(onNewCriticalError);

  // Keep callback ref updated
  useEffect(() => {
    onNewCriticalErrorRef.current = onNewCriticalError;
  }, [onNewCriticalError]);

  // Process preview error overlay
  useEffect(() => {
    if (!webcontainerState?.preview?.errorOverlay) return;

    const overlay = webcontainerState.preview.errorOverlay;
    const timestamp = overlay.timestamp;

    // Skip if already processed
    if (lastProcessedRef.current.errorOverlayTimestamp === timestamp) return;
    lastProcessedRef.current.errorOverlayTimestamp = timestamp;

    const message = overlay.message;
    const id = `preview-${hashString(message)}`;

    const { category, severity, fixStrategy } = categorizeError(message);

    const newError: AggregatedError = {
      id,
      source: "preview",
      severity: severity === "critical" ? "critical" : "error", // Preview errors are at least error level
      category,
      message,
      file: overlay.file,
      line: overlay.line,
      column: overlay.column,
      stack: overlay.stack,
      fixStrategy,
      timestamp,
      occurrenceCount: 1,
      lastOccurrence: timestamp,
    };

    setErrors((prev) => {
      const updated = new Map(prev);
      const existing = updated.get(id);

      if (existing) {
        updated.set(id, {
          ...existing,
          occurrenceCount: existing.occurrenceCount + 1,
          lastOccurrence: timestamp,
        });
      } else {
        updated.set(id, newError);

        // Trigger callback for new critical errors
        if (newError.severity === "critical" && onNewCriticalErrorRef.current) {
          setTimeout(() => onNewCriticalErrorRef.current?.(newError), 0);
        }
      }

      // Limit total errors
      if (updated.size > maxErrors) {
        const sorted = Array.from(updated.entries()).sort(
          ([, a], [, b]) => b.lastOccurrence - a.lastOccurrence
        );
        return new Map(sorted.slice(0, maxErrors));
      }

      return updated;
    });
  }, [webcontainerState?.preview?.errorOverlay, maxErrors]);

  // Process console messages
  useEffect(() => {
    if (!webcontainerState?.preview?.consoleMessages) return;

    const messages = webcontainerState.preview.consoleMessages;
    const currentLength = messages.length;

    // Only process new messages
    const lastLength = lastProcessedRef.current.consoleLength || 0;
    if (currentLength <= lastLength) return;

    lastProcessedRef.current.consoleLength = currentLength;

    // Process only new messages
    const newMessages = messages.slice(lastLength);

    setErrors((prev) => {
      const updated = new Map(prev);

      for (const msg of newMessages) {
        if (msg.type !== "error") continue;

        const content = msg.args
          .map((arg) => (typeof arg === "string" ? arg : JSON.stringify(arg)))
          .join(" ");

        if (shouldFilterError(content)) continue;

        const id = `console-${hashString(content)}`;
        const { category, severity, fixStrategy } = categorizeError(content);
        const fileInfo = extractFileInfo(content);

        const newError: AggregatedError = {
          id,
          source: "console",
          severity,
          category,
          message: content.slice(0, 500),
          ...fileInfo,
          stack: msg.stack,
          fixStrategy,
          timestamp: msg.timestamp,
          occurrenceCount: 1,
          lastOccurrence: msg.timestamp,
        };

        const existing = updated.get(id);
        if (existing) {
          updated.set(id, {
            ...existing,
            occurrenceCount: existing.occurrenceCount + 1,
            lastOccurrence: msg.timestamp,
          });
        } else {
          updated.set(id, newError);

          // Trigger callback for new critical errors
          if (newError.severity === "critical" && onNewCriticalErrorRef.current) {
            setTimeout(() => onNewCriticalErrorRef.current?.(newError), 0);
          }
        }
      }

      // Limit total errors
      if (updated.size > maxErrors) {
        const sorted = Array.from(updated.entries()).sort(
          ([, a], [, b]) => b.lastOccurrence - a.lastOccurrence
        );
        return new Map(sorted.slice(0, maxErrors));
      }

      return updated;
    });
  }, [webcontainerState?.preview?.consoleMessages, maxErrors]);

  // Clear error by ID
  const clearError = useCallback((id: string) => {
    setErrors((prev) => {
      const updated = new Map(prev);
      updated.delete(id);
      return updated;
    });
  }, []);

  // Clear all errors
  const clearAll = useCallback(() => {
    setErrors(new Map());
    lastProcessedRef.current = {};
  }, []);

  // Get error by ID
  const getErrorById = useCallback(
    (id: string) => {
      return errors.get(id);
    },
    [errors]
  );

  // Computed values
  const errorArray = useMemo(() => {
    return Array.from(errors.values()).sort(
      (a, b) => b.lastOccurrence - a.lastOccurrence
    );
  }, [errors]);

  const criticalCount = useMemo(() => {
    return errorArray.filter((e) => e.severity === "critical").length;
  }, [errorArray]);

  const errorCount = useMemo(() => {
    return errorArray.filter((e) => e.severity === "error").length;
  }, [errorArray]);

  const warningCount = useMemo(() => {
    return errorArray.filter((e) => e.severity === "warning").length;
  }, [errorArray]);

  const hasErrors = useMemo(() => {
    return errorArray.length > 0;
  }, [errorArray]);

  return {
    errors: errorArray,
    criticalCount,
    errorCount,
    warningCount,
    hasErrors,
    clearError,
    clearAll,
    getErrorById,
  };
}

export default useErrorAggregator;
