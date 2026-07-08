/**
 * Theme Selection Modal Component
 *
 * A modal dialog for selecting theme mode when exporting data
 * Only shown when the page supports both light and dark modes
 */

"use client";

import React, { useEffect, useCallback } from "react";
import { Sun, Moon, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ThemeMode } from "@/types/playwright";

interface ThemeSelectModalProps {
  /**
   * Whether the modal is open
   */
  isOpen: boolean;

  /**
   * Callback when modal is closed
   */
  onClose: () => void;

  /**
   * Callback when a theme is selected
   */
  onSelect: (theme: ThemeMode) => void;

  /**
   * Title shown in the modal header
   */
  title?: string;

  /**
   * Description text
   */
  description?: string;
}

export function ThemeSelectModal({
  isOpen,
  onClose,
  onSelect,
  title = "Select Theme",
  description = "Choose which theme version to export",
}: ThemeSelectModalProps) {
  // Close on escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      // Prevent body scroll
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className={cn(
          "relative z-10 w-full max-w-sm mx-4",
          "bg-white dark:bg-neutral-800",
          "rounded-2xl shadow-2xl",
          "animate-in fade-in-0 zoom-in-95 duration-200"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-2">
          <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
            {title}
          </h2>
          <button
            onClick={onClose}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              "text-neutral-500 hover:text-neutral-700",
              "dark:text-neutral-400 dark:hover:text-neutral-200",
              "hover:bg-neutral-100 dark:hover:bg-neutral-700"
            )}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Description */}
        <p className="px-6 text-sm text-neutral-500 dark:text-neutral-400">
          {description}
        </p>

        {/* Theme Options */}
        <div className="p-6 grid grid-cols-2 gap-4">
          {/* Light Mode Option */}
          <button
            onClick={() => onSelect("light")}
            className={cn(
              "flex flex-col items-center gap-3 p-5 rounded-xl",
              "border-2 border-neutral-200 dark:border-neutral-600",
              "bg-gradient-to-b from-amber-50 to-orange-50",
              "dark:from-amber-900/20 dark:to-orange-900/20",
              "hover:border-amber-400 dark:hover:border-amber-500",
              "hover:shadow-lg hover:shadow-amber-100 dark:hover:shadow-amber-900/20",
              "transition-all duration-200",
              "group"
            )}
          >
            <div
              className={cn(
                "p-3 rounded-full",
                "bg-gradient-to-br from-amber-400 to-orange-500",
                "text-white shadow-lg shadow-amber-200 dark:shadow-amber-900/40",
                "group-hover:scale-110 transition-transform"
              )}
            >
              <Sun className="h-6 w-6" />
            </div>
            <span className="font-medium text-neutral-800 dark:text-neutral-100">
              Light Mode
            </span>
          </button>

          {/* Dark Mode Option */}
          <button
            onClick={() => onSelect("dark")}
            className={cn(
              "flex flex-col items-center gap-3 p-5 rounded-xl",
              "border-2 border-neutral-200 dark:border-neutral-600",
              "bg-gradient-to-b from-indigo-50 to-purple-50",
              "dark:from-indigo-900/20 dark:to-purple-900/20",
              "hover:border-indigo-400 dark:hover:border-indigo-500",
              "hover:shadow-lg hover:shadow-indigo-100 dark:hover:shadow-indigo-900/20",
              "transition-all duration-200",
              "group"
            )}
          >
            <div
              className={cn(
                "p-3 rounded-full",
                "bg-gradient-to-br from-indigo-500 to-purple-600",
                "text-white shadow-lg shadow-indigo-200 dark:shadow-indigo-900/40",
                "group-hover:scale-110 transition-transform"
              )}
            >
              <Moon className="h-6 w-6" />
            </div>
            <span className="font-medium text-neutral-800 dark:text-neutral-100">
              Dark Mode
            </span>
          </button>
        </div>

        {/* Footer */}
        <div className="px-6 pb-6">
          <button
            onClick={onClose}
            className={cn(
              "w-full py-2.5 px-4 rounded-lg text-sm font-medium",
              "text-neutral-600 dark:text-neutral-400",
              "hover:bg-neutral-100 dark:hover:bg-neutral-700",
              "transition-colors"
            )}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default ThemeSelectModal;
