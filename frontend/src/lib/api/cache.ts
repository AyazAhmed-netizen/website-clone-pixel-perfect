/**
 * Cache API Client
 * 缓存 API 客户端
 *
 * Provides functions to interact with the backend memory cache:
 * - Store extraction results for Agent to use
 * - List available cached extractions
 * - Get/delete cached data
 *
 * Replaces Supabase JSON storage for the open-source version.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

/**
 * Cached extraction entry (summary from list endpoint)
 * 缓存的提取结果条目（列表接口返回的摘要）
 */
export interface CachedExtraction {
  id: string;
  url: string;
  title: string | null;
  timestamp: number | string;  // Unix timestamp (number) or ISO string
  created_at?: string;         // ISO string format
  expires_at?: string;         // ISO string format
  size_bytes?: number;
  top_keys?: string[];
  data?: Record<string, unknown>;  // Optional - only present in full response
}

/**
 * Full cached extraction with data
 * 完整的缓存条目（包含数据）
 */
export interface CachedExtractionFull extends CachedExtraction {
  data: Record<string, unknown>;
}

/**
 * Store extraction result to cache
 * 存储提取结果到缓存
 *
 * @param params - Store parameters
 * @returns Store result with cache ID
 */
export async function saveToCache(params: {
  url: string;
  data: Record<string, unknown>;
  title?: string;
}): Promise<{ success: boolean; id?: string; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/api/cache/store`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: params.url,
        data: params.data,
        title: params.title,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: result.detail || "Failed to store to cache",
      };
    }

    return {
      success: true,
      id: result.id,
    };
  } catch (error) {
    console.error("Save to cache error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Get list of all cached extractions
 * 获取所有缓存的提取结果列表
 *
 * @returns List of cached extractions
 */
export async function getCacheList(): Promise<{
  success: boolean;
  items?: CachedExtraction[];
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/cache/list`);

    const result = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: result.detail || "Failed to get cache list",
      };
    }

    return {
      success: true,
      items: result.items || [],
    };
  } catch (error) {
    console.error("Get cache list error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Get a single cached extraction with full data
 * 获取单个缓存条目（包含完整数据）
 *
 * @param id - Cache entry ID
 * @returns Full cached extraction
 */
export async function getCacheItem(id: string): Promise<{
  success: boolean;
  item?: CachedExtractionFull;
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/cache/${id}`);

    const result = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: result.detail || "Cache entry not found",
      };
    }

    return {
      success: true,
      item: result,
    };
  } catch (error) {
    console.error("Get cache item error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Delete a cached extraction
 * 删除缓存条目
 *
 * @param id - Cache entry ID
 * @returns Delete result
 */
export async function deleteCacheItem(id: string): Promise<{
  success: boolean;
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/cache/${id}`, {
      method: "DELETE",
    });

    const result = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: result.detail || "Failed to delete cache entry",
      };
    }

    return { success: true };
  } catch (error) {
    console.error("Delete cache item error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Get cache statistics
 * 获取缓存统计信息
 *
 * @returns Cache statistics
 */
export async function getCacheStats(): Promise<{
  success: boolean;
  stats?: {
    total_entries: number;
    max_entries: number;
    total_size_bytes: number;
    total_size_mb: number;
    default_ttl_hours: number;
  };
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/cache/stats`);

    const result = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: result.detail || "Failed to get cache stats",
      };
    }

    return {
      success: true,
      stats: result,
    };
  } catch (error) {
    console.error("Get cache stats error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
