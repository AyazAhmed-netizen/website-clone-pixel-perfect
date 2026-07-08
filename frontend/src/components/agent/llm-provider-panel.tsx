"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle, XCircle, Loader2, Save, FlaskConical, ChevronDown, Plus, Trash2, RefreshCw, Zap } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  groq: "Groq",
  mistral: "Mistral",
  azure_openai: "Azure OpenAI",
  custom_openai_compatible: "Custom (OpenAI-compatible)",
  custom_anthropic_compatible: "Custom (Anthropic-compatible)",
};

const PROVIDER_BASE_URL_PLACEHOLDER: Record<string, string> = {
  anthropic: "https://api.anthropic.com (optional)",
  openai: "https://api.openai.com/v1 (optional)",
  groq: "https://api.groq.com/openai/v1",
  mistral: "https://api.mistral.ai/v1",
  azure_openai: "https://<resource>.openai.azure.com/openai/deployments",
  custom_openai_compatible: "https://your-endpoint/v1",
  custom_anthropic_compatible: "https://your-endpoint/v1",
};

// Providers that always need a base URL
const REQUIRES_BASE_URL = new Set([
  "groq",
  "mistral",
  "azure_openai",
  "custom_openai_compatible",
  "custom_anthropic_compatible",
]);

type Status = "idle" | "testing" | "applying" | "ok" | "error";

interface ProviderEntry {
  id: string;
  provider: string;
  model: string;
  base_url: string;
  models: string[];
  is_active: boolean;
  last_tested: string | null;
  test_status: string | null;
  test_error: string | null;
  has_api_key: boolean;
}

export function LLMProviderPanel() {
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [providerTypes, setProviderTypes] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newProvider, setNewProvider] = useState({
    provider: "",
    model: "",
    apiKey: "",
    baseUrl: "",
  });

  // Load providers on mount
  const loadProviders = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers`);
      const data = await res.json();
      setProviderTypes(data.provider_types || []);
      setProviders(data.providers || []);
    } catch {
      console.error("Failed to load providers");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  // Handle activating a provider
  const activateProvider = useCallback(async (providerId: string) => {
    setStatus("applying");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers/${providerId}/activate`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.success) {
        setStatus("ok");
        setMessage("Provider activated successfully!");
        await loadProviders();
      } else {
        setStatus("error");
        setMessage(data.detail || "Failed to activate provider");
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Network error");
    }
  }, [loadProviders]);

  // Handle testing a provider
  const testProvider = useCallback(async (providerId: string) => {
    setStatus("testing");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers/${providerId}/test`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.success) {
        setStatus("ok");
        setMessage("Connection OK!");
        await loadProviders();
      } else {
        setStatus("error");
        setMessage(data.error || "Test failed");
        await loadProviders();
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Network error");
    }
  }, [loadProviders]);

  // Handle fetching models for a provider
  const fetchModels = useCallback(async (providerId: string) => {
    setStatus("applying");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers/${providerId}/fetch-models`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.success) {
        setStatus("ok");
        setMessage("Models fetched successfully!");
        await loadProviders();
      } else {
        setStatus("error");
        setMessage(data.detail || "Failed to fetch models");
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Network error");
    }
  }, [loadProviders]);

  // Handle deleting a provider
  const deleteProvider = useCallback(async (providerId: string) => {
    setStatus("applying");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers/${providerId}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (data.success) {
        setStatus("ok");
        setMessage("Provider deleted!");
        await loadProviders();
      } else {
        setStatus("error");
        setMessage(data.detail || "Failed to delete provider");
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Network error");
    }
  }, [loadProviders]);

  // Handle adding a new provider
  const addProvider = useCallback(async () => {
    setStatus("applying");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/llm/providers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: newProvider.provider,
          model: newProvider.model,
          api_key: newProvider.apiKey,
          base_url: newProvider.baseUrl || undefined,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setStatus("ok");
        setMessage("Provider added!");
        setShowAddForm(false);
        setNewProvider({ provider: "", model: "", apiKey: "", baseUrl: "" });
        await loadProviders();
      } else {
        setStatus("error");
        setMessage(data.detail || "Failed to add provider");
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Network error");
    }
  }, [newProvider, loadProviders]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-neutral-500">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading providers…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-sm w-full">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">
          AI Provider Settings
        </span>
        <button
          type="button"
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded-lg bg-violet-600 hover:bg-violet-700 text-white"
        >
          <Plus className="h-3 w-3" /> Add Provider
        </button>
      </div>

      {/* Status message */}
      {message && (
        <p
          className={`text-xs rounded-lg px-3 py-2 ${
            status === "ok"
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
          }`}
        >
          {message}
        </p>
      )}

      {/* Add Provider Form */}
      {showAddForm && (
        <div className="p-3 border border-neutral-200 dark:border-neutral-700 rounded-lg bg-neutral-50 dark:bg-neutral-800">
          <h4 className="text-xs font-medium mb-2">Add New Provider</h4>
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Provider</label>
              <div className="relative">
                <select
                  className="w-full appearance-none rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 px-3 py-2 pr-8 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={newProvider.provider}
                  onChange={(e) => setNewProvider({ ...newProvider, provider: e.target.value })}
                >
                  <option value="">Select a provider</option>
                  {providerTypes.map((p) => (
                    <option key={p} value={p}>
                      {PROVIDER_LABELS[p] ?? p}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Model</label>
              <input
                className="w-full rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
                value={newProvider.model}
                onChange={(e) => setNewProvider({ ...newProvider, model: e.target.value })}
                placeholder="e.g. gpt-4o-mini"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400">
                Base URL{newProvider.provider && REQUIRES_BASE_URL.has(newProvider.provider) ? " *" : " (optional)"}
              </label>
              <input
                className="w-full rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
                value={newProvider.baseUrl}
                onChange={(e) => setNewProvider({ ...newProvider, baseUrl: e.target.value })}
                placeholder={newProvider.provider ? PROVIDER_BASE_URL_PLACEHOLDER[newProvider.provider] : "https://..."}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400">API Key *</label>
              <input
                type="password"
                className="w-full rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
                value={newProvider.apiKey}
                onChange={(e) => setNewProvider({ ...newProvider, apiKey: e.target.value })}
                placeholder="sk-..."
              />
            </div>
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  setShowAddForm(false);
                  setNewProvider({ provider: "", model: "", apiKey: "", baseUrl: "" });
                }}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={addProvider}
                disabled={!newProvider.provider || !newProvider.model || !newProvider.apiKey}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Save className="h-3.5 w-3.5" /> Add
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Provider List */}
      <div className="flex flex-col gap-2">
        {providers.length === 0 ? (
          <p className="text-xs text-neutral-500 text-center py-4">
            No providers configured. Add one above!
          </p>
        ) : (
          providers.map((p) => (
            <div
              key={p.id}
              className={`p-3 border rounded-lg flex flex-col gap-2 ${
                p.is_active
                  ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
                  : "border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-neutral-800 dark:text-neutral-100">
                    {PROVIDER_LABELS[p.provider] ?? p.provider}
                  </span>
                  {p.is_active && (
                    <span className="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400">
                      <Zap className="h-3 w-3" /> Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {p.test_status === "ok" && (
                    <CheckCircle className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                  )}
                  {p.test_status === "error" && (
                    <XCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
                  )}
                </div>
              </div>
              <div className="text-xs text-neutral-600 dark:text-neutral-400">
                Model: <span className="font-medium">{p.model}</span>
              </div>
              <div className="flex gap-1.5 pt-1">
                {!p.is_active && (
                  <button
                    type="button"
                    onClick={() => activateProvider(p.id)}
                    className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs font-medium bg-violet-600 hover:bg-violet-700 text-white transition-colors"
                  >
                    <Zap className="h-3 w-3" /> Activate
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => testProvider(p.id)}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs font-medium border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                >
                  <FlaskConical className="h-3 w-3" /> Test
                </button>
                <button
                  type="button"
                  onClick={() => fetchModels(p.id)}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-xs font-medium border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Fetch Models
                </button>
                <button
                  type="button"
                  onClick={() => deleteProvider(p.id)}
                  className="px-2 py-1 rounded text-xs font-medium border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
              {p.models.length > 0 && (
                <div className="text-xs text-neutral-500">
                  Available models: {p.models.slice(0, 5).join(", ")}
                  {p.models.length > 5 && ` +${p.models.length - 5} more`}
                </div>
              )}
              {p.test_error && (
                <div className="text-xs text-red-600 dark:text-red-400">
                  Test error: {p.test_error}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
