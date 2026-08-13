// 步骤 1 · 目标确认：目标描述 + 源目录 + 实时风险估算 + 审批须知。

import { FolderOpen, ShieldAlert, Sparkles, Target } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { cn } from "@/lib/utils";
import { RISK_CONFIG, type RiskTone } from "./constants";

const TONE_BOX: Record<RiskTone, string> = {
  success: "border-success/25 bg-success/5",
  warning: "border-warning/25 bg-warning/5",
  danger: "border-danger/25 bg-danger/5",
};

const TONE_ACCENT: Record<RiskTone, string> = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

const INPUT_CLASS =
  "w-full rounded-md border border-border-default bg-surface-base px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-none focus:ring-1 focus:ring-border-focus/30";

interface MissionFormProps {
  objective: string;
  sourceDir: string;
  riskLevel: string | null;
  error: string | null;
  onObjectiveChange: (value: string) => void;
  onSourceDirChange: (value: string) => void;
  onCreate: () => void;
}

export function MissionForm({
  objective,
  sourceDir,
  riskLevel,
  error,
  onObjectiveChange,
  onSourceDirChange,
  onCreate,
}: MissionFormProps) {
  const risk = riskLevel ? RISK_CONFIG[riskLevel] : null;
  const RiskIcon = risk?.icon ?? null;
  const canSubmit = objective.trim().length > 0;

  return (
    <div className="space-y-5">
      {/* 任务目标 */}
      <div>
        <label
          htmlFor="mission-objective"
          className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-text-primary"
        >
          <Target className="h-4 w-4 text-accent-primary" />
          任务目标
        </label>
        <textarea
          id="mission-objective"
          value={objective}
          onChange={(e) => onObjectiveChange(e.target.value)}
          placeholder="描述你想要完成的任务目标…"
          rows={5}
          className={cn(INPUT_CLASS, "resize-none")}
        />
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="text-xs text-text-secondary">{objective.length} 字</span>
          {risk && <Badge tone={risk.tone}>{risk.label}</Badge>}
        </div>
      </div>

      {/* 源目录 */}
      <div>
        <label
          htmlFor="mission-source-dir"
          className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-text-primary"
        >
          <FolderOpen className="h-4 w-4 text-text-secondary" />
          源目录（可选）
        </label>
        <input
          id="mission-source-dir"
          value={sourceDir}
          onChange={(e) => onSourceDirChange(e.target.value)}
          placeholder="例如 /path/to/project"
          className={INPUT_CLASS}
        />
      </div>

      {/* 风险评估提示 */}
      {risk && (
        <div className={cn("rounded-lg border p-3", TONE_BOX[risk.tone])}>
          <div className="flex items-start gap-2">
            {RiskIcon && (
              <RiskIcon className={cn("mt-0.5 h-4 w-4 shrink-0", TONE_ACCENT[risk.tone])} />
            )}
            <div className="text-xs leading-relaxed text-text-secondary">
              <span className="font-medium text-text-primary">风险等级：</span>
              <span className={cn("font-medium", TONE_ACCENT[risk.tone])}>{risk.label}</span>
              <span className="ml-1.5">— {risk.desc}</span>
            </div>
          </div>
        </div>
      )}

      {/* 审批须知 */}
      <div className="flex items-start gap-2 rounded-lg border border-border-default bg-surface-subtle p-3">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <div className="text-xs leading-relaxed text-text-secondary">
          <span className="font-medium text-text-primary">审批须知：</span>
          系统不会自动绕过审批流程。所有任务在执行前均需经过人类审批。高风险操作（R3/R4）将标记为优先处理。
        </div>
      </div>

      {/* 错误 */}
      {error && <ErrorState isInline title="无法创建任务" details={error} />}

      {/* 提交 */}
      <Button
        variant="gold"
        size="lg"
        className="w-full"
        disabled={!canSubmit}
        onClick={onCreate}
      >
        <Sparkles className="h-4 w-4" />
        创建任务
      </Button>
    </div>
  );
}
