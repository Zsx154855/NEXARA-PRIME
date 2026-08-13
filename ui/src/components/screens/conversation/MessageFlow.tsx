import type { ConversationMessage } from "@/types";
import { cn } from "@/lib/utils";
import { ConversationMeta } from "./ConversationMeta";
import { extractMeta, formatTime } from "./utils";

type MessageFlowProps = {
  message: ConversationMessage;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
};

/**
 * 编辑式文本流 — 非气泡卡片：
 *  - 用户消息：石墨色文本左对齐，细左线指示
 *  - 助手消息：正文流（14px / 1.7 行高），下接真实元数据
 *  - 时间戳 text-secondary、≥12px
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
      className={cn(isUser && "border-l-2 border-graphite/25 pl-4")}
    >
      <header className="mb-1.5 flex items-center gap-2">
        {isUser ? (
          <span className="text-xs font-semibold text-text-secondary">你</span>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <span
              className="flex h-5 w-5 items-center justify-center rounded-[4px] bg-graphite font-editorial text-xs leading-none text-ivory"
              aria-hidden="true"
            >
              柏
            </span>
            <span className="text-xs font-semibold text-text-secondary">
              柏韩
            </span>
          </span>
        )}
        <time dateTime={message.created_at} className="text-xs text-text-secondary">
          {formatTime(message.created_at)}
          {meta.provider !== null ? ` · ${meta.provider}` : ""}
        </time>
      </header>
      <p className="whitespace-pre-wrap text-sm leading-[1.7] text-text-primary">
        {message.content}
      </p>
      {!isUser && (
        <ConversationMeta
          meta={meta}
          onMissionSelect={onMissionSelect}
          onViewApprovals={onViewApprovals}
        />
      )}
    </article>
  );
}
