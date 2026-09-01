import type { ConversationAttachment, ConversationMessage } from "@/types";
import { Cable, FileText, Puzzle } from "lucide-react";
import { attachmentContentUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { sanitizeAssistantContent } from "@/lib/presentation";
import { ConversationMeta } from "./ConversationMeta";
import { extractMeta, formatTime } from "./utils";

type MessageFlowProps = {
  message: ConversationMessage;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
};

function AttachmentChips({
  attachments,
  conversationId,
  isUser,
}: {
  attachments: ConversationAttachment[];
  conversationId?: string;
  isUser: boolean;
}) {
  const chipClass = cn(
    "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
    isUser
      ? "border-ivory/30 bg-ivory/10 text-ivory"
      : "border-border-subtle bg-surface-base text-text-secondary",
  );
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {attachments.map((attachment) => {
        const contentUrl =
          conversationId && attachment.kind !== "plugin" && attachment.kind !== "connection"
            ? attachmentContentUrl(conversationId, attachment.attachment_id)
            : null;
        if (attachment.kind === "image" && contentUrl) {
          return (
            <a key={attachment.attachment_id} href={contentUrl} target="_blank" rel="noreferrer" title={attachment.name}>
              <img
                src={contentUrl}
                alt={attachment.name}
                className="block max-h-48 max-w-[16rem] rounded-lg object-cover"
              />
            </a>
          );
        }
        if (attachment.kind === "video" && contentUrl) {
          return (
            <video
              key={attachment.attachment_id}
              src={contentUrl}
              controls
              className="block max-h-48 max-w-[16rem] rounded-lg"
              aria-label={attachment.name}
            />
          );
        }
        const icon =
          attachment.kind === "plugin" ? (
            <Puzzle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          ) : attachment.kind === "connection" ? (
            <Cable className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          );
        const label =
          attachment.kind === "plugin"
            ? `插件 · ${attachment.name}`
            : attachment.kind === "connection"
              ? `连接 · ${attachment.name}`
              : attachment.name;
        return contentUrl ? (
          <a
            key={attachment.attachment_id}
            href={contentUrl}
            target="_blank"
            rel="noreferrer"
            className={cn(chipClass, "hover:opacity-80")}
            title={attachment.name}
          >
            {icon}
            <span className="max-w-[12rem] truncate">{label}</span>
          </a>
        ) : (
          <span key={attachment.attachment_id} className={chipClass} title={attachment.ref_id ?? attachment.name}>
            {icon}
            <span className="max-w-[12rem] truncate">{label}</span>
          </span>
        );
      })}
    </div>
  );
}

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
  const attachments = message.metadata?.attachments ?? [];

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
          {attachments.length > 0 && (
            <AttachmentChips
              attachments={attachments}
              conversationId={message.conversation_id}
              isUser={isUser}
            />
          )}
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
