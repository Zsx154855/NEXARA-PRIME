import type { ConversationMessage } from "@/types";
import { cn } from "@/lib/utils";
import { sanitizeAssistantContent } from "@/lib/presentation";
import { ConversationMeta } from "./ConversationMeta";
import { extractMeta, formatTime } from "./utils";

type MessageFlowProps = {
  message: ConversationMessage;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
};

/**
 * 即时通讯式气泡流（微信风格）：
 *  - 用户消息：右侧气泡（石墨底、象牙字），气泡尾朝右
 *  - 助手消息：左侧气泡（浅面底、描边），气泡尾朝左
 *  - 名称 + 时间置于气泡外侧，助手保留真实元数据（ConversationMeta）
 */
export function MessageFlow({
  message,
  onMissionSelect,
  onViewApprovals,
}: MessageFlowProps) {
  const isUser = message.role === "user";
  const meta = extractMeta(message);

  return (
    <article
      className={cn(
        "flex w-full items-end gap-2",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser && (
        <span
          className="mb-5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-graphite font-editorial text-xs leading-none text-ivory"
          aria-hidden="true"
        >
          柏
        </span>
      )}

      <div
        className={cn(
          "flex max-w-[78%] flex-col",
          isUser ? "items-end" : "items-start",
        )}
      >
        <header
          className={cn(
            "mb-1 flex items-center gap-2 text-xs text-text-tertiary",
            isUser ? "flex-row-reverse" : "flex-row",
          )}
        >
          <span className="font-medium text-text-secondary">
            {isUser ? "你" : "柏韩"}
          </span>
          <time dateTime={message.created_at}>
            {formatTime(message.created_at)}
            {meta.provider !== null ? ` · ${meta.provider}` : ""}
          </time>
        </header>

        <div
          className={cn(
            "whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "rounded-br-sm bg-graphite text-ivory"
              : "rounded-bl-sm border border-border-subtle bg-surface-subtle text-text-primary",
          )}
        >
          {isUser ? message.content : sanitizeAssistantContent(message.content)}
        </div>

        {!isUser && (
          <ConversationMeta
            meta={meta}
            onMissionSelect={onMissionSelect}
            onViewApprovals={onViewApprovals}
          />
        )}
      </div>

      {isUser && (
        <span
          className="mb-5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-active font-editorial text-xs leading-none text-text-primary"
          aria-hidden="true"
        >
          你
        </span>
      )}
    </article>
  );
}
