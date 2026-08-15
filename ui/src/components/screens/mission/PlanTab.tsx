// 计划 Tab：目标、边界与约束、交付物、验收标准、风险等级、审批要求 + 计划步骤。
// 数据全部来自 MissionSnapshot（spec / plan 真实字段）。
import {
  AlertTriangle,
  CheckCircle2,
  ListChecks,
  ScrollText,
  Shield,
  Target,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Status } from "@/components/ui/Status";
import type { MissionSnapshot } from "@/types";
import {
  APPROVAL_STATUS_LABELS,
  RISK_LABELS,
  stateLabel,
  stepStatusTone,
} from "./constants";

interface PlanTabProps {
  mission: MissionSnapshot;
  isPlanning: boolean;
  planError?: string | null;
  onPlan: () => void;
}

function CardSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
        {icon}
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StringList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-xs text-text-tertiary">—</p>;
  }
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li
          key={item}
          className="flex items-start gap-2 text-sm leading-relaxed text-text-secondary"
        >
          <span className="mt-2 inline-block size-1 shrink-0 rounded-full bg-gold-text" />
          {item}
        </li>
      ))}
    </ul>
  );
}

export function PlanTab({ mission, isPlanning, planError, onPlan }: PlanTabProps) {
  const spec = mission.spec;
  const plan = mission.plan;
  const steps = plan?.steps ?? [];
  const state = mission.state ?? mission.current_state;

  const approvalTone =
    mission.approval_status === "approved" ||
    mission.approval_status === "consumed" ||
    mission.approval_status === "not_required"
      ? "success"
      : mission.approval_status === "rejected" ||
          mission.approval_status === "integrity_error"
        ? "danger"
        : "warning";

  return (
    <div className="space-y-4">
      <CardSection title="目标" icon={<Target className="h-4 w-4 text-gold-text" />}>
        <p className="text-sm leading-relaxed text-text-primary">
          {mission.objective ?? spec?.objective ?? "—"}
        </p>
      </CardSection>

      <CardSection
        title="边界与约束"
        icon={<Shield className="h-4 w-4 text-gold-text" />}
      >
        <h3 className="text-xs font-medium text-text-secondary">边界</h3>
        <div className="mt-1">
          <StringList items={spec?.boundaries ?? []} />
        </div>
        <h3 className="mt-3 text-xs font-medium text-text-secondary">约束</h3>
        <div className="mt-1">
          <StringList items={spec?.constraints ?? []} />
        </div>
      </CardSection>

      <CardSection
        title="交付物"
        icon={<ScrollText className="h-4 w-4 text-gold-text" />}
      >
        <StringList items={spec?.deliverables ?? []} />
      </CardSection>

      <CardSection
        title="验收标准"
        icon={<CheckCircle2 className="h-4 w-4 text-gold-text" />}
      >
        <StringList items={spec?.acceptance_criteria ?? []} />
      </CardSection>

      <CardSection
        title="风险与审批要求"
        icon={<AlertTriangle className="h-4 w-4 text-gold-text" />}
      >
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={mission.risk_level === "R3" || mission.risk_level === "R4" ? "danger" : "warning"}>
            {RISK_LABELS[mission.risk_level]}
          </Badge>
          <Status
            tone={approvalTone}
            label={
              APPROVAL_STATUS_LABELS[mission.approval_status as keyof typeof APPROVAL_STATUS_LABELS] ??
              mission.approval_status ??
              "—"
            }
          />
        </div>
      </CardSection>

      {planError && (
        <ErrorState
          isInline
          title="计划生成失败"
          details={planError}
          className="mt-2"
        />
      )}

      <CardSection
        title="计划步骤"
        icon={<ListChecks className="h-4 w-4 text-gold-text" />}
      >
        {steps.length === 0 ? (
          <EmptyState
            title="使命等待计划。"
            description={`当前状态：${stateLabel(state)}。生成计划后，此处会呈现每一步的角色、能力与执行状态。`}
            actionLabel={isPlanning ? "生成中…" : "生成计划"}
            onAction={onPlan}
          />
        ) : (
          <ol className="space-y-2">
            {steps.map((step, index) => (
              <li
                key={step.step_id}
                className="flex items-start gap-3 rounded-md border border-border-subtle bg-surface-subtle px-3 py-2.5"
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gold-soft text-xs font-medium text-gold-text">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {step.title}
                    </span>
                    <Status
                      tone={stepStatusTone(step.status)}
                      label={step.status}
                    />
                  </div>
                  <p className="mt-0.5 text-xs leading-relaxed text-text-secondary">
                    {step.description}
                  </p>
                  <p className="mt-0.5 text-xs text-text-tertiary">
                    {step.role} · {step.persona}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardSection>
    </div>
  );
}
