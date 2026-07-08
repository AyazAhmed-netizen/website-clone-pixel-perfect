"use client";

import React, { useState } from "react";
import {
  Globe,
  ArrowRight,
  Clock,
  FileJson,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { NetworkData, NetworkRequest } from "@/types/playwright";

/**
 * Network Tab Props
 */
interface NetworkTabProps {
  networkData: NetworkData | null;
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

/**
 * Get status color based on HTTP status code
 */
function getStatusColor(status: number | null | undefined): string {
  if (!status) return "text-neutral-400";
  if (status >= 200 && status < 300) return "text-green-500";
  if (status >= 300 && status < 400) return "text-yellow-500";
  if (status >= 400) return "text-red-500";
  return "text-neutral-400";
}

/**
 * Get request type badge color
 */
function getTypeBadgeColor(type: string): string {
  switch (type) {
    case "xhr":
    case "fetch":
      return "bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400";
    case "document":
      return "bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400";
    case "script":
      return "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400";
    case "stylesheet":
      return "bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400";
    case "image":
      return "bg-pink-100 dark:bg-pink-900/30 text-pink-600 dark:text-pink-400";
    case "font":
      return "bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400";
    default:
      return "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400";
  }
}

/**
 * Request Row Component
 * 请求行组件
 */
function RequestRow({ request }: { request: NetworkRequest }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyResponse = () => {
    if (request.response_body) {
      navigator.clipboard.writeText(request.response_body);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Parse URL to get pathname
  let pathname = request.url;
  try {
    const url = new URL(request.url);
    pathname = url.pathname + url.search;
  } catch {
    // Keep full URL if parsing fails
  }

  const isApiCall = request.request_type === "xhr" || request.request_type === "fetch";

  return (
    <div
      className={cn(
        "rounded-lg border",
        "bg-white dark:bg-neutral-900",
        "border-neutral-200 dark:border-neutral-700",
        isApiCall && "ring-1 ring-purple-200 dark:ring-purple-800"
      )}
    >
      {/* Main row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={cn(
          "w-full flex items-center gap-3 p-3 text-left",
          "hover:bg-neutral-50 dark:hover:bg-neutral-800/50",
          "transition-colors"
        )}
      >
        {/* Expand icon */}
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-neutral-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-neutral-400 flex-shrink-0" />
        )}

        {/* Method */}
        <span
          className={cn(
            "px-1.5 py-0.5 text-[10px] font-mono font-bold rounded",
            request.method === "GET"
              ? "bg-green-100 dark:bg-green-900/30 text-green-600"
              : "bg-blue-100 dark:bg-blue-900/30 text-blue-600"
          )}
        >
          {request.method}
        </span>

        {/* Status */}
        <span
          className={cn(
            "w-10 text-xs font-mono font-semibold",
            getStatusColor(request.response_status)
          )}
        >
          {request.response_status || "---"}
        </span>

        {/* Type badge */}
        <span
          className={cn(
            "px-1.5 py-0.5 text-[10px] rounded",
            getTypeBadgeColor(request.request_type)
          )}
        >
          {request.request_type}
        </span>

        {/* URL */}
        <span className="flex-1 text-xs font-mono truncate text-neutral-600 dark:text-neutral-400">
          {pathname}
        </span>

        {/* Timing */}
        {request.timing && (
          <span className="text-[10px] text-neutral-400 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {request.timing.toFixed(0)}ms
          </span>
        )}

        {/* Size */}
        {request.response_size && (
          <span className="text-[10px] text-neutral-400 w-16 text-right">
            {formatBytes(request.response_size)}
          </span>
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-neutral-200 dark:border-neutral-700 p-3 space-y-3">
          {/* Full URL */}
          <div>
            <p className="text-[10px] text-neutral-500 mb-1">URL</p>
            <p className="text-xs font-mono break-all text-neutral-700 dark:text-neutral-300">
              {request.url}
            </p>
          </div>

          {/* Request Headers (if API call) */}
          {isApiCall && Object.keys(request.headers).length > 0 && (
            <div>
              <p className="text-[10px] text-neutral-500 mb-1">Request Headers</p>
              <div className="bg-neutral-50 dark:bg-neutral-800 rounded p-2 text-xs font-mono max-h-32 overflow-auto">
                {Object.entries(request.headers).slice(0, 10).map(([key, val]) => (
                  <div key={key} className="flex gap-2">
                    <span className="text-blue-500">{key}:</span>
                    <span className="text-neutral-600 dark:text-neutral-400 truncate">
                      {val}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* POST Data */}
          {request.post_data && (
            <div>
              <p className="text-[10px] text-neutral-500 mb-1">Request Body</p>
              <pre className="bg-neutral-50 dark:bg-neutral-800 rounded p-2 text-xs font-mono max-h-40 overflow-auto">
                {request.post_data}
              </pre>
            </div>
          )}

          {/* Response Body */}
          {request.response_body && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] text-neutral-500">Response Body</p>
                <button
                  onClick={handleCopyResponse}
                  className="flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-600"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" /> Copy
                    </>
                  )}
                </button>
              </div>
              <pre className="bg-neutral-50 dark:bg-neutral-800 rounded p-2 text-xs font-mono max-h-60 overflow-auto whitespace-pre-wrap">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(request.response_body), null, 2);
                  } catch {
                    return request.response_body.slice(0, 3000);
                  }
                })()}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Network Tab Component
 * 网络请求 Tab 组件
 */
export function NetworkTab({ networkData }: NetworkTabProps) {
  const [filter, setFilter] = useState<"all" | "api">("all");

  if (!networkData) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-500">
        No network data available
      </div>
    );
  }

  const filteredRequests =
    filter === "api" ? networkData.api_calls : networkData.requests;

  // Calculate stats
  const successCount = networkData.requests.filter(
    (r) => r.response_status && r.response_status >= 200 && r.response_status < 400
  ).length;
  const errorCount = networkData.requests.filter(
    (r) => r.response_status && r.response_status >= 400
  ).length;

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/10 border border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-blue-500" />
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {networkData.total_requests}
            </p>
          </div>
          <p className="text-xs text-blue-700 dark:text-blue-500">Total Requests</p>
        </div>

        <div className="p-3 rounded-lg bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-900/10 border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2">
            <FileJson className="h-4 w-4 text-purple-500" />
            <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {networkData.api_calls.length}
            </p>
          </div>
          <p className="text-xs text-purple-700 dark:text-purple-500">API Calls</p>
        </div>

        <div className="p-3 rounded-lg bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-900/10 border border-green-200 dark:border-green-800">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {successCount}
            </p>
          </div>
          <p className="text-xs text-green-700 dark:text-green-500">Successful</p>
        </div>

        <div className="p-3 rounded-lg bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900/20 dark:to-red-900/10 border border-red-200 dark:border-red-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {errorCount}
            </p>
          </div>
          <p className="text-xs text-red-700 dark:text-red-500">Errors</p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setFilter("all")}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
            filter === "all"
              ? "bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
              : "text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          )}
        >
          All Requests ({networkData.total_requests})
        </button>
        <button
          onClick={() => setFilter("api")}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
            filter === "api"
              ? "bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"
              : "text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          )}
        >
          API Calls ({networkData.api_calls.length})
        </button>
      </div>

      {/* Request List */}
      <div className="space-y-2">
        {filteredRequests.length === 0 ? (
          <div className="text-center py-8 text-neutral-500">
            No {filter === "api" ? "API calls" : "requests"} captured
          </div>
        ) : (
          filteredRequests.map((request, idx) => (
            <RequestRow key={idx} request={request} />
          ))
        )}
      </div>

      {/* Total Size */}
      {networkData.total_size > 0 && (
        <div className="text-center text-xs text-neutral-400">
          Total transferred: {formatBytes(networkData.total_size)}
        </div>
      )}
    </div>
  );
}
