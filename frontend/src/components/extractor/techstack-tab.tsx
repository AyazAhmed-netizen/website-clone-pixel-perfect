"use client";

import React from "react";
import {
  Package,
  Layers,
  Wrench,
  Palette,
  Tag,
  CheckCircle,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TechStackData, DependencyInfo } from "@/types/playwright";

/**
 * Tech Stack Tab Props
 */
interface TechStackTabProps {
  techStack: TechStackData | null;
}

/**
 * Dependency Badge Component
 * 依赖项徽章组件
 */
function DependencyBadge({ dep }: { dep: DependencyInfo }) {
  // 根据置信度设置颜色
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30";
    if (confidence >= 50) return "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30";
    return "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30";
  };

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 p-2.5 rounded-lg border",
        "bg-white dark:bg-neutral-800",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
            {dep.name}
          </p>
          {dep.version && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400 font-mono">
              v{dep.version}
            </span>
          )}
        </div>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 capitalize mt-0.5">
          {dep.type}
        </p>
      </div>
      <div
        className={cn(
          "px-2 py-1 rounded text-xs font-medium",
          getConfidenceColor(dep.confidence)
        )}
      >
        {dep.confidence}%
      </div>
    </div>
  );
}

/**
 * Section Component
 * 分组展示组件
 */
function Section({
  title,
  icon: Icon,
  children,
  isEmpty = false,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  isEmpty?: boolean;
}) {
  return (
    <div
      className={cn(
        "p-4 rounded-lg border",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          {title}
        </h3>
      </div>
      {isEmpty ? (
        <p className="text-sm text-neutral-400 dark:text-neutral-500 italic">
          No {title.toLowerCase()} detected
        </p>
      ) : (
        children
      )}
    </div>
  );
}

/**
 * Tech Stack Tab Component
 * 技术栈分析 Tab 组件
 *
 * 展示页面使用的技术栈、框架、库和工具
 */
export function TechStackTab({ techStack }: TechStackTabProps) {
  if (!techStack) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Info className="h-12 w-12 text-neutral-300 dark:text-neutral-600 mb-3" />
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Tech stack analysis not available
        </p>
        <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
          Data may still be loading or analysis failed
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div
        className={cn(
          "p-4 rounded-lg border",
          "bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950/30 dark:to-cyan-950/30",
          "border-blue-200 dark:border-blue-800"
        )}
      >
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          <h3 className="font-semibold text-blue-900 dark:text-blue-100">
            Technology Stack Overview
          </h3>
        </div>
        <p className="text-sm text-blue-700 dark:text-blue-300">
          Detected technologies and frameworks used in this webpage
        </p>
      </div>

      {/* Frameworks */}
      <Section
        title="Frameworks"
        icon={Layers}
        isEmpty={techStack.frameworks.length === 0}
      >
        <div className="space-y-2">
          {techStack.frameworks.map((dep, idx) => (
            <DependencyBadge key={idx} dep={dep} />
          ))}
        </div>
      </Section>

      {/* UI Libraries */}
      <Section
        title="UI Libraries"
        icon={Package}
        isEmpty={techStack.ui_libraries.length === 0}
      >
        <div className="space-y-2">
          {techStack.ui_libraries.map((dep, idx) => (
            <DependencyBadge key={idx} dep={dep} />
          ))}
        </div>
      </Section>

      {/* Utilities */}
      <Section
        title="Utilities"
        icon={Wrench}
        isEmpty={techStack.utilities.length === 0}
      >
        <div className="space-y-2">
          {techStack.utilities.map((dep, idx) => (
            <DependencyBadge key={idx} dep={dep} />
          ))}
        </div>
      </Section>

      {/* Build Tools */}
      <Section
        title="Build Tools"
        icon={Package}
        isEmpty={techStack.build_tools.length === 0}
      >
        <div className="space-y-2">
          {techStack.build_tools.map((dep, idx) => (
            <DependencyBadge key={idx} dep={dep} />
          ))}
        </div>
      </Section>

      {/* Styling */}
      {(techStack.styling.preprocessor ||
        techStack.styling.framework ||
        techStack.styling.css_in_js) && (
        <Section title="Styling" icon={Palette}>
          <div className="space-y-2">
            {techStack.styling.preprocessor && (
              <div className="flex items-center gap-2 p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                <span className="text-xs text-neutral-500 dark:text-neutral-400 w-24">
                  Preprocessor:
                </span>
                <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {techStack.styling.preprocessor}
                </span>
              </div>
            )}
            {techStack.styling.framework && (
              <div className="flex items-center gap-2 p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                <span className="text-xs text-neutral-500 dark:text-neutral-400 w-24">
                  Framework:
                </span>
                <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {techStack.styling.framework}
                </span>
              </div>
            )}
            {techStack.styling.css_in_js && (
              <div className="flex items-center gap-2 p-2 rounded bg-neutral-50 dark:bg-neutral-800">
                <span className="text-xs text-neutral-500 dark:text-neutral-400 w-24">
                  CSS-in-JS:
                </span>
                <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {techStack.styling.css_in_js}
                </span>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Features */}
      {techStack.features.length > 0 && (
        <Section title="Detected Features" icon={Tag}>
          <div className="flex flex-wrap gap-2">
            {techStack.features.map((feature, idx) => (
              <span
                key={idx}
                className={cn(
                  "px-2.5 py-1 rounded-full text-xs font-medium",
                  "bg-blue-100 dark:bg-blue-900/30",
                  "text-blue-700 dark:text-blue-300"
                )}
              >
                {feature}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Meta Tags */}
      {Object.keys(techStack.meta_tags).length > 0 && (
        <Section title="Meta Information" icon={Info}>
          <div className="space-y-2">
            {Object.entries(techStack.meta_tags).map(([key, value], idx) => (
              <div
                key={idx}
                className="p-2 rounded bg-neutral-50 dark:bg-neutral-800"
              >
                <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1">
                  {key}
                </p>
                <p className="text-sm text-neutral-900 dark:text-neutral-100 break-all">
                  {value}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Package Manager */}
      {techStack.package_manager && (
        <div
          className={cn(
            "p-3 rounded-lg border",
            "bg-neutral-50 dark:bg-neutral-800/50",
            "border-neutral-200 dark:border-neutral-700"
          )}
        >
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-neutral-500 dark:text-neutral-400" />
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              Package Manager:
            </span>
            <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
              {techStack.package_manager}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
