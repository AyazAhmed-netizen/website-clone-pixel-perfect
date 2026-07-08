"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { getSource } from "@/lib/api/sources";
import { cn } from "@/lib/utils";
import { useBoxLite } from "@/hooks/use-boxlite";
import { BoxLiteIDE } from "./boxlite-ide";
import { ProjectHeader } from "./project-header";
import { SourcePanel, type SavedSource } from "./source-panel";
import { CheckpointPanel } from "./checkpoint-panel";
import { AppSidebar } from "@/components/app-sidebar";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { NextingAgentChatPanel } from "@/components/agent/chat-panel";

import type { ChatMessage, ToolCall, ContentBlock } from "@/types/agent";
import type { BoxLiteSandboxState } from "@/types/boxlite";

interface SelectedSource {
  id: string;
  title: string;
  url: string;
  theme: "light" | "dark";
}

export function BoxLiteAgentPage() {
  const searchParams = useSearchParams();
  const sourceIdParam = searchParams.get("source");
  const themeParam = searchParams.get("theme") as "light" | "dark" | null;
  const autoCloneParam = searchParams.get("autoClone") === "true";
  const checkpointParam = searchParams.get("checkpoint");
  const projectParam = searchParams.get("project");

  const {
    state,
    isConnected,
    isInitialized,
    error,
    readFile,
    writeFile,
    runCommand,
    startDevServer,
    stopDevServer,
    getTerminalOutput,
    sendTerminalInput,
    executeTool,
    agentLogs,
    addAgentLog,
    clearAgentLogs,
    restoreAgentLogs,
    fileDiffs,
    clearFileDiff,
    updateState,
  } = useBoxLite({
    autoInit: true,
    onFileWritten: (path) => console.log("[Sandbox] File written:", path),
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [chatPanelWidth, setChatPanelWidth] = useState(380);
  const [showChatPanel, setShowChatPanel] = useState(true);
  const [showSourcePanel, setShowSourcePanel] = useState(false);
  const [showCheckpointPanel, setShowCheckpointPanel] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [selectedSource, setSelectedSource] = useState<SelectedSource | null>(null);
  const [isAgentLoading, setIsAgentLoading] = useState(false);
  const [checkpointProjectId, setCheckpointProjectId] = useState<string | null>(null);
  const [autoCloneTriggered, setAutoCloneTriggered] = useState(false);
  const [shouldAutoSend, setShouldAutoSend] = useState(false);
  const [autoRestoreTriggered, setAutoRestoreTriggered] = useState(false);
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [restoreDialogData, setRestoreDialogData] = useState<{ checkpointId: string; projectId: string } | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

  const handleFileSelect = useCallback(async (path: string) => {
    setSelectedFile(path);
    const content = await readFile(path);
    setFileContent(content || "");
  }, [readFile]);

  const handleSaveFile = useCallback(async () => {
    if (selectedFile && fileContent) {
      await writeFile(selectedFile, fileContent);
      addAgentLog({ type: "file", content: `Saved: ${selectedFile}`, timestamp: Date.now() });
    }
  }, [selectedFile, fileContent, writeFile, addAgentLog]);

  const handleFileCreate = useCallback(async (path: string, content: string) => {
    await writeFile(path, content);
  }, [writeFile]);

  const handleFileDelete = useCallback(async (path: string) => {
    await executeTool("delete_file", { path });
  }, [executeTool]);

  const handleTerminalInput = useCallback(async (input: string) => {
    const terminalId = state?.active_terminal_id;
    if (terminalId) await sendTerminalInput(terminalId, input);
    else await runCommand(input.trim());
  }, [state, sendTerminalInput, runCommand]);

  const handleBoxLiteStateUpdate = useCallback((newState: BoxLiteSandboxState) => {
    updateState(newState);
  }, [updateState]);

  const handleClearFileDiffs = useCallback(() => {
    Object.keys(fileDiffs.diffs).forEach((path) => clearFileDiff(path));
  }, [fileDiffs.diffs, clearFileDiff]);

  const ensureCheckpointProject = useCallback(async (sourceId: string, sourceTitle: string, sourceUrl: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/checkpoints/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: sourceTitle || `Clone ${sourceId.slice(0, 8)}`, source_id: sourceId, source_url: sourceUrl }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.project?.id) {
          setCheckpointProjectId(data.project.id);
          return data.project.id;
        }
      }
    } catch (e) {
      console.error("[Checkpoint] Failed to create/get project:", e);
    }
    return null;
  }, [API_BASE]);

  const handleSelectSource = useCallback(async (source: SavedSource) => {
    setSelectedSource({ id: source.id, title: source.page_title || "Untitled", url: source.source_url, theme: source.metadata?.theme || "light" });
    await ensureCheckpointProject(source.id, source.page_title || "Untitled", source.source_url);
  }, [ensureCheckpointProject]);

  const handleSaveCheckpoint = useCallback(async () => {
    if (!checkpointProjectId || !state) return;
    try {
      const displayName = projectName || selectedSource?.title || "Project";
      const checkpointName = `${displayName} - Manual save (${new Date().toLocaleTimeString()})`;
      await fetch(`${API_BASE}/api/checkpoints/projects/${checkpointProjectId}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: checkpointName,
          conversation: messages.map(m => ({ id: m.id, role: m.role, content: m.content, timestamp: m.timestamp, toolCalls: m.toolCalls || [], contentBlocks: m.contentBlocks || [], isThinking: m.isThinking, images: m.images })),
          files: state.files || {},
          metadata: { manual: true, source_id: selectedSource?.id, project_name: displayName, agent_logs: agentLogs.slice(-100) },
        }),
      });
    } catch (e) {
      console.error("[Checkpoint] Failed to save:", e);
    }
  }, [checkpointProjectId, state, messages, selectedSource, agentLogs, projectName, API_BASE]);

  const handleRestoreCheckpoint = useCallback((checkpointId: string, projectId: string) => {
    const targetProjectId = projectId || checkpointProjectId;
    if (!targetProjectId) { alert("No project ID provided for restore"); return; }
    setRestoreDialogData({ checkpointId, projectId: targetProjectId });
    setRestoreDialogOpen(true);
  }, [checkpointProjectId]);

  const performRestore = useCallback(async () => {
    if (!restoreDialogData) return;
    setIsRestoring(true);
    try {
      const { checkpointId, projectId: targetProjectId } = restoreDialogData;
      const sandboxId = state?.sandbox_id || "default";
      const response = await fetch(`${API_BASE}/api/boxlite/sandbox/${sandboxId}/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: targetProjectId, checkpoint_id: checkpointId }),
      });
      if (!response.ok) throw new Error(`Backend restore failed: ${response.status}`);
      const data = await response.json();
      if (!data.success) throw new Error("Backend restore returned failure");
      const checkpoint = data.checkpoint;
      sessionStorage.setItem("checkpoint_restore", JSON.stringify({
        conversation: checkpoint.conversation || [],
        agentLogs: checkpoint.metadata?.agent_logs || [],
        checkpointName: checkpoint.name,
        projectId: targetProjectId,
        timestamp: Date.now(),
      }));
      window.location.reload();
    } catch (e) {
      alert(`Failed to restore: ${e instanceof Error ? e.message : "Unknown error"}`);
      setIsRestoring(false);
      setRestoreDialogOpen(false);
      setRestoreDialogData(null);
    }
  }, [restoreDialogData, state, API_BASE]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  // Restore from sessionStorage after page reload
  useEffect(() => {
    const raw = sessionStorage.getItem("checkpoint_restore");
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      if (Date.now() - (data.timestamp || 0) > 30000) { sessionStorage.removeItem("checkpoint_restore"); return; }
      if (data.conversation?.length > 0) {
        setMessages(data.conversation.map((msg: any, i: number) => ({
          id: msg.id || `restored-${i}-${Date.now()}`,
          role: msg.role as "user" | "assistant",
          content: msg.content,
          timestamp: msg.timestamp || Date.now(),
          toolCalls: msg.toolCalls || [],
          contentBlocks: msg.contentBlocks || [],
          isThinking: msg.isThinking || false,
          images: msg.images,
        })));
      }
      if (data.agentLogs?.length > 0) restoreAgentLogs(data.agentLogs);
      if (data.projectId) setCheckpointProjectId(data.projectId);
      setShowCheckpointPanel(true);
      addAgentLog({ type: "info", content: `✓ Restored checkpoint: "${data.checkpointName}"`, timestamp: Date.now() });
      sessionStorage.removeItem("checkpoint_restore");
    } catch (e) {
      sessionStorage.removeItem("checkpoint_restore");
    }
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;
      const newWidth = e.clientX - containerRef.current.getBoundingClientRect().left;
      setChatPanelWidth(Math.max(280, Math.min(600, newWidth)));
    };
    const handleMouseUp = () => setIsResizing(false);
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
    }
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
  }, [isResizing]);

  useEffect(() => {
    if (!sourceIdParam || autoCloneTriggered || !isInitialized) return;
    setAutoCloneTriggered(true);
    (async () => {
      try {
        const result = await getSource(sourceIdParam);
        if (result.success && result.source) {
          const source = result.source;
          setSelectedSource({ id: source.id, title: source.page_title || "Untitled", url: source.source_url, theme: themeParam || source.metadata?.theme || "light" });
          await ensureCheckpointProject(source.id, source.page_title || "Untitled", source.source_url);
          setShowSourcePanel(true);
          if (autoCloneParam) setTimeout(() => setShouldAutoSend(true), 500);
        }
      } catch (err) {
        console.error("[AutoClone] Error:", err);
      }
    })();
  }, [sourceIdParam, themeParam, autoCloneParam, autoCloneTriggered, isInitialized, ensureCheckpointProject]);

  useEffect(() => {
    if (!checkpointParam || !projectParam || autoRestoreTriggered || !isInitialized || !state?.sandbox_id) return;
    setAutoRestoreTriggered(true);
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/boxlite/sandbox/${state.sandbox_id}/restore`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_id: projectParam, checkpoint_id: checkpointParam }),
        });
        if (!response.ok) throw new Error(`${response.status}`);
        const data = await response.json();
        if (!data.success) throw new Error("restore failed");
        const checkpoint = data.checkpoint;
        sessionStorage.setItem("checkpoint_restore", JSON.stringify({
          conversation: checkpoint.conversation || [],
          agentLogs: checkpoint.metadata?.agent_logs || [],
          checkpointName: checkpoint.name,
          projectId: projectParam,
          timestamp: Date.now(),
        }));
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.delete("checkpoint");
        newUrl.searchParams.delete("project");
        window.location.href = newUrl.toString();
      } catch (e) {
        addAgentLog({ type: "error", content: `Failed to restore demo: ${e instanceof Error ? e.message : "Unknown error"}`, timestamp: Date.now() });
      }
    })();
  }, [checkpointParam, projectParam, autoRestoreTriggered, isInitialized, state, addAgentLog, API_BASE]);

  if (!isInitialized) {
    return (
      <div className="flex h-screen bg-white dark:bg-neutral-900">
        <AppSidebar currentPage="agent" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-neutral-900 dark:text-white">
            <RefreshCw className="h-12 w-12 animate-spin mx-auto mb-4 text-violet-500" />
            <p className="text-lg font-medium">Initializing Nexting Agent...</p>
            {error && <p className="text-red-500 mt-2">{error}</p>}
          </div>
        </div>
      </div>
    );
  }

  const getStatus = () => {
    if (!isConnected) return "idle";
    if (state?.status === "ready") return "ready";
    if (state?.status === "error") return "error";
    return "booting";
  };

  return (
    <div className="flex h-screen bg-white dark:bg-neutral-900">
      <AppSidebar currentPage="agent" />

      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        <ProjectHeader
          projectName={projectName}
          showChatPanel={showChatPanel}
          onToggleChatPanel={() => setShowChatPanel(!showChatPanel)}
          showSourcePanel={showSourcePanel}
          onToggleSourcePanel={() => setShowSourcePanel(!showSourcePanel)}
          showCheckpointPanel={showCheckpointPanel}
          onToggleCheckpointPanel={() => setShowCheckpointPanel(!showCheckpointPanel)}
          status={getStatus()}
        />

        <div ref={containerRef} className="flex-1 flex overflow-hidden min-h-0">
          {/* Chat Panel */}
          <div
            className="flex-shrink-0 overflow-hidden"
            style={{ width: `${chatPanelWidth}px`, display: showChatPanel ? "block" : "none" }}
          >
            {state?.sandbox_id ? (
              <NextingAgentChatPanel
                mode="boxlite"
                sandboxId={state.sandbox_id}
                boxliteState={state}
                onBoxLiteStateUpdate={handleBoxLiteStateUpdate}
                messages={messages}
                onMessagesChange={setMessages}
                onClearFileDiffs={handleClearFileDiffs}
                selectedSource={selectedSource}
                onClearSource={() => setSelectedSource(null)}
                onLoadingChange={setIsAgentLoading}
                onProjectNameGenerated={setProjectName}
                shouldAutoSend={shouldAutoSend}
                onAutoSendComplete={() => setShouldAutoSend(false)}
                onTriggerCheckpointSave={handleSaveCheckpoint}
              />
            ) : (
              <div className="h-full flex items-center justify-center bg-neutral-50 dark:bg-neutral-900 text-neutral-500">
                <div className="text-center">
                  <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
                  <p>Connecting to sandbox...</p>
                </div>
              </div>
            )}
          </div>

          {/* Resizable Divider */}
          <div
            className={cn(
              "flex-shrink-0 cursor-col-resize relative group transition-all duration-150",
              "w-px bg-neutral-200 dark:bg-neutral-700",
              "hover:w-1 hover:bg-violet-500 dark:hover:bg-violet-500",
              isResizing && "w-1 bg-violet-500 dark:bg-violet-500"
            )}
            style={{ display: showChatPanel ? "block" : "none" }}
            onMouseDown={handleMouseDown}
          >
            <div className={cn("absolute inset-y-0 -left-1 -right-1 group-hover:bg-violet-500/10", isResizing && "bg-violet-500/10")} />
          </div>

          {/* IDE Panel */}
          <div className="flex-1 overflow-hidden min-w-0">
            <BoxLiteIDE
              state={state}
              isConnected={isConnected}
              agentLogs={agentLogs}
              fileDiffs={fileDiffs}
              onFileSelect={handleFileSelect}
              onFileCreate={handleFileCreate}
              onFileDelete={handleFileDelete}
              onDiffClear={clearFileDiff}
              onWriteFile={writeFile}
              onTerminalInput={handleTerminalInput}
              getTerminalOutput={getTerminalOutput}
              selectedFile={selectedFile}
              fileContent={fileContent}
              onContentChange={setFileContent}
              onSaveFile={handleSaveFile}
              isResizing={isResizing}
              selectedSource={selectedSource}
              projectName={projectName || selectedSource?.title || "nexting-project"}
            />
          </div>

          {/* Source Panel */}
          {showSourcePanel && (
            <>
              <div className="flex-shrink-0 w-px bg-neutral-200 dark:bg-neutral-700" />
              <div className="flex-shrink-0 w-72 overflow-hidden">
                <SourcePanel selectedSourceId={selectedSource?.id} disabled={isAgentLoading} onSelectSource={handleSelectSource} />
              </div>
            </>
          )}

          {/* Checkpoint Panel */}
          {showCheckpointPanel && (
            <>
              <div className="flex-shrink-0 w-px bg-neutral-200 dark:bg-neutral-700" />
              <div className="flex-shrink-0 w-72 overflow-hidden">
                <CheckpointPanel projectId={checkpointProjectId} onSaveCheckpoint={handleSaveCheckpoint} onRestoreCheckpoint={handleRestoreCheckpoint} disabled={isAgentLoading} />
              </div>
            </>
          )}
        </div>
      </main>

      <ConfirmDialog
        isOpen={restoreDialogOpen}
        onClose={() => { setRestoreDialogOpen(false); setRestoreDialogData(null); }}
        onConfirm={performRestore}
        title="Restore Checkpoint?"
        description="This will refresh the page and restore all files, conversation history, and logs to the selected checkpoint. Any unsaved changes will be lost."
        confirmText="Restore"
        cancelText="Cancel"
        variant="warning"
        isLoading={isRestoring}
      />
    </div>
  );
}

export default BoxLiteAgentPage;
