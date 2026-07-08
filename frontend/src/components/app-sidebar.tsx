"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import {
  Bot,
  Globe,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Home,
} from "lucide-react";

/**
 * App Sidebar Props
 */
interface AppSidebarProps {
  currentPage?: "home" | "agent" | "extractor";
}

/**
 * App Sidebar Component
 * 简化版侧边栏，适用于开源版本
 *
 * 包含：
 * - Logo
 * - Agent 链接
 * - Extractor 链接
 * - 主题切换
 */
export function AppSidebar({ currentPage }: AppSidebarProps) {
  const [open, setOpen] = useState(false);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = theme === "dark";

  const handleToggleTheme = () => {
    setTheme(isDark ? "light" : "dark");
  };

  const links = [
    {
      label: "Home",
      href: "/",
      icon: Home,
      active: currentPage === "home",
    },
    {
      label: "Agent",
      href: "/agent",
      icon: Bot,
      active: currentPage === "agent",
    },
    {
      label: "Extractor",
      href: "/extractor",
      icon: Globe,
      active: currentPage === "extractor",
    },
  ];

  return (
    <div
      className={cn(
        "flex flex-col h-full flex-shrink-0 transition-all duration-200",
        "border-r border-neutral-200 dark:border-neutral-700",
        "bg-neutral-50 dark:bg-neutral-900",
        open ? "w-48" : "w-14"
      )}
    >
      {/* Logo Section */}
      <div
        className={cn(
          "flex items-center h-12 px-3 flex-shrink-0",
          "border-b border-neutral-200 dark:border-neutral-700"
        )}
      >
        <Link
          href="/"
          className="flex items-center gap-2 text-neutral-900 dark:text-white"
        >
          <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
            <img
              src="/logo-light.svg"
              alt="Logo"
              width={28}
              height={28}
              className="object-contain dark:hidden"
            />
            <img
              src="/logo-dark.svg"
              alt="Logo"
              width={28}
              height={28}
              className="object-contain hidden dark:block"
            />
          </div>
          {open && (
            <span className="font-semibold text-sm whitespace-nowrap">
              Nexting Agent
            </span>
          )}
        </Link>
      </div>

      {/* Menu Links */}
      <div className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex items-center gap-3 px-2 py-2 rounded-lg transition-colors",
                "text-sm font-medium",
                link.active
                  ? "bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300"
                  : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-white"
              )}
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              {open && <span className="whitespace-nowrap">{link.label}</span>}
            </Link>
          );
        })}
      </div>

      {/* Bottom Section */}
      <div className="px-2 py-3 space-y-1 border-t border-neutral-200 dark:border-neutral-700">
        {/* Theme Toggle */}
        <button
          onClick={handleToggleTheme}
          className={cn(
            "flex items-center gap-3 w-full px-2 py-2 rounded-lg transition-colors",
            "text-sm font-medium",
            "text-neutral-600 dark:text-neutral-400",
            "hover:bg-neutral-100 dark:hover:bg-neutral-800",
            "hover:text-neutral-900 dark:hover:text-white"
          )}
        >
          {mounted ? (
            isDark ? (
              <Sun className="h-5 w-5 flex-shrink-0" />
            ) : (
              <Moon className="h-5 w-5 flex-shrink-0" />
            )
          ) : (
            <div className="h-5 w-5 flex-shrink-0" />
          )}
          {open && (
            <span className="whitespace-nowrap">
              {mounted ? (isDark ? "Light Mode" : "Dark Mode") : "Theme"}
            </span>
          )}
        </button>

        {/* Collapse Toggle */}
        <button
          onClick={() => setOpen(!open)}
          className={cn(
            "flex items-center gap-3 w-full px-2 py-2 rounded-lg transition-colors",
            "text-sm font-medium",
            "text-neutral-600 dark:text-neutral-400",
            "hover:bg-neutral-100 dark:hover:bg-neutral-800",
            "hover:text-neutral-900 dark:hover:text-white"
          )}
        >
          {open ? (
            <ChevronLeft className="h-5 w-5 flex-shrink-0" />
          ) : (
            <ChevronRight className="h-5 w-5 flex-shrink-0" />
          )}
          {open && <span className="whitespace-nowrap">Collapse</span>}
        </button>
      </div>
    </div>
  );
}
