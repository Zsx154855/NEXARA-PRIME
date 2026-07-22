"use client";

import { useState, useCallback } from "react";
import type { NexaraAPI } from "@/lib/api";
import type { MissionCreateRequest } from "@/types";
import { cn } from "@/lib/utils";
import {
  Rocket,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  FileText,
  ArrowLeft,
  ShieldAlert,
  Target,
  FolderOpen,
  ChevronRight,
  Sparkles,
  Info,
} from "lucide-react";

// ─── Props ───

interface MissionCreatorProps {
  api: NexaraAPI;
  onCreated: () => void;
}

// ─── Chinese Labels ───

const LABELS = {
  title: "创建新任务",
  subtitle: "定义任务目标，系统将自动生成规划与合约",
  objective: "任务目标",
  objectivePlaceholder: "描述你想要完成的任务目标…",
  sourceDir: "源目录（可选）",
  sourceDirPlaceholder: "例如 /path/to/project",
  riskLevel: "风险等级",
  riskHint: "基于目标复杂度自动评估",
  createMission: "创建任务",
  creating: "正在创建…",
  generatePlan: "生成规划",
  submitApproval: "提交审批",
  back: "返回",
  success: "任务创建成功",
  error: "创建失败",
  objectiveRequired: "请输入任务目标",
  stepObjective: "目标确认",
  stepPlan: "生成规划",
  stepApproval: "提交审批",
  step_1_desc: "定义任务目标",
  step_2_desc: "AI 生成执行方案",
  step_3_desc: "提交人类审批",
  noAutoBypass: "系统不会自动绕过审批流程",
  creatingMission: "正在创建任务…",
  planningMission: "正在生成规划…",
  submittingApproval: "正在提交审批…",
};

// ─── Risk Level Display ───

const RISK_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof AlertTriangle; desc: string }
> = {
  R0: { label: "无风险", color: "text-moss-green bg-moss-green/10", icon: CheckCircle2, desc: "简单信息查询，无副作用" },
  R1: { label: "低风险", color: "text-moss-green bg-moss-green/10", icon: Info, desc: "只读操作，影响范围有限" },
  R2: { label: "中等风险", color: "text-amber bg-amber/10", icon: AlertTriangle, desc: "涉及写操作，但可回滚" },
  R3: { label: "高风险", color: "text-warm-red bg-warm-red/10", icon: ShieldAlert, desc: "不可逆操作或外部影响" },
  R4: { label: "极端风险", color: "text-warm-red bg-warm-red/15", icon: ShieldAlert, desc: "生产环境变更或安全敏感操作" },
};

// ─── Risk icon render helper (avoids JSX dynamic component indexing) ───

function risKIcon(riskLevel: string): React.ReactNode {
  const cfg = RISK_CONFIG[riskLevel];
  if (!cfg) return null;
  const Icon = cfg.icon;
  return <Icon className="h-3 w-3" />;
}

// ─── Step Indicator ───

function StepIndicator({
  current,
  steps,
}: {
  current: number;
  steps: { label: string; desc: string }[];
}) {
  return (
    <div className="flex items-center gap-0">
      {steps.map((step, i) => {
        const isActive = i === current;
        const isDone = i < current;
        return (
          <div key={i} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-all",
                  isDone
                    ? "bg-moss-green/20 text-moss-green"
                    : isActive
                      ? "bg-champagne/20 text-champagne ring-1 ring-champagne/40"
                      : "bg-taupe/30 text-stone"
                )}
              >
                {isDone ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  i + 1
                )}
              </span>
              <div className="hidden sm:block">
                <div
                  className={cn(
                    "text-xs font-medium",
                    isActive ? "text-champagne" : isDone ? "text-moss-green" : "text-stone"
                  )}
                >
                  {step.label}
                </div>
                <div className="text-[10px] text-stone">{step.desc}</div>
              </div>
            </div>
            {i < steps.length - 1 && (
              <ChevronRight
                className={cn(
                  "mx-2 h-3.5 w-3.5",
                  isDone ? "text-moss-green/40" : "text-taupe"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Component ───

export function MissionCreator({ api, onCreated }: MissionCreatorProps) {
  const [step, setStep] = useState(0); // 0: form, 1: creating, 2: success
  const [objective, setObjective] = useState("");
  const [sourceDir, setSourceDir] = useState("");
  const [riskLevel, setRiskLevel] = useState<string | null>(null);
  const [missionId, setMissionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phaseLabel, setPhaseLabel] = useState("");

  // ── Estimate risk level from objective text (simple heuristic) ──
  const estimateRisk = useCallback((text: string): string | null => {
    if (!text || text.trim().length < 10) return null;
    const lower = text.toLowerCase();
    // R4 indicators
    if (
      /production|deploy|prod|delete|remove|destroy|terminate|shutdown/i.test(lower)
    )
      return "R4";
    // R3 indicators
    if (
      /write|modify|update|change|create file|commit|push|merge|execute|run/i.test(
        lower
      )
    )
      return "R3";
    // R2 indicators
    if (
      /analyze|investigate|research|search|scan|audit|review|read|fetch/i.test(
        lower
      )
    )
      return "R2";
    // R1 indicators
    if (
      /summarize|list|show|tell|what|explain|describe|check|status/i.test(lower)
    )
      return "R1";
    return "R0";
  }, []);

  const handleObjectiveChange = (value: string) => {
    setObjective(value);
    setRiskLevel(estimateRisk(value));
  };

  // ── Create Mission (Step 1) ──
  const handleCreate = async () => {
    if (!objective.trim()) {
      setError(LABELS.objectiveRequired);
      return;
    }
    setLoading(true);
    setError(null);
    setStep(1);
    setPhaseLabel(LABELS.creatingMission);

    try {
      // Step 1: Create mission
      const body: MissionCreateRequest = {
        objective: objective.trim(),
        source_dir: sourceDir.trim() || null,
      };

      const mission = await api.createMission(body);
      setMissionId(mission.mission_id);
      setPhaseLabel(LABELS.planningMission);

      // Step 2: Generate plan (never auto-bypass approval)
      await api.planMission(mission.mission_id);
      setPhaseLabel(LABELS.submittingApproval);

      // Step 3: Done — transitions to Approval state naturally
      setStep(2);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
      setStep(0);
    }
  };

  const handleFinish = () => {
    onCreated();
  };

  // ── Render ──

  return (
    <div className="mx-auto max-w-2xl animate-fade-in space-y-6">
      {/* Back button */}
      <button
        onClick={onCreated}
        className="flex items-center gap-1.5 text-xs text-stone transition-colors hover:text-graphite"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        {LABELS.back}
      </button>

      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-champagne/10">
            <Rocket className="h-5 w-5 text-champagne" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-graphite">{LABELS.title}</h1>
            <p className="mt-0.5 text-sm text-stone">{LABELS.subtitle}</p>
          </div>
        </div>
      </div>

      {/* Step indicator */}
      <div className="rounded-lg border border-taupe bg-ivory px-4 py-3">
        <StepIndicator
          current={step}
          steps={[
            { label: LABELS.stepObjective, desc: LABELS.step_1_desc },
            { label: LABELS.stepPlan, desc: LABELS.step_2_desc },
            { label: LABELS.stepApproval, desc: LABELS.step_3_desc },
          ]}
        />
      </div>

      {/* ── Step 0: Form ── */}
      {step === 0 && (
        <div className="space-y-5">
          {/* Objective */}
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-graphite">
              <Target className="h-4 w-4 text-champagne" />
              {LABELS.objective}
            </label>
            <textarea
              value={objective}
              onChange={(e) => handleObjectiveChange(e.target.value)}
              placeholder={LABELS.objectivePlaceholder}
              rows={5}
              className="w-full resize-none rounded-lg border border-taupe bg-ivory px-3.5 py-2.5 text-sm text-graphite placeholder:text-stone/50 focus:border-champagne focus:outline-none focus:ring-1 focus:ring-champagne/30"
            />
            <div className="mt-1 flex items-center justify-between">
              <span className="text-[11px] text-stone">{objective.length} 字</span>
              {riskLevel && RISK_CONFIG[riskLevel] && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                    RISK_CONFIG[riskLevel].color
                  )}
                >
                  {risKIcon(riskLevel)}
                  {RISK_CONFIG[riskLevel].label}
                </span>
              )}
            </div>
          </div>

          {/* Source directory */}
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-graphite">
              <FolderOpen className="h-4 w-4 text-stone" />
              {LABELS.sourceDir}
            </label>
            <input
              value={sourceDir}
              onChange={(e) => setSourceDir(e.target.value)}
              placeholder={LABELS.sourceDirPlaceholder}
              className="w-full rounded-lg border border-taupe bg-ivory px-3.5 py-2.5 text-sm text-graphite placeholder:text-stone/50 focus:border-champagne focus:outline-none focus:ring-1 focus:ring-champagne/30"
            />
          </div>

          {/* Risk hint */}
          {riskLevel && RISK_CONFIG[riskLevel] && (
            <div
              className={cn(
                "rounded-lg border p-3 text-xs",
                riskLevel === "R3" || riskLevel === "R4"
                  ? "border-warm-red/20 bg-warm-red/5"
                  : "border-taupe bg-mist-gray"
              )}
            >
              <div className="flex items-start gap-2">
                {(() => {
                  const RiskIcon = RISK_CONFIG[riskLevel]?.icon ?? Info;
                  return <RiskIcon
                    className={cn(
                      "mt-0.5 h-4 w-4",
                      riskLevel === "R3" || riskLevel === "R4"
                        ? "text-warm-red"
                        : "text-stone"
                    )}
                  />;
                })()}
                <div>
                  <span className="font-medium text-graphite">
                    {LABELS.riskLevel}：
                  </span>
                  <span
                    className={cn(
                      "font-medium",
                      riskLevel === "R3" || riskLevel === "R4"
                        ? "text-warm-red"
                        : "text-moss-green"
                    )}
                  >
                    {RISK_CONFIG[riskLevel].label}
                  </span>
                  <span className="ml-1.5 text-stone">
                    — {RISK_CONFIG[riskLevel].desc}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Approval notice */}
          <div className="flex items-start gap-2 rounded-lg border border-taupe bg-mist-gray p-3">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
            <div className="text-xs text-stone">
              <span className="font-medium text-graphite">审批须知：</span>
              {LABELS.noAutoBypass}。所有任务在执行前均需经过人类审批。高风险操作（R3/R4）将标记为优先处理。
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-warm-red/20 bg-warm-red/5 px-3.5 py-2.5 text-sm text-warm-red">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleCreate}
            disabled={loading || !objective.trim()}
            className={cn(
              "flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-medium transition-all",
              loading || !objective.trim()
                ? "cursor-not-allowed bg-taupe/50 text-stone"
                : "bg-champagne text-ivory hover:bg-champagne/90 active:bg-champagne/80"
            )}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {LABELS.creating}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                {LABELS.createMission}
              </>
            )}
          </button>
        </div>
      )}

      {/* ── Step 1: Creating / Loading ── */}
      {step === 1 && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-champagne/10">
            <Loader2 className="h-8 w-8 animate-spin text-champagne" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-graphite">{phaseLabel}</p>
            <p className="mt-1 text-xs text-stone">
              任务 ID：{missionId ? missionId.slice(0, 16) + "…" : "—"}
            </p>
          </div>
          {/* Simulated progress bar */}
          <div className="mt-2 h-1 w-64 overflow-hidden rounded-full bg-taupe">
            <div className="h-full animate-pulse rounded-full bg-champagne" style={{ width: "60%" }} />
          </div>
        </div>
      )}

      {/* ── Step 2: Success ── */}
      {step === 2 && (
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-moss-green/10">
            <CheckCircle2 className="h-8 w-8 text-moss-green" />
          </div>
          <div className="text-center">
            <p className="text-base font-medium text-graphite">{LABELS.success}</p>
            <p className="mt-1 text-xs text-stone">
              任务 ID：
              <code className="ml-1 rounded bg-mist-gray px-1.5 py-0.5 font-mono text-xs text-graphite">
                {missionId}
              </code>
            </p>
          </div>
          <div className="mt-2 flex items-start gap-2 rounded-lg border border-taupe bg-mist-gray p-3 text-xs text-stone">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber" />
            任务已进入审批队列。请在"审批中心"中查看并处理。
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={handleFinish}
              className="rounded-lg border border-taupe bg-ivory px-4 py-2 text-sm font-medium text-graphite transition-colors hover:bg-mist-gray"
            >
              {LABELS.back}
            </button>
            <button
              onClick={handleFinish}
              className="flex items-center gap-1.5 rounded-lg bg-champagne px-4 py-2 text-sm font-medium text-ivory transition-colors hover:bg-champagne/90"
            >
              <FileText className="h-4 w-4" />
              查看审批队列
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
