/**
 * Playwright Extractor API Service
 * 封装与后端 Playwright 提取服务的通信
 *
 * 功能：
 * - 发送提取请求
 * - 处理响应数据
 * - 错误处理
 */

import { CODEGEN_CONFIG } from '@/config/codegen';
import type {
  ExtractRequest,
  ExtractionResult,
  ThemeMode,
  ThemeSupport,
  ThemeDetectionResult,
  ThemedData,
} from '@/types/playwright';

// API 基础 URL
const API_BASE = CODEGEN_CONFIG.API_URL;

// Playwright API 端点
const ENDPOINTS = {
  EXTRACT: '/api/playwright/extract',
  EXTRACT_QUICK: '/api/playwright/extract/quick',
  EXTRACT_STATUS: '/api/playwright/extract', // + /{request_id}/status
  HEALTH: '/api/playwright/health',
  CLEANUP: '/api/playwright/cleanup',
} as const;

/**
 * 提取阶段枚举
 */
export type ExtractionPhase = 'quick' | 'dom' | 'advanced' | 'complete' | 'error';

/**
 * 快速提取结果类型
 */
export interface QuickExtractionResult {
  success: boolean;
  message: string;
  request_id: string;
  phase: ExtractionPhase;
  progress: number;
  metadata?: {
    url: string;
    title: string;
    viewport_width: number;
    viewport_height: number;
    page_width: number;
    page_height: number;
    total_elements: number;
    max_depth: number;
    load_time_ms: number;
  } | null;
  screenshot?: string | null;
  assets?: {
    images: Array<{ url: string; type: string }>;
    scripts: Array<{ url: string; type: string }>;
    stylesheets: Array<{ url: string; type: string }>;
    fonts: Array<{ url: string; type: string }>;
    total_images: number;
    total_scripts: number;
    total_stylesheets: number;
    total_fonts: number;
  } | null;
  raw_html?: string | null;
  error?: string | null;

  // Theme related fields
  theme_detection?: ThemeDetectionResult | null;
  current_theme?: ThemeMode;
  light_mode_data?: ThemedData | null;
  dark_mode_data?: ThemedData | null;
}

/**
 * 提取状态响应类型
 */
export interface ExtractionStatusResponse {
  request_id: string;
  phase: ExtractionPhase;
  progress: number;
  is_complete: boolean;
  // DOM 阶段数据
  dom_tree?: unknown;
  style_summary?: unknown;
  // 高级阶段数据
  css_data?: unknown;
  network_data?: unknown;
  full_page_screenshot?: string | null;
  interaction_data?: unknown;
  tech_stack?: unknown;
  components?: unknown;
  // 完成阶段数据
  downloaded_resources?: unknown;
  // 主题相关（完成阶段后更新）
  light_mode_data?: ThemedData | null;
  dark_mode_data?: ThemedData | null;
  // 错误信息
  error?: string | null;
}

/**
 * 提取网页结构信息
 *
 * @param request - 提取请求参数
 * @returns ExtractionResult - 完整的提取结果
 * @throws Error - 请求失败时抛出错误
 *
 * @example
 * const result = await extractPage({
 *   url: 'https://example.com',
 *   viewport_width: 1920,
 *   include_screenshot: true
 * });
 */
export async function extractPage(request: ExtractRequest): Promise<ExtractionResult> {
  const response = await fetch(`${API_BASE}${ENDPOINTS.EXTRACT}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url: request.url,
      viewport_width: request.viewport_width ?? 1920,
      viewport_height: request.viewport_height ?? 1080,
      wait_for_selector: request.wait_for_selector ?? null,
      wait_timeout: request.wait_timeout ?? 30000,
      include_screenshot: request.include_screenshot ?? true,
      max_depth: request.max_depth ?? 50,
      include_hidden: request.include_hidden ?? false,
      // 新增选项 - 像素级复刻功能
      download_resources: request.download_resources ?? true,
      capture_network: request.capture_network ?? true,
      capture_interactions: request.capture_interactions ?? true,
      extract_css: request.extract_css ?? true,
      full_page_screenshot: request.full_page_screenshot ?? false,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error: ${response.status}`);
  }

  return response.json();
}

/**
 * 快速提取网页结构信息（分阶段提取，优化首屏加载）
 *
 * @param request - 提取请求参数
 * @returns QuickExtractionResult - 快速提取结果，包含 request_id 用于后续轮询
 * @throws Error - 请求失败时抛出错误
 *
 * @example
 * const result = await extractPageQuick({
 *   url: 'https://example.com',
 *   viewport_width: 1920,
 *   include_screenshot: true
 * });
 * // 开始轮询获取后续数据
 * pollExtractionStatus(result.request_id, (status) => {
 *   console.log('Progress:', status.progress);
 * });
 */
function withTimeout(ms: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { controller, cleanup: () => clearTimeout(timer) };
}


async function fetchJsonWithDiagnostics<T>(url: string, init: RequestInit & { timeoutMs?: number }): Promise<T> {
  const timeoutMs = init.timeoutMs ?? 30_000;
  const { controller, cleanup } = withTimeout(timeoutMs);

  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      let detail: string | undefined;
      try {
        const maybeJson = JSON.parse(text);
        detail = maybeJson?.detail ?? maybeJson?.error;
      } catch {
        // ignore
      }
      throw new Error(
        `Request failed. url=${url} status=${response.status} ${detail ? `detail=${detail}` : ''} ${text ? `body=${text.slice(0, 500)}` : ''}`
      );
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(`Request timeout after ${timeoutMs}ms. url=${url}`);
    }
    // Browser often throws generic 'Failed to fetch' for CORS/network/DNS.
    throw new Error(`Fetch failed: ${(err as Error)?.message || String(err)}. url=${url}. Check NEXT_PUBLIC_BACKEND_URL and CORS.`);
  } finally {
    cleanup();
  }
}

export async function extractPageQuick(request: ExtractRequest): Promise<QuickExtractionResult> {
  const url = `${API_BASE}${ENDPOINTS.EXTRACT_QUICK}`;

  return fetchJsonWithDiagnostics<QuickExtractionResult>(url, {
    timeoutMs: 60_000,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url: request.url,
      viewport_width: request.viewport_width ?? 1920,
      viewport_height: request.viewport_height ?? 1080,
      wait_for_selector: request.wait_for_selector ?? null,
      wait_timeout: request.wait_timeout ?? 30000,
      include_screenshot: request.include_screenshot ?? true,
      max_depth: request.max_depth ?? 50,
      include_hidden: request.include_hidden ?? false,
      // 新增选项 - 像素级复刻功能
      download_resources: request.download_resources ?? true,
      capture_network: request.capture_network ?? true,
      capture_interactions: request.capture_interactions ?? true,
      extract_css: request.extract_css ?? true,
      full_page_screenshot: request.full_page_screenshot ?? false,
    }),
  });
}


/**
 * 获取提取状态和后续阶段数据
 *
 * @param requestId - 快速提取返回的请求 ID
 * @returns ExtractionStatusResponse - 当前状态和已完成阶段的数据
 * @throws Error - 请求失败时抛出错误
 */
export async function getExtractionStatus(requestId: string): Promise<ExtractionStatusResponse> {
  const response = await fetch(`${API_BASE}${ENDPOINTS.EXTRACT_STATUS}/${requestId}/status`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error: ${response.status}`);
  }

  return response.json();
}

/**
 * 轮询提取状态直到完成
 *
 * @param requestId - 请求 ID
 * @param onUpdate - 状态更新回调
 * @param options - 轮询选项
 * @returns Promise<ExtractionStatusResponse> - 最终状态
 */
export async function pollExtractionStatus(
  requestId: string,
  onUpdate?: (status: ExtractionStatusResponse) => void,
  options?: {
    interval?: number;      // 轮询间隔（毫秒），默认 1000
    maxAttempts?: number;   // 最大尝试次数，默认 60
  }
): Promise<ExtractionStatusResponse> {
  const interval = options?.interval ?? 1000;
  const maxAttempts = options?.maxAttempts ?? 60;
  let attempts = 0;

  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        attempts++;
        const status = await getExtractionStatus(requestId);

        // 回调通知更新
        onUpdate?.(status);

        // 检查是否完成或出错
        if (status.is_complete || status.phase === 'error') {
          resolve(status);
          return;
        }

        // 检查是否超过最大尝试次数
        if (attempts >= maxAttempts) {
          reject(new Error('Polling timeout: max attempts reached'));
          return;
        }

        // 继续轮询
        setTimeout(poll, interval);
      } catch (error) {
        reject(error);
      }
    };

    // 开始轮询
    poll();
  });
}

/**
 * 检查 Playwright 服务健康状态
 *
 * @returns Promise<boolean> - 服务是否正常
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}${ENDPOINTS.HEALTH}`);
    if (response.ok) {
      const data = await response.json();
      return data.success === true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * 清理浏览器资源
 * 关闭后端的浏览器实例，释放内存
 *
 * @returns Promise<boolean> - 是否成功清理
 */
export async function cleanupBrowser(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}${ENDPOINTS.CLEANUP}`, {
      method: 'POST',
    });
    if (response.ok) {
      const data = await response.json();
      return data.success === true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * 格式化文件大小
 *
 * @param bytes - 字节数
 * @returns 格式化后的字符串
 */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return 'Unknown';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * 格式化加载时间
 *
 * @param ms - 毫秒
 * @returns 格式化后的字符串
 */
export function formatLoadTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * 统计 DOM 树中的元素数量
 *
 * @param element - 根元素
 * @returns 总元素数
 */
export function countElements(element: { children: unknown[] } | null | undefined): number {
  if (!element) return 0;
  let count = 1;
  for (const child of element.children || []) {
    count += countElements(child as { children: unknown[] });
  }
  return count;
}

/**
 * 获取 URL 的域名部分
 *
 * @param url - 完整 URL
 * @returns 域名
 */
export function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
