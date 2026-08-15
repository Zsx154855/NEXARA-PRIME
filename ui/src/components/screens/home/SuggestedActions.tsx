// ─── 建议动作：创建使命 / 打开对话 / 查看待批准 / 查看记忆 ───
// 路由跳转由父层（Overview）注入回调。

"use client";

import { ArrowRight, Brain, MessageSquare, Plus, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Section } from "./Section";

type SuggestedActionsProps = {
  pendingApprovalCount: number;
  onCreateMission: () => void;
  onOpenConversation: () => void;
  onViewApprovals: () => void;
  onViewMemory: () => void;
};

function ActionButton({
  icon,
  label,
  badge,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover active:bg-surface-active focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
    >
      <span className="text-text-tertiary" aria-hidden="true">
        {icon}
      </span>
      {label}
      {badge !== undefined && <Badge tone="warning">{badge}</Badge>}
      <ArrowRight
        className="h-3.5 w-3.5 text-text-tertiary"
        aria-hidden="true"
      />
    </button>
  );
}

export function SuggestedActions({
  pendingApprovalCount,
  onCreateMission,
  onOpenConversation,
  onViewApprovals,
  onViewMemory,
}: SuggestedActionsProps) {
  return (
    <Section id="actions" overline="下一步" title="建议动作">
      <div className="flex flex-wrap gap-2">
        <ActionButton
          icon={<Plus className="h-4 w-4" />}
          label="创建使命"
          onClick={onCreateMission}
        />
        <ActionButton
          icon={<MessageSquare className="h-4 w-4" />}
          label="打开对话"
          onClick={onOpenConversation}
        />
        <ActionButton
          icon={<ShieldCheck className="h-4 w-4" />}
          label="查看待批准"
          badge={pendingApprovalCount > 0 ? pendingApprovalCount : undefined}
          onClick={onViewApprovals}
        />
        <ActionButton
          icon={<Brain className="h-4 w-4" />}
          label="查看记忆"
          onClick={onViewMemory}
        />
      </div>
    </Section>
  );
}
