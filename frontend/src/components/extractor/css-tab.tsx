"use client";

import React, { useState } from "react";
import {
  Play,
  Palette,
  Code2,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  CSSData,
  CSSAnimation,
  CSSVariable,
  StylesheetContent,
  PseudoElementStyle,
} from "@/types/playwright";

/**
 * CSS Tab Props
 */
interface CSSTabProps {
  cssData: CSSData | null;
}

/**
 * Collapsible Section Component
 * 可折叠区域组件
 */
function CollapsibleSection({
  title,
  icon: Icon,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ElementType;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div
      className={cn(
        "rounded-lg border",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full flex items-center justify-between p-3",
          "hover:bg-neutral-50 dark:hover:bg-neutral-800/50",
          "transition-colors"
        )}
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-blue-500" />
          <span className="font-medium text-neutral-900 dark:text-neutral-100">
            {title}
          </span>
          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
            {count}
          </span>
        </div>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-neutral-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-neutral-400" />
        )}
      </button>
      {isOpen && (
        <div className="p-3 pt-0 border-t border-neutral-200 dark:border-neutral-700">
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * Animation Card Component
 * 动画卡片组件
 */
function AnimationCard({ animation }: { animation: CSSAnimation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "p-3 rounded-lg border",
        "bg-neutral-50 dark:bg-neutral-800/50",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Play className="h-3.5 w-3.5 text-purple-500" />
          <code className="text-sm font-mono font-semibold text-purple-600 dark:text-purple-400">
            {animation.name}
          </code>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
        >
          {expanded ? "Hide" : "Show"} keyframes
        </button>
      </div>
      {expanded && (
        <div className="mt-2 space-y-1">
          {animation.keyframes.map((kf, idx) => (
            <div
              key={idx}
              className="text-xs font-mono p-2 rounded bg-neutral-100 dark:bg-neutral-900"
            >
              <span className="text-blue-500">{kf.offset}</span>
              <span className="text-neutral-400"> {"{"} </span>
              {Object.entries(kf.styles).map(([prop, val], i) => (
                <span key={i}>
                  <span className="text-green-600 dark:text-green-400">{prop}</span>
                  <span className="text-neutral-400">: </span>
                  <span className="text-orange-500">{val}</span>
                  <span className="text-neutral-400">; </span>
                </span>
              ))}
              <span className="text-neutral-400">{"}"}</span>
            </div>
          ))}
        </div>
      )}
      {animation.source_stylesheet && (
        <p className="text-[10px] text-neutral-400 mt-1 truncate">
          Source: {animation.source_stylesheet}
        </p>
      )}
    </div>
  );
}

/**
 * Variable Card Component
 * CSS 变量卡片组件
 */
function VariableCard({ variable }: { variable: CSSVariable }) {
  const isColor = variable.value.startsWith("#") ||
                  variable.value.startsWith("rgb") ||
                  variable.value.startsWith("hsl");

  return (
    <div
      className={cn(
        "flex items-center justify-between p-2 rounded",
        "bg-neutral-50 dark:bg-neutral-800/50"
      )}
    >
      <code className="text-xs font-mono text-cyan-600 dark:text-cyan-400">
        {variable.name}
      </code>
      <div className="flex items-center gap-2">
        {isColor && (
          <div
            className="w-4 h-4 rounded border border-neutral-300 dark:border-neutral-600"
            style={{ backgroundColor: variable.value }}
          />
        )}
        <code className="text-xs font-mono text-neutral-600 dark:text-neutral-400">
          {variable.value}
        </code>
      </div>
    </div>
  );
}

/**
 * Stylesheet Card Component
 * 样式表卡片组件
 */
function StylesheetCard({ stylesheet }: { stylesheet: StylesheetContent }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Safe access to content with fallback
  const content = stylesheet.content || "";
  const url = stylesheet.url || "";

  const handleCopy = () => {
    if (content) {
      navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      className={cn(
        "rounded-lg border",
        "bg-neutral-50 dark:bg-neutral-800/50",
        "border-neutral-200 dark:border-neutral-700"
      )}
    >
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-2 min-w-0">
          <Code2 className="h-4 w-4 text-green-500 flex-shrink-0" />
          <span className="text-sm font-mono truncate text-neutral-700 dark:text-neutral-300">
            {stylesheet.is_inline ? "Inline Style" : url.split("/").pop() || "Unknown"}
          </span>
          {stylesheet.is_inline && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600">
              inline
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-400">
            {(content.length / 1024).toFixed(1)} KB
          </span>
          <button
            onClick={handleCopy}
            className="p-1 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded"
            disabled={!content}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5 text-neutral-400" />
            )}
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-500 hover:text-blue-600"
          >
            {expanded ? "Hide" : "Preview"}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-neutral-200 dark:border-neutral-700">
          <pre className="p-3 text-xs font-mono overflow-auto max-h-60 text-neutral-600 dark:text-neutral-400">
            {content.slice(0, 5000)}
            {content.length > 5000 && "\n\n... (truncated)"}
          </pre>
        </div>
      )}
    </div>
  );
}

/**
 * Pseudo Element Card Component
 * 伪元素卡片组件
 */
function PseudoElementCard({ pseudo }: { pseudo: PseudoElementStyle }) {
  return (
    <div
      className={cn(
        "p-2 rounded text-xs font-mono",
        "bg-neutral-50 dark:bg-neutral-800/50"
      )}
    >
      <div className="flex items-center gap-1 mb-1">
        <span className="text-blue-500">{pseudo.selector}</span>
        <span className="text-purple-500">{pseudo.pseudo}</span>
      </div>
      <div className="text-neutral-500 space-x-2">
        {Object.entries(pseudo.styles).slice(0, 5).map(([prop, val], i) => (
          <span key={i}>
            <span className="text-green-600">{prop}</span>
            <span className="text-neutral-400">: </span>
            <span className="text-orange-500">{String(val).slice(0, 30)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * CSS Tab Component
 * CSS 数据 Tab 组件
 */
export function CSSTab({ cssData }: CSSTabProps) {
  if (!cssData) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No CSS data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-900/10 border border-green-200 dark:border-green-800">
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">
            {cssData.stylesheets.length}
          </p>
          <p className="text-xs text-green-700 dark:text-green-500">Stylesheets</p>
        </div>
        <div className="p-3 rounded-lg bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-900/10 border border-purple-200 dark:border-purple-800">
          <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {cssData.animations.length}
          </p>
          <p className="text-xs text-purple-700 dark:text-purple-500">Animations</p>
        </div>
        <div className="p-3 rounded-lg bg-gradient-to-br from-cyan-50 to-cyan-100 dark:from-cyan-900/20 dark:to-cyan-900/10 border border-cyan-200 dark:border-cyan-800">
          <p className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">
            {cssData.variables.length}
          </p>
          <p className="text-xs text-cyan-700 dark:text-cyan-500">Variables</p>
        </div>
        <div className="p-3 rounded-lg bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-900/10 border border-orange-200 dark:border-orange-800">
          <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
            {cssData.pseudo_elements.length}
          </p>
          <p className="text-xs text-orange-700 dark:text-orange-500">Pseudo Elements</p>
        </div>
      </div>

      {/* Stylesheets */}
      <CollapsibleSection
        title="Stylesheets"
        icon={Code2}
        count={cssData.stylesheets.length}
        defaultOpen={true}
      >
        <div className="space-y-2 mt-3">
          {cssData.stylesheets.map((sheet, idx) => (
            <StylesheetCard key={idx} stylesheet={sheet} />
          ))}
        </div>
      </CollapsibleSection>

      {/* Animations */}
      {cssData.animations.length > 0 && (
        <CollapsibleSection
          title="Animations (@keyframes)"
          icon={Play}
          count={cssData.animations.length}
          defaultOpen={true}
        >
          <div className="space-y-2 mt-3">
            {cssData.animations.map((anim, idx) => (
              <AnimationCard key={idx} animation={anim} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* CSS Variables */}
      {cssData.variables.length > 0 && (
        <CollapsibleSection
          title="CSS Variables"
          icon={Palette}
          count={cssData.variables.length}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
            {cssData.variables.map((variable, idx) => (
              <VariableCard key={idx} variable={variable} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Pseudo Elements */}
      {cssData.pseudo_elements.length > 0 && (
        <CollapsibleSection
          title="Pseudo Elements"
          icon={Sparkles}
          count={cssData.pseudo_elements.length}
        >
          <div className="space-y-2 mt-3">
            {cssData.pseudo_elements.slice(0, 20).map((pseudo, idx) => (
              <PseudoElementCard key={idx} pseudo={pseudo} />
            ))}
            {cssData.pseudo_elements.length > 20 && (
              <p className="text-xs text-neutral-400 text-center">
                ... and {cssData.pseudo_elements.length - 20} more
              </p>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Transitions */}
      {cssData.transitions.length > 0 && (
        <CollapsibleSection
          title="Transitions"
          icon={Play}
          count={cssData.transitions.length}
        >
          <div className="space-y-1 mt-3">
            {cssData.transitions.slice(0, 30).map((trans, idx) => (
              <div
                key={idx}
                className="text-xs font-mono p-2 rounded bg-neutral-50 dark:bg-neutral-800"
              >
                <span className="text-green-500">{trans.property}</span>
                <span className="text-neutral-400"> | </span>
                <span className="text-blue-500">{trans.duration}</span>
                <span className="text-neutral-400"> | </span>
                <span className="text-orange-500">{trans.timing_function}</span>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
