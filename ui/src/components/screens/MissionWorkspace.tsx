"use client";

import { useState, useEffect, useCallback } from "react";
import type { NexaraAPI } from "@/lib/api";
import type {
  MissionSnapshot,
  PlanStep,
  Event,
  ToolInvocation,
} from "@/types";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  RotateCcw,
  Shield,
  Ban,
  WifiOff,
  Activity,
  Clock,
  FileText,
  Zap,
  User,
  ChevronRight,
  ListChecks,
  ScrollText,
  History,
  XCircle,
  Info,
} from "lucide-react";

// ─── Props ───

interface MissionWorkspaceProps {
  api: NexaraAPI;
  missionId: string;
  onBack: () => void;
}

// ─── Chinese Labels ───

const LABELS = {
  title: "任务工作区",
  loading: "加载中…",
  error: "加载失败",
  notFound: "任务未找到",
  retry: "重试",
  back: "返回仪表盘",
  backToOverview: "返回总览",
  missionInfo: "任务信息",
  stateRail: "状态轨道",
  contract: "合约信息",
  planSteps: "执行规划",
  eventTimeline: "事件时间线",
  toolInvocations: "工具调用",
  failureCodes: "故障代码",
  reasonCodes: "原因代码",
  objective: "目标",
  sourceDir: "源目录",
  riskLevel: "风险等级",
  provider: "供应器",
  paused: "已暂停",
  safeMode: "安全模式",
  pause: "暂停",
  resume: "恢复",
  rollback: "回滚",
  enableSafeMode: "启用安全模式",
  disableSafeMode: "禁用安全模式",
  confirmPause: "确定要暂停此任务吗？",
  confirmResume: "确定要恢复此任务吗？",
  confirmRollback: "确定要回滚此任务吗？回滚后任务将不可执行。",
  confirmSafeMode: "确定要{action}安全模式吗？",
  confirm: "确认",
  cancel: "取消",
  noData: "暂无数据",
  noSteps: "暂无规划步骤",
  noEvents: "暂无事件记录",
  noTools: "暂无工具调用",
  action: "操作",
  status: "状态",
  timestamp: "时间",
  duration: "耗时",
  yes: "是",
  no: "否",
  loadingMission: "加载任务详情…",
  loadingPlan: "加载规划…",
  loadingEvents: "加载事件…",
  loadingTools: "加载工具调用…",
};

// ─── State Labels ───

const STATE_LABELS: Record<string, string> = {
  Intent: "意图",
  Context: "上下文",
  Contract: "合约",
  Plan: "规划",
  Simulation: "模拟",
  Approval: "审批中",
  Execution: "执行中",
  Verification: "验证中",
  Evidence: "证据收集",
  MemoryPatch: "记忆更新",
  Evaluation: "评估",
  Completed: "已完成",
  Blocked: "已阻塞",
  Failed: "已失败",
  RolledBack: "已回滚",
  Created: "已创建",
  Triaged: "已分类",
  Planned: "已规划",
  Scheduled: "已调度",
  AwaitingApproval: "等待审批",
  Running: "运行中",
  Verifying: "验证中",
  Paused: "已暂停",
  Cancelled: "已取消",
  RollingBack: "回滚中",
};

const STATE_ORDER: string[] = [
  "Intent",
  "Context",
  "Contract",
  "Plan",
  "Simulation",
  "Approval",
  "Execution",
  "Verification",
  "Evidence",
  "MemoryPatch",
  "Evaluation",
  "Completed",
];

function isStateTerminal(state: string): boolean {
  return ["Completed", "Failed", "RolledBack", "Cancelled"].includes(state);
}

// ─── Sub: Confirm Dialog ───

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  confirmVariant,
  onConfirm,
  onCancel,
  loading,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  confirmVariant: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/20 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-sm animate-fade-in rounded-xl border border-taupe bg-ivory p-6 shadow-xl">
        <h3 className="text-base font-semibold text-graphite">{title}</h3>
        <p className="mt-2 text-sm text-stone">{message}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-taupe bg-ivory px-4 py-2 text-sm font-medium text-graphite transition-colors hover:bg-mist-gray disabled:cursor-not-allowed disabled:opacity-50"
          >
            {LABELS.cancel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-ivory transition-colors disabled:cursor-not-allowed disabled:opacity-50",
              confirmVariant === "danger"
                ? "bg-warm-red hover:bg-warm-red/90"
                : "bg-champagne hover:bg-champagne/90"
            )}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sub: Skeleton ───

function MissionSkeleton() {
  return (
    <div className="space-y-4 animate-pulse-soft">
      <div className="skeleton h-6 w-48 rounded" />
      <div className="skeleton h-4 w-72 rounded" />
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="skeleton h-32 rounded-lg" />
        <div className="skeleton h-32 rounded-lg" />
        <div className="skeleton h-32 rounded-lg" />
      </div>
      <div className="skeleton h-48 rounded-lg" />
    </div>
  );
}

// ─── Sub: State Rail ───

function StateRail({ currentState }: { currentState: string }) {
  const currentIdx = STATE_ORDER.indexOf(currentState);
  const visibleStates =
    currentIdx < 6
      ? STATE_ORDER.slice(0, 7)
      : STATE_ORDER.slice(Math.min(currentIdx - 3, 5), currentIdx + 4);

  return (
    <div className="rounded-lg border border-taupe bg-ivory p-4">
      <div className="mb-2 flex items-center gap-1.5">
        <Activity className="h-4 w-4 text-champagne" />
        <span className="text-xs font-medium text-graphite">{LABELS.stateRail}</span>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {visibleStates.map((state, i) => {
          const idx = STATE_ORDER.indexOf(state);
          const isCurrent = state === currentState;
          const isPast = idx < currentIdx;
          const isLast = i === visibleStates.length - 1;

          return (
            <div key={state} className="flex items-center gap-1 shrink-0">
              <div
                className={cn(
                  "flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium transition-all",
                  isCurrent
                    ? "bg-champagne/15 text-champagne ring-1 ring-champagne/40"
                    : isPast
                      ? "bg-moss-green/10 text-moss-green"
                      : "bg-mist-gray text-stone/60"
                )}
              >
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    isCurrent
                      ? "bg-champagne"
                      : isPast
                        ? "bg-moss-green"
                        : "bg-taupe"
                  )}
                />
                {STATE_LABELS[state] ?? state}
              </div>
              {!isLast && (
                <ChevronRight
                  className={cn(
                    "h-3 w-3",
                    isPast ? "text-moss-green/30" : "text-taupe"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Sub: Info Card ───

function InfoRow({
  label,
  value,
  icon,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  icon?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="flex items-center gap-1.5 text-stone">
        {icon}
        {label}
      </span>
      <span
        className={cn(
          "text-right font-medium text-graphite max-w-[60%] truncate",
          mono && "font-mono text-xs"
        )}
      >
        {value ?? "—"}
      </span>
    </div>
  );
}

// ─── Sub: Event Timeline ───

function EventTimeline({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <History className="h-8 w-8 text-stone/30" />
        <p className="text-sm text-stone">{LABELS.noEvents}</p>
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {events.slice(0, 20).map((ev, i) => (
        <div key={ev.event_id ?? i} className="flex gap-3 px-1 py-1.5">
          <div className="flex flex-col items-center">
            <div className="h-2 w-2 rounded-full bg-champagne/50" />
            {i < events.length - 1 && (
              <div className="mt-1 w-px flex-1 bg-taupe" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-xs font-medium text-graphite">
                {ev.event_type}
              </span>
              <span className="shrink-0 text-[10px] text-stone">
                {new Date(ev.timestamp).toLocaleString("zh-CN", {
                  month: "2-digit",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-stone">
              <span className="flex items-center gap-0.5">
                <User className="h-2.5 w-2.5" />
                {ev.actor}
              </span>
              {ev.trace_id && (
                <code className="font-mono">{ev.trace_id.slice(0, 12)}</code>
              )}
            </div>
          </div>
        </div>
      ))}
      {events.length > 20 && (
        <p className="pt-1 text-center text-[11px] text-stone">
          还有 {events.length - 20} 条事件… 
        </p>
      )}
    </div>
  );
}

// ─── Sub: Tool Invocations ───

function ToolList({ tools }: { tools: ToolInvocation[] }) {
  if (tools.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <Zap className="h-8 w-8 text-stone/30" />
        <p className="text-sm text-stone">{LABELS.noTools}</p>
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {tools.map((tool) => {
        const isError = !!tool.failure_code || tool.status === "error";
        return (
          <div
            key={tool.invocation_id}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-xs transition-colors",
              isError ? "bg-warm-red/5" : "bg-mist-gray"
            )}
          >
            <Zap
              className={cn(
                "h-3.5 w-3.5 shrink-0",
                isError ? "text-warm-red" : "text-champagne"
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <code className="font-mono font-medium text-graphite">
                  {tool.tool_name}
                </code>
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                    isError
                      ? "bg-warm-red/10 text-warm-red"
                      : tool.status === "success"
                        ? "bg-moss-green/10 text-moss-green"
                        : "bg-amber/10 text-amber"
                  )}
                >
                  {tool.status ?? "—"}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[10px] text-stone">
                {tool.duration_ms > 0 && (
                  <span>{(tool.duration_ms / 1000).toFixed(1)}s</span>
                )}
                {tool.failure_code && (
                  <span className="text-warm-red">{tool.failure_code}</span>
                )}
                {tool.reason_code && (
                  <span>{tool.reason_code}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Component ───

export function MissionWorkspace({
  api,
  missionId,
  onBack,
}: MissionWorkspaceProps) {
  const [mission, setMission] = useState<MissionSnapshot | null>(null);
  const [planSteps, setPlanSteps] = useState<PlanStep[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [tools, setTools] = useState<ToolInvocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<() => void>(() => {});
  const [confirmTitle, setConfirmTitle] = useState("");
  const [confirmMessage, setConfirmMessage] = useState("");
  const [confirmLabel, setConfirmLabel] = useState("");
  const [confirmVariant, setConfirmVariant] = useState<"danger" | "default">(
    "default"
  );
  const [actionLoading, setActionLoading] = useState(false);

  // ── Load all mission data ──
  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [missionData, eventData, toolData] = await Promise.all([
        api.getMission(missionId),
        api.fetchEvents(missionId).catch(() => [] as Event[]),
        api.fetchTools ? api.fetchTools(missionId).catch(() => [] as ToolInvocation[]) : Promise.resolve([] as ToolInvocation[]),
      ]);
      setMission(missionData);
      setEvents(eventData);
      setTools(toolData);

      // Try to load plan steps from mission data
      if (missionData.spec?.risks) {
        // In a real implementation, this would come from a plan endpoint
        // For now, derive from mission state
        setPlanSteps([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api, missionId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Action helpers ──
  const showConfirm = (
    title: string,
    message: string,
    label: string,
    variant: "danger" | "default",
    action: () => Promise<void>
  ) => {
    setConfirmTitle(title);
    setConfirmMessage(message);
    setConfirmLabel(label);
    setConfirmVariant(variant);
    setConfirmAction(() => action);
    setConfirmOpen(true);
  };

  const handlePause = () =>
    showConfirm(
      LABELS.confirmPause,
      LABELS.confirmPause,
      LABELS.pause,
      "default",
      async () => {
        setActionLoading(true);
        try {
          const res = await api.pauseMission(missionId);
          setMission(res);
        } catch (err) {
          console.error(err);
        } finally {
          setActionLoading(false);
          setConfirmOpen(false);
        }
      }
    );

  const handleResume = () =>
    showConfirm(
      LABELS.confirmResume,
      LABELS.confirmResume,
      LABELS.resume,
      "default",
      async () => {
        setActionLoading(true);
        try {
          const res = await api.resumeMission(missionId);
          setMission(res);
        } catch (err) {
          console.error(err);
        } finally {
          setActionLoading(false);
          setConfirmOpen(false);
        }
      }
    );

  const handleRollback = () =>
    showConfirm(
      LABELS.confirmRollback,
      LABELS.confirmRollback,
      LABELS.rollback,
      "danger",
      async () => {
        setActionLoading(true);
        try {
          const res = await api.rollbackMission(missionId);
          setMission(res);
        } catch (err) {
          console.error(err);
        } finally {
          setActionLoading(false);
          setConfirmOpen(false);
        }
      }
    );

  const toggleSafeMode = () => {
    const current = mission?.safe_mode ?? false;
    const action = current ? "禁用" : "启用";
    showConfirm(
      LABELS.confirmSafeMode.replace("{action}", action),
      `确定要${action}安全模式吗？`,
      action,
      current ? "default" : "danger",
      async () => {
        setActionLoading(true);
        try {
          const res = await api.setSafeMode(missionId, { enabled: !current });
          setMission(res);
        } catch (err) {
          console.error(err);
        } finally {
          setActionLoading(false);
          setConfirmOpen(false);
        }
      }
    );
  };

  // ── Loading State ──
  if (loading && !mission) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={onBack}
          className="mb-4 flex items-center gap-1.5 text-xs text-stone transition-colors hover:text-graphite"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {LABELS.backToOverview}
        </button>
        <MissionSkeleton />
      </div>
    );
  }

  // ── Error State ──
  if (error && !mission) {
    return (
      <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-taupe bg-ivory px-8 py-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-warm-red/10">
            <WifiOff className="h-7 w-7 text-warm-red" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-graphite">{LABELS.error}</h3>
            <p className="mt-1 text-sm text-stone">{error}</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 rounded-lg border border-taupe bg-ivory px-4 py-2 text-sm font-medium text-graphite transition-colors hover:bg-mist-gray"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              {LABELS.backToOverview}
            </button>
            <button
              onClick={loadAll}
              className="flex items-center gap-1.5 rounded-lg bg-champagne px-4 py-2 text-sm font-medium text-ivory transition-colors hover:bg-champagne/90"
            >
              <Loader2 className="h-3.5 w-3.5" />
              {LABELS.retry}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Empty / Not Found ──
  if (!mission) {
    return (
      <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-taupe bg-ivory px-8 py-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-mist-gray">
            <Ban className="h-7 w-7 text-stone" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-graphite">{LABELS.notFound}</h3>
            <p className="mt-1 text-sm text-stone">
              任务 <code className="font-mono">{missionId.slice(0, 16)}…</code> 不存在或已被删除
            </p>
          </div>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 rounded-lg border border-taupe bg-ivory px-4 py-2 text-sm font-medium text-graphite transition-colors hover:bg-mist-gray"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {LABELS.backToOverview}
          </button>
        </div>
      </div>
    );
  }

  const currentState = mission.state ?? mission.current_state;

  // ── Render ──
  return (
    <div className="animate-fade-in space-y-6">
      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel={confirmLabel}
        confirmVariant={confirmVariant}
        onConfirm={confirmAction}
        onCancel={() => setConfirmOpen(false)}
        loading={actionLoading}
      />

      {/* Back + Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={onBack}
            className="mb-2 flex items-center gap-1.5 text-xs text-stone transition-colors hover:text-graphite"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {LABELS.backToOverview}
          </button>
          <h1 className="text-lg font-semibold text-graphite">
            {mission.title || "任务工作区"}
          </h1>
          <p className="mt-0.5 text-sm text-stone">
            <code className="font-mono text-xs">{mission.mission_id}</code>
            {mission.created_at && (
              <span className="ml-2">
                · 创建于 {new Date(mission.created_at).toLocaleString("zh-CN")}
              </span>
            )}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2">
          {!isStateTerminal(currentState) && (
            <>
              {mission.paused ? (
                <button
                  onClick={handleResume}
                  className="flex items-center gap-1.5 rounded-lg border border-moss-green/30 bg-moss-green/5 px-3 py-1.5 text-xs font-medium text-moss-green transition-colors hover:bg-moss-green/10"
                >
                  <PlayCircle className="h-3.5 w-3.5" />
                  {LABELS.resume}
                </button>
              ) : (
                <button
                  onClick={handlePause}
                  className="flex items-center gap-1.5 rounded-lg border border-amber/30 bg-amber/5 px-3 py-1.5 text-xs font-medium text-amber transition-colors hover:bg-amber/10"
                >
                  <PauseCircle className="h-3.5 w-3.5" />
                  {LABELS.pause}
                </button>
              )}
              <button
                onClick={handleRollback}
                className="flex items-center gap-1.5 rounded-lg border border-warm-red/30 bg-warm-red/5 px-3 py-1.5 text-xs font-medium text-warm-red transition-colors hover:bg-warm-red/10"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {LABELS.rollback}
              </button>
              <button
                onClick={toggleSafeMode}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                  mission.safe_mode
                    ? "border-moss-green/30 bg-moss-green/5 text-moss-green hover:bg-moss-green/10"
                    : "border-amber/30 bg-amber/5 text-amber hover:bg-amber/10"
                )}
              >
                <Shield className="h-3.5 w-3.5" />
                {mission.safe_mode ? LABELS.disableSafeMode : LABELS.enableSafeMode}
              </button>
            </>
          )}
        </div>
      </div>

      {/* State Rail */}
      <StateRail currentState={currentState} />

      {/* Top Info Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Mission Info */}
        <div className="rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-2 flex items-center gap-1.5">
            <Info className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.missionInfo}</h3>
          </div>
          <div className="space-y-1 divide-y divide-taupe/50">
            <InfoRow
              label={LABELS.objective}
              value={mission.objective ?? mission.spec?.objective}
            />
            <InfoRow
              label="状态"
              value={STATE_LABELS[currentState] ?? currentState}
              icon={<Activity className="h-3.5 w-3.5" />}
            />
            <InfoRow
              label={LABELS.riskLevel}
              value={mission.risk_level ?? mission.spec?.risk_level}
              icon={<AlertTriangle className="h-3.5 w-3.5" />}
            />
            <InfoRow
              label={LABELS.provider}
              value={mission.provider}
            />
            <InfoRow
              label="供应器状态"
              value={mission.provider_unavailable ? "不可用" : "可用"}
              icon={
                mission.provider_unavailable ? (
                  <XCircle className="h-3.5 w-3.5 text-warm-red" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5 text-moss-green" />
                )
              }
            />
          </div>
        </div>

        {/* Contract Info */}
        <div className="rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-2 flex items-center gap-1.5">
            <ScrollText className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.contract}</h3>
          </div>
          <div className="space-y-1 divide-y divide-taupe/50">
            <InfoRow
              label="审批状态"
              value={
                mission.approval_status === "approved"
                  ? "已批准"
                  : mission.approval_status === "rejected"
                    ? "已拒绝"
                    : mission.approval_status === "pending"
                      ? "待审批"
                      : mission.approval_status ?? "—"
              }
              icon={
                mission.approval_status === "approved" ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-moss-green" />
                ) : mission.approval_status === "rejected" ? (
                  <XCircle className="h-3.5 w-3.5 text-warm-red" />
                ) : (
                  <Clock className="h-3.5 w-3.5 text-amber" />
                )
              }
            />
            <InfoRow
              label="证据数量"
              value={String(mission.evidence_count ?? 0)}
              icon={<FileText className="h-3.5 w-3.5" />}
            />
            <InfoRow
              label="回执状态"
              value={
                mission.receipt_status === "present" ? "已存在" : "缺失"
              }
              icon={
                mission.receipt_status === "present" ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-moss-green" />
                ) : (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber" />
                )
              }
            />
            <InfoRow
              label="记忆状态"
              value={
                mission.memory_patch_status === "patched"
                  ? "已更新"
                  : "未更新"
              }
            />
            <InfoRow
              label="评估状态"
              value={
                mission.evaluation_status === "passed"
                  ? "通过"
                  : mission.evaluation_status === "failed"
                    ? "未通过"
                    : "未评估"
              }
            />
          </div>
        </div>

        {/* Status Summary */}
        <div className="rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-2 flex items-center gap-1.5">
            <ListChecks className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.status}</h3>
          </div>
          <div className="space-y-3">
            {/* Paused indicator */}
            {mission.paused && (
              <div className="flex items-center gap-2 rounded-lg bg-amber/5 px-3 py-2 text-xs">
                <PauseCircle className="h-4 w-4 text-amber" />
                <span className="font-medium text-amber">{LABELS.paused}</span>
              </div>
            )}

            {/* Safe mode indicator */}
            {mission.safe_mode && (
              <div className="flex items-center gap-2 rounded-lg bg-moss-green/5 px-3 py-2 text-xs">
                <Shield className="h-4 w-4 text-moss-green" />
                <span className="font-medium text-moss-green">{LABELS.safeMode}</span>
              </div>
            )}

            {/* Source dir */}
            {mission.spec?.source_dir && (
              <InfoRow
                label={LABELS.sourceDir}
                value={mission.spec.source_dir}
                mono
              />
            )}

            {/* Failure codes */}
            {mission.terminal_reason && (
              <InfoRow
                label="终止原因"
                value={mission.terminal_reason}
                icon={<AlertTriangle className="h-3.5 w-3.5 text-warm-red" />}
              />
            )}

            {/* Retry count */}
            {mission.retry_count > 0 && (
              <InfoRow label="重试次数" value={String(mission.retry_count)} />
            )}

            {/* Recovery pointer */}
            {mission.recovery_pointer && (
              <InfoRow
                label="恢复指针"
                value={mission.recovery_pointer}
                mono
              />
            )}
          </div>
        </div>
      </div>

      {/* Bottom Grid: Plan Steps + Events + Tools */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Plan Steps */}
        <div className="lg:col-span-1 rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-1.5">
            <ListChecks className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.planSteps}</h3>
            <span className="ml-auto text-[10px] text-stone">
              {planSteps.length} 步
            </span>
          </div>
          {planSteps.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <ListChecks className="h-8 w-8 text-stone/30" />
              <p className="text-sm text-stone">{LABELS.noSteps}</p>
              <p className="text-[11px] text-stone/60">
                规划将在任务通过审批后生成
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {planSteps.map((step, i) => (
                <div
                  key={step.step_id}
                  className="flex items-center gap-3 rounded-lg bg-mist-gray px-3 py-2"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-champagne/10 text-[10px] font-medium text-champagne">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-graphite">
                      {step.title}
                    </div>
                    <div className="mt-0.5 text-[10px] text-stone">
                      {step.role} · {step.persona}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Event Timeline */}
        <div className="lg:col-span-1 rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-1.5">
            <History className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.eventTimeline}</h3>
            <span className="ml-auto text-[10px] text-stone">
              {events.length} 条
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            <EventTimeline events={events} />
          </div>
        </div>

        {/* Tool Invocations */}
        <div className="lg:col-span-1 rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-1.5">
            <Zap className="h-4 w-4 text-champagne" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.toolInvocations}</h3>
            <span className="ml-auto text-[10px] text-stone">
              {tools.length} 次
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            <ToolList tools={tools} />
          </div>
        </div>
      </div>

      {/* Failure Codes + Reason Codes */}
      {tools.some((t) => t.failure_code || t.reason_code) && (
        <div className="rounded-xl border border-taupe bg-ivory p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4 text-warm-red" />
            <h3 className="text-xs font-semibold text-graphite">{LABELS.failureCodes}</h3>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {tools
              .filter((t) => t.failure_code)
              .map((t) => (
                <div
                  key={t.invocation_id + "_fail"}
                  className="flex items-center gap-2 rounded-lg bg-warm-red/5 px-3 py-2 text-xs"
                >
                  <XCircle className="h-3.5 w-3.5 shrink-0 text-warm-red" />
                  <code className="font-mono font-medium text-warm-red">
                    {t.failure_code}
                  </code>
                  <span className="text-stone">· {t.tool_name}</span>
                </div>
              ))}
            {tools
              .filter((t) => t.reason_code && !t.failure_code)
              .map((t) => (
                <div
                  key={t.invocation_id + "_reason"}
                  className="flex items-center gap-2 rounded-lg bg-amber/5 px-3 py-2 text-xs"
                >
                  <Info className="h-3.5 w-3.5 shrink-0 text-amber" />
                  <code className="font-mono font-medium text-amber">
                    {t.reason_code}
                  </code>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
