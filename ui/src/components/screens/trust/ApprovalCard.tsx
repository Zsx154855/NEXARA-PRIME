"use client";

// ─── 待审批卡：一张卡回答五个问题 ───
// 做什么（action）、为什么（rationale）、风险（risk_level）、
// 访问什么（affected_resources）、将改变什么（external_effect / reversible / expires_at）。
// 只有 status === "pending" 且绑定使命的请求才给决定按钮；
// paused 如实呈现为「已暂停」并禁止决定。

import type { ApprovalRequest } from "@/types";
import { Button } from "@/components/ui/Button";
import { Status } from "@/components/ui/Status";
import { PermissionState } from "@/components/ui/PermissionState";
import { CheckCircle2, Clock, Undo2, XCircle } from "lucide-react";
import { formatDateTime, riskMeta, type DecisionKind } from "./approvalMeta";

type ApprovalCardProps = {
  approval: ApprovalRequest;
  isBusy: boolean;
  onDecide: (approval: ApprovalRequest, decision: DecisionKind) => void;
};

export function ApprovalCard({ approval, isBusy, onDecide }: ApprovalCardProps) {
  const risk = riskMeta(approval.risk_level);
  const RiskIcon = risk.icon;
  const isPaused = approval.status === "paused";
  const canDecide = approval.status === "pending" && Boolean(approval.mission_id);

  return (
    <article
      className={
        approval.status === "pending"
          ? "animate-gate-open rounded-md border border-border-default bg-surface-elevated px-5 py-4"
          : "rounded-md border border-border-default bg-surface-elevated px-5 py-4"
      }
    >
      {/* 做什么 + 风险 */}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2.5">
          <Status
            tone={risk.tone}
            icon={<RiskIcon className="size-3.5" aria-hidden="true" />}
            label={`${approval.risk_level} · ${risk.label}`}
          />
          <h3 className="min-w-0 text-base font-medium text-text-primary">
            {approval.action}
          </h3>
        </div>
        {isPaused ? (
          <Status tone="warning" label="已暂停" />
        ) : (
          approval.expires_at && (
            <span className="flex shrink-0 items-center gap-1 text-xs text-text-secondary">
              <Clock className="size-3.5" aria-hidden="true" />
              过期
              <time dateTime={approval.expires_at}>
                {formatDateTime(approval.expires_at)}
              </time>
            </span>
          )
        )}
      </div>

      {/* 为什么 */}
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">
        {approval.rationale}
      </p>

      {/* 访问什么 */}
      {approval.affected_resources.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {approval.affected_resources.map((res) => (
            <li
              key={res}
              className="rounded border border-border-subtle bg-surface-subtle px-2 py-0.5 font-data text-xs text-text-secondary"
            >
              {res}
            </li>
          ))}
        </ul>
      )}

      {/* 将改变什么 */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <Status
          tone={approval.external_effect ? "warning" : "neutral"}
          label={approval.external_effect ? "有外部影响" : "无外部影响"}
        />
        <Status
          tone={approval.reversible ? "success" : "danger"}
          label={approval.reversible ? "可回滚" : "不可回滚"}
        />
        <span className="font-data text-xs text-text-tertiary">
          mission:{approval.mission_id}
        </span>
      </div>

      {/* 决定按钮 */}
      {canDecide ? (
        <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-border-subtle pt-3">
          <Button
            variant="ghost"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide(approval, "changes_requested")}
          >
            <Undo2 className="size-3.5" aria-hidden="true" />
            要求修改
          </Button>
          <Button
            variant="dangerSolid"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide(approval, "rejected")}
          >
            <XCircle className="size-3.5" aria-hidden="true" />
            拒绝
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide(approval, "approved")}
          >
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            批准
          </Button>
        </div>
      ) : (
        approval.status === "pending" && (
          <PermissionState
            requirement="审批决策"
            reason="该审批未绑定使命，决策必须经由使命审批触发面执行；用户级审批权限为 PLANNED 能力。"
            className="mt-3"
          />
        )
      )}
    </article>
  );
}
