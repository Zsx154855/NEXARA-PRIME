"use client";

// ─── NEXARA 使命详情（WORKSPACE 并入）───
// 四 Tab：计划 / 执行 / 结果 / 时间线（默认计划）+ 右侧五级信任阶梯（始终可见）。
// 数据源：api.getMission 权威快照 + getApprovals / fetchTools / getEvidence /
// getMemory / getEvents（Promise.allSettled，单源失败不拖垮整体，阶梯如实红）。
// props 与 ui/src/app/(shell)/missions/page.tsx 的既有调用保持兼容。
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import type { NexaraAPI } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import type {
  ApprovalRequest,
  EvidenceArtifact,
  Event,
  MemoryRecord,
  MissionSnapshot,
  ToolInvocation,
} from "@/types";
import {
  ApprovalDialog,
  type ApprovalDecision,
} from "./mission/ApprovalDialog";
import { ExecutionTab } from "./mission/ExecutionTab";
import { MissionConfirmDialog } from "./mission/MissionConfirmDialog";
import { PlanTab } from "./mission/PlanTab";
import { ResultTab } from "./mission/ResultTab";
import { TabBar } from "./mission/TabBar";
import { TimelineTab } from "./mission/TimelineTab";
import {
  TrustLadderPanel,
  type SideDataStatus,
} from "./mission/TrustLadderPanel";
import {
  RISK_LABELS,
  TERMINAL_STATES,
  stateLabel,
} from "./mission/constants";
import type { MissionTabId } from "./mission/constants";

// ─── Props（与 missions/page.tsx 既有调用保持兼容）───

interface MissionWorkspaceProps {
  api: NexaraAPI;
  missionId: string;
  onBack: () => void;
}

interface ConfirmState {
  title: string;
  description: string;
  confirmLabel: string;
  isDanger: boolean;
  action: () => Promise<unknown>;
}

function reasonOf(result: PromiseRejectedResult): string {
  return result.reason instanceof Error ? result.reason.message : String(result.reason);
}

// ─── 容器：数据加载 + 控制动作 + Tab 编排 ───

export function MissionWorkspace({ api, missionId, onBack }: MissionWorkspaceProps) {
  const [mission, setMission] = useState<MissionSnapshot | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [tools, setTools] = useState<ToolInvocation[]>([]);
  const [evidence, setEvidence] = useState<EvidenceArtifact[]>([]);
  const [memory, setMemory] = useState<MemoryRecord[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [sideStatus, setSideStatus] = useState<Record<string, SideDataStatus>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<MissionTabId>("plan");

  // 控制动作确认弹窗（暂停 / 恢复 / 回滚 / 安全模式）
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 审批决策弹窗（WHAT / WHY / 访问 / 风险 / 改变）
  const [approvalTarget, setApprovalTarget] = useState<ApprovalRequest | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  // 计划生成
  const [isPlanning, setIsPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    let snapshot: MissionSnapshot;
    try {
      snapshot = await api.getMission(missionId);
      setMission(snapshot);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
      setIsLoading(false);
      return;
    }

    // 侧路数据 best-effort：单源失败如实记入阶梯，不拖垮整体视图
    const [approvalsR, toolsR, evidenceR, memoryR, eventsR] =
      await Promise.allSettled([
        api.getApprovals(missionId),
        api.fetchTools(missionId),
        api.getEvidence(missionId),
        api.getMemory(missionId),
        api.getEvents(missionId),
      ]);

    setApprovals(approvalsR.status === "fulfilled" ? approvalsR.value : []);
    setTools(toolsR.status === "fulfilled" ? toolsR.value : []);
    setEvidence(evidenceR.status === "fulfilled" ? evidenceR.value : []);
    setMemory(memoryR.status === "fulfilled" ? memoryR.value : []);
    setEvents(eventsR.status === "fulfilled" ? eventsR.value : []);
    setSideStatus({
      approvals: { loaded: true, error: approvalsR.status === "rejected" ? reasonOf(approvalsR) : null },
      tools: { loaded: true, error: toolsR.status === "rejected" ? reasonOf(toolsR) : null },
      evidence: { loaded: true, error: evidenceR.status === "rejected" ? reasonOf(evidenceR) : null },
      memory: { loaded: true, error: memoryR.status === "rejected" ? reasonOf(memoryR) : null },
      events: { loaded: true, error: eventsR.status === "rejected" ? reasonOf(eventsR) : null },
    });
    setIsLoading(false);
  }, [api, missionId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── 控制动作（真实 api 方法 + 确认弹窗）──

  const openControl = (
    title: string,
    description: string,
    confirmLabel: string,
    isDanger: boolean,
    action: () => Promise<unknown>,
  ) => {
    setActionError(null);
    setConfirm({ title, description, confirmLabel, isDanger, action });
  };

  const runConfirmed = async () => {
    if (!confirm) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await confirm.action();
      setConfirm(null);
      await loadAll();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionBusy(false);
    }
  };

  const handleRun = () =>
    openControl(
      "开始执行",
      "运行时将按当前计划推进执行。执行中的每次工具调用都会如实入流。",
      "开始执行",
      false,
      () => api.runMission(missionId),
    );

  const handlePause = () =>
    openControl(
      "暂停使命",
      "暂停后运行时不会继续推进，你可以随时恢复。",
      "暂停",
      false,
      () => api.pauseMission(missionId),
    );

  const handleResume = () =>
    openControl(
      "恢复使命",
      "从暂停处恢复，运行时按当前状态继续。",
      "恢复",
      false,
      () => api.resumeMission(missionId),
    );

  const handleRollback = () =>
    openControl(
      "回滚使命",
      "回滚后使命进入已回滚终态，不再继续执行。回滚点证据会自动入链。",
      "回滚",
      true,
      () => api.rollbackMission(missionId),
    );

  const handleToggleSafeMode = () => {
    const enabled = !(mission?.safe_mode ?? false);
    openControl(
      enabled ? "启用安全模式" : "关闭安全模式",
      enabled
        ? "安全模式下，未经批准的使命不会自动运行。"
        : "关闭后使命按原计划运行。",
      enabled ? "启用" : "关闭",
      enabled,
      () => api.setSafeMode(missionId, { enabled }),
    );
  };

  // ── 审批决策（POST /api/missions/{id}/approve）──

  const handleDecide = async (decision: ApprovalDecision, note: string) => {
    if (!approvalTarget) return;
    setApprovalBusy(true);
    setApprovalError(null);
    try {
      await api.approveMission(missionId, {
        approved: decision === "approved",
        actor: "human", // 本地单用户模式：actor 如实为 human（身份接线 = AUTH BACKEND REQUIRED）
        note: note || undefined,
        decision,
      });
      setApprovalTarget(null);
      await loadAll();
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : String(err));
    } finally {
      setApprovalBusy(false);
    }
  };

  // ── 计划生成（POST /api/missions/{id}/plan）──

  const handlePlan = async () => {
    setIsPlanning(true);
    setPlanError(null);
    try {
      await api.planMission(missionId);
      await loadAll();
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsPlanning(false);
    }
  };

  // ── 加载 / 错误 / 未找到 ──

  if (isLoading && !mission) {
    return (
      <div className="animate-fade-in space-y-4">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回使命列表
        </button>
        <LoadingState label="加载使命详情…" />
      </div>
    );
  }

  if (loadError && !mission) {
    return (
      <div className="animate-fade-in space-y-4">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回使命列表
        </button>
        <ErrorState
          title="使命状态加载失败。"
          details={`数据未变，仅视图未刷新。${loadError}`}
          actionLabel="重试"
          onAction={loadAll}
        />
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="animate-fade-in space-y-4">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回使命列表
        </button>
        <EmptyState
          title="使命不存在或已被删除。"
          description={`使命 ${missionId} 无法加载。你可以返回列表重新选择，或从对话委派新使命。`}
          actionLabel="返回使命列表"
          onAction={onBack}
        />
      </div>
    );
  }

  // ── 主渲染 ──

  const state = mission.state ?? mission.current_state;
  const isTerminal = TERMINAL_STATES.includes(state);
  const stateTone: "success" | "danger" | "warning" | "info" = isTerminal
    ? state === "Completed"
      ? "success"
      : "danger"
    : state === "Paused" ||
        state === "Blocked" ||
        state === "AwaitingApproval" ||
        state === "Approval" ||
        state === "Degraded"
      ? "warning"
      : "info";
  const riskTone =
    mission.risk_level === "R3" || mission.risk_level === "R4"
      ? "danger"
      : mission.risk_level === "R2"
        ? "warning"
        : "neutral";

  return (
    <div className="animate-fade-in space-y-5">
      {/* 返回 + 页头（title / objective / risk_level 徽章 / state 徽标） */}
      <div>
        <button
          type="button"
          onClick={onBack}
          className="mb-3 flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回使命列表
        </button>
        <h1 className="text-lg font-semibold text-text-primary">
          {mission.title || "使命工作区"}
        </h1>
        {mission.objective && (
          <p className="mt-0.5 max-w-2xl text-sm leading-relaxed text-text-secondary">
            {mission.objective}
          </p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
          <code className="font-data">{mission.mission_id}</code>
          <Badge tone={riskTone}>{RISK_LABELS[mission.risk_level]}</Badge>
          <Status tone={stateTone} label={stateLabel(state)} />
          {mission.paused && <Badge tone="warning">已暂停</Badge>}
          {mission.safe_mode && <Badge tone="info">安全模式</Badge>}
          {mission.provider_unavailable && (
            <Badge tone="danger">模型服务不可用</Badge>
          )}
          {mission.provider && <span>· {mission.provider}</span>}
          <span>· 创建于 {formatDate(mission.created_at)}</span>
        </div>
      </div>

      {/* 内容 + 右侧垂直信任阶梯（始终可见） */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <TabBar active={activeTab} onChange={setActiveTab} />
          {activeTab === "plan" && (
            <PlanTab
              mission={mission}
              isPlanning={isPlanning}
              planError={planError}
              onPlan={handlePlan}
            />
          )}
          {activeTab === "execution" && (
            <ExecutionTab
              mission={mission}
              tools={tools}
              planSteps={mission.plan?.steps ?? []}
              toolsError={sideStatus.tools?.error ?? null}
              onRun={handleRun}
              onPause={handlePause}
              onResume={handleResume}
              onRollback={handleRollback}
              onToggleSafeMode={handleToggleSafeMode}
            />
          )}
          {activeTab === "result" && (
            <ResultTab mission={mission} evidence={evidence} />
          )}
          {activeTab === "timeline" && (
            <TimelineTab events={events} currentState={state} />
          )}
        </div>

        <aside className="lg:sticky lg:top-4">
          <TrustLadderPanel
            mission={mission}
            approvals={approvals}
            tools={tools}
            evidence={evidence}
            memory={memory}
            sideStatus={sideStatus}
            onDecide={setApprovalTarget}
          />
        </aside>
      </div>

      {/* 确认弹窗（控制动作） */}
      <MissionConfirmDialog
        open={confirm !== null}
        title={confirm?.title ?? ""}
        description={confirm?.description ?? ""}
        confirmLabel={confirm?.confirmLabel ?? ""}
        isDanger={confirm?.isDanger}
        isBusy={actionBusy}
        error={actionError}
        onConfirm={runConfirmed}
        onCancel={() => {
          setConfirm(null);
          setActionError(null);
        }}
      />

      {/* 审批决策弹窗（WHAT / WHY / 访问 / 风险 / 改变） */}
      <ApprovalDialog
        approval={approvalTarget}
        isBusy={approvalBusy}
        error={approvalError}
        onDecide={handleDecide}
        onClose={() => {
          setApprovalTarget(null);
          setApprovalError(null);
        }}
      />
    </div>
  );
}
