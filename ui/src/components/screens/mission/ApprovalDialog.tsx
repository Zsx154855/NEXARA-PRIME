// 审批决策弹窗：WHAT / WHY / 访问 / 风险 / 改变 + 批准 / 拒绝 / 要求修改。
// 决策真实写入 POST /api/missions/{id}/approve（decision 字段）。
import { useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
  RotateCcw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { useDialogA11y } from "@/components/ui/dialog-a11y";
import { cn } from "@/lib/utils";
import type { ApprovalRequest } from "@/types";
import { RISK_LABELS, formatTimestamp } from "./constants";

export type ApprovalDecision = "approved" | "rejected" | "changes_requested";

interface ApprovalDialogProps {
  approval: ApprovalRequest | null;
  isBusy: boolean;
  error?: string | null;
  onDecide: (decision: ApprovalDecision, note: string) => void;
  onClose: () => void;
}

function DetailRow({
  label,
  children,
  tone,
}: {
  label: string;
  children: React.ReactNode;
  tone?: "danger";
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="shrink-0 text-xs text-text-secondary">{label}</span>
      <span
        className={cn(
          "min-w-0 text-right text-xs",
          tone === "danger" ? "text-danger" : "text-text-primary",
        )}
      >
        {children}
      </span>
    </div>
  );
}

export function ApprovalDialog({
  approval,
  isBusy,
  error,
  onDecide,
  onClose,
}: ApprovalDialogProps) {
  const [note, setNote] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogA11y(approval !== null, onClose, panelRef);
  if (!approval) return null;

  const hasRollbackPlan =
    approval.rollback_plan && Object.keys(approval.rollback_plan).length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/30 px-4 backdrop-blur-sm">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`审批：${approval.action}`}
        className="flex max-h-[90vh] w-full max-w-lg flex-col animate-fade-in rounded-xl border border-border-default bg-ivory p-6 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-text-primary">
              审批：{approval.action}
            </h3>
            <p className="mt-0.5 font-data text-xs text-text-secondary">
              {approval.approval_scope}
            </p>
          </div>
          <Button variant="quiet" size="sm" onClick={onClose} disabled={isBusy}>
            关闭
          </Button>
        </div>

        <div className="mt-4 space-y-4 overflow-y-auto pr-1">
          {/* WHY — 为什么需要批准 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <Info className="h-3.5 w-3.5 text-gold-text" />
              WHY · 为什么
            </h4>
            <p className="mt-1 text-sm leading-relaxed text-text-secondary">
              {approval.rationale || "—"}
            </p>
          </section>

          {/* 访问 — 会碰到什么资源 */}
          <section className="rounded-md border border-border-subtle bg-surface-subtle px-3 py-2">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <FileText className="h-3.5 w-3.5 text-gold-text" />
              访问 · 涉及资源
            </h4>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {approval.affected_resources.length > 0 ? (
                approval.affected_resources.map((res) => (
                  <code
                    key={res}
                    className="rounded bg-surface-elevated px-1.5 py-0.5 font-data text-xs text-text-primary"
                  >
                    {res}
                  </code>
                ))
              ) : (
                <span className="text-xs text-text-tertiary">—</span>
              )}
            </div>
            {approval.proposal_sha256 && (
              <p className="mt-1.5 break-all font-data text-xs text-text-tertiary">
                proposal_sha256:{approval.proposal_sha256}
              </p>
            )}
          </section>

          {/* 风险 — 边界与代价 */}
          <section className="rounded-md border border-border-subtle bg-surface-subtle px-3 py-2">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <ShieldAlert className="h-3.5 w-3.5 text-gold-text" />
              风险 · 边界与代价
            </h4>
            <div className="mt-1 divide-y divide-border-subtle">
              <DetailRow label="风险等级">
                {RISK_LABELS[approval.risk_level]}
              </DetailRow>
              <DetailRow label="可回滚">
                {approval.reversible ? "是" : "否"}
              </DetailRow>
              <DetailRow label="外部影响" tone={approval.external_effect ? "danger" : undefined}>
                {approval.external_effect ? "是（影响本机之外）" : "否"}
              </DetailRow>
              <DetailRow label="估算成本">
                {approval.estimated_cost > 0 ? String(approval.estimated_cost) : "—"}
              </DetailRow>
              <DetailRow label="过期时间">
                {approval.expires_at ? formatTimestamp(approval.expires_at) : "—"}
              </DetailRow>
            </div>
          </section>

          {/* 改变 — 批准后会改变什么 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <AlertTriangle className="h-3.5 w-3.5 text-gold-text" />
              改变 · 影响与回滚计划
            </h4>
            <ul className="mt-1.5 space-y-1">
              {approval.impact.length > 0 ? (
                approval.impact.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2 text-xs leading-relaxed text-text-secondary"
                  >
                    <span className="mt-1.5 inline-block size-1 shrink-0 rounded-full bg-gold-text" />
                    {item}
                  </li>
                ))
              ) : (
                <li className="text-xs text-text-tertiary">—</li>
              )}
            </ul>
            {hasRollbackPlan ? (
              <pre className="mt-2 max-h-28 overflow-y-auto rounded-md bg-surface-subtle p-2 font-data text-xs leading-relaxed text-text-secondary">
                {JSON.stringify(approval.rollback_plan, null, 2)}
              </pre>
            ) : (
              <p className="mt-1.5 text-xs text-text-tertiary">
                {approval.reversible ? "无可回滚计划" : "不可逆操作，无回滚计划"}
              </p>
            )}
          </section>

          <label className="block">
            <span className="text-xs text-text-secondary">决策备注（可选）</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={isBusy}
              rows={2}
              placeholder="给运行时和审计留一句理由…"
              className="mt-1 w-full rounded-md border border-border-default bg-surface-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-2 focus:outline-[var(--color-focus-ring)] disabled:opacity-50"
            />
          </label>

          {error && (
            <ErrorState
              isInline
              title="决策提交失败"
              details={error}
              className="mt-2"
            />
          )}
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-border-subtle pt-4">
          <Button
            variant="quiet"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide("changes_requested", note)}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            要求修改
          </Button>
          <Button
            variant="danger"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide("rejected", note)}
          >
            <XCircle className="h-3.5 w-3.5" />
            拒绝
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={isBusy}
            onClick={() => onDecide("approved", note)}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            批准
          </Button>
        </div>
      </div>
    </div>
  );
}
