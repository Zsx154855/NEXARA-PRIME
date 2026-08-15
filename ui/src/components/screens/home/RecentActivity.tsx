// ─── 最近：最近对话 + 最近结果（Completed 前 3 个）───
// 编辑式列表（发丝线分隔），不做卡片网格堆叠。

"use client";

import type { ConversationDetail, MissionSnapshot } from "@/types";
import { Status } from "@/components/ui/Status";
import { Section } from "./Section";
import { byUpdatedAtDesc, formatShortTime } from "./time";

type RecentActivityProps = {
  conversations: ConversationDetail[];
  missions: MissionSnapshot[];
  onOpenConversation: (conversationId: string) => void;
  onSelectMission: (missionId: string) => void;
};

const RECENT_LIMIT = 3;

export function RecentActivity({
  conversations,
  missions,
  onOpenConversation,
  onSelectMission,
}: RecentActivityProps) {
  const recentConversations = [...conversations]
    .sort(byUpdatedAtDesc)
    .slice(0, RECENT_LIMIT);
  const recentResults = missions
    .filter((m) => m.state === "Completed")
    .sort(byUpdatedAtDesc)
    .slice(0, RECENT_LIMIT);

  if (recentConversations.length === 0 && recentResults.length === 0) {
    return null;
  }

  return (
    <Section id="recent" overline="最近" title="进展">
      {recentConversations.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
            最近对话
          </h3>
          <ul className="mt-3 divide-y divide-border-subtle">
            {recentConversations.map((conversation) => (
              <li key={conversation.conversation_id}>
                <button
                  type="button"
                  onClick={() => onOpenConversation(conversation.conversation_id)}
                  className="flex w-full items-baseline justify-between gap-4 py-3.5 text-left transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-text-primary">
                      {conversation.title || "未命名对话"}
                    </span>
                    <span className="mt-0.5 block text-xs text-text-secondary">
                      {conversation.messages.length} 条消息
                      {conversation.status === "closed" ? " · 已关闭" : ""}
                    </span>
                  </span>
                  <time
                    className="shrink-0 text-xs text-text-tertiary"
                    dateTime={conversation.updated_at}
                  >
                    {formatShortTime(conversation.updated_at)}
                  </time>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {recentResults.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
            最近结果
          </h3>
          <ul className="mt-3 divide-y divide-border-subtle">
            {recentResults.map((mission) => (
              <li key={mission.mission_id}>
                <button
                  type="button"
                  onClick={() => onSelectMission(mission.mission_id)}
                  className="flex w-full items-center justify-between gap-4 py-3.5 text-left transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-text-primary">
                      {mission.title}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-text-secondary">
                      {mission.objective}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <Status tone="success" label="已完成" />
                    <time
                      className="text-xs text-text-tertiary"
                      dateTime={mission.updated_at}
                    >
                      {formatShortTime(mission.updated_at)}
                    </time>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}
