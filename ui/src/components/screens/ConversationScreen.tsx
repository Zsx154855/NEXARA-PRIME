"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  ConversationAttachmentRef,
  ConversationDetail,
  ConversationExecutionMode,
  ConversationMessage,
} from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { Lock, MessageSquare, RefreshCw, Send, Unlock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { cn } from "@/lib/utils";
import { ConversationList } from "./conversation/ConversationList";
import { MessageFlow } from "./conversation/MessageFlow";
import { ThinkingState } from "./conversation/ThinkingState";
import { PromptCraft } from "./conversation/PromptCraft";
import { AttachmentBar, type PendingAttachment } from "./conversation/AttachmentBar";

// ── Props ──

interface ConversationScreenProps {
  api: NexaraAPI;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
}

// ── Constants ──

const MODES: { id: ConversationExecutionMode; label: string }[] = [
  { id: "chat", label: "对话" },
  { id: "auto", label: "自动" },
  { id: "mission", label: "使命" },
];

// ── Main ──

export function ConversationScreen({
  api,
  onMissionSelect,
  onViewApprovals,
}: ConversationScreenProps) {
  const [conversations, setConversations] = useState<ConversationDetail[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<"open" | "closed">("open");
  const [title, setTitle] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [sending, setSending] = useState(false);
  const [mutatingStatus, setMutatingStatus] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ConversationExecutionMode>("auto");
  const [draft, setDraft] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);

  const isClosed = status === "closed";

  const loadList = useCallback(async () => {
    try {
      const list = await api.getConversations();
      setConversations(list);
      return list;
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载对话列表");
      return null;
    } finally {
      setLoadingList(false);
    }
  }, [api]);

  const loadConversation = useCallback(
    async (conversationId: string) => {
      try {
        const detail = await api.getConversation(conversationId);
        setTitle(detail.title);
        setStatus(detail.status);
        setMessages(detail.messages ?? []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "无法加载对话");
      }
    },
    [api],
  );

  // Initial load — server is the source of truth (persistence after reload).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const list = await loadList();
      if (cancelled || !list) return;
      const mostRecent = list[0] ?? null;
      if (mostRecent) {
        setActiveId(mostRecent.conversation_id);
        await loadConversation(mostRecent.conversation_id);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadList, loadConversation]);

  const refreshList = async (): Promise<void> => {
    await loadList();
  };

  const handleSelect = async (conversationId: string): Promise<void> => {
    setActiveId(conversationId);
    setDraft("");
    setPendingAttachments([]);
    setError(null);
    await loadConversation(conversationId);
  };

  const handleCreate = async (): Promise<void> => {
    setError(null);
    try {
      const created = await api.createConversation();
      setActiveId(created.conversation_id);
      setTitle(created.title);
      setStatus(created.status);
      setMessages([]);
      setDraft("");
      setPendingAttachments([]);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建对话失败");
    }
  };

  const handlePickFiles = (files: File[]): void => {
    if (!activeId) return;
    const conversationId = activeId;
    for (const file of files) {
      const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const kind = file.type.startsWith("image/")
        ? "image"
        : file.type.startsWith("video/")
          ? "video"
          : "file";
      setPendingAttachments((prev) => [
        ...prev,
        { localId, name: file.name, kind, status: "uploading" },
      ]);
      api
        .uploadAttachment(conversationId, file)
        .then((record) => {
          setPendingAttachments((prev) =>
            prev.map((item) =>
              item.localId === localId ? { ...item, status: "ready", record } : item,
            ),
          );
        })
        .catch((err: unknown) => {
          setPendingAttachments((prev) =>
            prev.map((item) =>
              item.localId === localId
                ? {
                    ...item,
                    status: "error",
                    error: err instanceof Error ? err.message : "上传失败",
                  }
                : item,
            ),
          );
        });
    }
  };

  const handlePickRef = (ref: ConversationAttachmentRef): void => {
    const localId = `ref-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setPendingAttachments((prev) => [
      ...prev,
      {
        localId,
        name: ref.name ?? ref.ref_id,
        kind: ref.kind,
        status: "ready",
        ref,
      },
    ]);
  };

  const handleRemoveAttachment = (localId: string): void => {
    setPendingAttachments((prev) => prev.filter((item) => item.localId !== localId));
  };

  const readyAttachments = pendingAttachments.filter((item) => item.status === "ready");
  const uploadingCount = pendingAttachments.filter((item) => item.status === "uploading").length;

  const handleSend = async (): Promise<void> => {
    const text = draft.trim();
    const content =
      text ||
      (readyAttachments.length > 0
        ? `[附件] ${readyAttachments.map((item) => item.name).join("、")}`
        : "");
    if (!content || !activeId || sending || isClosed || uploadingCount > 0) return;
    setSending(true);
    setError(null);
    try {
      const attachmentIds = readyAttachments
        .map((item) => item.record?.attachment_id)
        .filter((id): id is string => typeof id === "string");
      const attachmentRefs = readyAttachments
        .map((item) => item.ref)
        .filter((ref): ref is ConversationAttachmentRef => ref !== undefined);
      await api.sendMessage(activeId, {
        content,
        execution_mode: mode,
        idempotency_key:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `ui-${Date.now()}`,
        attachment_ids: attachmentIds.length > 0 ? attachmentIds : undefined,
        attachment_refs: attachmentRefs.length > 0 ? attachmentRefs : undefined,
      });
      // 发送已被服务端持久化后立即清空输入框与待发送附件，避免刷新失败时残留已发送内容。
      setDraft("");
      setPendingAttachments([]);
      // Server is the single source of truth — re-read the conversation.
      await loadConversation(activeId);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
      // Re-read so UI never pretends a failed send succeeded.
      await loadConversation(activeId);
    } finally {
      setSending(false);
    }
  };

  const handleClose = async (): Promise<void> => {
    if (!activeId || mutatingStatus) return;
    setMutatingStatus(true);
    setError(null);
    try {
      const detail = await api.closeConversation(activeId);
      setStatus(detail.status);
      setMessages(detail.messages ?? []);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "关闭失败");
    } finally {
      setMutatingStatus(false);
    }
  };

  const handleReopen = async (): Promise<void> => {
    if (!activeId || mutatingStatus) return;
    setMutatingStatus(true);
    setError(null);
    try {
      const detail = await api.reopenConversation(activeId);
      setStatus(detail.status);
      setMessages(detail.messages ?? []);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重新打开失败");
    } finally {
      setMutatingStatus(false);
    }
  };

  // aria-live polite：最新助手消息到达时播报；错误走 role="alert"。
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const liveAnnouncement =
    lastMessage != null && lastMessage.role === "assistant"
      ? `柏韩：${lastMessage.content}`
      : "";

  return (
    <div className="flex h-full min-h-[calc(100vh-8rem)] gap-4">
      <ConversationList
        conversations={conversations}
        activeId={activeId}
        loadingList={loadingList}
        onSelect={handleSelect}
        onCreate={handleCreate}
      />

      {/* ── Thread ── */}
      <section
        className="flex min-w-0 flex-1 flex-col rounded-xl border border-border-subtle bg-surface-elevated"
        aria-label="对话内容"
      >
        {/* Header */}
        <header className="flex items-center justify-between gap-3 border-b border-border-subtle px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-graphite text-xs font-bold text-ivory"
              aria-hidden="true"
            >
              柏
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-text-primary">
                {title || "NEXARA 对话"}
              </h2>
              <p className="text-xs text-text-secondary">
                {isClosed ? "已关闭 · 只读" : "进行中 · 持久化对话"}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => activeId !== null && loadConversation(activeId)}
              aria-label="刷新对话"
              title="刷新对话"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            </Button>
            {activeId !== null &&
              (isClosed ? (
                <Button
                  variant="primary"
                  size="sm"
                  isBusy={mutatingStatus}
                  onClick={handleReopen}
                >
                  <Unlock className="h-3.5 w-3.5" aria-hidden="true" />
                  重新打开
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  isBusy={mutatingStatus}
                  onClick={handleClose}
                >
                  <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                  关闭对话
                </Button>
              ))}
          </div>
        </header>

        {/* Error banner — alert 级播报；HTTP 400 真实拒绝，永不假成功 */}
        {error && (
          <ErrorState
            isInline
            title="对话请求失败"
            details={error}
            className="mx-5 mt-3"
          />
        )}

        {/* Messages — 编辑式文本流 */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {activeId === null && !loadingList && (
            <div className="flex h-full items-center justify-center">
              <EmptyState
                className="w-full max-w-md"
                title="从一次对话开始"
                description="选择左侧对话，或新建一个——柏韩将如实记录每一次往返，绝不假成功。"
                icon={<MessageSquare className="h-8 w-8" />}
                actionLabel="新建对话"
                onAction={handleCreate}
              />
            </div>
          )}
          {activeId !== null && messages.length === 0 && !isClosed && (
            <div className="flex h-full items-center justify-center">
              <EmptyState
                className="w-full max-w-md"
                title="对柏韩说点什么"
                description="输入目标或问题——运行时将如实判定意图（对话 / 自动 / 使命），并按持久化结果回复。"
                icon={
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full bg-graphite font-editorial text-sm text-ivory"
                    aria-hidden="true"
                  >
                    柏
                  </div>
                }
              />
            </div>
          )}
          {messages.length > 0 && (
            <div className="space-y-4">
              {messages.map((message) => (
                <MessageFlow
                  key={message.message_id}
                  message={message}
                  onMissionSelect={onMissionSelect}
                  onViewApprovals={onViewApprovals}
                />
              ))}
              {sending && <ThinkingState />}
            </div>
          )}
        </div>

        {/* Composer / closed panel */}
        <div className="border-t border-border-subtle px-5 py-4">
          {activeId === null ? (
            <p className="py-3 text-center text-xs text-text-secondary">
              选择或创建对话后即可发送消息
            </p>
          ) : isClosed ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-subtle px-4 py-3">
              <p className="text-xs text-text-secondary">
                对话已关闭 — 按产品设计拒绝新消息，直到重新打开
              </p>
              <Button
                variant="primary"
                size="sm"
                isBusy={mutatingStatus}
                onClick={handleReopen}
              >
                <Unlock className="h-3.5 w-3.5" aria-hidden="true" />
                重新打开
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-1" role="group" aria-label="执行模式">
                {MODES.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMode(m.id)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring",
                      mode === m.id
                        ? "bg-surface-active text-text-primary"
                        : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                    )}
                    aria-pressed={mode === m.id}
                  >
                    {m.label}
                  </button>
                ))}
                <span className="ml-auto text-xs text-text-secondary">
                  {mode === "mission" && "直接创建并执行使命"}
                  {mode === "auto" && "由运行时判定意图"}
                  {mode === "chat" && "仅对话，不触发使命"}
                </span>
              </div>
              <AttachmentBar
                attachments={pendingAttachments}
                disabled={isClosed}
                onPickFiles={handlePickFiles}
                onPickRef={handlePickRef}
                onRemove={handleRemoveAttachment}
              />
              <div className="flex items-end gap-2">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  rows={2}
                  placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                  className="min-h-[3.5rem] flex-1 resize-none rounded-md border border-border-default bg-surface-base px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                  aria-label="消息输入"
                />
                <Button
                  size="md"
                  className="h-14"
                  isBusy={sending}
                  disabled={(!draft.trim() && readyAttachments.length === 0) || uploadingCount > 0}
                  onClick={handleSend}
                  aria-label="发送消息"
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                  {sending ? "发送中…" : "发送"}
                </Button>
              </div>
              <PromptCraft
                initialText={draft}
                onUsePrompt={(promptText) => setDraft(promptText)}
              />
            </div>
          )}
        </div>
      </section>

      {/* 新消息到达 polite 播报（读屏器） */}
      <div aria-live="polite" className="sr-only">
        {liveAnnouncement}
      </div>
    </div>
  );
}
