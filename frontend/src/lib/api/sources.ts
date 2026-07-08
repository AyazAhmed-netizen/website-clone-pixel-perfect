/**
 * Sources API Client
 * 数据源 API 客户端
 *
 * 提取的网站数据保存到文件系统:
 * - 存储在 backend/data/sources/ 目录下
 * - 每个 source 是一个 JSON 文件
 * - 用户可以直接查看这些文件
 * - Source Panel 自动显示这些数据
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

/**
 * Saved source entry
 */
export interface SavedSource {
  id: string;
  source_url: string;
  page_title: string | null;
  json_size: number;
  top_keys: string[];
  metadata: {
    viewport?: { width: number; height: number };
    extracted_at?: string;
    theme?: "light" | "dark";
  };
  created_at: string;
  updated_at: string;
  data?: Record<string, unknown>;
}

/**
 * Save extraction result to sources (file system)
 * 保存提取结果到 Sources（文件系统）
 *
 * 数据会保存到 backend/data/sources/{id}.json
 *
 * @param params - Save parameters
 * @returns Save result with source ID
 */
export async function saveToSources(params: {
  url: string;
  data: Record<string, unknown>;
  title?: string;
  theme?: "light" | "dark";
}): Promise<{ success: boolean; id?: string; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/api/sources`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source_url: params.url,
        page_title: params.title,
        data: params.data,
        metadata: {
          extracted_at: new Date().toISOString(),
          theme: params.theme || "light",
        },
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();

    if (result.success && result.source) {
      return {
        success: true,
        id: result.source.id,
      };
    } else {
      return {
        success: false,
        error: result.error || "Unknown error",
      };
    }
  } catch (error) {
    console.error("[Sources] Save error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to save to sources",
    };
  }
}

/**
 * Get all saved sources
 * 获取所有保存的 sources
 */
export async function getSources(): Promise<{
  success: boolean;
  sources?: SavedSource[];
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/sources`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return {
      success: true,
      sources: result.sources || [],
    };
  } catch (error) {
    console.error("[Sources] Fetch error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch sources",
    };
  }
}

/**
 * Get a single source with full data
 * 获取单个 source（包含完整数据）
 */
export async function getSource(sourceId: string): Promise<{
  success: boolean;
  source?: SavedSource;
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/sources/${sourceId}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return {
      success: true,
      source: result.source,
    };
  } catch (error) {
    console.error("[Sources] Fetch error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch source",
    };
  }
}

/**
 * Delete a source
 * 删除 source
 */
export async function deleteSource(sourceId: string): Promise<{
  success: boolean;
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE}/api/sources/${sourceId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return { success: true };
  } catch (error) {
    console.error("[Sources] Delete error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete source",
    };
  }
}
