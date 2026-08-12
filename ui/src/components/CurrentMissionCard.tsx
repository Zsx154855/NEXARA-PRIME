"use client";

import { Play, Clock, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MissionSnapshot, MissionState } from "@/types";

// ── Props ──

interface CurrentMissionCardProps {
  mission: MissionSnapshot | null;
  onContinue: () => void;
  onCreateMission: () => void;
}

// ── Helpers ──

function stateLabel(s: MissionState): string {
  const map: Partial<Record<MissionState, string>> = {
    Intent: "意图",
    Context: "上下文",
    Contract: "合约",
    Plan: "计划",
    Simulation: "仿真",
    Approval: "审批",
    Execution: "执行中",
    Verification: "验证",
    Evidence: "证据",
    MemoryPatch: "记忆回写",
    Evaluation: "评估",
    Completed: "已完成",
    Blocked: "已阻塞",
    Failed: "已失败",
    RolledBack: "已回滚",
    Paused: "已暂停",
  };
  return map[s] ?? s;
}

function isActive(s: MissionState): boolean {
  return !["Completed", "Failed", "RolledBack"].includes(s);
}

// ── Component ──

export function CurrentMissionCard({
  mission,
  onContinue,
  onCreateMission,
}: CurrentMissionCardProps) {
  // Empty state
  if (!mission) {
    return (
      <div
        className="flex flex-col items-center gap-3 rounded-2xl border border-border-subtle bg-surface-subtle px-6 py-8 text-center"
        role="region"
        aria-label="当前使命"
      >
        <Clock className="h-8 w-8 text-text-tertiary" />
        <div>
          <p className="text-sm font-medium text-text-secondary">
            当前没有正在执行的使命
          </p>
          <p className="mt-1 text-xs text-text-tertiary">
            创建一个新使命以开始
          </p>
        </div>
        <button
          onClick={onCreateMission}
          className="mt-2 rounded-lg bg-accent-primary px-5 py-2.5 text-sm font-medium text-ivory transition-colors hover:bg-accent-primary/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
          aria-label="创建新使命"
        >
          创建使命
        </button>
      </div>
    );
  }

  const active = isActive(mission.state);
  const StateIcon = mission.state === "Completed" ? CheckCircle2
    : mission.state === "Failed" ? AlertTriangle
    : mission.state === "Blocked" ? AlertTriangle
    : Play;

  return (
    <div
      className="rounded-2xl border border-border-subtle bg-surface-elevated px-6 py-5 shadow-sm"
      role="region"
      aria-label={`当前使命: ${mission.title}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {/* Status + title */}
          <div className="flex items-center gap-2.5">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium border",
                active && "bg-success/10 text-success border-success/20",
                mission.state === "Completed" && "bg-success/10 text-success border-success/20",
                mission.state === "Failed" && "bg-danger/10 text-danger border-danger/20",
                mission.state === "Blocked" && "bg-warning/10 text-warning border-warning/20",
                mission.state === "Paused" && "bg-warning/10 text-warning border-warning/20",
                !active && mission.state !== "Completed" && mission.state !== "Failed" && mission.state !== "Blocked" && mission.state !== "Paused" && "bg-accent-soft/10 text-accent-primary border-accent-primary/20",
              )}
            >
              <StateIcon className="h-3 w-3" />
              {stateLabel(mission.state)}
            </span>
            {mission.paused && (
              <span className="text-[11px] text-warning font-medium">已暂停</span>
            )}
          </div>

          <h3 className="mt-2 text-base font-semibold text-text-primary truncate">
            {mission.title}
          </h3>

          {/* Info row */}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-tertiary">
            <span>{mission.mission_id?.slice(0, 14)}…</span>
            {mission.evidence_count > 0 && (
              <span>证据 {mission.evidence_count}</span>
            )}
            {mission.receipt_status === "present" && (
              <span className="text-success">Receipt ✓</span>
            )}
          </div>
        </div>

        {/* Continue button */}
        {active && (
          <button
            onClick={onContinue}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-graphite px-5 py-2.5 text-sm font-medium text-ivory transition-all hover:bg-graphite/90 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
            aria-label="继续当前使命"
          >
            <Play className="h-4 w-4" />
            继续任务
          </button>
        )}
      </div>
    </div>
  );
}
