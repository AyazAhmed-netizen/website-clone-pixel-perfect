"use client";

/**
 * Error Status Bar Component
 *
 * Displays a compact status bar showing error counts and Auto-Fix button.
 * Appears when errors are detected in the WebContainer preview.
 */

import React from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, AlertCircle, Loader2, Zap, X, ChevronDown } from "lucide-react";

interface ErrorStatusBarProps {
  /** Number of critical errors */
  criticalCount: number;
  /** Number of non-critical errors */
  errorCount: number;
  /** Number of warnings */
  warningCount: number;
  /** Whether healing loop is active */
  isHealing?: boolean;
  /** Current healing attempt number */
  healingAttempt?: number;
  /** Maximum healing attempts */
  maxHealingAttempts?: number;
  /** Callback when Auto-Fix button is clicked */
  onAutoFix?: () => void;
  /** Callback when dismiss button is clicked */
  onDismiss?: () => void;
  /** Callback when expand button is clicked */
  onExpand?: () => void;
  /** Whether the detail panel is expanded */
  isExpanded?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export function ErrorStatusBar({
  criticalCount,
  errorCount,
  warningCount,
  isHealing = false,
  healingAttempt = 0,
  maxHealingAttempts = 5,
  onAutoFix,
  onDismiss,
  onExpand,
  isExpanded = false,
  className,
}: ErrorStatusBarProps) {
  const totalErrors = criticalCount + errorCount;
  const hasIssues = totalErrors > 0 || warningCount > 0;

  // Don't render if no issues and not healing
  if (!hasIssues && !isHealing) return null;

  // Determine status level for styling
  const isCritical = criticalCount > 0;
  const hasErrors = errorCount > 0;

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
        isCritical
          ? "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800"
          : hasErrors
          ? "bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200 border border-orange-200 dark:border-orange-800"
          : "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800",
        className
      )}
    >
      {/* Status Icon */}
      {isHealing ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" />
      ) : isCritical ? (
        <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
      )}

      {/* Status Text */}
      <span className="flex-1 truncate">
        {isHealing ? (
          <>
            Auto-fixing... ({healingAttempt}/{maxHealingAttempts})
          </>
        ) : (
          <>
            {criticalCount > 0 && (
              <span className="font-semibold">
                {criticalCount} critical
                {errorCount > 0 && ", "}
              </span>
            )}
            {errorCount > 0 && (
              <span>
                {errorCount} error{errorCount > 1 ? "s" : ""}
              </span>
            )}
            {warningCount > 0 && (criticalCount > 0 || errorCount > 0) && (
              <span className="opacity-70">, {warningCount} warning{warningCount > 1 ? "s" : ""}</span>
            )}
            {warningCount > 0 && criticalCount === 0 && errorCount === 0 && (
              <span>{warningCount} warning{warningCount > 1 ? "s" : ""}</span>
            )}
          </>
        )}
      </span>

      {/* Action Buttons */}
      <div className="flex items-center gap-1">
        {/* Auto-Fix Button - Only show for critical/errors, not warnings only */}
        {!isHealing && totalErrors > 0 && onAutoFix && (
          <button
            onClick={onAutoFix}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold transition-colors",
              isCritical
                ? "bg-red-200 dark:bg-red-800 hover:bg-red-300 dark:hover:bg-red-700"
                : "bg-orange-200 dark:bg-orange-800 hover:bg-orange-300 dark:hover:bg-orange-700"
            )}
            title="Start automatic error fixing"
          >
            <Zap className="h-2.5 w-2.5" />
            Auto-Fix
          </button>
        )}

        {/* Expand Button */}
        {onExpand && hasIssues && (
          <button
            onClick={onExpand}
            className={cn(
              "p-0.5 rounded transition-colors",
              isCritical
                ? "hover:bg-red-200 dark:hover:bg-red-800"
                : hasErrors
                ? "hover:bg-orange-200 dark:hover:bg-orange-800"
                : "hover:bg-yellow-200 dark:hover:bg-yellow-800"
            )}
            title={isExpanded ? "Collapse error details" : "Expand error details"}
          >
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform",
                isExpanded && "rotate-180"
              )}
            />
          </button>
        )}

        {/* Dismiss Button */}
        {onDismiss && !isHealing && (
          <button
            onClick={onDismiss}
            className={cn(
              "p-0.5 rounded transition-colors",
              isCritical
                ? "hover:bg-red-200 dark:hover:bg-red-800"
                : hasErrors
                ? "hover:bg-orange-200 dark:hover:bg-orange-800"
                : "hover:bg-yellow-200 dark:hover:bg-yellow-800"
            )}
            title="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorStatusBar;
