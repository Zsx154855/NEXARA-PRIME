"use client";

// ─── 决定确认弹窗：确认制，决定前把五问摊开 ───
// 做什么 / 为什么 / 访问什么 / 风险 / 将改变什么 + 可选备注。
// 提交走 POST /api/missions/:id/approve（decision + actor="human" + note）。

import { useEffect, useRef, useState } from "react";
import type { ApprovalRequest } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Status } from "@/components/ui/Status";
import { X } from "lucide-react";
import { formatDateTime, riskMeta, type DecisionKind } from "./approvalMeta";

const CONFIRM_LABEL: Record<DecisionKind, string> = {
  approved: "确认批准",
  rejected: "确认拒绝",
  changes_requested: "确认要求修改",
};

type DecisionDialogProps = {
  approval: ApprovalRequest;
  decision: DecisionKind;
  isBusy: boolean;
  error: string | null;
  onConfirm: (note: string) => void;
  onCancel: () => void;
};

export function DecisionDialog({
  approval,
  decision,
  isBusy,
  error,
  onConfirm,
  onCancel,
}: DecisionDialogProps) {
  const [note, setNote] = useState("");
  const risk = riskMeta(approval.risk_level);
  const RiskIcon = risk.icon;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isBusy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isBusy, onCancel]);

  // 初始聚焦：审批弹窗打开时聚焦首个可聚焦元素（关闭按钮）
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (panelRef.current) {
      const first = panelRef.current.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled])',
      );
      first?.focus();
    }
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/30 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !isBusy) onCancel();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="decision-dialog-title"
        className="w-full max-w-lg animate-fade-in rounded-lg border border-border-default bg-surface-elevated shadow-lg"
      >
        {/* 标题 */}
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle px-5 py-4">
          <div>
            <h2
              id="decision-dialog-title"
              className="font-editorial text-lg text-text-primary"
            >
              {CONFIRM_LABEL[decision]}
            </h2>
            <p className="mt-0.5 text-xs text-text-tertiary">
              审批 {approval.approval_id} · 创建于{" "}
              {formatDateTime(approval.created_at)}
            </p>
          </div>
          <Button
            variant="quiet"
            size="sm"
            disabled={isBusy}
            onClick={onCancel}
            aria-label="关闭"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>

        {/* 确认内容 */}
        <div className="max-h-[60vh] space-y-4 overflow-y-auto px-5 py-4">
          <dl className="space-y-3">
            <div>
              <dt className="text-xs text-text-tertiary">做什么</dt>
              <dd className="mt-0.5 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-text-primary">
                  {approval.action}
                </span>
                {approval.approval_scope && (
                  <Badge tone="neutral">{approval.approval_scope}</Badge>
                )}
              </dd>
              <dd className="mt-1 font-data text-xs text-text-tertiary">
                mission:{approval.mission_id}
              </dd>
            </div>

            <div>
              <dt className="text-xs text-text-tertiary">为什么</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-text-secondary">
                {approval.rationale}
              </dd>
              {approval.reason && (
                <dd className="mt-1 text-sm leading-relaxed text-text-secondary">
                  原因：{approval.reason}
                </dd>
              )}
            </div>

            <div>
              <dt className="text-xs text-text-tertiary">访问什么</dt>
              <dd className="mt-1.5">
                {approval.affected_resources.length > 0 ? (
                  <ul className="flex flex-wrap gap-1.5">
                    {approval.affected_resources.map((res) => (
                      <li
                        key={res}
                        className="rounded border border-border-subtle bg-surface-subtle px-2 py-0.5 font-data text-xs text-text-secondary"
                      >
                        {res}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-sm text-text-tertiary">
                    未声明访问对象
                  </span>
                )}
              </dd>
            </div>

            <div>
              <dt className="text-xs text-text-tertiary">风险</dt>
              <dd className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                <Status
                  tone={risk.tone}
                  icon={<RiskIcon className="size-3.5" aria-hidden="true" />}
                  label={`${approval.risk_level} · ${risk.label}`}
                />
                <Status
                  tone={approval.external_effect ? "warning" : "neutral"}
                  label={approval.external_effect ? "有外部影响" : "无外部影响"}
                />
                <Status
                  tone={approval.reversible ? "success" : "danger"}
                  label={approval.reversible ? "可回滚" : "不可回滚"}
                />
              </dd>
            </div>

            <div>
              <dt className="text-xs text-text-tertiary">将改变什么</dt>
              <dd className="mt-1.5">
                {approval.impact.length > 0 ? (
                  <ul className="list-disc pl-5 text-sm text-text-secondary">
                    {approval.impact.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-sm text-text-tertiary">未声明影响</span>
                )}
                {approval.estimated_cost > 0 && (
                  <p className="mt-1.5 text-xs text-text-secondary">
                    预估成本{" "}
                    <span className="font-data tabular-nums">
                      {approval.estimated_cost}
                    </span>{" "}
                    积分
                  </p>
                )}
              </dd>
            </div>
          </dl>

          <label className="block">
            <span className="text-xs text-text-tertiary">决策备注（可选）</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={isBusy}
              rows={3}
              placeholder="写给 NEXARA 或你自己的决定记录…"
              className="mt-1 w-full rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
            />
          </label>

          {error && <ErrorState isInline title="决定提交失败" details={error} />}
        </div>

        {/* 底部 */}
        <div className="flex justify-end gap-2 border-t border-border-subtle px-5 py-4">
          <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
            取消
          </Button>
          <Button
            variant={decision === "rejected" ? "dangerSolid" : "primary"}
            isBusy={isBusy}
            onClick={() => onConfirm(note)}
          >
            {CONFIRM_LABEL[decision]}
          </Button>
        </div>
      </div>
    </div>
  );
}
