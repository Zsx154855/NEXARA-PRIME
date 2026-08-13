// 结果 Tab：验收条件达成度如实呈现（evidence_count / latest_evidence /
// receipt_status / evaluation_status / memory_patch_status / retry_count）+
// EvaluationResult（passed 由 evaluation_status 如实映射；notes 仅呈现真实字段）。
import { CheckCircle2, FileText, ShieldCheck, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { EvidenceChain } from "@/components/ui/EvidenceChain";
import { Status } from "@/components/ui/Status";
import type { EvidenceArtifact, MissionSnapshot } from "@/types";
import { stateLabel } from "./constants";

interface ResultTabProps {
  mission: MissionSnapshot;
  evidence: EvidenceArtifact[];
}

function MetricRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border-subtle py-2 last:border-b-0">
      <span className="text-xs text-text-secondary">{label}</span>
      <span className="text-right text-xs text-text-primary">{children}</span>
    </div>
  );
}

export function ResultTab({ mission, evidence }: ResultTabProps) {
  const state = mission.state ?? mission.current_state;
  const isTerminal =
    state === "Completed" || state === "Failed" || state === "RolledBack" || state === "Cancelled";

  const evaluationTone =
    mission.evaluation_status === "passed"
      ? "success"
      : mission.evaluation_status === "failed"
        ? "danger"
        : "neutral";
  const evaluationLabel =
    mission.evaluation_status === "passed"
      ? "通过"
      : mission.evaluation_status === "failed"
        ? "未通过"
        : "未评估";

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
          <FileText className="h-4 w-4 text-gold-text" />
          结果总览
        </h2>
        <div className="mt-2">
          <MetricRow label="使命状态">
            <Status tone={state === "Completed" ? "success" : state === "Failed" || state === "RolledBack" ? "danger" : "info"} label={stateLabel(state)} />
          </MetricRow>
          <MetricRow label="证据数量">{String(mission.evidence_count ?? 0)} 条</MetricRow>
          <MetricRow label="收据状态">
            <Status
              tone={mission.receipt_status === "present" ? "success" : "warning"}
              label={mission.receipt_status === "present" ? "已存在" : "缺失"}
            />
          </MetricRow>
          <MetricRow label="记忆沉淀">
            <Status
              tone={mission.memory_patch_status === "patched" ? "success" : "neutral"}
              label={
                mission.memory_patch_status === "patched"
                  ? "已自动沉淀（auto_commit）"
                  : "未沉淀"
              }
            />
          </MetricRow>
          <MetricRow label="重试次数">
            {mission.retry_count > 0 ? String(mission.retry_count) : "0"}
          </MetricRow>
          {mission.terminal_reason && (
            <MetricRow label="终止原因">
              <span className="text-danger">{mission.terminal_reason}</span>
            </MetricRow>
          )}
        </div>
      </section>

      {/* EvaluationResult：passed / notes 如实呈现 */}
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
          <CheckCircle2 className="h-4 w-4 text-gold-text" />
          评估
        </h2>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Status tone={evaluationTone} label={`评估：${evaluationLabel}`} />
          {mission.evaluation_status === "passed" && (
            <Badge tone="success">验收通过</Badge>
          )}
          {mission.evaluation_status === "failed" && (
            <Badge tone="danger">验收未通过</Badge>
          )}
        </div>
        {mission.evaluation_status === "failed" && mission.terminal_reason ? (
          <ul className="mt-3 space-y-1.5">
            <li className="flex items-start gap-2 text-xs leading-relaxed text-text-secondary">
              <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
              {mission.terminal_reason}
            </li>
          </ul>
        ) : (
          <p className="mt-3 text-xs leading-relaxed text-text-secondary">
            {mission.evaluation_status === "not_evaluated"
              ? "评估阶段尚未执行。使命完成并验证后，通过/未通过结论会如实呈现。"
              : "评估详情以运行时评估阶段的真实输出为准。"}
          </p>
        )}
      </section>

      {/* 证据与收据引用 */}
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="h-4 w-4 text-gold-text" />
          <h2 className="text-sm font-semibold text-text-primary">证据链</h2>
          <span className="ml-auto text-xs text-text-tertiary">
            {evidence.length} 条
          </span>
        </div>
        <div className="mt-3">
          {evidence.length === 0 ? (
            <EmptyState
              title={
                isTerminal && state === "Completed"
                  ? "还没有证据记录。"
                  : "使命尚未产生证据。"
              }
              description={
                isTerminal && state === "Completed"
                  ? "证据在执行并验证后自动入链。当前收据状态：收据缺失。"
                  : `当前状态：${stateLabel(state)}。关键动作执行并验证后，证据会自动入链。`
              }
            />
          ) : (
            <EvidenceChain evidence={evidence} />
          )}
        </div>
      </section>
    </div>
  );
}
