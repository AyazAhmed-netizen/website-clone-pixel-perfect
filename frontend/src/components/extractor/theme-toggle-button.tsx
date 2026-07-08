/**
 * Theme Toggle Button Component
 *
 * A toggle button for switching between light and dark theme preview
 * Only visible when the page supports both themes
 */

"use client";

import React from "react";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ThemeMode } from "@/types/playwright";

interface ThemeToggleButtonProps {
  /**
   * Current active theme
   */
  activeTheme: ThemeMode;

  /**
   * Callback when theme is changed
   */
  onThemeChange: (theme: ThemeMode) => void;

  /**
   * Whether the toggle is disabled
   */
  disabled?: boolean;

  /**
   * Additional CSS classes
   */
  className?: string;
}

export function ThemeToggleButton({
  activeTheme,
  onThemeChange,
  disabled = false,
  className,
}: ThemeToggleButtonProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center p-1 rounded-lg",
        "bg-neutral-100 dark:bg-neutral-700",
        "border border-neutral-200 dark:border-neutral-600",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
    >
      {/* Light Mode Button */}
      <button
        onClick={() => onThemeChange("light")}
        disabled={disabled}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium",
          "transition-all duration-200",
          activeTheme === "light"
            ? "bg-white dark:bg-neutral-600 text-amber-600 dark:text-amber-400 shadow-sm"
            : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
        )}
        title="Switch to Light Mode preview"
      >
        <Sun className="h-4 w-4" />
        <span>Light</span>
      </button>

      {/* Dark Mode Button */}
      <button
        onClick={() => onThemeChange("dark")}
        disabled={disabled}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium",
          "transition-all duration-200",
          activeTheme === "dark"
            ? "bg-white dark:bg-neutral-600 text-indigo-600 dark:text-indigo-400 shadow-sm"
            : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
        )}
        title="Switch to Dark Mode preview"
      >
        <Moon className="h-4 w-4" />
        <span>Dark</span>
      </button>
    </div>
  );
}

export default ThemeToggleButton;
