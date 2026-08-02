"use client";

import { useState, useCallback, useEffect } from "react";
import type { NexaraAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Pause, Play, XCircle, Hand, Undo2,
  RotateCcw, Loader2, CheckCircle2,
  AlertTriangle,
} from "lucide-react";

interface HumanControlProps {
  api: NexaraAPI;
  missionId: string;
  className?: string;
}

const LABELS = {
  title: "人工控制",
  pause: "暂停",
  resume: "恢复",
  cancel: "取消任务",
  takeover: "接管控制",
  release: "释放控制",
  recover: "恢复执行",
  safeMode: "安全模式",
  noActions: "当前无可用操作",
  pauseDesc: "暂停任务执行，保存进度",
  resumeDesc: "从暂停处恢复执行",
  cancelDesc: "永久终止当前任务",
  takeoverDesc: "暂停自动调度，人工接管",
  releaseDesc: "释放人工控制，恢复自动",
  recoverDesc: "从最近检查点恢复",
  safeModeDesc: "仅允许只读操作",
  cancelled: "已取消",
  paused: "已暂停",
  controlling: "人工控制中",
  autonomous: "自动运行中",
} as const;

interface ControlState {
  control_state: string;
  mission_state: string;
  available_actions: string[];
  safe_mode?: boolean;
}

type ActionResult = { ok: boolean; reason_message?: string } | null;

export function HumanControl({ api, missionId, className }: HumanControlProps) {
  const [control, setControl] = useState<ControlState | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult>(null);

  const loadControl = useCallback(async () => {
    try {
      const data = await api.getMissionControl(missionId) as unknown as ControlState;
      setControl(data);
    } catch {
      // keep stale state
    } finally {
      setLoading(false);
    }
  }, [api, missionId]);

  useEffect(() => { loadControl(); }, [loadControl]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setActing(label);
    setResult(null);
    try {
      const r = await fn();
      setResult(r as ActionResult);
      await loadControl();
    } catch (e) {
      setResult({ ok: false, reason_message: e instanceof Error ? e.message : "操作失败" });
    } finally {
      setActing(null);
    }
  }

  if (loading) return <ControlSkeleton />;

  const actions = control?.available_actions ?? [];
  const cs = control?.control_state ?? "unknown";

  return (
    <div className={cn("space-y-4", className)}>
      {/* Status */}
      <div className="flex items-center gap-3 p-3 rounded-xl border border-champagne/15 bg-ivory/60 backdrop-blur-lg">
        <div className={cn(
          "h-2.5 w-2.5 rounded-full",
          cs === "autonomous" && "bg-moss-green",
          cs === "paused" && "bg-amber",
          cs === "human_controlled" && "bg-champagne",
          cs === "cancelled" && "bg-warm-red",
        )} />
        <span className="text-sm font-medium text-graphite">
          {cs === "autonomous" && LABELS.autonomous}
          {cs === "paused" && LABELS.paused}
          {cs === "human_controlled" && LABELS.controlling}
          {cs === "cancelled" && LABELS.cancelled}
          {!["autonomous", "paused", "human_controlled", "cancelled"].includes(cs) && cs}
        </span>
        {control?.mission_state && (
          <span className="text-xs text-graphite/50 ml-auto">{control.mission_state}</span>
        )}
      </div>

      {/* Result feedback */}
      {result && (
        <div className={cn(
          "p-3 rounded-xl border text-sm",
          result.ok ? "border-moss-green/20 bg-moss-green/5 text-moss-green" : "border-warm-red/20 bg-warm-red/5 text-warm-red",
        )}>
          {result.ok ? <CheckCircle2 className="inline h-4 w-4 mr-1" /> : <AlertTriangle className="inline h-4 w-4 mr-1" />}
          {result.ok ? "操作成功" : result.reason_message || "操作失败"}
        </div>
      )}

      {/* Actions */}
      {actions.length === 0 ? (
        <p className="text-sm text-graphite/40">{LABELS.noActions}</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {actions.includes("pause") && !actions.includes("resume") && (
            <ControlButton icon={Pause} label={LABELS.pause} desc={LABELS.pauseDesc}
              loading={acting === LABELS.pause}
              onClick={() => act(LABELS.pause, () => api.pauseMission(missionId))} />
          )}
          {actions.includes("resume") && (
            <ControlButton icon={Play} label={LABELS.resume} desc={LABELS.resumeDesc}
              loading={acting === LABELS.resume}
              onClick={() => act(LABELS.resume, () => api.resumeMission(missionId))} />
          )}
          {actions.includes("cancel") && (
            <ControlButton icon={XCircle} label={LABELS.cancel} desc={LABELS.cancelDesc} danger
              loading={acting === LABELS.cancel}
              onClick={() => act(LABELS.cancel, () => api.cancelMission(missionId))} />
          )}
          {actions.includes("takeover") && (
            <ControlButton icon={Hand} label={LABELS.takeover} desc={LABELS.takeoverDesc}
              loading={acting === LABELS.takeover}
              onClick={() => act(LABELS.takeover, () => api.takeoverMission(missionId))} />
          )}
          {actions.includes("release_takeover") && (
            <ControlButton icon={Undo2} label={LABELS.release} desc={LABELS.releaseDesc}
              loading={acting === LABELS.release}
              onClick={() => act(LABELS.release, () => api.releaseTakeover(missionId))} />
          )}
          <ControlButton icon={RotateCcw} label={LABELS.recover} desc={LABELS.recoverDesc}
            loading={acting === LABELS.recover}
            onClick={() => act(LABELS.recover, () => api.recoverMission(missionId))} />
        </div>
      )}
    </div>
  );
}

function ControlButton({ icon: Icon, label, desc, danger, loading, onClick }: {
  icon: typeof Pause; label: string; desc: string;
  danger?: boolean; loading?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={cn(
        "flex flex-col items-start gap-1 p-3 rounded-xl border transition-all min-h-[44px]",
        "hover:shadow-md active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-champagne",
        danger
          ? "border-warm-red/20 bg-warm-red/5 hover:bg-warm-red/10"
          : "border-champagne/15 bg-ivory/60 hover:bg-ivory/80",
        loading && "opacity-50 cursor-wait",
      )}
      aria-label={label}
    >
      <span className="flex items-center gap-2">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
        <span className={cn("text-sm font-medium", danger ? "text-warm-red" : "text-graphite")}>{label}</span>
      </span>
      <span className="text-[11px] text-graphite/40 text-left">{desc}</span>
    </button>
  );
}

function ControlSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-10 bg-graphite/5 rounded-xl" />
      <div className="grid grid-cols-2 gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-graphite/5 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
