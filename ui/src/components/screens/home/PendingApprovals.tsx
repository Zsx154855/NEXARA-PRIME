// ─── 待审批卡：pending approvals 列表 ───
// 显示 action / rationale / risk_level / created_at 真实字段。
// 0 项时整卡隐藏（避免空卡空白）。

"use client";

import type { ApprovalRequest } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Section } from "./Section";
import { riskLabel, riskTone } from "./missionState";
import { formatShortTime } from "./time";

type PendingApprovalsProps = {
  /** 已过滤为 status === "pending" 的审批 */
  approvals: ApprovalRequest[];
  /** 前往审批中心（/trust） */
  onViewAll: () => void;
  /** 打开所属使命详情 */
  onOpenMission: (missionId: string) => void;
};

const MAX_VISIBLE = 5;

export function PendingApprovals({
  approvals,
  onViewAll,
  onOpenMission,
}: PendingApprovalsProps) {
  if (approvals.length === 0) return null;

  return (
    <Section
      id="approvals"
      overline="需要你决定"
      title="待审批"
      meta={`${approvals.length} 项`}
      actionLabel="查看全部"
      onAction={onViewAll}
    >
      <ul className="divide-y divide-border-subtle">
        {approvals.slice(0, MAX_VISIBLE).map((approval) => (
          <li key={approval.approval_id}>
            <button
              type="button"
              onClick={() =>
                approval.mission_id
                  ? onOpenMission(approval.mission_id)
                  : onViewAll()
              }
              className="flex w-full items-start justify-between gap-4 py-4 text-left transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
            >
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-text-primary">
                    {approval.action}
                  </span>
                  <Badge tone={riskTone(approval.risk_level)}>
                    {riskLabel(approval.risk_level)}
                  </Badge>
                </span>
                <span className="mt-1 block text-sm leading-relaxed text-text-secondary line-clamp-2">
                  {approval.rationale}
                </span>
              </span>
              <time
                className="shrink-0 text-xs text-text-tertiary"
                dateTime={approval.created_at}
              >
                {formatShortTime(approval.created_at)}
              </time>
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}
