// ─── 当前意图区：活跃使命摘要 / 最近一次对话消息 ───
// 无数据显示诚实空态（「现在没有进行中的工作」+ 下一步）。

"use client";

import { MessageSquare, Play, Sparkles } from "lucide-react";
import type { ConversationDetail, MissionSnapshot } from "@/types";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Status } from "@/components/ui/Status";
import { sanitizeAssistantContent } from "@/lib/presentation";
import { Section } from "./Section";
import { stateLabel, stateTone } from "./missionState";
import { formatShortTime } from "./time";

export type IntentState =
  | { kind: "mission"; mission: MissionSnapshot }
  | { kind: "conversation"; conversation: ConversationDetail }
  | null;

type IntentSectionProps = {
  intent: IntentState;
  onContinueMission: (mission: MissionSnapshot) => void;
  onOpenMission: (missionId: string) => void;
  onOpenConversation: (conversationId: string) => void;
  onCreateMission: () => void;
};

function MissionBlock({
  mission,
  onContinueMission,
  onOpenMission,
}: {
  mission: MissionSnapshot;
  onContinueMission: (mission: MissionSnapshot) => void;
  onOpenMission: (missionId: string) => void;
}) {
  return (
    <article className="rounded-lg border border-border-default bg-surface-elevated px-6 py-6 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex flex-wrap items-center gap-2">
        <Status tone={stateTone(mission.state)} label={stateLabel(mission.state)} />
        {mission.paused && <Status tone="warning" label="已暂停" />}
      </div>
      <h3 className="mt-4 font-editorial text-2xl leading-snug text-text-primary">
        {mission.title}
      </h3>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary line-clamp-2">
        {mission.objective}
      </p>
      {mission.pending_action && (
        <p className="mt-3">
          <Status tone="warning" label={`下一步：${mission.pending_action}`} />
        </p>
      )}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="primary" size="md" onClick={() => onContinueMission(mission)}>
          <Play className="h-4 w-4" />
          继续任务
        </Button>
        <Button
          variant="ghost"
          size="md"
          onClick={() => onOpenMission(mission.mission_id)}
        >
          查看使命
        </Button>
      </div>
    </article>
  );
}

function ConversationBlock({
  conversation,
  onOpenConversation,
}: {
  conversation: ConversationDetail;
  onOpenConversation: (conversationId: string) => void;
}) {
  const messages = conversation.messages ?? [];
  const lastMessage = messages[messages.length - 1];
  return (
    <article className="rounded-lg border border-border-default bg-surface-elevated px-6 py-6 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex flex-wrap items-center gap-2">
        <Status tone="info" label="最近对话" />
        {conversation.status === "closed" && (
          <Status tone="neutral" label="已关闭" />
        )}
      </div>
      <h3 className="mt-4 font-editorial text-2xl leading-snug text-text-primary">
        {conversation.title || "未命名对话"}
      </h3>
      {lastMessage && (
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary line-clamp-2">
          {lastMessage.role === "assistant"
            ? sanitizeAssistantContent(lastMessage.content)
            : lastMessage.content}
        </p>
      )}
      <div className="mt-6">
        <Button
          variant="primary"
          size="md"
          onClick={() => onOpenConversation(conversation.conversation_id)}
        >
          <MessageSquare className="h-4 w-4" />
          打开对话
        </Button>
      </div>
    </article>
  );
}

export function IntentSection({
  intent,
  onContinueMission,
  onOpenMission,
  onOpenConversation,
  onCreateMission,
}: IntentSectionProps) {
  const meta =
    intent?.kind === "mission"
      ? `更新于 ${formatShortTime(intent.mission.updated_at)}`
      : intent?.kind === "conversation"
        ? `更新于 ${formatShortTime(intent.conversation.updated_at)}`
        : undefined;

  return (
    <Section id="intent" overline="值守摘要" title="当前意图" meta={meta}>
      {intent === null ? (
        <EmptyState
          title="现在没有进行中的工作"
          description="NEXARA 已就位、正在值守。可以创建第一个使命，或先与 NEXARA 对话了解当前能力。"
          actionLabel="创建使命"
          onAction={onCreateMission}
          icon={<Sparkles className="h-5 w-5" />}
        />
      ) : intent.kind === "mission" ? (
        <MissionBlock
          mission={intent.mission}
          onContinueMission={onContinueMission}
          onOpenMission={onOpenMission}
        />
      ) : (
        <ConversationBlock
          conversation={intent.conversation}
          onOpenConversation={onOpenConversation}
        />
      )}
    </Section>
  );
}
