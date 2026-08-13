"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  ConversationDetail,
  ConversationExecutionMode,
  ConversationMessage,
} from "@/types";
import type { NexaraAPI } from "@/lib/api";
import {
  MessageSquare,
  Plus,
  Send,
  Loader2,
  Lock,
  Unlock,
  ShieldAlert,
  Rocket,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Props ──

interface ConversationScreenProps {
  api: NexaraAPI;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
}

// ── Helpers ──

const MODES: { id: ConversationExecutionMode; label: string }[] = [
  { id: "chat", label: "对话" },
  { id: "auto", label: "自动" },
  { id: "mission", label: "使命" },
];

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function messageMeta(message: ConversationMessage) {
  const m = message.metadata ?? {};
  return {
    intent: typeof m.intent === "string" ? m.intent : null,
    provider: typeof m.provider === "string" ? m.provider : null,
    missionId: typeof m.mission_id === "string" ? m.mission_id : null,
    approvalRequired: m.approval_required === true,
  };
}

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
        setMessages(detail.messages);
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
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建对话失败");
    }
  };

  const handleSend = async (): Promise<void> => {
    const content = draft.trim();
    if (!content || !activeId || sending || isClosed) return;
    setSending(true);
    setError(null);
    try {
      await api.sendMessage(activeId, {
        content,
        execution_mode: mode,
        idempotency_key:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `ui-${Date.now()}`,
      });
      // Server is the single source of truth — re-read the conversation.
      await loadConversation(activeId);
      setDraft("");
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
      setMessages(detail.messages);
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
      setMessages(detail.messages);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重新打开失败");
    } finally {
      setMutatingStatus(false);
    }
  };

  return (
    <div className="flex h-full min-h-[calc(100vh-8rem)] gap-4">
      {/* ── Conversation list ── */}
      <section
        className="flex w-64 shrink-0 flex-col rounded-xl border border-border-subtle bg-surface-subtle"
        aria-label="对话列表"
      >
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-text-tertiary">
            对话 · {conversations.length}
          </h2>
          <button
            type="button"
            onClick={handleCreate}
            className="inline-flex items-center gap-1 rounded-lg bg-graphite px-2.5 py-1.5 text-xs font-semibold text-ivory transition-colors hover:bg-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            aria-label="新建对话"
          >
            <Plus className="h-3.5 w-3.5" />
            新建
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {loadingList && (
            <div className="flex items-center justify-center gap-2 py-8 text-xs text-text-tertiary">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载中…
            </div>
          )}
          {!loadingList && conversations.length === 0 && (
            <div className="py-10 text-center text-xs text-text-tertiary">
              还没有对话
              <div className="mt-3">
                <button
                  type="button"
                  onClick={handleCreate}
                  className="rounded-lg border border-border-default px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                >
                  创建第一个对话
                </button>
              </div>
            </div>
          )}
          {conversations.map((c) => (
            <button
              key={c.conversation_id}
              type="button"
              onClick={() => handleSelect(c.conversation_id)}
              className={cn(
                "mb-1 block w-full rounded-lg px-3 py-2.5 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus-ring",
                c.conversation_id === activeId
                  ? "bg-surface-active"
                  : "hover:bg-surface-hover",
              )}
              aria-current={c.conversation_id === activeId ? "true" : undefined}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "truncate text-sm",
                    c.conversation_id === activeId
                      ? "font-semibold text-text-primary"
                      : "text-text-secondary",
                  )}
                >
                  {c.title}
                </span>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium",
                    c.status === "open"
                      ? "bg-moss-green/10 text-moss-green"
                      : "bg-taupe/40 text-stone",
                  )}
                >
                  {c.status === "open" ? "进行中" : "已关闭"}
                </span>
              </div>
              <div className="mt-0.5 text-[10px] text-text-tertiary">
                {formatTime(c.updated_at)}
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* ── Thread ── */}
      <section
        className="flex min-w-0 flex-1 flex-col rounded-xl border border-border-subtle bg-surface-elevated"
        aria-label="对话内容"
      >
        {/* Header */}
        <header className="flex items-center justify-between gap-3 border-b border-border-subtle px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-graphite text-xs font-bold text-ivory">
              柏
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-text-primary">
                {title || "NEXARA 对话"}
              </h2>
              <p className="text-[10px] text-text-tertiary">
                {isClosed ? "已关闭 · 只读" : "进行中 · 持久化对话"}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => activeId && loadConversation(activeId)}
              className="rounded-lg border border-border-default p-2 text-text-tertiary transition-colors hover:bg-surface-hover hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              aria-label="刷新对话"
              title="刷新对话"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            {activeId &&
              (isClosed ? (
                <button
                  type="button"
                  onClick={handleReopen}
                  disabled={mutatingStatus}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-moss-green px-3 py-1.5 text-xs font-semibold text-ivory transition-colors hover:opacity-90 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                >
                  {mutatingStatus ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Unlock className="h-3.5 w-3.5" />
                  )}
                  重新打开
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={mutatingStatus}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-semibold text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                >
                  {mutatingStatus ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Lock className="h-3.5 w-3.5" />
                  )}
                  关闭对话
                </button>
              ))}
          </div>
        </header>

        {/* Error banner — never pretend success */}
        {error && (
          <div
            className="mx-5 mt-3 flex items-start gap-2 rounded-lg border border-warm-red/30 bg-warm-red/10 px-3 py-2 text-xs text-warm-red"
            role="alert"
          >
            <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {activeId === null && !loadingList && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <MessageSquare className="h-10 w-10 text-text-disabled" />
              <p className="max-w-xs text-sm text-text-tertiary">
                选择或创建对话，开始与柏韩协作
              </p>
            </div>
          )}
          {activeId !== null && messages.length === 0 && !isClosed && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-graphite text-base font-bold text-ivory">
                柏
              </div>
              <p className="max-w-xs text-sm text-text-tertiary">
                说点什么 — 输入目标或问题，柏韩将如实回答
              </p>
            </div>
          )}
          {messages.map((message) => {
            const meta = messageMeta(message);
            const isUser = message.role === "user";
            return (
              <div
                key={message.message_id}
                className={cn("flex", isUser ? "justify-end" : "justify-start")}
              >
                <div className={cn("max-w-[80%]", isUser ? "text-right" : "text-left")}>
                  {!isUser && (
                    <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-tertiary">
                      <div className="flex h-4 w-4 items-center justify-center rounded bg-graphite text-[8px] text-ivory">
                        柏
                      </div>
                      柏韩
                    </div>
                  )}
                  <div
                    className={cn(
                      "inline-block whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-left text-sm leading-relaxed",
                      isUser
                        ? "bg-graphite text-ivory"
                        : "border border-border-subtle bg-surface-base text-text-primary",
                    )}
                  >
                    {message.content}
                  </div>
                  {/* Metadata row — product truth, not decoration */}
                  {!isUser && (meta.intent || meta.missionId || meta.approvalRequired) && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {meta.intent && (
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5 text-[9px] font-medium",
                            meta.intent === "mission"
                              ? "bg-champagne/20 text-champagne ring-1 ring-champagne/30"
                              : "bg-taupe/30 text-stone",
                          )}
                        >
                          {meta.intent === "mission" ? "使命意图" : "对话意图"}
                        </span>
                      )}
                      {meta.approvalRequired && (
                        <span className="rounded bg-amber/15 px-1.5 py-0.5 text-[9px] font-medium text-amber">
                          需人工审批
                        </span>
                      )}
                      {meta.missionId && (
                        <button
                          type="button"
                          onClick={() => onMissionSelect(meta.missionId!)}
                          className="inline-flex items-center gap-1 rounded bg-moss-green/10 px-1.5 py-0.5 text-[9px] font-semibold text-moss-green transition-colors hover:bg-moss-green/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                        >
                          <Rocket className="h-2.5 w-2.5" />
                          使命 {meta.missionId}
                        </button>
                      )}
                      {meta.approvalRequired && (
                        <button
                          type="button"
                          onClick={onViewApprovals}
                          className="rounded bg-amber/15 px-1.5 py-0.5 text-[9px] font-semibold text-amber transition-colors hover:bg-amber/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                        >
                          去审批
                        </button>
                      )}
                    </div>
                  )}
                  <div
                    className={cn(
                      "mt-1 text-[9px] text-text-disabled",
                      isUser ? "text-right" : "text-left",
                    )}
                  >
                    {formatTime(message.created_at)}
                    {meta.provider ? ` · ${meta.provider}` : ""}
                  </div>
                </div>
              </div>
            );
          })}
          {sending && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-xl border border-border-subtle bg-surface-base px-3.5 py-2.5 text-sm text-text-tertiary">
                <Loader2 className="h-4 w-4 animate-spin" />
                柏韩思考中…
              </div>
            </div>
          )}
        </div>

        {/* Composer / closed panel */}
        <div className="border-t border-border-subtle p-4">
          {activeId === null ? (
            <p className="py-3 text-center text-xs text-text-tertiary">
              选择或创建对话后即可发送消息
            </p>
          ) : isClosed ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-subtle px-4 py-3">
              <p className="text-xs text-text-tertiary">
                对话已关闭 — 按产品设计拒绝新消息，直到重新打开
              </p>
              <button
                type="button"
                onClick={handleReopen}
                disabled={mutatingStatus}
                className="shrink-0 rounded-lg bg-moss-green px-3 py-1.5 text-xs font-semibold text-ivory transition-colors hover:opacity-90 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              >
                重新打开
              </button>
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
                      "rounded-md px-2.5 py-1 text-[10px] font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring",
                      mode === m.id
                        ? "bg-surface-active text-text-primary"
                        : "text-text-tertiary hover:bg-surface-hover hover:text-text-secondary",
                    )}
                    aria-pressed={mode === m.id}
                  >
                    {m.label}
                  </button>
                ))}
                <span className="ml-auto text-[9px] text-text-disabled">
                  {mode === "mission" && "直接创建并执行使命"}
                  {mode === "auto" && "由运行时判定意图"}
                  {mode === "chat" && "仅对话，不触发使命"}
                </span>
              </div>
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
                  className="min-h-[3.5rem] flex-1 resize-none rounded-lg border border-border-default bg-surface-base px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-disabled focus:border-text-tertiary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                  aria-label="消息输入"
                />
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={sending || !draft.trim()}
                  className="inline-flex h-[3.5rem] shrink-0 items-center gap-1.5 rounded-lg bg-graphite px-4 text-sm font-semibold text-ivory transition-colors hover:bg-text-primary disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                  aria-label="发送消息"
                >
                  {sending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  发送
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
