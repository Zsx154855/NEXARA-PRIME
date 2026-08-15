// 三步向导容器：目标确认（表单）→ 生成规划（细线进度）→ 提交审批（成功态）。
// 状态机：0 表单 · 1 生成中 · 2 成功；生成失败回到表单并保留输入。

"use client";

import { useState } from "react";
import { ArrowLeft, Rocket } from "lucide-react";
import type { NexaraAPI } from "@/lib/api";
import type { MissionCreateRequest } from "@/types";
import { StepIndicator } from "./StepIndicator";
import { MissionForm } from "./MissionForm";
import { ProgressView } from "./ProgressView";
import { SuccessView } from "./SuccessView";
import { WIZARD_STEPS, estimateRisk } from "./constants";

const PHASE_LABELS = {
  creating: "正在创建任务…",
  planning: "正在生成规划…",
  submitting: "正在提交审批…",
} as const;

interface MissionWizardProps {
  api: NexaraAPI;
  onClose: () => void;
}

export function MissionWizard({ api, onClose }: MissionWizardProps) {
  const [step, setStep] = useState(0); // 0 表单 · 1 生成中 · 2 成功
  const [objective, setObjective] = useState("");
  const [sourceDir, setSourceDir] = useState("");
  const [missionId, setMissionId] = useState<string | null>(null);
  const [phaseLabel, setPhaseLabel] = useState("");
  const [error, setError] = useState<string | null>(null);

  const riskLevel = estimateRisk(objective);

  const handleCreate = async () => {
    if (!objective.trim()) {
      setError("请输入任务目标");
      return;
    }
    setError(null);
    setStep(1);
    setPhaseLabel(PHASE_LABELS.creating);

    try {
      // 步骤 1：创建任务
      const body: MissionCreateRequest = {
        objective: objective.trim(),
        source_dir: sourceDir.trim() || null,
      };
      const mission = await api.createMission(body);
      setMissionId(mission.mission_id);
      setPhaseLabel(PHASE_LABELS.planning);

      // 步骤 2：生成规划（永不自动绕过审批）
      await api.planMission(mission.mission_id);
      setPhaseLabel(PHASE_LABELS.submitting);

      // 步骤 3：完成——任务自然转入审批状态
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStep(0);
    }
  };

  return (
    <div className="mx-auto max-w-2xl animate-fade-in space-y-6">
      <button
        type="button"
        onClick={onClose}
        className="flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        返回
      </button>

      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gold-soft">
          <Rocket className="h-5 w-5 text-gold-text" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-text-primary">创建新任务</h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            定义任务目标，系统将自动生成规划与合约
          </p>
        </div>
      </div>

      {step === 0 && (
        <>
          <div className="rounded-lg border border-border-default bg-surface-elevated px-4 py-3">
            <StepIndicator current={0} steps={WIZARD_STEPS} />
          </div>
          <MissionForm
            objective={objective}
            sourceDir={sourceDir}
            riskLevel={riskLevel}
            error={error}
            onObjectiveChange={setObjective}
            onSourceDirChange={setSourceDir}
            onCreate={handleCreate}
          />
        </>
      )}

      {step === 1 && <ProgressView phaseLabel={phaseLabel} missionId={missionId} />}

      {step === 2 && <SuccessView missionId={missionId} onDone={onClose} />}
    </div>
  );
}
