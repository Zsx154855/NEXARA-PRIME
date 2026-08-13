import { Plus } from "lucide-react";
import type { ConversationDetail } from "@/types";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { cn } from "@/lib/utils";
import { formatTime } from "./utils";

type ConversationListProps = {
  conversations: ConversationDetail[];
  activeId: string | null;
  loadingList: boolean;
  onSelect: (conversationId: string) => void;
  onCreate: () => void;
};

/** 左侧对话列表 — 固定 256px（w-64）。 */
export function ConversationList({
  conversations,
  activeId,
  loadingList,
  onSelect,
  onCreate,
}: ConversationListProps) {
  return (
    <section
      className="flex w-64 shrink-0 flex-col rounded-xl border border-border-subtle bg-surface-subtle"
      aria-label="对话列表"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
          对话 · {conversations.length}
        </h2>
        <Button variant="primary" size="sm" onClick={onCreate} aria-label="新建对话">
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          新建
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {loadingList ? (
          <div className="px-2 py-6">
            <LoadingState label="正在读取对话列表" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
            <p className="text-sm text-text-secondary">
              还没有对话——让柏韩从第一句开始
            </p>
            <Button variant="ghost" size="sm" onClick={onCreate}>
              创建第一个对话
            </Button>
          </div>
        ) : (
          <ul className="space-y-1">
            {conversations.map((c) => {
              const isActive = c.conversation_id === activeId;
              return (
                <li key={c.conversation_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(c.conversation_id)}
                    aria-current={isActive ? "true" : undefined}
                    className={cn(
                      "block w-full rounded-lg px-3 py-2.5 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus-ring",
                      isActive ? "bg-surface-active" : "hover:bg-surface-hover",
                    )}
                  >
                    <span
                      className={cn(
                        "block truncate text-sm",
                        isActive
                          ? "font-semibold text-text-primary"
                          : "text-text-secondary",
                      )}
                    >
                      {c.title}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-2">
                      <Status
                        tone={c.status === "open" ? "success" : "neutral"}
                        label={c.status === "open" ? "进行中" : "已关闭"}
                      />
                      <time
                        dateTime={c.updated_at}
                        className="text-xs text-text-secondary"
                      >
                        {formatTime(c.updated_at)}
                      </time>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
