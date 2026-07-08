/**
 * Codegen Configuration
 */

export const CODEGEN_CONFIG = {
  // Backend API URL
  API_URL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001",

  // Claude/OpenAI API settings are configured via the provider settings UI.
  // IMPORTANT: no hardcoded API keys in frontend source.
  CLAUDE_API_KEY: process.env.CLAUDE_PROXY_API_KEY || "",
  CLAUDE_BASE_URL: process.env.CLAUDE_PROXY_BASE_URL || "https://api.anthropic.com/v1/messages",
  CLAUDE_MODEL: process.env.CLAUDE_PROXY_MODEL || "",

  // Extraction settings
  DEFAULT_VIEWPORT_WIDTH: 1920,
  DEFAULT_VIEWPORT_HEIGHT: 1080,
  MAX_EXTRACTION_TIMEOUT: 60000,
  
  // Token estimation
  CHARS_PER_TOKEN: 4,
  MAX_TOKENS_PER_SECTION: 8000,
} as const;