"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type {
  WebContainerState,
  ProcessOutput,
  TerminalSession,
  ConsoleMessage,
  PreviewState,
  FileDiffState,
} from "@/types/nexting-agent";

// Use a ref-based history buffer to avoid setState race conditions
interface TerminalHistoryBuffer {
  [terminalId: string]: ProcessOutput[];
}

// ============================================
// WebContainer API Types
// ============================================

// Using 'any' for WebContainer instance to avoid strict type conflicts
// between our interface and the actual library types
type WebContainerInstance = any;
type WebContainerProcess = any;

// FileSystemTree type for mounting files
interface FileSystemTree {
  [path: string]: {
    file?: { contents: string };
    directory?: FileSystemTree;
  };
}

// ============================================
// Constants
// ============================================

const MAX_TERMINALS = 5;
const MAX_CONSOLE_MESSAGES = 200;
const MAX_HISTORY_ENTRIES = 1000;

// Error prefixes for WebContainer action results
// These are used to detect failures in action responses
export const ERROR_PREFIX_ACTION_FAILED = "[ACTION_FAILED]";
export const ERROR_PREFIX_COMMAND_FAILED = "[COMMAND_FAILED]";

/**
 * Check if an action result indicates an error
 * Detects various error formats from WebContainer actions:
 * - [ACTION_FAILED] - general action failures (file read, delete, etc.)
 * - [COMMAND_FAILED] - shell command execution failures
 * - Error: - legacy/generic error format
 */
export function isActionError(result: string): boolean {
  return (
    result.startsWith(ERROR_PREFIX_ACTION_FAILED) ||
    result.startsWith(ERROR_PREFIX_COMMAND_FAILED) ||
    result.startsWith("Error:")
  );
}

// ============================================
// Hook Options Interface
// ============================================

/**
 * Agent log entry for terminal display
 */
export interface AgentLogEntry {
  type: "command" | "output" | "error" | "info" | "file";
  content: string;
  timestamp: number;
}

export interface UseWebContainerOptions {
  /**
   * Callback when a console error occurs in the preview.
   * Use this to automatically notify the Agent about errors.
   */
  onPreviewError?: (error: {
    message: string;
    stack?: string;
    timestamp: number;
  }) => void;

  /**
   * Callback when preview health changes (after HMR).
   * Returns true if healthy, false if there are errors.
   */
  onHealthChange?: (healthy: boolean, errorCount: number) => void;

  /**
   * Callback when Agent performs an action (for terminal logging).
   * This allows displaying Agent operations in the terminal.
   */
  onAgentLog?: (log: AgentLogEntry) => void;

  /**
   * Callback when a file is written.
   * Used by external image downloader to trigger processing.
   */
  onFileWritten?: (path: string, content: string) => void;
}

// ============================================
// Default Project Files
// ============================================

const DEFAULT_FILES: Record<string, string> = {
  "/package.json": JSON.stringify(
    {
      name: "nexting-agent-project",
      version: "1.0.0",
      private: true,
      scripts: {
        dev: "vite",
        build: "vite build",
        preview: "vite preview",
      },
      dependencies: {
        react: "^18.2.0",
        "react-dom": "^18.2.0",
      },
      devDependencies: {
        "@vitejs/plugin-react": "^4.2.0",
        vite: "^5.0.0",
        // Tailwind CSS v3.x for styling (locked to avoid v4 breaking changes)
        tailwindcss: "3.4.17",
        postcss: "^8.4.32",
        autoprefixer: "^10.4.16",
      },
    },
    null,
    2
  ),

  // ============================================
  // Tailwind CSS Configuration
  // ============================================
  "/tailwind.config.js": `/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Common custom colors used by many websites
      colors: {
        'brand': 'var(--color-brand, #f26625)',
        'linkColor': 'var(--color-link, #0066cc)',
      },
      // Custom max-widths
      maxWidth: {
        'page': 'var(--max-width-page, 1200px)',
      },
    },
  },
  plugins: [],
  // Enable arbitrary values for full compatibility
  // e.g., class="py-[13px]" or "max-w-[1200px]"
}
`,

  "/postcss.config.js": `export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
`,

  // ============================================
  // Public Images Directory
  // ============================================
  // Pre-create /public/images/ directory for downloaded images
  // This directory will store images downloaded from external URLs
  "/public/images/.gitkeep": `# This directory stores downloaded images from external URLs
# Images are automatically downloaded when Agent writes code with external image links
`,

  // ============================================
  // Image Proxy Plugin - Modular Vite middleware
  // Enables loading external images via internal proxy
  // Bypasses CORS restrictions in WebContainer
  // ============================================
  "/_image-proxy-plugin.js": `/**
 * Nexting Image Proxy Plugin for Vite
 *
 * Provides a middleware endpoint to proxy external images,
 * bypassing CORS restrictions in WebContainer environment.
 *
 * Usage:
 *   - Original: <img src="https://example.com/image.jpg" />
 *   - Proxied:  <img src="/proxy-image?url=https%3A%2F%2Fexample.com%2Fimage.jpg" />
 *
 * The plugin automatically handles:
 *   - URL decoding
 *   - Content-Type passthrough
 *   - Error handling with fallback placeholder
 */

/**
 * Create image proxy Vite plugin
 * @returns {import('vite').Plugin} Vite plugin
 */
export function imageProxyPlugin() {
  return {
    name: 'nexting-image-proxy',

    configureServer(server) {
      // Add middleware for image proxy
      server.middlewares.use('/proxy-image', async (req, res) => {
        try {
          // Parse URL from query string
          const url = new URL(req.url, 'http://localhost');
          const imageUrl = url.searchParams.get('url');

          if (!imageUrl) {
            res.statusCode = 400;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ error: 'Missing url parameter' }));
            return;
          }

          // Decode URL if needed
          const decodedUrl = decodeURIComponent(imageUrl);
          console.log('[Image Proxy] Fetching:', decodedUrl);

          // Fetch the image using Node.js fetch (no CORS in WebContainer's Node.js)
          const response = await fetch(decodedUrl, {
            headers: {
              // Mimic browser User-Agent to avoid blocks
              'User-Agent': 'Mozilla/5.0 (compatible; NextingAgent/1.0)',
              'Accept': 'image/*,*/*',
            },
          });

          if (!response.ok) {
            console.error('[Image Proxy] Fetch failed:', response.status, response.statusText);
            res.statusCode = response.status;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({
              error: 'Failed to fetch image',
              status: response.status,
              url: decodedUrl
            }));
            return;
          }

          // Get content type from response
          const contentType = response.headers.get('content-type') || 'image/png';

          // Read response as buffer
          const arrayBuffer = await response.arrayBuffer();
          const buffer = Buffer.from(arrayBuffer);

          // Set response headers
          res.statusCode = 200;
          res.setHeader('Content-Type', contentType);
          res.setHeader('Content-Length', buffer.length);
          res.setHeader('Cache-Control', 'public, max-age=31536000'); // Cache for 1 year
          res.setHeader('Access-Control-Allow-Origin', '*');

          // Send the image
          res.end(buffer);
          console.log('[Image Proxy] Success:', decodedUrl, contentType, buffer.length, 'bytes');

        } catch (error) {
          console.error('[Image Proxy] Error:', error.message);
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({
            error: 'Proxy error',
            message: error.message
          }));
        }
      });

      console.log('[Image Proxy] Middleware initialized at /proxy-image');
    },
  };
}

/**
 * Helper function to convert external image URL to proxied URL
 * @param {string} originalUrl - Original external image URL
 * @returns {string} Proxied URL
 */
export function toProxyUrl(originalUrl) {
  if (!originalUrl) return originalUrl;

  // Skip data URLs and relative paths
  if (originalUrl.startsWith('data:') || originalUrl.startsWith('/')) {
    return originalUrl;
  }

  // Skip if already proxied
  if (originalUrl.includes('/proxy-image?url=')) {
    return originalUrl;
  }

  // Convert to proxy URL
  return '/proxy-image?url=' + encodeURIComponent(originalUrl);
}

export default imageProxyPlugin;
`,

  "/vite.config.js": `import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { imageProxyPlugin } from './_image-proxy-plugin.js';

/**
 * Nexting Bridge Injection Plugin
 * Automatically injects the Bridge script into all HTML responses.
 * This ensures the Agent can communicate with the preview even if
 * the user modifies index.html or creates new HTML files.
 */
function nextingBridgePlugin() {
  return {
    name: 'nexting-bridge-inject',
    transformIndexHtml(html) {
      // Check if Bridge script is already included
      if (html.includes('nexting-bridge.js') || html.includes('__nextingBridgeInitialized')) {
        return html;
      }
      // Inject Bridge script reference before </body>
      return html.replace(
        '</body>',
        '    <!-- Nexting Bridge: Auto-injected by Vite plugin -->\\n    <script src="/nexting-bridge.js"></script>\\n  </body>'
      );
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    imageProxyPlugin(),  // Enable image proxy for external images
    nextingBridgePlugin(),  // Auto-inject Bridge script for Agent communication
  ],
  server: {
    host: true,
  },
});
`,
  "/index.html": `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Nexting Agent App</title>
    <!-- html2canvas is loaded dynamically by Nexting Bridge to avoid blocking -->
    <!-- Nexting Configuration: Backend URL for image proxy -->
    <script>
      // Detect backend URL from parent window or use default
      (function() {
        try {
          // Try to get from parent window (if embedded in Nexting Agent)
          if (window.parent && window.parent.__NEXTING_BACKEND_URL) {
            window.__NEXTING_BACKEND_URL = window.parent.__NEXTING_BACKEND_URL;
          } else {
            // Default: localhost for development, or detect from current location
            var isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            // Production URL: Update this after deploying backend to Railway/Fly.io
            // Example: 'https://nexting-backend-production.up.railway.app'
            var PRODUCTION_BACKEND_URL = 'https://api.nexting.ai';
            window.__NEXTING_BACKEND_URL = isLocalhost ? 'http://localhost:5001' : PRODUCTION_BACKEND_URL;
          }
          console.log('[Nexting Config] Backend URL:', window.__NEXTING_BACKEND_URL);
        } catch (e) {
          window.__NEXTING_BACKEND_URL = 'http://localhost:5001';
        }
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
    <!-- Nexting Bridge: Enables Agent to inspect DOM and take screenshots -->
    <script src="/nexting-bridge.js"></script>
  </body>
</html>
`,
  // Bridge script for Agent communication (DOM snapshots, screenshots, etc.)
  // Placed in /public so Vite can serve it as a static file
  "/public/nexting-bridge.js": `/**
 * Nexting Bridge Script
 * Enables communication between parent window (Nexting Agent) and WebContainer preview.
 * Provides DOM snapshot and screenshot capabilities.
 * Also handles image fallback for CORS-restricted external images.
 */
(function() {
  'use strict';

  // Prevent multiple initializations
  if (window.__nextingBridgeInitialized) return;
  window.__nextingBridgeInitialized = true;

  console.log('[Nexting Bridge] Initializing...');

  // ============================================
  // Dynamic html2canvas Loading (with short timeout)
  // ============================================
  // Load html2canvas dynamically - but with very short timeout
  // Primary screenshot method is now SVG-based (doesn't need external lib)

  let html2canvasLoadAttempted = false;
  let html2canvasLoading = null;

  function loadHtml2Canvas() {
    if (html2canvasLoadAttempted) return html2canvasLoading;
    html2canvasLoadAttempted = true;

    html2canvasLoading = new Promise((resolve) => {
      // If already loaded, resolve immediately
      if (typeof html2canvas !== 'undefined') {
        console.log('[Nexting Bridge] html2canvas already loaded');
        resolve(true);
        return;
      }

      // Create script element
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      script.async = true;

      // Timeout - 8 seconds for CDN loading in WebContainer environment
      const timeout = setTimeout(() => {
        console.log('[Nexting Bridge] html2canvas load timeout - using SVG fallback');
        resolve(false);
      }, 8000);

      script.onload = () => {
        clearTimeout(timeout);
        console.log('[Nexting Bridge] html2canvas loaded successfully');
        resolve(true);
      };

      script.onerror = () => {
        clearTimeout(timeout);
        console.log('[Nexting Bridge] html2canvas load failed - using SVG fallback');
        resolve(false);
      };

      document.head.appendChild(script);
    });

    return html2canvasLoading;
  }

  // Start loading html2canvas in background (non-blocking)
  loadHtml2Canvas();

  // ============================================
  // Image Error Handler (Fallback)
  // ============================================
  // Images are now downloaded at writeFile time, but this provides
  // a fallback for any images that fail to load (shows placeholder)

  function showErrorPlaceholder(img) {
    if (img.dataset.nextingFailed === 'true') return;
    img.dataset.nextingFailed = 'true';

    const originalSrc = img.dataset.originalSrc || img.src || 'unknown';
    const w = img.width || img.naturalWidth || 200;
    const h = img.height || img.naturalHeight || 150;

    const svgPlaceholder = \`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='\${w}' height='\${h}' viewBox='0 0 \${w} \${h}'%3E%3Crect fill='%23f3f4f6' width='100%25' height='100%25'/%3E%3Ctext x='50%25' y='45%25' dominant-baseline='middle' text-anchor='middle' fill='%239ca3af' font-family='system-ui,sans-serif' font-size='12'%3E🖼️ Image%3C/text%3E%3Ctext x='50%25' y='60%25' dominant-baseline='middle' text-anchor='middle' fill='%239ca3af' font-family='system-ui,sans-serif' font-size='10'%3E\${w}x\${h}%3C/text%3E%3C/svg%3E\`;

    img.src = svgPlaceholder;
    img.title = \`Image could not be loaded: \${originalSrc.substring(0, 100)}\`;
    img.style.cursor = 'help';
    console.log('[Nexting Bridge] Image failed, showing placeholder:', originalSrc.substring(0, 50));
  }

  // Handle image errors globally
  document.addEventListener('error', (e) => {
    if (e.target?.tagName === 'IMG') {
      showErrorPlaceholder(e.target);
    }
  }, true);

  // Check already loaded images for failures
  document.querySelectorAll('img').forEach(img => {
    if (img.complete && img.naturalHeight === 0 && img.src && !img.src.startsWith('data:')) {
      showErrorPlaceholder(img);
    }
  });

  // ============================================
  // Vite Error Overlay Detection
  // ============================================
  // Captures Vite build/HMR errors and forwards to Agent
  // This enables Agent to fix errors without needing screenshots

  let lastReportedError = '';
  let errorReportTimeout = null;

  function extractViteErrorMessage(overlay) {
    // Try to extract error message from Vite error overlay
    // Vite 5.x uses shadow DOM with different structure than Vite 4.x
    const shadowRoot = overlay.shadowRoot;
    if (!shadowRoot) {
      // Fallback: try to get text content directly
      return overlay.textContent?.slice(0, 2000) || 'Unknown Vite error';
    }

    // Vite 5.x selectors (prioritize these)
    const vite5Selectors = [
      '.error-message',
      '.message',
      '[class*="message"]',
      '.error',
      'pre',
      'code',
      '.stack',
      '.frame'
    ];

    // Vite 4.x selectors (fallback)
    const vite4Selectors = [
      '.message-body',
      '.plugin',
      '.file'
    ];

    const allSelectors = [...vite5Selectors, ...vite4Selectors];

    // Try each selector
    for (const selector of allSelectors) {
      const el = shadowRoot.querySelector(selector);
      if (el && el.textContent?.trim()) {
        return el.textContent.slice(0, 2000);
      }
    }

    // Try to get all text from backdrop/overlay container
    const container = shadowRoot.querySelector('.backdrop') ||
                      shadowRoot.querySelector('.overlay') ||
                      shadowRoot.querySelector('[class*="overlay"]') ||
                      shadowRoot.querySelector('div');
    if (container && container.textContent?.trim()) {
      return container.textContent.slice(0, 2000);
    }

    // Last fallback: get all text from shadow root
    return shadowRoot.textContent?.slice(0, 2000) || 'Unknown Vite error';
  }

  // Extract structured error info from Vite overlay (for detailed error reporting)
  function extractStructuredViteError(overlay) {
    const result = {
      message: '',
      file: null,
      line: null,
      column: null,
      frame: null,
      stack: null,
      plugin: null
    };

    const shadowRoot = overlay.shadowRoot;
    if (!shadowRoot) {
      result.message = overlay.textContent?.slice(0, 2000) || 'Unknown error';
      return result;
    }

    // Vite 5.x: Try to get structured info
    // The error message
    const msgEl = shadowRoot.querySelector('.message') ||
                  shadowRoot.querySelector('.error-message') ||
                  shadowRoot.querySelector('[class*="message"]') ||
                  shadowRoot.querySelector('pre');
    if (msgEl) {
      result.message = msgEl.textContent?.trim()?.slice(0, 2000) || '';
    }

    // File location
    const fileEl = shadowRoot.querySelector('.file') ||
                   shadowRoot.querySelector('[class*="file"]') ||
                   shadowRoot.querySelector('.loc');
    if (fileEl) {
      const fileText = fileEl.textContent?.trim() || '';
      result.file = fileText;
      // Try to extract line:column from file path
      const locMatch = fileText.match(/:(\d+):(\d+)/);
      if (locMatch) {
        result.line = parseInt(locMatch[1], 10);
        result.column = parseInt(locMatch[2], 10);
      }
    }

    // Code frame
    const frameEl = shadowRoot.querySelector('.frame') ||
                    shadowRoot.querySelector('[class*="frame"]') ||
                    shadowRoot.querySelector('pre code');
    if (frameEl) {
      result.frame = frameEl.textContent?.trim()?.slice(0, 1000) || null;
    }

    // Stack trace
    const stackEl = shadowRoot.querySelector('.stack') ||
                    shadowRoot.querySelector('[class*="stack"]');
    if (stackEl) {
      result.stack = stackEl.textContent?.trim()?.slice(0, 1500) || null;
    }

    // Plugin name (e.g., vite:react-babel)
    const pluginEl = shadowRoot.querySelector('.plugin') ||
                     shadowRoot.querySelector('[class*="plugin"]');
    if (pluginEl) {
      result.plugin = pluginEl.textContent?.trim() || null;
    }

    // If no message found, get all text
    if (!result.message) {
      result.message = shadowRoot.textContent?.slice(0, 2000) || 'Unknown error';
    }

    return result;
  }

  function reportViteError(errorMessage) {
    // Deduplicate: don't report same error twice in quick succession
    if (errorMessage === lastReportedError) return;
    lastReportedError = errorMessage;

    // Clear after 5 seconds to allow re-reporting if error persists
    clearTimeout(errorReportTimeout);
    errorReportTimeout = setTimeout(() => {
      lastReportedError = '';
    }, 5000);

    console.log('[Nexting Bridge] Vite error detected:', errorMessage.slice(0, 100) + '...');

    // Send to parent window
    window.parent.postMessage({
      type: 'vite-error',
      id: 'vite-error-' + Date.now(),
      data: {
        message: errorMessage,
        timestamp: Date.now(),
        source: 'vite-overlay'
      }
    }, '*');
  }

  function checkForViteErrorOverlay() {
    // ==========================================
    // Strategy 1: Check for vite-error-overlay custom element (Vite 4.x & 5.x)
    // ==========================================
    const viteOverlay = document.querySelector('vite-error-overlay');
    if (viteOverlay) {
      const errorMessage = extractViteErrorMessage(viteOverlay);
      if (errorMessage && errorMessage !== 'Unknown Vite error') {
        reportViteError(errorMessage);
        return true;
      }
    }

    // ==========================================
    // Strategy 2: Check for Vite 5.x dialog-based overlay
    // ==========================================
    // Vite 5.x may use a <dialog> element or fixed-position overlay
    const dialogs = document.querySelectorAll('dialog[open], [role="dialog"], [aria-modal="true"]');
    for (const dialog of dialogs) {
      const text = dialog.textContent?.trim() || '';
      // Check if it contains error-like content
      if (text.length > 20 && (
        text.includes('error') ||
        text.includes('Error') ||
        text.includes('failed') ||
        text.includes('Failed') ||
        text.includes('[plugin:')
      )) {
        reportViteError(text.slice(0, 3000));
        return true;
      }
    }

    // ==========================================
    // Strategy 3: Check for fixed-position error overlays
    // ==========================================
    // Many bundlers show errors in fixed/absolute positioned overlays
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const style = window.getComputedStyle(el);
      const isOverlay = (style.position === 'fixed' || style.position === 'absolute') &&
                        parseInt(style.zIndex) > 1000;
      if (isOverlay) {
        const text = el.textContent?.trim() || '';
        const bgColor = style.backgroundColor;
        const isErrorBg = bgColor && (
          bgColor.includes('rgb(255') ||   // Red variants
          bgColor.includes('rgba(255') ||
          bgColor.includes('rgb(200') ||
          bgColor.includes('rgb(220') ||
          bgColor.includes('rgb(239') ||   // Tailwind red-500
          bgColor.includes('rgb(248') ||   // Light red
          bgColor.includes('rgb(254')      // Very light red
        );

        // Check if it looks like an error overlay
        if ((isErrorBg || el.className.toLowerCase().includes('error') || el.id.toLowerCase().includes('error')) &&
            text.length > 20 && text.length < 10000) {
          reportViteError(text.slice(0, 3000));
          return true;
        }
      }
    }

    // ==========================================
    // Strategy 4: Check for data attributes and common class patterns
    // ==========================================
    const errorOverlaySelectors = [
      '[data-vite-error]',
      '.vite-error-overlay',
      '[class*="vite-error"]',
      '[class*="error-overlay"]',
      '[class*="ErrorOverlay"]',
      '#vite-error-overlay',
      '.error-overlay',
      '.runtime-error'
    ];

    for (const selector of errorOverlaySelectors) {
      try {
        const overlay = document.querySelector(selector);
        if (overlay) {
          const text = overlay.textContent?.trim();
          if (text && text.length > 20) {
            reportViteError(text.slice(0, 3000));
            return true;
          }
        }
      } catch (e) {
        // Invalid selector, skip
      }
    }

    // ==========================================
    // Strategy 5: Check for React error boundaries
    // ==========================================
    const reactErrorBoundary = document.querySelector('[data-react-error-boundary]') ||
                                document.querySelector('.react-error-overlay') ||
                                document.querySelector('[class*="react-error"]');
    if (reactErrorBoundary) {
      const errorMessage = reactErrorBoundary.textContent?.slice(0, 2000) || 'React Error';
      reportViteError(errorMessage);
      return true;
    }

    // ==========================================
    // Strategy 6: Check for plugin errors in body text
    // ==========================================
    const bodyText = document.body?.textContent || '';
    const pluginErrorMatch = bodyText.match(/\\[plugin:([^\\]]+)\\]/);
    if (pluginErrorMatch) {
      const preElements = document.querySelectorAll('pre');
      let errorMessage = '';
      preElements.forEach(pre => {
        errorMessage += (pre.textContent || '') + '\\n';
      });
      if (!errorMessage.trim()) {
        errorMessage = bodyText.slice(0, 3000);
      }
      reportViteError(errorMessage.trim());
      return true;
    }

    // ==========================================
    // Strategy 7: Check body background and error keywords
    // ==========================================
    const body = document.body;
    if (body) {
      const bodyStyle = window.getComputedStyle(body);
      const bgColor = bodyStyle.backgroundColor;
      const isRedBg = bgColor && (
        bgColor.includes('rgb(255') ||
        bgColor.includes('rgba(255') ||
        bgColor.includes('rgb(200') ||
        bgColor.includes('rgb(220') ||
        bgColor.includes('rgb(239')
      );

      const hasErrorKeywords = body.innerHTML.includes('SyntaxError') ||
                               body.innerHTML.includes('Unexpected token') ||
                               body.innerHTML.includes('TypeError') ||
                               body.innerHTML.includes('ReferenceError') ||
                               body.innerHTML.includes('Cannot read properties') ||
                               body.innerHTML.includes('is not defined') ||
                               body.innerHTML.includes('Failed to resolve import') ||
                               body.innerHTML.includes('[vite]') ||
                               body.innerHTML.includes('[plugin:');

      if (isRedBg || hasErrorKeywords) {
        const errorText = body.textContent?.trim();
        if (errorText && errorText.length > 20 && errorText.length < 10000) {
          reportViteError(errorText.slice(0, 3000));
          return true;
        }
      }
    }

    // ==========================================
    // Strategy 8: Check <pre> elements for stack traces
    // ==========================================
    const preElements = document.querySelectorAll('pre');
    for (const pre of preElements) {
      const text = pre.textContent?.trim() || '';
      if (text.length > 50 && (
        text.includes('at ') ||           // Stack trace
        text.includes('Error:') ||
        text.includes('error:') ||
        text.includes('SyntaxError') ||
        text.includes('TypeError') ||
        text.includes('[plugin:')
      )) {
        reportViteError(text.slice(0, 3000));
        return true;
      }
    }

    return false;
  }

  // Watch for Vite error overlay appearing
  const viteErrorObserver = new MutationObserver((mutations) => {
    // Debounce to avoid multiple rapid detections
    clearTimeout(viteErrorObserver._debounce);
    viteErrorObserver._debounce = setTimeout(() => {
      checkForViteErrorOverlay();
    }, 100);
  });

  viteErrorObserver.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  // Also check on initial load
  setTimeout(checkForViteErrorOverlay, 500);

  // ============================================
  // White Screen Detection
  // ============================================
  // Detects when page loads but renders nothing visible
  // This catches silent errors that don't show error overlays

  let whiteScreenReported = false;
  let whiteScreenCheckCount = 0;
  const MAX_WHITE_SCREEN_CHECKS = 3;

  function checkForWhiteScreen() {
    // Don't report more than once
    if (whiteScreenReported) return false;

    // Only check after document is fully loaded
    if (document.readyState !== 'complete') return false;

    const body = document.body;
    const root = document.getElementById('root') || document.getElementById('app');

    // Check if there's an error overlay - if so, that's not a white screen
    if (document.querySelector('vite-error-overlay') ||
        document.querySelector('[data-vite-error]') ||
        document.querySelector('.vite-error-overlay')) {
      return false;
    }

    // Check for common loading states - don't report as white screen
    const hasLoadingIndicator = document.querySelector('.loading, [data-loading], .spinner, [role="progressbar"]');
    if (hasLoadingIndicator) return false;

    // Check if root element exists and has content
    if (root) {
      const hasChildren = root.children.length > 0;
      const hasText = (root.textContent?.trim().length || 0) > 10;
      const hasVisibleContent = root.innerHTML.length > 50;

      // Root exists but is effectively empty
      if (!hasChildren && !hasText && !hasVisibleContent) {
        whiteScreenCheckCount++;

        // Only report after multiple checks to avoid false positives during initial render
        if (whiteScreenCheckCount >= MAX_WHITE_SCREEN_CHECKS) {
          whiteScreenReported = true;
          const message = 'WHITE_SCREEN: Page loaded but root element is empty. No visible content rendered. ' +
                          'This usually indicates: 1) Error in component lifecycle, 2) React/Vue failed to mount, ' +
                          '3) Entry point not rendering to DOM correctly.';
          reportViteError(message);
          return true;
        }
      }
    } else {
      // No root element at all after page load
      const bodyHasContent = (body?.children.length || 0) > 1; // > 1 to exclude script tags
      const bodyHasText = (body?.textContent?.trim().length || 0) > 20;

      if (!bodyHasContent && !bodyHasText) {
        whiteScreenCheckCount++;

        if (whiteScreenCheckCount >= MAX_WHITE_SCREEN_CHECKS) {
          whiteScreenReported = true;
          const message = 'WHITE_SCREEN: Page loaded but no content found. Neither #root nor #app element exists. ' +
                          'Check if ReactDOM.createRoot() or Vue.mount() is being called correctly.';
          reportViteError(message);
          return true;
        }
      }
    }

    return false;
  }

  // Check for white screen after page fully loads
  // Use multiple delayed checks to avoid false positives
  window.addEventListener('load', () => {
    setTimeout(checkForWhiteScreen, 2000);  // First check at 2s
    setTimeout(checkForWhiteScreen, 4000);  // Second check at 4s
    setTimeout(checkForWhiteScreen, 6000);  // Third check at 6s
  });

  // Also check after DOMContentLoaded with longer delay
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkForWhiteScreen, 3000);
  });

  // Listen for Vite HMR error events
  if (import.meta?.hot) {
    import.meta.hot.on('vite:error', (data) => {
      console.log('[Nexting Bridge] Vite HMR error event:', data);
      const errorMessage = data?.err?.message || data?.message || JSON.stringify(data);
      reportViteError(errorMessage);
    });
  }

  // ============================================
  // Console Error Storage for get-build-errors
  // ============================================
  // Store console errors for later retrieval by Agent
  window.__nextingConsoleErrors = window.__nextingConsoleErrors || [];
  const MAX_STORED_ERRORS = 20;

  // Also intercept console.error for build errors that log there
  const originalConsoleError = console.error;
  console.error = function(...args) {
    originalConsoleError.apply(console, args);

    // Store error for get-build-errors retrieval
    const errorStr = args.map(a => {
      if (a instanceof Error) return a.message + (a.stack ? '\\n' + a.stack : '');
      if (typeof a === 'object') {
        try { return JSON.stringify(a); } catch { return String(a); }
      }
      return String(a);
    }).join(' ');

    // Only store meaningful errors (filter noise)
    if (errorStr.length > 5 && !errorStr.includes('[HMR]') && !errorStr.includes('[vite] connected')) {
      window.__nextingConsoleErrors.push({
        message: errorStr.slice(0, 1000),
        timestamp: Date.now()
      });
      // Keep only recent errors
      if (window.__nextingConsoleErrors.length > MAX_STORED_ERRORS) {
        window.__nextingConsoleErrors = window.__nextingConsoleErrors.slice(-MAX_STORED_ERRORS);
      }
    }

    // Check if this looks like a Vite/build error
    if (errorStr.includes('[vite]') ||
        errorStr.includes('[plugin:') ||
        errorStr.includes('postcss') ||
        errorStr.includes('Failed to fetch dynamically imported module')) {
      reportViteError(errorStr.slice(0, 2000));
    }
  };

  // Clear errors on successful HMR update
  if (import.meta?.hot) {
    import.meta.hot.on('vite:afterUpdate', () => {
      // Clear stored errors after successful update
      window.__nextingConsoleErrors = [];
      console.log('[Nexting Bridge] HMR success, cleared stored errors');
    });
  }

  // ============================================
  // Preview Mode Banner
  // ============================================
  // Shows a dismissible banner indicating this is preview mode

  function showPreviewBanner() {
    // Don't show if already exists
    if (document.getElementById('nexting-preview-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'nexting-preview-banner';
    banner.innerHTML = \`
      <div style="
        position: fixed;
        bottom: 16px;
        right: 16px;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 10px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 13px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        z-index: 99999;
        max-width: 280px;
        backdrop-filter: blur(8px);
        animation: slideIn 0.3s ease-out;
      ">
        <style>
          @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
          }
        </style>
        <div style="display: flex; align-items: flex-start; gap: 10px;">
          <span style="font-size: 18px;">👁️</span>
          <div style="flex: 1;">
            <div style="font-weight: 600; margin-bottom: 4px;">Preview Mode</div>
            <div style="opacity: 0.9; line-height: 1.4; font-size: 12px;">
              Some external images show placeholders due to browser restrictions.
              Deploy to production to see all real images.
            </div>
          </div>
          <button onclick="this.closest('#nexting-preview-banner').remove()" style="
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
          ">✕</button>
        </div>
      </div>
    \`;
    document.body.appendChild(banner);

    // Auto-hide after 8 seconds
    setTimeout(() => {
      const el = document.getElementById('nexting-preview-banner');
      if (el) {
        el.style.transition = 'opacity 0.3s, transform 0.3s';
        el.style.opacity = '0';
        el.style.transform = 'translateX(100%)';
        setTimeout(() => el.remove(), 300);
      }
    }, 8000);
  }

  // Show banner after a short delay (let page render first)
  setTimeout(showPreviewBanner, 1500);

  /**
   * Extract simplified DOM structure
   * @param {Element} element - Root element to extract
   * @param {number} maxDepth - Maximum depth to traverse
   * @param {number} currentDepth - Current depth level
   * @returns {object} Simplified DOM tree
   */
  function extractDOM(element, maxDepth = 5, currentDepth = 0) {
    if (!element || currentDepth > maxDepth) {
      return null;
    }

    const tagName = element.tagName?.toLowerCase() || 'unknown';

    // Skip script and style tags
    if (tagName === 'script' || tagName === 'style' || tagName === 'noscript') {
      return null;
    }

    // Get relevant attributes
    const attrs = {};
    const relevantAttrs = ['id', 'class', 'href', 'src', 'alt', 'title', 'type', 'name', 'placeholder', 'value'];
    for (const attr of relevantAttrs) {
      const val = element.getAttribute?.(attr);
      if (val) {
        attrs[attr] = val.length > 100 ? val.substring(0, 100) + '...' : val;
      }
    }

    // Get text content (only direct text, not from children)
    let text = '';
    for (const node of element.childNodes || []) {
      if (node.nodeType === Node.TEXT_NODE) {
        const trimmed = node.textContent?.trim();
        if (trimmed) {
          text += (text ? ' ' : '') + trimmed;
        }
      }
    }
    if (text.length > 200) {
      text = text.substring(0, 200) + '...';
    }

    // Get computed styles for visibility check
    const styles = window.getComputedStyle?.(element);
    const isHidden = styles?.display === 'none' || styles?.visibility === 'hidden';

    // Get bounding rect for position info
    const rect = element.getBoundingClientRect?.();
    const bounds = rect ? {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height)
    } : null;

    // Process children
    const children = [];
    for (const child of element.children || []) {
      const childNode = extractDOM(child, maxDepth, currentDepth + 1);
      if (childNode) {
        children.push(childNode);
      }
    }

    return {
      tag: tagName,
      attrs: Object.keys(attrs).length > 0 ? attrs : undefined,
      text: text || undefined,
      hidden: isHidden || undefined,
      bounds: bounds,
      children: children.length > 0 ? children : undefined
    };
  }

  /**
   * Convert DOM tree to readable text format
   * @param {object} node - DOM tree node
   * @param {number} indent - Current indentation level
   * @returns {string} Text representation
   */
  function domToText(node, indent = 0) {
    if (!node) return '';

    const prefix = '  '.repeat(indent);
    let result = prefix + '<' + node.tag;

    // Add key attributes
    if (node.attrs) {
      if (node.attrs.id) result += ' id="' + node.attrs.id + '"';
      if (node.attrs.class) result += ' class="' + node.attrs.class + '"';
    }

    result += '>';

    // Add text content
    if (node.text) {
      result += ' "' + node.text + '"';
    }

    // Add bounds info for positioning
    if (node.bounds && node.bounds.width > 0 && node.bounds.height > 0) {
      result += ' [' + node.bounds.width + 'x' + node.bounds.height + ' @' + node.bounds.x + ',' + node.bounds.y + ']';
    }

    // Mark hidden elements
    if (node.hidden) {
      result += ' (hidden)';
    }

    result += '\\n';

    // Process children
    if (node.children) {
      for (const child of node.children) {
        result += domToText(child, indent + 1);
      }
    }

    return result;
  }

  /**
   * Get page visual summary
   * @returns {object} Visual summary information
   */
  function getVisualSummary() {
    const body = document.body;
    const bodyRect = body.getBoundingClientRect();
    const bodyStyles = window.getComputedStyle(body);

    // Count visible elements
    const allElements = document.querySelectorAll('*');
    let visibleCount = 0;
    let textContent = '';

    for (const el of allElements) {
      const rect = el.getBoundingClientRect();
      const styles = window.getComputedStyle(el);

      if (rect.width > 0 && rect.height > 0 &&
          styles.display !== 'none' && styles.visibility !== 'hidden') {
        visibleCount++;

        // Collect visible text
        if (el.childNodes.length > 0) {
          for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
              const text = node.textContent?.trim();
              if (text && text.length > 2) {
                textContent += text + ' ';
              }
            }
          }
        }
      }
    }

    // Truncate text content
    if (textContent.length > 1000) {
      textContent = textContent.substring(0, 1000) + '...';
    }

    return {
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      bodySize: {
        width: Math.round(bodyRect.width),
        height: Math.round(bodyRect.height),
        scrollHeight: body.scrollHeight
      },
      backgroundColor: bodyStyles.backgroundColor,
      visibleElementCount: visibleCount,
      hasContent: visibleCount > 5 || textContent.length > 50,
      textPreview: textContent.trim(),
      title: document.title,
      url: window.location.href
    };
  }

  /**
   * Take screenshot using multiple strategies (no external dependency required)
   * Strategy 1: SVG foreignObject (built-in, fast)
   * Strategy 2: html2canvas (if CDN loaded)
   * Strategy 3: Visual summary fallback
   * @param {string} selector - Optional CSS selector to screenshot
   * @param {boolean} fullPage - Whether to capture full scrollable page
   * @returns {Promise<Object>} Screenshot result
   */
  async function takeScreenshot(selector, fullPage) {
    console.log('[Nexting Bridge] takeScreenshot called:', { selector, fullPage });

    const element = selector ? document.querySelector(selector) : document.body;
    if (!element) {
      return { error: 'Element not found: ' + selector };
    }

    // ============================================
    // Strategy 1: SVG foreignObject (built-in, fast)
    // ============================================
    try {
      console.log('[Nexting Bridge] Trying SVG capture...');
      const svgResult = await captureWithSVG(element, fullPage);
      if (svgResult) {
        console.log('[Nexting Bridge] SVG capture succeeded');
        return { data: svgResult };
      }
    } catch (err) {
      console.log('[Nexting Bridge] SVG capture failed:', err.message);
    }

    // ============================================
    // Strategy 2: html2canvas (if available)
    // ============================================
    try {
      const loaded = await loadHtml2Canvas();
      if (loaded && typeof html2canvas !== 'undefined') {
        console.log('[Nexting Bridge] Taking screenshot with html2canvas...');
        const canvas = await html2canvas(element, {
          useCORS: true,
          allowTaint: true,
          backgroundColor: '#ffffff',
          logging: false,
          timeout: 10000  // 10 second timeout for rendering
        });
        console.log('[Nexting Bridge] html2canvas screenshot captured');
        return { data: canvas.toDataURL('image/png') };
      }
    } catch (err) {
      console.log('[Nexting Bridge] html2canvas failed:', err.message);
    }

    // ============================================
    // Strategy 3: Visual summary fallback
    // ============================================
    console.log('[Nexting Bridge] All screenshot methods failed, returning visual summary');
    return {
      error: 'Screenshot capture failed. Providing visual summary instead.',
      fallback: getVisualSummary()
    };
  }

  /**
   * Capture screenshot using SVG foreignObject approach
   * Works without external libraries
   * @param {Element} element - Element to capture
   * @param {boolean} fullPage - Whether to capture full page
   * @returns {Promise<string|null>} Base64 image or null
   */
  async function captureWithSVG(element, fullPage) {
    return new Promise((resolve) => {
      try {
        const rect = element.getBoundingClientRect();
        const width = fullPage ? document.body.scrollWidth : Math.min(rect.width || 800, 1920);
        const height = fullPage ? Math.min(document.body.scrollHeight, 4000) : Math.min(rect.height || 600, 2000);

        if (width <= 0 || height <= 0) {
          resolve(null);
          return;
        }

        // Clone and inline styles
        const clonedElement = element.cloneNode(true);
        inlineAllStyles(element, clonedElement);

        // Create SVG with foreignObject
        const svgData = \`<svg xmlns="http://www.w3.org/2000/svg" width="\${width}" height="\${height}">
          <foreignObject width="100%" height="100%">
            <div xmlns="http://www.w3.org/1999/xhtml" style="width:\${width}px;height:\${height}px;overflow:hidden;background:#fff;">
              \${clonedElement.outerHTML}
            </div>
          </foreignObject>
        </svg>\`;

        const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
        const svgUrl = URL.createObjectURL(svgBlob);

        const img = new Image();
        let resolved = false;

        img.onload = () => {
          if (resolved) return;
          resolved = true;
          try {
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            if (ctx) {
              ctx.fillStyle = '#ffffff';
              ctx.fillRect(0, 0, width, height);
              ctx.drawImage(img, 0, 0);
              URL.revokeObjectURL(svgUrl);
              resolve(canvas.toDataURL('image/png'));
            } else {
              URL.revokeObjectURL(svgUrl);
              resolve(null);
            }
          } catch (e) {
            URL.revokeObjectURL(svgUrl);
            resolve(null);
          }
        };

        img.onerror = () => {
          if (resolved) return;
          resolved = true;
          URL.revokeObjectURL(svgUrl);
          resolve(null);
        };

        // 5 second timeout for SVG rendering
        setTimeout(() => {
          if (!resolved) {
            resolved = true;
            URL.revokeObjectURL(svgUrl);
            resolve(null);
          }
        }, 5000);

        img.src = svgUrl;
      } catch (e) {
        console.log('[Nexting Bridge] captureWithSVG error:', e);
        resolve(null);
      }
    });
  }

  /**
   * Inline computed styles from source to target element
   * @param {Element} source - Source element
   * @param {Element} target - Target element (clone)
   */
  function inlineAllStyles(source, target) {
    try {
      const computedStyle = window.getComputedStyle(source);
      if (target.style) {
        // Copy key styles that affect rendering
        const importantStyles = [
          'font-family', 'font-size', 'font-weight', 'font-style', 'color',
          'background-color', 'background-image', 'background',
          'border', 'border-radius', 'padding', 'margin',
          'display', 'flex-direction', 'justify-content', 'align-items', 'gap',
          'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
          'position', 'top', 'left', 'right', 'bottom',
          'transform', 'opacity', 'box-shadow',
          'text-align', 'line-height', 'letter-spacing', 'text-decoration',
          'overflow', 'white-space', 'word-break', 'text-overflow'
        ];
        for (const prop of importantStyles) {
          try {
            const value = computedStyle.getPropertyValue(prop);
            if (value) target.style.setProperty(prop, value);
          } catch { /* ignore */ }
        }
      }
      // Recursively process children
      const sourceChildren = source.children;
      const targetChildren = target.children;
      for (let i = 0; i < sourceChildren.length && i < targetChildren.length; i++) {
        inlineAllStyles(sourceChildren[i], targetChildren[i]);
      }
    } catch { /* ignore styling errors */ }
  }

  /**
   * Handle incoming messages from parent window
   */
  window.addEventListener('message', async function(event) {
    const { type, id, selector, depth, fullPage } = event.data || {};

    if (!type || !id) return;

    console.log('[Nexting Bridge] Received:', type, id, { selector, fullPage });

    try {
      switch (type) {
        case 'get-dom': {
          // Extract DOM structure
          const targetElement = selector ? document.querySelector(selector) : document.body;

          if (!targetElement) {
            window.parent.postMessage({
              type: 'dom-result',
              id: id,
              error: 'Element not found: ' + selector
            }, '*');
            return;
          }

          const domTree = extractDOM(targetElement, depth || 5);
          const textRepresentation = domToText(domTree);
          const summary = getVisualSummary();

          window.parent.postMessage({
            type: 'dom-result',
            id: id,
            data: JSON.stringify({
              success: true,
              summary: summary,
              dom: textRepresentation,
              elementCount: summary.visibleElementCount
            }, null, 2)
          }, '*');
          break;
        }

        case 'take-screenshot': {
          const result = await takeScreenshot(selector, fullPage);

          if (result.error) {
            // Return visual summary as fallback
            window.parent.postMessage({
              type: 'screenshot-result',
              id: id,
              data: JSON.stringify({
                success: false,
                error: result.error,
                visualSummary: result.fallback || getVisualSummary()
              }, null, 2)
            }, '*');
          } else {
            window.parent.postMessage({
              type: 'screenshot-result',
              id: id,
              data: result.data
            }, '*');
          }
          break;
        }

        case 'get-visual-summary': {
          const summary = getVisualSummary();
          window.parent.postMessage({
            type: 'visual-summary-result',
            id: id,
            data: JSON.stringify({
              success: true,
              ...summary
            }, null, 2)
          }, '*');
          break;
        }

        case 'get-build-errors': {
          // Actively check for build/compilation errors using multiple strategies
          const errors = [];
          const processedMessages = new Set(); // Deduplicate errors

          function addError(errorObj) {
            const key = (errorObj.message || '').slice(0, 100);
            if (!processedMessages.has(key)) {
              processedMessages.add(key);
              errors.push(errorObj);
            }
          }

          // ==========================================
          // Strategy 1: Check for vite-error-overlay custom element (Vite 4.x & 5.x)
          // ==========================================
          const viteOverlay = document.querySelector('vite-error-overlay');
          if (viteOverlay) {
            // Use extractStructuredViteError for detailed info
            const structured = extractStructuredViteError(viteOverlay);
            if (structured.message && structured.message !== 'Unknown error') {
              addError({
                type: 'vite-overlay',
                message: structured.message,
                file: structured.file,
                line: structured.line,
                column: structured.column,
                frame: structured.frame,
                stack: structured.stack,
                plugin: structured.plugin,
                timestamp: Date.now()
              });
            }
          }

          // ==========================================
          // Strategy 2: Check for Vite 5.x dialog-based overlay
          // ==========================================
          const dialogs = document.querySelectorAll('dialog[open], [role="dialog"], [aria-modal="true"]');
          for (const dialog of dialogs) {
            const text = dialog.textContent?.trim() || '';
            if (text.length > 20 && (
              text.includes('error') || text.includes('Error') ||
              text.includes('failed') || text.includes('Failed') ||
              text.includes('[plugin:')
            )) {
              addError({
                type: 'dialog-error',
                message: text.slice(0, 3000),
                timestamp: Date.now()
              });
            }
          }

          // ==========================================
          // Strategy 3: Check for fixed-position error overlays
          // ==========================================
          const allElements = document.querySelectorAll('*');
          for (const el of allElements) {
            const style = window.getComputedStyle(el);
            const isOverlay = (style.position === 'fixed' || style.position === 'absolute') &&
                              parseInt(style.zIndex) > 1000;
            if (isOverlay) {
              const text = el.textContent?.trim() || '';
              const bgColor = style.backgroundColor;
              const isErrorBg = bgColor && (
                bgColor.includes('rgb(255') || bgColor.includes('rgba(255') ||
                bgColor.includes('rgb(200') || bgColor.includes('rgb(220') ||
                bgColor.includes('rgb(239') || bgColor.includes('rgb(248') ||
                bgColor.includes('rgb(254')
              );

              const className = (el.className || '').toString().toLowerCase();
              const elId = (el.id || '').toLowerCase();

              if ((isErrorBg || className.includes('error') || elId.includes('error')) &&
                  text.length > 20 && text.length < 10000) {
                addError({
                  type: 'overlay-error',
                  message: text.slice(0, 3000),
                  timestamp: Date.now()
                });
                break; // Found one, stop
              }
            }
          }

          // ==========================================
          // Strategy 4: Check for data attributes and common class patterns
          // ==========================================
          const errorOverlaySelectors = [
            '[data-vite-error]',
            '.vite-error-overlay',
            '[class*="vite-error"]',
            '[class*="error-overlay"]',
            '[class*="ErrorOverlay"]',
            '#vite-error-overlay',
            '.error-overlay',
            '.runtime-error'
          ];

          for (const selector of errorOverlaySelectors) {
            try {
              const overlays = document.querySelectorAll(selector);
              overlays.forEach(overlay => {
                const text = overlay.textContent?.trim();
                if (text && text.length > 20) {
                  addError({
                    type: 'error-overlay',
                    message: text.slice(0, 2000),
                    timestamp: Date.now()
                  });
                }
              });
            } catch (e) {
              // Invalid selector, skip
            }
          }

          // ==========================================
          // Strategy 5: Check for React error boundaries
          // ==========================================
          const reactErrorSelectors = [
            '[data-react-error-boundary]',
            '.react-error-overlay',
            '[class*="react-error"]',
            '#react-error-overlay'
          ];

          for (const selector of reactErrorSelectors) {
            try {
              const boundary = document.querySelector(selector);
              if (boundary) {
                addError({
                  type: 'react-error-boundary',
                  message: boundary.textContent?.trim()?.slice(0, 2000) || 'React Error',
                  timestamp: Date.now()
                });
              }
            } catch (e) {}
          }

          // ==========================================
          // Strategy 6: Check for plugin errors in body text
          // ==========================================
          if (errors.length === 0) {
            const bodyText = document.body?.textContent || '';
            const pluginErrorMatch = bodyText.match(/\\[plugin:([^\\]]+)\\]/);
            if (pluginErrorMatch) {
              const preElements = document.querySelectorAll('pre');
              let errorMessage = '';
              preElements.forEach(pre => {
                errorMessage += (pre.textContent || '') + '\\n';
              });
              if (!errorMessage.trim()) {
                errorMessage = bodyText.slice(0, 3000);
              }
              addError({
                type: 'vite-plugin-error',
                plugin: pluginErrorMatch[1],
                message: errorMessage.trim().slice(0, 3000),
                timestamp: Date.now()
              });
            }
          }

          // ==========================================
          // Strategy 7: Check body background and error keywords
          // ==========================================
          if (errors.length === 0) {
            const body = document.body;
            if (body) {
              const bodyStyle = window.getComputedStyle(body);
              const bgColor = bodyStyle.backgroundColor;
              const isRedBg = bgColor && (
                bgColor.includes('rgb(255') || bgColor.includes('rgba(255') ||
                bgColor.includes('rgb(200') || bgColor.includes('rgb(220') ||
                bgColor.includes('rgb(239')
              );

              const hasErrorKeywords = body.innerHTML.includes('SyntaxError') ||
                body.innerHTML.includes('Unexpected token') ||
                body.innerHTML.includes('TypeError') ||
                body.innerHTML.includes('ReferenceError') ||
                body.innerHTML.includes('Cannot read properties') ||
                body.innerHTML.includes('is not defined') ||
                body.innerHTML.includes('Failed to resolve import') ||
                body.innerHTML.includes('[vite]') ||
                body.innerHTML.includes('[plugin:');

              if (isRedBg || hasErrorKeywords) {
                const errorText = body.textContent?.trim();
                if (errorText && errorText.length > 20 && errorText.length < 10000) {
                  addError({
                    type: 'page-error',
                    message: errorText.slice(0, 3000),
                    timestamp: Date.now()
                  });
                }
              }
            }
          }

          // ==========================================
          // Strategy 8: Check <pre> elements for stack traces
          // ==========================================
          if (errors.length === 0) {
            const preElements = document.querySelectorAll('pre');
            for (const pre of preElements) {
              const text = pre.textContent?.trim() || '';
              if (text.length > 50 && (
                text.includes('at ') ||
                text.includes('Error:') ||
                text.includes('error:') ||
                text.includes('SyntaxError') ||
                text.includes('TypeError') ||
                text.includes('[plugin:')
              )) {
                addError({
                  type: 'pre-error',
                  message: text.slice(0, 3000),
                  timestamp: Date.now()
                });
                break;
              }
            }
          }

          // ==========================================
          // Strategy 9: Check console for recent errors
          // ==========================================
          if (window.__nextingConsoleErrors && window.__nextingConsoleErrors.length > 0) {
            const recentErrors = window.__nextingConsoleErrors.filter(
              e => Date.now() - e.timestamp < 30000 // Last 30 seconds
            );
            recentErrors.forEach(e => {
              addError({
                type: 'console-error',
                message: e.message?.slice(0, 1000),
                timestamp: e.timestamp
              });
            });
          }

          window.parent.postMessage({
            type: 'build-errors-result',
            id: id,
            data: JSON.stringify({
              success: true,
              hasErrors: errors.length > 0,
              errorCount: errors.length,
              errors: errors,
              timestamp: Date.now()
            }, null, 2)
          }, '*');
          break;
        }

        case 'ping': {
          window.parent.postMessage({
            type: 'pong',
            id: id,
            data: { ready: true, timestamp: Date.now() }
          }, '*');
          break;
        }

        default:
          console.log('[Nexting Bridge] Unknown message type:', type);
      }
    } catch (err) {
      console.error('[Nexting Bridge] Error handling message:', err);
      window.parent.postMessage({
        type: type + '-result',
        id: id,
        error: err.message
      }, '*');
    }
  });

  // Notify parent that bridge is ready
  window.parent.postMessage({
    type: 'nexting-bridge-ready',
    id: 'init',
    data: { ready: true, timestamp: Date.now() }
  }, '*');

  console.log('[Nexting Bridge] Ready');
})();
`,
  "/src/main.jsx": `import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
`,
  "/src/App.jsx": `import React from 'react';

function App() {
  return (
    <div className="app">
      <h1>Welcome to Nexting Agent</h1>
      <p>Start by asking the AI to create something!</p>
    </div>
  );
}

export default App;
`,
  "/src/index.css": `/* Tailwind CSS */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* CSS Variables for custom theme colors */
:root {
  --color-brand: #f26625;
  --color-link: #0066cc;
  --max-width-page: 1200px;
}

/* Base styles */
* {
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  min-height: 100vh;
  margin: 0;
  padding: 0;
}

/* Default app container (will be replaced by Agent) */
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
  text-align: center;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.app h1 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.app p {
  font-size: 1.2rem;
  opacity: 0.9;
}
`,
};

// ============================================
// Helper Functions
// ============================================

/**
 * Generate a unique terminal ID
 */
function generateTerminalId(): string {
  return `term-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a unique console message ID
 */
function generateConsoleMessageId(): string {
  return `console-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Clean ANSI escape codes from terminal output
 */
function cleanAnsiCodes(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
}

// ============================================
// useWebContainer Hook
// ============================================

export function useWebContainer(options: UseWebContainerOptions = {}) {
  const { onPreviewError, onHealthChange, onAgentLog, onFileWritten } = options;

  // Store callbacks in refs to avoid dependency issues
  const onPreviewErrorRef = useRef(onPreviewError);
  const onHealthChangeRef = useRef(onHealthChange);
  const onAgentLogRef = useRef(onAgentLog);
  const onFileWrittenRef = useRef(onFileWritten);
  useEffect(() => {
    onPreviewErrorRef.current = onPreviewError;
    onHealthChangeRef.current = onHealthChange;
    onAgentLogRef.current = onAgentLog;
    onFileWrittenRef.current = onFileWritten;
  }, [onPreviewError, onHealthChange, onAgentLog, onFileWritten]);

  // Helper function to log Agent actions
  const logAgent = useCallback((type: AgentLogEntry["type"], content: string) => {
    if (onAgentLogRef.current) {
      onAgentLogRef.current({
        type,
        content,
        timestamp: Date.now(),
      });
    }
  }, []);

  // State version ref (for tracking file changes)
  const stateVersionRef = useRef(0);

  // State
  const [state, setState] = useState<WebContainerState>({
    status: "idle",
    files: DEFAULT_FILES,
    activeFile: "/src/App.jsx",
    terminals: [],
    activeTerminalId: null,
    previewUrl: null,
    preview: {
      url: null,
      isLoading: false,
      hasError: false,
      consoleMessages: [],
      viewport: { width: 1280, height: 720 },
    },
    error: null,
    fileDiffs: {}, // Track file diffs made by Agent
    version: 0, // State version for sync tracking
    imageUrlMapping: {}, // Track image URL mappings for export (local path -> original URL)
  });

  // Refs
  const webcontainerRef = useRef<WebContainerInstance | null>(null);
  const bootingRef = useRef(false);
  const processesRef = useRef<Map<string, WebContainerProcess>>(new Map());
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  // Use ref for history to avoid setState race conditions
  const historyBufferRef = useRef<TerminalHistoryBuffer>({});
  // Interactive shell process and writer (for XTerm terminal display)
  const shellProcessRef = useRef<WebContainerProcess | null>(null);
  const shellWriterRef = useRef<WritableStreamDefaultWriter | null>(null);
  // Ref to always get latest state (avoids closure issues in async callbacks)
  const stateRef = useRef(state);
  stateRef.current = state;

  // Background shell ready flag - set when terminal spawns shell
  // This allows other parts of the hook to know if a shell is available
  const backgroundShellReadyRef = useRef(false);

  // ============================================
  // Vite Error Message Listener
  // ============================================
  // Listens for vite-error messages from preview iframe and forwards to Agent
  useEffect(() => {
    /**
     * Parse Vite error message to extract structured information
     */
    const parseViteError = (errorMessage: string) => {
      // Extract plugin name: [plugin:vite:react-babel]
      const pluginMatch = errorMessage.match(/\[plugin:([^\]]+)\]/);
      const plugin = pluginMatch ? pluginMatch[1] : undefined;

      // Extract file path and location: /path/to/file.jsx:168:82
      const fileMatch = errorMessage.match(/([^\s]+\.(jsx?|tsx?|vue|svelte)):(\d+):(\d+)/);
      const file = fileMatch ? fileMatch[1] : undefined;
      const line = fileMatch ? parseInt(fileMatch[3], 10) : undefined;
      const column = fileMatch ? parseInt(fileMatch[4], 10) : undefined;

      // Extract code frame (lines with | separator)
      const frameLines: string[] = [];
      const lines = errorMessage.split('\n');
      for (const l of lines) {
        // Match lines like "166|   <span..." or "   |   ^"
        if (/^\s*\d*\|/.test(l) || /^\s+\|/.test(l)) {
          frameLines.push(l);
        }
      }
      const frame = frameLines.length > 0 ? frameLines.join('\n') : undefined;

      // Extract stack trace (lines starting with "at ")
      const stackLines = lines.filter(l => l.trim().startsWith('at '));
      const stack = stackLines.length > 0 ? stackLines.join('\n') : undefined;

      return { plugin, file, line, column, frame, stack };
    };

    const handleViteError = (event: MessageEvent) => {
      // Only handle vite-error messages from iframes
      if (event.data?.type === "vite-error") {
        const errorData = event.data.data;
        console.log("[WebContainer] Received Vite error from preview:", errorData?.message?.slice(0, 100));

        // Format error message for Agent
        const errorMessage = errorData?.message || "Unknown Vite error";
        const timestamp = errorData?.timestamp || Date.now();

        // Parse error to extract structured info
        const parsed = parseViteError(errorMessage);

        // Store error in state for Agent access
        setState(prev => ({
          ...prev,
          preview: {
            ...prev.preview,
            hasError: true,
            errorMessage: errorMessage.slice(0, 500),
            errorOverlay: {
              message: errorMessage,
              file: parsed.file,
              line: parsed.line,
              column: parsed.column,
              stack: parsed.stack,
              plugin: parsed.plugin,
              frame: parsed.frame,
              timestamp,
            },
          },
        }));

        // Log to terminal
        logAgent("error", `⚠️ Build Error:\n${errorMessage.slice(0, 500)}`);

        // Also forward to onPreviewError callback
        if (onPreviewErrorRef.current) {
          onPreviewErrorRef.current({
            message: errorMessage,
            stack: parsed.stack,
            timestamp,
          });
        }
      }
    };

    window.addEventListener("message", handleViteError);
    return () => {
      window.removeEventListener("message", handleViteError);
    };
  }, [logAgent]);

  // ============================================
  // Core WebContainer Methods
  // ============================================

  /**
   * Boot WebContainer
   */
  const boot = useCallback(async () => {
    // Prevent multiple boot attempts
    if (bootingRef.current || webcontainerRef.current) {
      return;
    }

    bootingRef.current = true;
    setState((prev) => ({ ...prev, status: "booting" }));

    try {
      // Dynamically import WebContainer API
      console.log("[WebContainer] Importing WebContainer API...");
      const { WebContainer } = await import("@webcontainer/api");
      console.log("[WebContainer] API imported, booting...");

      // Boot the container
      const instance = await WebContainer.boot();
      webcontainerRef.current = instance;
      console.log("[WebContainer] Instance created successfully");

      // Convert files to WebContainer format
      const tree: FileSystemTree = {};
      for (const [path, content] of Object.entries(DEFAULT_FILES)) {
        const parts = path.split("/").filter(Boolean);
        let current = tree;

        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          const isLast = i === parts.length - 1;

          if (isLast) {
            current[part] = { file: { contents: content } };
          } else {
            if (!current[part]) {
              current[part] = { directory: {} };
            }
            current = current[part].directory!;
          }
        }
      }

      // Mount files
      await instance.mount(tree as any);

      // Listen for server ready
      instance.on("server-ready", (port: number, url: string) => {
        console.log("[WebContainer] Server ready on port", port, url);
        setState((prev) => ({
          ...prev,
          previewUrl: url,
          preview: {
            ...prev.preview,
            url,
            isLoading: false,
            hasError: false,
          },
        }));
      });

      // Listen for errors
      instance.on("error", (error: Error) => {
        console.error("[WebContainer] Error:", error);
        setState((prev) => ({
          ...prev,
          error: error.message,
          preview: {
            ...prev.preview,
            hasError: true,
            errorMessage: error.message,
          },
        }));
      });

      setState((prev) => ({
        ...prev,
        status: "ready",
        error: null,
      }));

      console.log("[WebContainer] Boot complete, creating /dev/null...");

      // Create /dev/null to prevent ENOENT errors
      // WebContainer doesn't have /dev by default, but some tools expect it
      try {
        await instance.fs.mkdir("/dev", { recursive: true });
        await instance.fs.writeFile("/dev/null", "");
        console.log("[WebContainer] /dev/null created successfully");
      } catch (devNullError) {
        console.warn("[WebContainer] Could not create /dev/null:", devNullError);
        // Non-fatal, continue anyway
      }

      // NOTE: Dev server auto-start is now handled by useEffect below
      // This ensures it runs through the terminal system for unified management
      console.log("[WebContainer] Boot complete, dev server will start via terminal system");
    } catch (error) {
      console.error("[WebContainer] Boot failed:", error);
      setState((prev) => ({
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      }));
    } finally {
      bootingRef.current = false;
    }
  }, []);

  // Auto-boot on mount
  useEffect(() => {
    boot();

    return () => {
      // Cleanup on unmount
      if (webcontainerRef.current) {
        webcontainerRef.current.teardown();
        webcontainerRef.current = null;
      }
      processesRef.current.clear();
    };
  }, [boot]);

  // ============================================
  // File Operations
  // ============================================
  // Note: Image download is now handled by the independent useImageDownloader hook

  /**
   * Write file to WebContainer
   * @param path - File path
   * @param content - File content
   * @param trackDiff - If true, track diff for Agent-made changes (default: false)
   */
  const writeFile = useCallback(async (
    path: string,
    content: string,
    trackDiff: boolean = false
  ) => {
    const instance = webcontainerRef.current;
    if (!instance) {
      throw new Error("WebContainer not ready");
    }

    // Ensure path starts with / and doesn't end with / (directory)
    let normalizedPath = path.startsWith("/") ? path : `/${path}`;
    // Remove trailing slash - paths ending with / are directories
    if (normalizedPath.endsWith("/") && normalizedPath.length > 1) {
      console.warn("[WebContainer] Path ends with /, removing trailing slash:", normalizedPath);
      normalizedPath = normalizedPath.slice(0, -1);
    }

    // Validate path is not empty or just /
    if (!normalizedPath || normalizedPath === "/") {
      throw new Error("Invalid file path: cannot write to root directory");
    }

    // Get old content for diff tracking
    let oldContent = "";
    if (trackDiff) {
      oldContent = state.files[normalizedPath] || "";
    }

    // Create parent directories if needed
    const parts = normalizedPath.split("/").filter(Boolean);
    if (parts.length > 1) {
      const dir = "/" + parts.slice(0, -1).join("/");
      try {
        await instance.fs.mkdir(dir, { recursive: true });
      } catch {
        // Directory might already exist
      }
    }

    // Write the file content directly (no image processing here)
    await instance.fs.writeFile(normalizedPath, content);

    // Increment version for sync tracking
    stateVersionRef.current += 1;
    const newVersion = stateVersionRef.current;

    // Update state
    setState((prev) => {
      const newState: WebContainerState = {
        ...prev,
        files: {
          ...prev.files,
          [normalizedPath]: content,
        },
        version: newVersion,
      };

      // Track diff if requested and content actually changed
      if (trackDiff && oldContent !== content) {
        newState.fileDiffs = {
          ...prev.fileDiffs,
          [normalizedPath]: {
            path: normalizedPath,
            oldContent,
            newContent: content,
            timestamp: Date.now(),
          },
        };
      }

      return newState;
    });

    console.log("[WebContainer] File written:", normalizedPath, `v${newVersion}`,
      trackDiff ? "(with diff tracking)" : "");

    // Notify external image downloader that a file was written
    if (onFileWrittenRef.current) {
      onFileWrittenRef.current(normalizedPath, content);
    }
  }, [state.files]);

  /**
   * Read file from WebContainer
   */
  const readFile = useCallback(async (path: string): Promise<string> => {
    const instance = webcontainerRef.current;
    if (!instance) {
      throw new Error("WebContainer not ready");
    }

    // Normalize path
    let normalizedPath = path.startsWith("/") ? path : `/${path}`;
    // Remove trailing slash - paths ending with / are directories
    if (normalizedPath.endsWith("/") && normalizedPath.length > 1) {
      console.warn("[WebContainer] Read path ends with /, removing trailing slash:", normalizedPath);
      normalizedPath = normalizedPath.slice(0, -1);
    }

    // Validate path
    if (!normalizedPath || normalizedPath === "/") {
      throw new Error("Invalid file path: cannot read root directory as file");
    }

    const content = await instance.fs.readFile(normalizedPath, "utf-8");
    return content as string;
  }, []);

  /**
   * Delete file from WebContainer
   */
  const deleteFile = useCallback(async (path: string) => {
    const instance = webcontainerRef.current;
    if (!instance) {
      throw new Error("WebContainer not ready");
    }

    // Normalize path
    let normalizedPath = path.startsWith("/") ? path : `/${path}`;
    // Remove trailing slash
    if (normalizedPath.endsWith("/") && normalizedPath.length > 1) {
      normalizedPath = normalizedPath.slice(0, -1);
    }

    // Validate path
    if (!normalizedPath || normalizedPath === "/") {
      throw new Error("Invalid file path: cannot delete root directory");
    }

    // Check if path is a directory or file
    try {
      const stat = await instance.fs.stat(normalizedPath);
      const isDirectory = stat.isDirectory();

      // Use recursive option for directories
      await instance.fs.rm(normalizedPath, { recursive: isDirectory });

      // Update state - remove file and all children if directory
      setState((prev) => {
        const newFiles = { ...prev.files };
        if (isDirectory) {
          // Remove all files under this directory
          const prefix = normalizedPath + "/";
          for (const filePath of Object.keys(newFiles)) {
            if (filePath === normalizedPath || filePath.startsWith(prefix)) {
              delete newFiles[filePath];
            }
          }
        } else {
          delete newFiles[normalizedPath];
        }
        return { ...prev, files: newFiles };
      });

      console.log("[WebContainer] Deleted:", normalizedPath, isDirectory ? "(directory)" : "(file)");
    } catch (err) {
      // If stat fails, try to delete anyway with recursive option
      console.warn("[WebContainer] Stat failed, attempting recursive delete:", err);
      await instance.fs.rm(normalizedPath, { recursive: true });

      // Update state
      setState((prev) => {
        const newFiles = { ...prev.files };
        const prefix = normalizedPath + "/";
        for (const filePath of Object.keys(newFiles)) {
          if (filePath === normalizedPath || filePath.startsWith(prefix)) {
            delete newFiles[filePath];
          }
        }
        return { ...prev, files: newFiles };
      });

      console.log("[WebContainer] Deleted (forced recursive):", normalizedPath);
    }
  }, []);

  /**
   * Edit file (search and replace)
   * @param path - File path
   * @param oldText - Text to search for
   * @param newText - Text to replace with
   * @param replaceAll - Replace all occurrences (default: false)
   * @param trackDiff - If true, track diff for Agent-made changes (default: false)
   */
  const editFile = useCallback(
    async (
      path: string,
      oldText: string,
      newText: string,
      replaceAll: boolean = false,
      trackDiff: boolean = false
    ) => {
      const instance = webcontainerRef.current;
      if (!instance) {
        throw new Error("WebContainer not ready");
      }

      // Normalize path
      let normalizedPath = path.startsWith("/") ? path : `/${path}`;
      // Remove trailing slash - paths ending with / are directories
      if (normalizedPath.endsWith("/") && normalizedPath.length > 1) {
        console.warn("[WebContainer] Edit path ends with /, removing trailing slash:", normalizedPath);
        normalizedPath = normalizedPath.slice(0, -1);
      }

      // Validate path
      if (!normalizedPath || normalizedPath === "/") {
        throw new Error("Invalid file path: cannot edit root directory");
      }

      // Read current content
      const currentContent = await instance.fs.readFile(
        normalizedPath,
        "utf-8"
      );

      // Save old content for diff tracking
      const oldContent = currentContent as string;

      // Perform replacement
      let newContent: string;
      if (replaceAll) {
        newContent = oldContent.split(oldText).join(newText);
      } else {
        newContent = oldContent.replace(oldText, newText);
      }

      // Write back
      await instance.fs.writeFile(normalizedPath, newContent);

      // Update state (including diff if tracking)
      setState((prev) => {
        const newState = {
          ...prev,
          files: {
            ...prev.files,
            [normalizedPath]: newContent,
          },
        };

        // Track diff if requested and content actually changed
        if (trackDiff && oldContent !== newContent) {
          newState.fileDiffs = {
            ...prev.fileDiffs,
            [normalizedPath]: {
              path: normalizedPath,
              oldContent,
              newContent,
              timestamp: Date.now(),
            },
          };
        }

        return newState;
      });

      console.log("[WebContainer] File edited:", normalizedPath, trackDiff ? "(with diff tracking)" : "");
    },
    []
  );

  /**
   * Rename/move file
   */
  const renameFile = useCallback(
    async (oldPath: string, newPath: string) => {
      const instance = webcontainerRef.current;
      if (!instance) {
        throw new Error("WebContainer not ready");
      }

      // Normalize paths
      let oldNormalized = oldPath.startsWith("/") ? oldPath : `/${oldPath}`;
      let newNormalized = newPath.startsWith("/") ? newPath : `/${newPath}`;

      // Remove trailing slashes
      if (oldNormalized.endsWith("/") && oldNormalized.length > 1) {
        oldNormalized = oldNormalized.slice(0, -1);
      }
      if (newNormalized.endsWith("/") && newNormalized.length > 1) {
        newNormalized = newNormalized.slice(0, -1);
      }

      // Validate paths
      if (!oldNormalized || oldNormalized === "/" || !newNormalized || newNormalized === "/") {
        throw new Error("Invalid file path for rename operation");
      }

      // Read old content
      const content = await instance.fs.readFile(oldNormalized, "utf-8");

      // Create new file
      await writeFile(newNormalized, content);

      // Delete old file
      await deleteFile(oldNormalized);

      console.log("[WebContainer] File renamed:", oldNormalized, "->", newNormalized);
    },
    [writeFile, deleteFile]
  );

  /**
   * Create directory
   */
  const createDirectory = useCallback(async (path: string) => {
    const instance = webcontainerRef.current;
    if (!instance) {
      throw new Error("WebContainer not ready");
    }

    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    await instance.fs.mkdir(normalizedPath, { recursive: true });

    console.log("[WebContainer] Directory created:", normalizedPath);
  }, []);

  /**
   * List files in a directory
   * @param dirPath Directory path to list
   * @param recursive Whether to list recursively
   * @returns Formatted string of files and directories
   */
  const listFilesRecursive = useCallback(
    async (dirPath: string, recursive: boolean = false): Promise<string> => {
      const instance = webcontainerRef.current;
      if (!instance) {
        throw new Error("WebContainer not ready");
      }

      const normalizedPath = dirPath.startsWith("/") ? dirPath : `/${dirPath}`;
      const results: string[] = [];

      const listDir = async (currentPath: string, indent: string = "") => {
        try {
          const entries = await instance.fs.readdir(currentPath, { withFileTypes: true });

          for (const entry of entries) {
            const entryPath = currentPath === "/" ? `/${entry.name}` : `${currentPath}/${entry.name}`;

            if (entry.isDirectory()) {
              results.push(`${indent}📁 ${entry.name}/`);
              if (recursive) {
                await listDir(entryPath, indent + "  ");
              }
            } else {
              results.push(`${indent}📄 ${entry.name}`);
            }
          }
        } catch (error) {
          results.push(`${indent}Error reading ${currentPath}: ${error}`);
        }
      };

      await listDir(normalizedPath);

      if (results.length === 0) {
        return `Directory ${normalizedPath} is empty`;
      }

      return `Contents of ${normalizedPath}:\n${results.join("\n")}`;
    },
    []
  );

  // ============================================
  // Terminal Operations
  // ============================================

  /**
   * Create a new terminal session
   */
  const createTerminal = useCallback((name?: string): string => {
    const id = generateTerminalId();
    const terminalName = name || `Terminal ${state.terminals.length + 1}`;

    const session: TerminalSession = {
      id,
      name: terminalName,
      cwd: "/",
      isRunning: false,
      history: [],
      createdAt: Date.now(),
    };

    // Initialize history buffer for this terminal
    historyBufferRef.current[id] = [];

    setState((prev) => {
      // Limit terminals
      if (prev.terminals.length >= MAX_TERMINALS) {
        console.warn("[WebContainer] Maximum terminals reached");
        return prev;
      }

      return {
        ...prev,
        terminals: [...prev.terminals, session],
        activeTerminalId: id,
      };
    });

    console.log("[WebContainer] Terminal created:", id);
    return id;
  }, [state.terminals.length]);

  /**
   * Spawn an interactive shell (jsh) for the terminal
   * Returns the shell streams for direct XTerm integration.
   *
   * The terminal component will get its own writer from shell.input.
   * Agent commands use separate spawn processes, but their output is
   * displayed in terminal via agentLogs mechanism.
   */
  const spawnShell = useCallback(async () => {
    const instance = webcontainerRef.current;
    if (!instance) {
      throw new Error("WebContainer not ready");
    }

    // Kill existing shell if any
    if (shellProcessRef.current) {
      shellProcessRef.current.kill();
      shellProcessRef.current = null;
    }
    if (shellWriterRef.current) {
      try {
        shellWriterRef.current.releaseLock();
      } catch (e) {
        // Ignore
      }
      shellWriterRef.current = null;
    }

    // Spawn jsh (JavaScript Shell) - the interactive shell for WebContainer
    const shellProcess = await instance.spawn("jsh", {
      terminal: {
        cols: 80,
        rows: 24,
      },
    });
    shellProcessRef.current = shellProcess;

    // Mark background shell as ready (terminal will get its own writer)
    backgroundShellReadyRef.current = true;

    console.log("[WebContainer] Interactive shell spawned");

    // Return shell streams for XTerm to use directly
    return {
      output: shellProcess.output,
      input: shellProcess.input,
      exit: shellProcess.exit,
      resize: shellProcess.resize ? (dims: { cols: number; rows: number }) => {
        shellProcess.resize?.(dims);
      } : undefined,
    };
  }, []);

  /**
   * Write to the interactive shell's stdin
   * @param data - Data to write (can include escape sequences for special keys)
   */
  const writeToShell = useCallback(async (data: string) => {
    const writer = shellWriterRef.current;
    if (!writer) {
      console.warn("[WebContainer] No shell writer available");
      return;
    }

    try {
      await writer.write(data);
    } catch (error) {
      console.error("[WebContainer] Shell write error:", error);
    }
  }, []);

  /**
   * Resize shell terminal
   */
  const resizeShell = useCallback((cols: number, rows: number) => {
    const shellProcess = shellProcessRef.current;
    if (shellProcess && shellProcess.resize) {
      shellProcess.resize({ cols, rows });
    }
  }, []);

  /**
   * Check if a command is a long-running process (dev server, etc.)
   * These commands should NOT block - they run in background.
   */
  const isLongRunningCommand = (command: string, args: string[]): boolean => {
    const cmdLower = command.toLowerCase();
    const argsStr = args.join(" ").toLowerCase();

    // npm/yarn/pnpm dev server commands
    if (cmdLower === "npm" || cmdLower === "yarn" || cmdLower === "pnpm") {
      if (argsStr.includes("run dev") || argsStr.includes("run start") ||
          argsStr.includes("run serve") || argsStr.includes("run watch")) {
        return true;
      }
    }

    // npx vite or similar
    if (cmdLower === "npx" && (argsStr.includes("vite") || argsStr.includes("next"))) {
      return true;
    }

    // Direct vite/next commands
    if (cmdLower === "vite" || cmdLower === "next") {
      if (args.length === 0 || argsStr.includes("dev") || argsStr.includes("start")) {
        return true;
      }
    }

    // node server.js or similar
    if (cmdLower === "node" && args.length > 0) {
      const file = args[0].toLowerCase();
      if (file.includes("server") || file.includes("app") || file.includes("index")) {
        return true;
      }
    }

    return false;
  };

  /**
   * Run command in terminal
   * Uses ref-based history buffer to avoid setState race conditions
   *
   * IMPORTANT: Long-running commands (npm run dev, etc.) return immediately
   * and run in background. Use get_state() to check if server is ready.
   */
  const runCommand = useCallback(
    async (
      command: string,
      args: string[] = [],
      terminalId?: string
    ): Promise<string> => {
      const instance = webcontainerRef.current;
      if (!instance) {
        throw new Error("WebContainer not ready");
      }

      console.log("[WebContainer] Running:", command, args.join(" "));

      // Find or create terminal
      let targetId = terminalId || state.activeTerminalId;
      if (!targetId) {
        targetId = createTerminal();
      }

      const cmdStr = `${command} ${args.join(" ")}`.trim();

      // Initialize history buffer for this terminal
      if (!historyBufferRef.current[targetId]) {
        historyBufferRef.current[targetId] = [];
      }

      // Mark terminal as running and clear old history for new command
      setState((prev) => ({
        ...prev,
        terminals: prev.terminals.map((t) =>
          t.id === targetId
            ? { ...t, isRunning: true, command: cmdStr, exitCode: undefined }
            : t
        ),
      }));

      const process = await instance.spawn(command, args);
      processesRef.current.set(targetId, process);

      // Check if this is a long-running command (dev server, etc.)
      const isLongRunning = isLongRunningCommand(command, args);

      const output: string[] = [];
      let isProcessRunning = true;

      // Read output using ref buffer to accumulate
      console.log("[WebContainer] Starting to read output for:", cmdStr, isLongRunning ? "(long-running)" : "");

      // Batch update interval (update state every 100ms for smoother UI)
      let lastUpdateTime = Date.now();
      const UPDATE_INTERVAL = 100;

      // Read output stream in background
      const readOutput = async () => {
        const reader = process.output.getReader();
        try {
          while (isProcessRunning) {
            const { done, value } = await reader.read();
            if (done) {
              console.log("[WebContainer] Output stream ended for:", cmdStr);
              break;
            }

            output.push(value);

            // Filter out pure ANSI control sequences (spinner frames, cursor movements)
            const strippedValue = value
              // eslint-disable-next-line no-control-regex
              .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '') // Remove ANSI escape codes
              .replace(/\r/g, '') // Remove carriage returns
              .trim();

            // Check if this is just a spinner character (single char like | / - \)
            const isSpinner = strippedValue.length <= 1 && /^[|/\-\\]?$/.test(strippedValue);

            // Store all non-spinner output
            if (!isSpinner && strippedValue.length > 0) {
              console.log("[WebContainer] Output:", strippedValue.substring(0, 100));

              // Add to ref buffer (immediate, no race condition)
              const processOutput: ProcessOutput = {
                type: "stdout",
                data: value,
                timestamp: Date.now(),
              };
              historyBufferRef.current[targetId].push(processOutput);

              // Limit buffer size
              if (historyBufferRef.current[targetId].length > MAX_HISTORY_ENTRIES) {
                historyBufferRef.current[targetId] =
                  historyBufferRef.current[targetId].slice(-MAX_HISTORY_ENTRIES);
              }

              // ============================================
              // Detect Vite build errors from terminal output
              // This catches errors when bridge script isn't loaded
              // ============================================
              const cleanedForErrorCheck = cleanAnsiCodes(value);

              // Check for Vite plugin errors: [plugin:vite:react-babel]
              const vitePluginMatch = cleanedForErrorCheck.match(/\[plugin:(vite:[^\]]+)\]/);

              // Check for common error patterns
              const hasError =
                vitePluginMatch ||
                cleanedForErrorCheck.includes("error:") ||
                cleanedForErrorCheck.includes("SyntaxError:") ||
                cleanedForErrorCheck.includes("Failed to resolve import") ||
                cleanedForErrorCheck.includes("Unexpected token");

              if (hasError) {
                console.log("[WebContainer] Detected Vite error in terminal output");

                // Accumulate error context from recent output
                const recentOutput = historyBufferRef.current[targetId]
                  .slice(-20)
                  .map(h => cleanAnsiCodes(h.data))
                  .join("\n");

                // Extract file path: /path/to/file.jsx:line:column
                const fileMatch = recentOutput.match(/([^\s]+\.(jsx?|tsx?|vue|svelte)):(\d+):(\d+)/);
                const file = fileMatch ? fileMatch[1] : undefined;
                const line = fileMatch ? parseInt(fileMatch[3], 10) : undefined;
                const column = fileMatch ? parseInt(fileMatch[4], 10) : undefined;

                // Extract code frame (lines with | separator)
                const frameLines: string[] = [];
                for (const l of recentOutput.split('\n')) {
                  if (/^\s*\d+\s*\|/.test(l) || /^\s+\|/.test(l)) {
                    frameLines.push(l);
                  }
                }
                const frame = frameLines.length > 0 ? frameLines.join('\n') : undefined;

                // Extract plugin name
                const plugin = vitePluginMatch ? vitePluginMatch[1] : undefined;

                // Update state with detected error
                setState(prev => {
                  // Only update if we don't already have an error or this is newer
                  if (!prev.preview.errorOverlay || Date.now() - prev.preview.errorOverlay.timestamp > 1000) {
                    return {
                      ...prev,
                      preview: {
                        ...prev.preview,
                        hasError: true,
                        errorMessage: cleanedForErrorCheck.slice(0, 500),
                        errorOverlay: {
                          message: recentOutput.slice(0, 3000),
                          file,
                          line,
                          column,
                          plugin,
                          frame,
                          timestamp: Date.now(),
                        },
                      },
                    };
                  }
                  return prev;
                });
              }
            }

            // Batch state updates for performance
            const now = Date.now();
            if (now - lastUpdateTime >= UPDATE_INTERVAL) {
              lastUpdateTime = now;

              // Ensure buffer exists and is an array before spreading
              if (!historyBufferRef.current[targetId]) {
                historyBufferRef.current[targetId] = [];
              }

              const currentHistory = Array.isArray(historyBufferRef.current[targetId])
                ? [...historyBufferRef.current[targetId]]
                : [];

              if (currentHistory.length > 0) {
                console.log("[WebContainer] Syncing history to state, length:", currentHistory.length);
                setState((prev) => ({
                  ...prev,
                  terminals: prev.terminals.map((t) =>
                    t.id === targetId
                      ? { ...t, history: currentHistory }
                      : t
                  ),
                }));
              }
            }
          }
        } catch (err) {
          console.log("[WebContainer] Output read stopped:", err);
        } finally {
          reader.releaseLock();
        }
      };

      // Start reading output (don't await - runs in parallel)
      readOutput();

      // ============================================
      // LONG-RUNNING COMMAND: Return immediately!
      // ============================================
      if (isLongRunning) {
        console.log("[WebContainer] Long-running command detected, returning immediately");

        // Wait a short time to collect initial output (e.g., "vite starting...")
        await new Promise(resolve => setTimeout(resolve, 500));

        // Return immediately with status message
        // The process continues running in background
        // Agent should use get_state() to check preview_url for server readiness
        const initialOutput = output.join("").slice(0, 500);
        return `Server starting in background...\n\n` +
               `Initial output:\n${initialOutput}\n\n` +
               `The dev server is now running. Use get_state() to check if preview_url is available.`;
      }

      // ============================================
      // REGULAR COMMAND: Wait for completion
      // ============================================

      // Wait for process exit (this is the reliable completion signal)
      const exitCode = await process.exit;
      isProcessRunning = false;
      console.log("[WebContainer] Command exit code:", exitCode);

      // Give a small delay for final output to be processed
      await new Promise(resolve => setTimeout(resolve, 50));

      // Final sync of history buffer to state
      // Ensure buffer exists and is an array before spreading
      if (!historyBufferRef.current[targetId]) {
        historyBufferRef.current[targetId] = [];
      }
      const finalHistory = Array.isArray(historyBufferRef.current[targetId])
        ? [...historyBufferRef.current[targetId]]
        : [];
      console.log("[WebContainer] Final history sync, length:", finalHistory.length);

      // Mark session as complete with final history
      setState((prev) => ({
        ...prev,
        terminals: prev.terminals.map((t) =>
          t.id === targetId
            ? { ...t, isRunning: false, exitCode, history: finalHistory }
            : t
        ),
      }));

      processesRef.current.delete(targetId);

      // ============================================
      // IMPROVED: Return structured result with exitCode
      // ============================================
      const outputStr = output.join("");
      // Note: cmdStr is already defined above at line ~1954

      if (exitCode !== 0) {
        // Command failed - return detailed error information
        console.log("[WebContainer] Command failed:", cmdStr, "exitCode:", exitCode);
        return `${ERROR_PREFIX_COMMAND_FAILED}\n` +
               `Exit Code: ${exitCode}\n` +
               `Command: ${cmdStr}\n` +
               `\n--- Output ---\n${outputStr || "(no output)"}\n--- End Output ---`;
      }

      // Command succeeded
      return outputStr;
    },
    [state.activeTerminalId, createTerminal]
  );

  /**
   * Send input to running terminal
   */
  const sendTerminalInput = useCallback(
    async (terminalId: string, input: string) => {
      const process = processesRef.current.get(terminalId);
      if (!process) {
        throw new Error(`No running process in terminal ${terminalId}`);
      }

      const writer = process.input.getWriter();
      await writer.write(input);
      writer.releaseLock();

      console.log("[WebContainer] Input sent to terminal:", terminalId);
    },
    []
  );

  /**
   * Kill terminal and its process
   */
  const killTerminal = useCallback(async (terminalId: string) => {
    const process = processesRef.current.get(terminalId);
    if (process) {
      process.kill();
      processesRef.current.delete(terminalId);
    }

    // Clean up history buffer
    delete historyBufferRef.current[terminalId];

    setState((prev) => ({
      ...prev,
      terminals: prev.terminals.filter((t) => t.id !== terminalId),
      activeTerminalId:
        prev.activeTerminalId === terminalId
          ? prev.terminals[0]?.id || null
          : prev.activeTerminalId,
    }));

    console.log("[WebContainer] Terminal killed:", terminalId);
  }, []);

  /**
   * Switch active terminal
   */
  const switchTerminal = useCallback((terminalId: string) => {
    setState((prev) => ({
      ...prev,
      activeTerminalId: terminalId,
    }));
  }, []);

  /**
   * Install dependencies
   */
  const installDependencies = useCallback(
    async (packages: string[] = [], dev: boolean = false) => {
      const args =
        packages.length > 0
          ? ["install", ...(dev ? ["--save-dev"] : []), ...packages]
          : ["install"];
      return await runCommand("npm", args);
    },
    [runCommand]
  );

  /**
   * Start dev server
   */
  const startDevServer = useCallback(async () => {
    setState((prev) => ({
      ...prev,
      preview: { ...prev.preview, isLoading: true },
    }));

    // First install dependencies
    await installDependencies();
    // Then start dev server
    return await runCommand("npm", ["run", "dev"]);
  }, [runCommand, installDependencies]);

  /**
   * Stop all processes
   */
  const stopProcess = useCallback(async () => {
    for (const [id, process] of processesRef.current) {
      process.kill();
      console.log("[WebContainer] Process killed:", id);
    }
    processesRef.current.clear();

    setState((prev) => ({
      ...prev,
      terminals: prev.terminals.map((t) => ({ ...t, isRunning: false })),
      preview: { ...prev.preview, url: null, isLoading: false },
      previewUrl: null,
    }));
  }, []);

  /**
   * Interrupt running process in main terminal (Ctrl+C equivalent)
   * Kills the process but keeps the terminal alive
   */
  const interruptProcess = useCallback(() => {
    const mainTerminal = state.terminals[0];
    if (!mainTerminal) {
      console.log("[WebContainer] No terminal to interrupt");
      return;
    }

    const process = processesRef.current.get(mainTerminal.id);
    if (process) {
      process.kill();
      processesRef.current.delete(mainTerminal.id);
      console.log("[WebContainer] Process interrupted in terminal:", mainTerminal.id);

      // Update terminal state to show it's no longer running
      setState((prev) => ({
        ...prev,
        terminals: prev.terminals.map((t) =>
          t.id === mainTerminal.id
            ? { ...t, isRunning: false, exitCode: 130 } // 130 = interrupted by Ctrl+C
            : t
        ),
      }));

      // Add interrupt message to history
      if (historyBufferRef.current[mainTerminal.id]) {
        historyBufferRef.current[mainTerminal.id].push({
          type: "stderr",
          data: "\n^C (interrupted)\n",
          timestamp: Date.now(),
        });
      }
    } else {
      console.log("[WebContainer] No running process to interrupt");
    }
  }, [state.terminals]);

  /**
   * Clear terminal output history
   */
  const clearTerminalHistory = useCallback(() => {
    const mainTerminal = state.terminals[0];
    if (!mainTerminal) {
      console.log("[WebContainer] No terminal to clear");
      return;
    }

    // Clear history buffer
    historyBufferRef.current[mainTerminal.id] = [];

    // Update state
    setState((prev) => ({
      ...prev,
      terminals: prev.terminals.map((t) =>
        t.id === mainTerminal.id
          ? { ...t, history: [], exitCode: undefined }
          : t
      ),
    }));

    console.log("[WebContainer] Terminal history cleared:", mainTerminal.id);
  }, [state.terminals]);

  // ============================================
  // Preview Operations
  // ============================================

  /**
   * Set iframe reference for preview operations
   */
  const setPreviewIframe = useCallback((iframe: HTMLIFrameElement | null) => {
    iframeRef.current = iframe;
  }, []);

  /**
   * Repair/inject Bridge script into WebContainer project
   * This ensures the Bridge script exists and is properly referenced.
   * Returns true if repair was performed, false if already OK.
   */
  const repairBridgeScript = useCallback(async (): Promise<{ repaired: boolean; actions: string[] }> => {
    const instance = webcontainerRef.current;
    if (!instance) {
      return { repaired: false, actions: ["WebContainer not ready"] };
    }

    const actions: string[] = [];
    let repaired = false;

    try {
      // 1. Check and write Bridge script file
      const bridgePath = "/public/nexting-bridge.js";
      const bridgeContent = DEFAULT_FILES[bridgePath];

      if (!bridgeContent) {
        actions.push("ERROR: Bridge script template not found in DEFAULT_FILES");
        return { repaired: false, actions };
      }

      let needsBridgeFile = false;
      try {
        await instance.fs.readFile(bridgePath, "utf-8");
        actions.push("Bridge script file exists");
      } catch {
        needsBridgeFile = true;
        actions.push("Bridge script file missing, will create");
      }

      if (needsBridgeFile) {
        // Ensure /public directory exists
        try {
          await instance.fs.mkdir("/public", { recursive: true });
        } catch {
          // Directory might exist
        }
        await instance.fs.writeFile(bridgePath, bridgeContent);
        actions.push("Created /public/nexting-bridge.js");
        repaired = true;
      }

      // 2. Check and update index.html to include Bridge script reference
      const indexPath = "/index.html";
      let indexContent = "";
      try {
        indexContent = await instance.fs.readFile(indexPath, "utf-8");
      } catch {
        actions.push("index.html not found, cannot inject Bridge reference");
        return { repaired, actions };
      }

      if (!indexContent.includes("nexting-bridge.js")) {
        // Inject Bridge script reference before </body>
        const updatedIndex = indexContent.replace(
          "</body>",
          '    <!-- Nexting Bridge: Auto-injected for Agent communication -->\n    <script src="/nexting-bridge.js"></script>\n  </body>'
        );
        await instance.fs.writeFile(indexPath, updatedIndex);
        actions.push("Injected Bridge script reference into index.html");
        repaired = true;
      } else {
        actions.push("index.html already references Bridge script");
      }

      // 3. Check vite.config.js for Bridge injection plugin
      const vitePath = "/vite.config.js";
      let viteContent = "";
      try {
        viteContent = await instance.fs.readFile(vitePath, "utf-8");
      } catch {
        actions.push("vite.config.js not found");
      }

      if (viteContent && !viteContent.includes("nextingBridgePlugin")) {
        // Add the Bridge injection plugin to vite.config.js
        const viteTemplate = DEFAULT_FILES["/vite.config.js"];
        if (viteTemplate) {
          await instance.fs.writeFile(vitePath, viteTemplate);
          actions.push("Updated vite.config.js with Bridge injection plugin");
          repaired = true;
        }
      }

      return { repaired, actions };
    } catch (error) {
      actions.push(`Repair error: ${error}`);
      return { repaired: false, actions };
    }
  }, []);

  /**
   * Refresh the preview iframe
   */
  const refreshPreviewIframe = useCallback(() => {
    const iframe = iframeRef.current;
    if (iframe) {
      try {
        // Try to reload using contentWindow
        if (iframe.contentWindow) {
          iframe.contentWindow.location.reload();
        }
      } catch {
        // Cross-origin fallback: reassign src
        const currentSrc = iframe.src;
        iframe.src = "";
        setTimeout(() => {
          iframe.src = currentSrc;
        }, 50);
      }
    }
  }, []);

  /**
   * Take screenshot of preview using backend Playwright API
   *
   * This calls the backend Playwright service to capture a screenshot of the
   * WebContainer preview URL. Since Playwright runs as a separate browser instance,
   * it can directly access the preview URL without cross-origin restrictions.
   *
   * @param selector - Optional CSS selector to capture specific element (not yet implemented)
   * @param fullPage - Optional flag for full page capture (not yet implemented)
   * @returns Base64 encoded screenshot data URL, or JSON error object
   */
  const takeScreenshot = useCallback(
    async (
      selector?: string,
      fullPage?: boolean
    ): Promise<string> => {
      console.log("[Screenshot] Starting screenshot capture...");

      // ============================================
      // Pre-flight check: Need preview URL
      // ============================================
      if (!state.previewUrl) {
        return JSON.stringify({
          success: false,
          error: "NO_PREVIEW_URL",
          message: "No preview URL available. Dev server may not be running.",
          suggestion: "Start the dev server and wait for preview_url to appear in get_state().",
        }, null, 2);
      }

      console.log("[Screenshot] Using Playwright API to capture:", state.previewUrl);

      // ============================================
      // Use backend Playwright API to capture screenshot
      // ============================================
      // This works because Playwright is a separate browser instance
      // that can access the WebContainer preview URL directly
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

        const response = await fetch(`${API_URL}/api/playwright/extract`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            url: state.previewUrl,
            include_screenshot: true,
            viewport_width: 1920,
            viewport_height: 1080,
            wait_timeout: 15000,
            // If fullPage is requested, we might need to handle scrolling
            // For now, we capture the viewport
          }),
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error("[Screenshot] Playwright API error:", response.status, errorText);
          return JSON.stringify({
            success: false,
            error: "PLAYWRIGHT_API_ERROR",
            status: response.status,
            message: `Playwright API returned error: ${errorText}`,
            previewUrl: state.previewUrl,
            suggestion: "Ensure the backend Playwright service is running. Check if the preview URL is accessible.",
          }, null, 2);
        }

        const result = await response.json();

        if (!result.success) {
          console.error("[Screenshot] Playwright extraction failed:", result.error);
          return JSON.stringify({
            success: false,
            error: "PLAYWRIGHT_EXTRACTION_FAILED",
            message: result.error || "Playwright failed to extract page",
            previewUrl: state.previewUrl,
            suggestion: "The preview URL may not be accessible from the backend. Check if WebContainer preview is publicly reachable.",
          }, null, 2);
        }

        // Check if screenshot is available
        if (result.screenshot) {
          console.log("[Screenshot] Playwright capture succeeded");
          // Return the base64 screenshot with data URL prefix if not present
          const screenshot = result.screenshot.startsWith("data:image")
            ? result.screenshot
            : `data:image/png;base64,${result.screenshot}`;
          return screenshot;
        }

        // No screenshot in response
        console.warn("[Screenshot] Playwright response has no screenshot");
        return JSON.stringify({
          success: false,
          error: "NO_SCREENSHOT_IN_RESPONSE",
          message: "Playwright API returned success but no screenshot data",
          previewUrl: state.previewUrl,
          metadata: result.metadata || null,
          suggestion: "The page may have loaded but screenshot capture failed. Try again.",
        }, null, 2);

      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        console.error("[Screenshot] Playwright API call failed:", errorMsg);

        return JSON.stringify({
          success: false,
          error: "PLAYWRIGHT_API_CALL_FAILED",
          message: errorMsg,
          previewUrl: state.previewUrl,
          suggestion: "Check if the backend server is running at " + (process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001"),
        }, null, 2);
      }
    },
    [state.previewUrl]
  );

  /**
   * Get DOM structure from preview
   *
   * Uses the Nexting Bridge script to extract DOM tree with element bounds,
   * text content, and visibility information.
   *
   * Returns a structured representation that helps Agent understand the page layout.
   *
   * IMPORTANT: This function handles cases where iframe is not available gracefully.
   * Instead of throwing, it returns a descriptive message for the Agent.
   */
  const getPreviewDOM = useCallback(
    async (selector: string = "body", depth: number = 5): Promise<string> => {
      const iframe = iframeRef.current;

      // Check iframe availability and provide useful feedback
      if (!iframe) {
        return JSON.stringify({
          success: false,
          error: "iframe_not_mounted",
          message: "Preview iframe is not mounted yet.",
          suggestion: "Wait for the preview to load, or check if the dev server is running with get_state()."
        }, null, 2);
      }

      if (!iframe.contentWindow) {
        return JSON.stringify({
          success: false,
          error: "iframe_no_content",
          message: "Preview iframe exists but has no content window.",
          suggestion: "The preview may still be loading. Try again in a few seconds."
        }, null, 2);
      }

      // Check if preview URL is available
      if (!state.previewUrl) {
        return JSON.stringify({
          success: false,
          error: "no_preview_url",
          message: "No preview URL available. Dev server may not be running.",
          suggestion: "Start the dev server with shell('npm run dev', background=True) and wait for preview_url to appear."
        }, null, 2);
      }

      return new Promise((resolve) => {
        const messageId = `dom-${Date.now()}`;
        let resolved = false;

        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === "dom-result" && event.data?.id === messageId) {
            window.removeEventListener("message", handleMessage);
            resolved = true;

            if (event.data.error) {
              resolve(JSON.stringify({
                success: false,
                error: "dom_error",
                message: event.data.error,
                suggestion: "The DOM query failed. Check if the selector is valid."
              }, null, 2));
            } else if (event.data.data) {
              resolve(event.data.data);
            } else {
              resolve(JSON.stringify({
                success: false,
                error: "empty_response",
                message: "DOM query returned empty response."
              }, null, 2));
            }
          }
        };

        window.addEventListener("message", handleMessage);

        try {
          iframe.contentWindow?.postMessage(
            {
              type: "get-dom",
              id: messageId,
              selector,
              depth,
            },
            "*"
          );
        } catch (e) {
          window.removeEventListener("message", handleMessage);
          resolve(JSON.stringify({
            success: false,
            error: "postmessage_failed",
            message: `Failed to communicate with iframe: ${e}`,
            suggestion: "The Nexting Bridge may not be loaded. Try refreshing the preview."
          }, null, 2));
          return;
        }

        // Timeout after 5 seconds
        setTimeout(() => {
          if (!resolved) {
            window.removeEventListener("message", handleMessage);
            resolve(JSON.stringify({
              success: false,
              error: "dom_query_timeout",
              message: "DOM query request timed out after 5 seconds.",
              suggestion: "The Nexting Bridge may not be responding. Try refreshing the preview or check console for errors."
            }, null, 2));
          }
        }, 5000);
      });
    },
    [state.previewUrl]
  );

  /**
   * Get visual summary of preview page
   *
   * Returns high-level information about the preview without needing full DOM or screenshot:
   * - Viewport and body dimensions
   * - Number of visible elements
   * - Text content preview
   * - Whether the page appears to have meaningful content
   *
   * This is a lightweight alternative to DOM snapshot or screenshot.
   */
  const getVisualSummary = useCallback(
    async (): Promise<string> => {
      const iframe = iframeRef.current;

      // Check iframe availability
      if (!iframe) {
        return JSON.stringify({
          success: false,
          error: "iframe_not_mounted",
          message: "Preview iframe is not mounted yet.",
          suggestion: "Wait for the preview to load."
        }, null, 2);
      }

      if (!iframe.contentWindow) {
        return JSON.stringify({
          success: false,
          error: "iframe_no_content",
          message: "Preview iframe exists but has no content window."
        }, null, 2);
      }

      if (!state.previewUrl) {
        return JSON.stringify({
          success: false,
          error: "no_preview_url",
          message: "No preview URL available."
        }, null, 2);
      }

      return new Promise((resolve) => {
        const messageId = `visual-summary-${Date.now()}`;
        let resolved = false;

        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === "visual-summary-result" && event.data?.id === messageId) {
            window.removeEventListener("message", handleMessage);
            resolved = true;

            if (event.data.error) {
              resolve(JSON.stringify({
                success: false,
                error: "visual_summary_error",
                message: event.data.error
              }, null, 2));
            } else if (event.data.data) {
              resolve(event.data.data);
            } else {
              resolve(JSON.stringify({
                success: false,
                error: "empty_response",
                message: "Visual summary returned empty response."
              }, null, 2));
            }
          }
        };

        window.addEventListener("message", handleMessage);

        try {
          iframe.contentWindow?.postMessage(
            {
              type: "get-visual-summary",
              id: messageId,
            },
            "*"
          );
        } catch (e) {
          window.removeEventListener("message", handleMessage);
          resolve(JSON.stringify({
            success: false,
            error: "postmessage_failed",
            message: `Failed to communicate with iframe: ${e}`
          }, null, 2));
          return;
        }

        // Timeout after 3 seconds
        setTimeout(() => {
          if (!resolved) {
            window.removeEventListener("message", handleMessage);
            resolve(JSON.stringify({
              success: false,
              error: "visual_summary_timeout",
              message: "Visual summary request timed out."
            }, null, 2));
          }
        }, 3000);
      });
    },
    [state.previewUrl]
  );

  /**
   * Get build/compilation errors from preview iframe
   * This tool actively queries the preview for any visible error overlays
   * (Vite errors, React error boundaries, etc.)
   */
  const getBuildErrors = useCallback(
    async (): Promise<string> => {
      const iframe = iframeRef.current;

      // Check iframe availability
      if (!iframe) {
        return JSON.stringify({
          success: false,
          error: "iframe_not_mounted",
          message: "Preview iframe is not mounted yet.",
          suggestion: "Wait for the preview to load, or start the dev server first.",
          hasErrors: false,
          errorCount: 0,
          errors: []
        }, null, 2);
      }

      if (!iframe.contentWindow) {
        return JSON.stringify({
          success: false,
          error: "iframe_no_content",
          message: "Preview iframe exists but has no content window.",
          suggestion: "The preview may still be loading. Try again in a few seconds.",
          hasErrors: false,
          errorCount: 0,
          errors: []
        }, null, 2);
      }

      if (!state.previewUrl) {
        return JSON.stringify({
          success: false,
          error: "no_preview_url",
          message: "No preview URL available. Dev server may not be running.",
          suggestion: "Start the dev server with shell('npm run dev', background=True).",
          hasErrors: false,
          errorCount: 0,
          errors: []
        }, null, 2);
      }

      return new Promise((resolve) => {
        const messageId = `build-errors-${Date.now()}`;
        let resolved = false;

        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === "build-errors-result" && event.data?.id === messageId) {
            window.removeEventListener("message", handleMessage);
            resolved = true;

            if (event.data.error) {
              resolve(JSON.stringify({
                success: false,
                error: "query_error",
                message: event.data.error,
                hasErrors: false,
                errorCount: 0,
                errors: []
              }, null, 2));
            } else if (event.data.data) {
              resolve(event.data.data);
            } else {
              resolve(JSON.stringify({
                success: true,
                hasErrors: false,
                errorCount: 0,
                errors: [],
                message: "No build errors detected."
              }, null, 2));
            }
          }
        };

        window.addEventListener("message", handleMessage);

        try {
          iframe.contentWindow?.postMessage(
            {
              type: "get-build-errors",
              id: messageId,
            },
            "*"
          );
        } catch (e) {
          window.removeEventListener("message", handleMessage);
          resolve(JSON.stringify({
            success: false,
            error: "postmessage_failed",
            message: `Failed to communicate with iframe: ${e}`,
            hasErrors: false,
            errorCount: 0,
            errors: []
          }, null, 2));
          return;
        }

        // Timeout after 5 seconds (longer for error detection)
        // IMPORTANT: Fall back to errorOverlay state if iframe doesn't respond
        setTimeout(() => {
          if (!resolved) {
            window.removeEventListener("message", handleMessage);

            // CRITICAL: Check errorOverlay state as fallback
            // This captures Vite errors detected from terminal output or previous iframe messages
            const currentState = stateRef.current;
            const errorOverlay = currentState.preview?.errorOverlay;

            if (errorOverlay && errorOverlay.message) {
              // Build errors object from errorOverlay state
              const errors = [{
                type: errorOverlay.plugin || "build_error",
                message: errorOverlay.message,
                file: errorOverlay.file ?
                  `${errorOverlay.file}${errorOverlay.line ? `:${errorOverlay.line}` : ''}${errorOverlay.column ? `:${errorOverlay.column}` : ''}`
                  : undefined,
                frame: errorOverlay.frame,
                stack: errorOverlay.stack,
                plugin: errorOverlay.plugin,
              }];

              console.log("[WebContainer] getBuildErrors: Using errorOverlay fallback", errorOverlay.message?.slice(0, 100));

              resolve(JSON.stringify({
                success: true,
                hasErrors: true,
                errorCount: 1,
                errors,
                source: "errorOverlay_fallback",
                message: "Error detected from terminal/cached state (iframe bridge not responding)"
              }, null, 2));
              return;
            }

            // Also check for console errors as secondary fallback
            const consoleMessages = currentState.preview?.consoleMessages || [];
            const consoleErrors = consoleMessages
              .filter(m => m.type === "error")
              .slice(-5)
              .map(m => ({
                type: "console_error",
                message: m.args.map(arg =>
                  typeof arg === "string" ? arg :
                  arg instanceof Error ? arg.message :
                  String(arg)
                ).join(" ").slice(0, 500),
                stack: m.stack,
              }));

            if (consoleErrors.length > 0) {
              console.log("[WebContainer] getBuildErrors: Using console errors fallback");
              resolve(JSON.stringify({
                success: true,
                hasErrors: true,
                errorCount: consoleErrors.length,
                errors: consoleErrors,
                source: "console_fallback",
                message: "Console errors detected (iframe bridge not responding)"
              }, null, 2));
              return;
            }

            // No errors found anywhere
            resolve(JSON.stringify({
              success: true,
              hasErrors: false,
              errorCount: 0,
              errors: [],
              source: "timeout_fallback",
              message: "No build errors detected (iframe bridge timed out, checked state fallbacks)."
            }, null, 2));
          }
        }, 5000);
      });
    },
    [state.previewUrl]
  );

  /**
   * Add console message from preview
   */
  const addConsoleMessage = useCallback(
    (type: ConsoleMessage["type"], args: unknown[], stack?: string) => {
      const message: ConsoleMessage = {
        id: generateConsoleMessageId(),
        type,
        args,
        timestamp: Date.now(),
        stack,
      };

      setState((prev) => ({
        ...prev,
        preview: {
          ...prev.preview,
          consoleMessages: [
            ...prev.preview.consoleMessages.slice(-MAX_CONSOLE_MESSAGES),
            message,
          ],
        },
      }));

      // Auto-notify about errors (方案 A)
      if (type === "error" && onPreviewErrorRef.current) {
        // Format error message from args
        const errorMessage = args
          .map((arg) => {
            if (typeof arg === "string") return arg;
            if (arg instanceof Error) return arg.message;
            try {
              return JSON.stringify(arg);
            } catch {
              return String(arg);
            }
          })
          .join(" ");

        onPreviewErrorRef.current({
          message: errorMessage,
          stack,
          timestamp: Date.now(),
        });
      }
    },
    []
  );

  /**
   * Clear console messages
   */
  const clearConsole = useCallback(() => {
    setState((prev) => ({
      ...prev,
      preview: {
        ...prev.preview,
        consoleMessages: [],
      },
    }));
  }, []);

  /**
   * Set preview viewport size
   */
  const setPreviewViewport = useCallback((width: number, height: number) => {
    setState((prev) => ({
      ...prev,
      preview: {
        ...prev.preview,
        viewport: { width, height },
      },
    }));
  }, []);

  // ============================================
  // File Diff Operations
  // ============================================

  /**
   * Clear all file diffs (called when user sends new message)
   */
  const clearFileDiffs = useCallback(() => {
    setState((prev) => ({
      ...prev,
      fileDiffs: {},
    }));
    console.log("[WebContainer] File diffs cleared");
  }, []);

  /**
   * Clear diff for a specific file
   */
  const clearFileDiff = useCallback((path: string) => {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    setState((prev) => {
      const newDiffs = { ...prev.fileDiffs };
      delete newDiffs[normalizedPath];
      return {
        ...prev,
        fileDiffs: newDiffs,
      };
    });
    console.log("[WebContainer] File diff cleared:", normalizedPath);
  }, []);

  // ============================================
  // ============================================
  // Auto-Create Default Terminal & Start Dev Server
  // ============================================

  /**
   * Create default terminal and start dev server when WebContainer is ready.
   *
   * This ensures:
   * 1. Only ONE terminal exists (created at startup)
   * 2. Dev server runs IN this terminal (visible to user)
   * 3. Agent's shell commands reuse this same terminal
   */
  useEffect(() => {
    // Only run when:
    // - WebContainer is ready
    // - No terminals exist yet (first time setup)
    // - No preview URL (server not running)
    if (
      state.status !== "ready" ||
      state.terminals.length > 0 ||
      state.preview.url
    ) {
      return;
    }

    console.log("[WebContainer] Creating default terminal and starting dev server...");

    // Create default terminal and start dev server
    const setupTerminal = async () => {
      try {
        // 1. Create the default terminal
        const terminalId = createTerminal("Main Terminal");
        console.log("[WebContainer] Default terminal created:", terminalId);

        // 2. Small delay to ensure terminal state is updated
        await new Promise(resolve => setTimeout(resolve, 100));

        // 3. Log and run npm install
        logAgent("info", "🚀 Starting development environment...");
        logAgent("command", "npm install");

        const installOutput = await installDependencies();

        // Log npm install output (summarized)
        if (installOutput) {
          const lines = installOutput.split("\n").filter((l: string) => l.trim());
          const meaningfulLines = lines
            .filter((l: string) => !l.includes("npm warn") && l.trim())
            .slice(-5);
          if (meaningfulLines.length > 0) {
            logAgent("output", meaningfulLines.join("\n"));
          }
        }
        logAgent("info", "✓ Dependencies installed");

        // 4. Start dev server in the same terminal
        logAgent("command", "npm run dev");
        const devOutput = await runCommand("npm", ["run", "dev"]);

        if (devOutput) {
          logAgent("output", devOutput.slice(0, 300));
        }

        logAgent("info", "✓ Development server started");
        console.log("[WebContainer] Dev server started in default terminal");

      } catch (error) {
        console.error("[WebContainer] Failed to setup terminal:", error);
        logAgent("error", `Failed to start dev server: ${error instanceof Error ? error.message : String(error)}`);
      }
    };

    // Small delay to ensure WebContainer is fully ready
    const timer = setTimeout(setupTerminal, 500);
    return () => clearTimeout(timer);

  }, [state.status, state.terminals.length, state.preview.url, createTerminal, logAgent, installDependencies, runCommand]);

  // ============================================
  // Health Check Helper (方案 D)
  // ============================================

  /**
   * Check preview health after file changes.
   * Waits briefly for HMR and checks for:
   * 1. Console errors from state
   * 2. Vite build errors from errorOverlay (captured from iframe)
   * Uses stateRef to get latest state (avoids closure issues).
   */
  const checkPreviewHealth = useCallback(async (): Promise<{
    healthy: boolean;
    errorCount: number;
    recentErrors: string[];
  }> => {
    // Wait for HMR to process the file change
    await new Promise((resolve) => setTimeout(resolve, 500));

    const allErrors: string[] = [];

    // 1. Check for Vite build errors from errorOverlay (captured from iframe bridge)
    const errorOverlay = stateRef.current.preview.errorOverlay;
    if (errorOverlay) {
      const buildError = errorOverlay.message?.slice(0, 200) || 'Build error';
      allErrors.push(`[Build Error] ${buildError}`);
    }

    // 2. Get console errors from state
    const consoleMessages = stateRef.current.preview.consoleMessages;
    const recentTimeThreshold = Date.now() - 5000; // Errors in last 5 seconds

    const consoleErrors = consoleMessages
      .filter(
        (msg) =>
          msg.type === "error" && msg.timestamp > recentTimeThreshold
      )
      .map((msg) => {
        const errorText = msg.args
          .map((arg) => {
            if (typeof arg === "string") return arg;
            try {
              return JSON.stringify(arg);
            } catch {
              return String(arg);
            }
          })
          .join(" ");
        return errorText.slice(0, 200); // Limit length
      });

    // Add console errors to all errors
    allErrors.push(...consoleErrors);

    const healthy = allErrors.length === 0;

    // Notify health change
    if (onHealthChangeRef.current) {
      onHealthChangeRef.current(healthy, allErrors.length);
    }

    return {
      healthy,
      errorCount: allErrors.length,
      recentErrors: allErrors.slice(0, 3), // Max 3 errors
    };
  }, []);

  // ============================================
  // WebContainer Action Handler
  // ============================================

  /**
   * Handle action from Agent
   */
  const handleAction = useCallback(
    async (action: { type: string; payload: Record<string, any> }): Promise<string> => {
      const { type, payload } = action;

      try {
        switch (type) {
          // File operations (with diff tracking for Agent changes)
          case "write_file": {
            // Log the file write operation
            logAgent("file", `Writing: ${payload.path}`);

            // Enable diff tracking for Agent-made file changes
            await writeFile(payload.path, payload.content, true);

            // 方案 D: Health check after file write
            // Only check health if preview is running (use stateRef for latest state)
            if (stateRef.current.preview.url) {
              const health = await checkPreviewHealth();
              if (!health.healthy) {
                const errorResult = `File written: ${payload.path}\n\n⚠️ Preview Errors (${health.errorCount}):\n${health.recentErrors.map(e => `  • ${e}`).join("\n")}`;
                logAgent("error", `Preview errors after writing ${payload.path}`);
                return errorResult;
              }
              logAgent("info", `✓ ${payload.path} written successfully`);
              return `File written: ${payload.path}\n✓ No errors`;
            }
            logAgent("info", `✓ ${payload.path} written`);
            return `File written: ${payload.path}`;
          }

          case "edit_file": {
            // Log the file edit operation
            logAgent("file", `Editing: ${payload.path}`);

            // Enable diff tracking for Agent-made file edits
            await editFile(
              payload.path,
              payload.old_text,
              payload.new_text,
              payload.replace_all,
              true // trackDiff
            );

            // 方案 D: Health check after file edit (use stateRef for latest state)
            if (stateRef.current.preview.url) {
              const health = await checkPreviewHealth();
              if (!health.healthy) {
                const errorResult = `File edited: ${payload.path}\n\n⚠️ Preview Errors (${health.errorCount}):\n${health.recentErrors.map(e => `  • ${e}`).join("\n")}`;
                logAgent("error", `Preview errors after editing ${payload.path}`);
                return errorResult;
              }
              logAgent("info", `✓ ${payload.path} edited successfully`);
              return `File edited: ${payload.path}\n✓ No errors`;
            }
            logAgent("info", `✓ ${payload.path} edited`);
            return `File edited: ${payload.path}`;
          }

          case "delete_file":
            logAgent("file", `Deleting: ${payload.path}`);
            await deleteFile(payload.path);
            logAgent("info", `✓ ${payload.path} deleted`);
            return `File deleted: ${payload.path}`;

          case "rename_file":
            logAgent("file", `Renaming: ${payload.old_path} → ${payload.new_path}`);
            await renameFile(payload.old_path, payload.new_path);
            logAgent("info", `✓ File renamed`);
            return `File renamed: ${payload.old_path} -> ${payload.new_path}`;

          case "create_directory":
            logAgent("file", `Creating directory: ${payload.path}`);
            await createDirectory(payload.path);
            logAgent("info", `✓ Directory created`);
            return `Directory created: ${payload.path}`;

          case "read_file":
            // Read file content
            const fileContent = await readFile(payload.path);
            return fileContent;

          case "list_files":
            // List directory contents
            const listPath = payload.path || "/";
            const recursive = payload.recursive || false;
            const fileList = await listFilesRecursive(listPath, recursive);
            return fileList;

          // Terminal operations
          case "shell": {
            // V2 shell tool - universal command execution
            // Handles full command strings like "npm install" or complex commands like "cd / && npm install"

            // Get the raw command string (prefer raw_command over reconstructing from command+args)
            let rawShellCommand = payload.raw_command || payload.command || "";

            // If command is provided separately with args, reconstruct full command
            if (!payload.raw_command && payload.command && payload.args) {
              const argsStr = Array.isArray(payload.args) ? payload.args.join(" ") : String(payload.args || "");
              rawShellCommand = `${payload.command} ${argsStr}`.trim();
            }

            console.log("[WebContainer] Shell raw command:", rawShellCommand);

            // Log the command to terminal
            logAgent("command", rawShellCommand);

            // Check if command contains shell operators that require jsh interpretation
            const shellOperators = /[;&|><]|\|\||&&/;
            const hasShellOperators = shellOperators.test(rawShellCommand);

            // Check for unsupported commands in WebContainer
            const unsupportedCommands = ["cd", "export", "source", "alias"];
            const firstWord = rawShellCommand.trim().split(/\s+/)[0];
            const isUnsupportedBuiltin = unsupportedCommands.includes(firstWord);

            if (isUnsupportedBuiltin && firstWord === "cd") {
              // Handle cd specially - WebContainer always starts in /
              // If command is just "cd" or "cd /", it's a no-op
              if (/^cd\s*\/?$/.test(rawShellCommand.trim())) {
                console.log("[WebContainer] Ignoring no-op cd command");
                logAgent("info", "Already in root directory /");
                return "Already in root directory /";
              }

              // If command is "cd /path && other_command", strip the cd part
              const cdAndMatch = rawShellCommand.match(/^cd\s+[^\s]+\s*&&\s*(.+)$/);
              if (cdAndMatch) {
                rawShellCommand = cdAndMatch[1].trim();
                console.log("[WebContainer] Stripped cd, running:", rawShellCommand);
              } else {
                // Just cd to a directory - warn user this doesn't persist
                console.warn("[WebContainer] cd command has no effect in WebContainer - each command runs in /");
                logAgent("info", "Note: cd has no effect in WebContainer");
                return "Note: cd has no effect in WebContainer. Each command runs from root /. Use absolute paths instead.";
              }
            }

            // Helper function to format shell output for Agent
            const formatShellResult = (output: string, command: string): string => {
              const cleanedOutput = cleanAnsiCodes(output).slice(-3000);

              // Check if command failed (new structured error format)
              if (cleanedOutput.startsWith(ERROR_PREFIX_COMMAND_FAILED)) {
                logAgent("error", `Command failed: ${command}`);
                // Return the detailed error info for Agent to understand
                return cleanedOutput;
              }

              // Success case
              const displayOutput = cleanedOutput || "(command completed with no output)";
              logAgent("output", displayOutput.slice(0, 500) + (displayOutput.length > 500 ? "..." : ""));
              return displayOutput;
            };

            // For commands with shell operators, use jsh to interpret them
            if (hasShellOperators) {
              console.log("[WebContainer] Using jsh for complex command:", rawShellCommand);
              const shellOutput = await runCommand("jsh", ["-c", rawShellCommand]);
              return formatShellResult(shellOutput, rawShellCommand);
            }

            // For simple commands, parse and execute directly
            const parts = rawShellCommand.trim().split(/\s+/);
            const shellCommand = parts[0] || "";
            const shellArgs = parts.slice(1);

            console.log("[WebContainer] Shell executing:", shellCommand, shellArgs);
            const shellOutput = await runCommand(shellCommand, shellArgs);
            return formatShellResult(shellOutput, rawShellCommand);
          }

          case "run_command": {
            // Type guard: ensure args is array (LLM might send string)
            let commandArgs = payload.args || [];
            if (typeof commandArgs === "string") {
              commandArgs = commandArgs.trim() ? commandArgs.trim().split(/\s+/) : [];
              console.warn("[WebContainer] Coerced args from string to array:", commandArgs);
            } else if (!Array.isArray(commandArgs)) {
              console.warn("[WebContainer] Unexpected args type, using empty array");
              commandArgs = [];
            }
            const fullCmd = `${payload.command} ${(commandArgs as string[]).join(" ")}`.trim();
            logAgent("command", fullCmd);
            const output = await runCommand(
              payload.command,
              commandArgs as string[]
            );
            const cleanedOutput = cleanAnsiCodes(output).slice(-3000);

            // Check for command failure
            if (cleanedOutput.startsWith(ERROR_PREFIX_COMMAND_FAILED)) {
              logAgent("error", `Command failed: ${fullCmd}`);
              return cleanedOutput;
            }

            const displayOutput = cleanedOutput || "(command completed with no output)";
            logAgent("output", displayOutput.slice(0, 500) + (displayOutput.length > 500 ? "..." : ""));
            return displayOutput;
          }

          case "install_dependencies": {
            // Type guard: ensure packages is array (LLM might send string)
            let packages = payload.packages || [];
            if (typeof packages === "string") {
              packages = packages.trim() ? packages.trim().split(/\s+/) : [];
              console.warn("[WebContainer] Coerced packages from string to array:", packages);
            } else if (!Array.isArray(packages)) {
              console.warn("[WebContainer] Unexpected packages type, using empty array");
              packages = [];
            }
            const pkgList = (packages as string[]).length > 0 ? (packages as string[]).join(" ") : "(all)";
            logAgent("command", `npm install ${pkgList}${payload.dev ? " --save-dev" : ""}`);
            const installOutput = await installDependencies(
              packages as string[],
              payload.dev || false
            );
            const cleanedInstall = cleanAnsiCodes(installOutput).slice(-3000);

            // Check for command failure
            if (cleanedInstall.startsWith(ERROR_PREFIX_COMMAND_FAILED)) {
              logAgent("error", `npm install failed`);
              return cleanedInstall;
            }

            const displayInstall = cleanedInstall || "(install completed with no output)";
            logAgent("output", displayInstall.slice(0, 500) + (displayInstall.length > 500 ? "..." : ""));
            return displayInstall;
          }

          case "start_dev_server":
            logAgent("command", "npm run dev");
            startDevServer(); // Don't await - runs in background
            logAgent("info", "Dev server starting in background...");
            return "Dev server starting...";

          case "stop_process":
            logAgent("command", "Stopping all processes");
            await stopProcess();
            logAgent("info", "All processes stopped");
            return "Processes stopped";

          case "create_terminal":
            const termId = createTerminal(payload.name);
            return `Terminal created: ${termId}`;

          case "switch_terminal":
            switchTerminal(payload.terminal_id);
            return `Switched to terminal: ${payload.terminal_id}`;

          case "send_terminal_input":
            await sendTerminalInput(payload.terminal_id, payload.input);
            return `Input sent to terminal: ${payload.terminal_id}`;

          case "kill_terminal":
            await killTerminal(payload.terminal_id);
            return `Terminal killed: ${payload.terminal_id}`;

          // Preview operations
          case "take_screenshot":
            const screenshot = await takeScreenshot(
              payload.selector,
              payload.full_page
            );
            // Check if result is an error object (JSON string)
            if (screenshot.startsWith('{') && screenshot.includes('"success":false')) {
              try {
                const errorObj = JSON.parse(screenshot);
                return `Screenshot failed: ${errorObj.message}\nSuggestion: ${errorObj.suggestion}`;
              } catch {
                // Not valid JSON, return as-is
              }
            }
            return screenshot; // Returns base64

          case "get_preview_dom":
            const dom = await getPreviewDOM(payload.selector, payload.depth);
            // Check if result is an error object (JSON string)
            if (dom.startsWith('{') && dom.includes('"success":false')) {
              try {
                const errorObj = JSON.parse(dom);
                return `DOM query failed: ${errorObj.message}\nSuggestion: ${errorObj.suggestion}`;
              } catch {
                // Not valid JSON, return as-is
              }
            }
            return dom;

          case "clear_console":
            clearConsole();
            return "Console cleared";

          case "get_visual_summary":
            const visualSummary = await getVisualSummary();
            // Check if result is an error object
            if (visualSummary.startsWith('{') && visualSummary.includes('"success":false')) {
              try {
                const errorObj = JSON.parse(visualSummary);
                return `Visual summary failed: ${errorObj.message}`;
              } catch {
                // Not valid JSON, return as-is
              }
            }
            return visualSummary;

          case "get_build_errors":
            logAgent("info", "Checking for build/compilation errors...");
            const buildErrors = await getBuildErrors();
            // Parse and format the response for better Agent understanding
            try {
              const errorsObj = JSON.parse(buildErrors);
              if (errorsObj.hasErrors && errorsObj.errorCount > 0) {
                // Format errors for Agent to understand and fix
                let formattedResponse = `⚠️ BUILD ERRORS DETECTED (${errorsObj.errorCount} error${errorsObj.errorCount > 1 ? 's' : ''}):\n\n`;
                errorsObj.errors.forEach((err: { type: string; message: string; file?: string; frame?: string; stack?: string; tip?: string }, idx: number) => {
                  formattedResponse += `--- Error ${idx + 1} (${err.type}) ---\n`;
                  if (err.file) formattedResponse += `File: ${err.file}\n`;
                  formattedResponse += `Message: ${err.message}\n`;
                  if (err.frame) formattedResponse += `Code Frame:\n${err.frame}\n`;
                  if (err.stack) formattedResponse += `Stack: ${err.stack.slice(0, 500)}\n`;
                  if (err.tip) formattedResponse += `Tip: ${err.tip}\n`;
                  formattedResponse += '\n';
                });
                formattedResponse += `\nPlease fix these errors in the affected files.`;
                logAgent("error", `Found ${errorsObj.errorCount} build error(s)`);
                return formattedResponse;
              } else {
                logAgent("info", "No build errors found");
                return "✅ No build errors detected. The preview is rendering correctly.";
              }
            } catch {
              // Return raw response if parsing fails
              return buildErrors;
            }

          // Get error overlay from state (passive - uses stored Vite errors)
          case "get_error_overlay": {
            logAgent("info", "Getting Vite error overlay from state...");
            const currentState = stateRef.current;
            const errorOverlay = currentState.preview?.errorOverlay;

            if (!errorOverlay) {
              logAgent("info", "No error overlay found in state");
              return JSON.stringify({
                success: true,
                has_error: false,
                message: "No Vite build errors detected in state",
              });
            }

            // Format error for Agent
            const formattedError = [
              `## 🔴 Vite Build Error`,
              ``,
              `**Plugin:** ${errorOverlay.plugin || "unknown"}`,
              `**File:** ${errorOverlay.file || "unknown"}`,
              `**Location:** Line ${errorOverlay.line || "?"}:${errorOverlay.column || "?"}`,
              ``,
              `### Error Message:`,
              "```",
              errorOverlay.message.slice(0, 2000),
              "```",
            ];

            if (errorOverlay.frame) {
              formattedError.push(
                ``,
                `### Code Frame:`,
                "```jsx",
                errorOverlay.frame,
                "```"
              );
            }

            if (errorOverlay.stack) {
              formattedError.push(
                ``,
                `### Stack Trace:`,
                "```",
                errorOverlay.stack.slice(0, 500),
                "```"
              );
            }

            formattedError.push(
              ``,
              `**Captured at:** ${new Date(errorOverlay.timestamp).toISOString()}`
            );

            logAgent("error", `Found Vite error in ${errorOverlay.file || "unknown file"}`);
            return formattedError.join("\n");
          }

          // Clear error overlay from state (after fixing the error)
          case "clear_error_overlay": {
            logAgent("info", "Clearing error overlay from state...");
            setState(prev => ({
              ...prev,
              preview: {
                ...prev.preview,
                hasError: false,
                errorMessage: undefined,
                errorOverlay: undefined,
              },
            }));
            return "Error overlay cleared";
          }

          // Get full state including error overlay
          case "get_state": {
            const currentState = stateRef.current;
            return JSON.stringify({
              status: currentState.status,
              preview: {
                url: currentState.preview?.url || currentState.previewUrl,
                has_error: currentState.preview?.hasError || false,
                error_message: currentState.preview?.errorMessage,
                error_overlay: currentState.preview?.errorOverlay ? {
                  message: currentState.preview.errorOverlay.message?.slice(0, 2000),
                  file: currentState.preview.errorOverlay.file,
                  line: currentState.preview.errorOverlay.line,
                  column: currentState.preview.errorOverlay.column,
                  plugin: currentState.preview.errorOverlay.plugin,
                  frame: currentState.preview.errorOverlay.frame,
                  timestamp: currentState.preview.errorOverlay.timestamp,
                } : null,
              },
              files_count: Object.keys(currentState.files).length,
              terminals_count: currentState.terminals.length,
            }, null, 2);
          }

          default:
            logAgent("error", `Unknown action type: ${type}`);
            return `Unknown action type: ${type}`;
        }
      } catch (error) {
        // ============================================
        // IMPROVED: Extract comprehensive error information
        // ============================================
        let errorMsg = "Unknown error";
        let errorStack = "";
        let errorDetails = "";

        if (error instanceof Error) {
          // Standard Error object
          errorMsg = error.message || error.name || "Error (no message)";
          if (error.stack) {
            errorStack = error.stack.slice(0, 800);
          }
          // Check for additional properties (e.g., cause, code)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const anyError = error as any;
          if (anyError.code) {
            errorDetails += `Code: ${anyError.code}\n`;
          }
          if (anyError.cause) {
            errorDetails += `Cause: ${String(anyError.cause)}\n`;
          }
        } else if (typeof error === "string") {
          errorMsg = error || "Empty error string";
        } else if (error && typeof error === "object") {
          // Object-like error (e.g., from WebContainer)
          try {
            errorMsg = JSON.stringify(error, null, 2).slice(0, 1000);
          } catch {
            errorMsg = String(error) || "Unserializable error object";
          }
        } else {
          errorMsg = String(error) || "Unknown error type";
        }

        console.error(`[WebContainer] Action failed: ${type}`, error);

        // Build comprehensive error response
        const errorResponse = [
          ERROR_PREFIX_ACTION_FAILED,
          `Action: ${type}`,
          `Error: ${errorMsg}`,
          errorDetails ? `\nDetails:\n${errorDetails}` : "",
          errorStack ? `\nStack Trace:\n${errorStack}` : "",
        ].filter(Boolean).join("\n");

        logAgent("error", `${type} failed: ${errorMsg}`);
        return errorResponse;
      }
    },
    [
      writeFile,
      readFile,
      editFile,
      deleteFile,
      renameFile,
      createDirectory,
      listFilesRecursive,
      runCommand,
      installDependencies,
      startDevServer,
      stopProcess,
      createTerminal,
      switchTerminal,
      sendTerminalInput,
      killTerminal,
      takeScreenshot,
      getPreviewDOM,
      getVisualSummary,
      getBuildErrors,
      clearConsole,
      logAgent,
      checkPreviewHealth,
    ]
  );

  // ============================================
  // Sync Files from WebContainer
  // ============================================

  /**
   * Read all files from WebContainer and update state
   * This ensures state.files is in sync with the actual WebContainer file system
   * Call this before export to ensure the latest content is exported
   */
  const syncFilesFromContainer = useCallback(async (): Promise<Record<string, string>> => {
    const instance = webcontainerRef.current;
    if (!instance) {
      console.log("[WebContainer] Not ready, returning current state files");
      return stateRef.current.files;
    }

    console.log("[WebContainer] Syncing files from container...");

    const syncedFiles: Record<string, string> = {};

    // Recursive function to read directory
    const readDir = async (dirPath: string) => {
      try {
        const entries = await instance.fs.readdir(dirPath, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = dirPath === "/" ? `/${entry.name}` : `${dirPath}/${entry.name}`;

          // Skip node_modules and hidden directories
          if (entry.name === "node_modules" || entry.name.startsWith(".")) {
            continue;
          }

          if (entry.isDirectory()) {
            await readDir(fullPath);
          } else if (entry.isFile()) {
            try {
              // Check if it's a binary file (image, etc.)
              const ext = entry.name.split('.').pop()?.toLowerCase() || '';
              const binaryExtensions = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'avif', 'heic', 'bmp', 'tiff', 'woff', 'woff2', 'ttf', 'eot', 'mp3', 'mp4', 'wav', 'ogg', 'pdf'];

              if (binaryExtensions.includes(ext)) {
                // For binary files, store a placeholder to show in file tree
                syncedFiles[fullPath] = `[Binary: ${ext.toUpperCase()} file]`;
              } else {
                const content = await instance.fs.readFile(fullPath, "utf-8");
                // Only include text files (skip binary)
                if (typeof content === "string" && !content.startsWith("[Binary")) {
                  syncedFiles[fullPath] = content as string;
                }
              }
            } catch (readError) {
              // Skip files that can't be read
              console.warn(`[WebContainer] Could not read file: ${fullPath}`);
            }
          }
        }
      } catch (dirError) {
        console.warn(`[WebContainer] Could not read directory: ${dirPath}`);
      }
    };

    await readDir("/");

    // Update state with synced files
    setState((prev) => ({
      ...prev,
      files: syncedFiles,
    }));

    console.log(`[WebContainer] Synced ${Object.keys(syncedFiles).length} files from container`);
    return syncedFiles;
  }, []);

  // ============================================
  // Return Hook Interface
  // ============================================

  return {
    // State
    state,

    // Core
    boot,

    // File operations
    writeFile,
    readFile,
    deleteFile,
    editFile,
    renameFile,
    createDirectory,
    syncFilesFromContainer,

    // Terminal operations
    createTerminal,
    runCommand,
    sendTerminalInput,
    killTerminal,
    switchTerminal,
    installDependencies,
    startDevServer,
    stopProcess,
    interruptProcess,
    clearTerminalHistory,
    // Interactive shell
    spawnShell,
    writeToShell,
    resizeShell,

    // Preview operations
    setPreviewIframe,
    takeScreenshot,
    getPreviewDOM,
    getVisualSummary,
    getBuildErrors,
    addConsoleMessage,
    clearConsole,
    setPreviewViewport,

    // Diff operations
    clearFileDiffs,
    clearFileDiff,

    // Action handler for Agent
    handleAction,

    // Expose webcontainerRef for external image downloader
    webcontainerRef,
  };
}
