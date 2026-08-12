"use client";

import type { RuntimeOverview, RuntimeStats, MissionSnapshot, MemoryStats } from "@/types";
import {
  ShieldCheck,
  Server,
  CheckCircle2,
  XCircle,
  Play,
  Plus,
  Brain,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MemoryWheel } from "@/components/MemoryWheel";
import { CurrentMissionCard } from "@/components/CurrentMissionCard";

// ── Props ──

interface OverviewProps {
  overview: RuntimeOverview | null;
  stats: RuntimeStats | null;
  memoryStats: MemoryStats | null;
  loading: boolean;
  error: string | null;
  onMissionSelect: (missionId: string) => void;
  onCreateMission: () => void;
  onContinueMission: (mission: MissionSnapshot) => void;
  onViewMemory: () => void;
}

// ── State Rail (preserved from V1) ──

const ALL_STATES = [
  "Intent", "Context", "Contract", "Plan", "Simulation",
  "Approval", "Execution", "Verification", "Evidence",
  "MemoryPatch", "Evaluation", "Completed",
];

function StateRail({ state }: { state: string }) {
  const idx = ALL_STATES.indexOf(state);
  return (
    <div className="flex flex-wrap gap-1">
      {ALL_STATES.map((s, i) => (
        <span
          key={s}
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px]",
            i < idx && "bg-moss-green/10 text-moss-green",
            i === idx && "bg-champagne/20 text-champagne font-medium ring-1 ring-champagne/30",
            i > idx && "bg-taupe/20 text-stone/40",
          )}
        >
          {s}
        </span>
      ))}
    </div>
  );
}

// ── Helpers ──

function getActiveMission(overview: RuntimeOverview): MissionSnapshot | null {
  if (!overview?.missions?.length) return null;
  const active = overview.missions.filter(
    (m) => !["Completed", "Failed", "RolledBack"].includes(m.state),
  );
  if (active.length === 0) return null;
  // Prefer the most recently updated active mission
  active.sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );
  return active[0] ?? null;
}

// ── Skeleton ──

function Skeleton() {
  return (
    <div className="animate-pulse-soft space-y-6">
      <div className="flex flex-col items-center gap-6">
        <div className="h-[320px] w-[320px] rounded-2xl bg-taupe/30" />
        <div className="h-24 w-96 rounded-xl bg-taupe/30" />
      </div>
    </div>
  );
}

// ── Main ──

export function Overview({
  overview,
  stats,
  memoryStats,
  loading,
  error,
  onMissionSelect,
  onCreateMission,
  onContinueMission,
  onViewMemory,
}: OverviewProps) {
  if (loading && !overview) return <Skeleton />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-warm-red/10">
          <Server className="h-8 w-8 text-warm-red/60" />
        </div>
        <h2 className="mb-2 text-lg font-semibold text-text-primary">Runtime 不可用</h2>
        <p className="mb-4 max-w-md text-sm text-text-secondary">{error}</p>
        <p className="text-xs text-text-tertiary">
          请确认 NEXARA PRIME 服务正在运行
        </p>
      </div>
    );
  }

  if (!overview) return null;

  const activeMission = getActiveMission(overview);
  const system = overview.system;

  // Runtime status derivation
  const runtimeStatus: "healthy" | "degraded" | "offline" = !system.healthy
    ? "offline"
    : system.mock_default
      ? "degraded"
      : "healthy";

  return (
    <div className="animate-fade-in mx-auto flex max-w-2xl flex-col items-center gap-8 py-4">
      {/* ── Runtime Status Bar ── */}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium border",
            system.healthy
              ? "bg-moss-green/10 text-moss-green border-moss-green/20"
              : "bg-warm-red/10 text-warm-red border-warm-red/20",
          )}
          role="status"
          aria-label={system.healthy ? "系统在线" : "系统异常"}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", system.healthy ? "bg-moss-green" : "bg-warm-red")} />
          {system.healthy ? "系统在线" : "系统异常"}
        </span>

        <span className="text-xs text-text-secondary">
          {stats ? `${stats.total_missions} 使命 · ${stats.total_evidence} 证据` : "NEXARA Control Plane"}
        </span>

        {system.mock_default && (
          <span className="rounded-full bg-amber/10 px-2.5 py-0.5 text-[11px] text-amber border border-amber/20">
            安全模式
          </span>
        )}
      </div>

      {/* ── Memory Wheel ── */}
      <MemoryWheel
        activeQuadrant={null}
        onSelectQuadrant={onViewMemory}
        runtimeStatus={runtimeStatus}
        memoryCounts={
          memoryStats
            ? {
                perceptual: memoryStats.layers.working,
                procedural: memoryStats.layers.procedural,
                world: memoryStats.layers.semantic,
                relational: memoryStats.layers.episodic,
              }
            : undefined
        }
      />

      {/* ── Current Mission ── */}
      <div className="w-full">
        <CurrentMissionCard
          mission={activeMission}
          onContinue={() => {
            if (activeMission) onContinueMission(activeMission);
          }}
          onCreateMission={onCreateMission}
        />
      </div>

      {/* ── Action Hierarchy ── */}
      <div className="flex flex-wrap items-center justify-center gap-3">
        {/* Primary: Create (when no active mission, this is the main CTA) */}
        {!activeMission && (
          <button
            onClick={onCreateMission}
            className="flex items-center gap-2 rounded-xl bg-graphite px-6 py-3 text-sm font-semibold text-ivory shadow-sm transition-all hover:bg-graphite/90 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
            aria-label="创建新使命"
          >
            <Plus className="h-4 w-4" />
            创建使命
          </button>
        )}

        {/* Secondary: New Mission (when active mission exists, continue is in CurrentMissionCard) */}
        {activeMission && (
          <button
            onClick={onCreateMission}
            className="flex items-center gap-2 rounded-xl border border-border-default bg-surface-elevated px-5 py-3 text-sm font-medium text-text-primary transition-all hover:bg-surface-hover hover:border-border-focus focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
            aria-label="创建新使命"
          >
            <Plus className="h-4 w-4" />
            创建使命
          </button>
        )}

        {/* Tertiary: View Memory */}
        <button
          onClick={onViewMemory}
          className="flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-medium text-text-secondary transition-all hover:bg-surface-hover hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
          aria-label="查看记忆"
        >
          <Brain className="h-4 w-4" />
          查看记忆
        </button>
      </div>

      {/* ── Stats Row (compact, secondary info) ── */}
      <div className="flex flex-wrap items-center justify-center gap-4 text-[11px] text-text-tertiary">
        {stats && (
          <>
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-success" />
              已完成 {stats.completed_missions}
            </span>
            <span className="flex items-center gap-1">
              <Play className="h-3 w-3 text-accent-primary" />
              进行中 {stats.active_missions}
            </span>
            {stats.failed_missions > 0 && (
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3 text-danger" />
                失败 {stats.failed_missions}
              </span>
            )}
            {stats.pending_approvals > 0 && (
              <span className="flex items-center gap-1">
                <ShieldCheck className="h-3 w-3 text-warning" />
                待审批 {stats.pending_approvals}
              </span>
            )}
          </>
        )}
      </div>

      {/* ── Recent Activity (preserved, compact) ── */}
      {overview.missions.length > 0 && (
        <div className="w-full max-w-lg">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            最近活动
          </h2>
          <div className="space-y-2">
            {overview.missions.slice(-3).reverse().map((m) => (
              <button
                key={m.mission_id}
                onClick={() => onMissionSelect(m.mission_id)}
                className="w-full rounded-xl border border-border-subtle bg-surface-elevated p-3.5 text-left transition-all hover:border-accent-primary/20 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-semibold text-text-primary">
                      {m.title}
                    </h3>
                    <p className="mt-0.5 line-clamp-1 text-xs text-text-secondary">
                      {m.objective}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "ml-3 shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium",
                      m.state === "Completed" && "bg-moss-green/10 text-moss-green",
                      m.state === "Failed" && "bg-warm-red/10 text-warm-red",
                      m.state === "Blocked" && "bg-amber/10 text-amber",
                      m.state === "Execution" && "bg-champagne/10 text-champagne",
                      !["Completed", "Failed", "Blocked", "Execution"].includes(m.state) &&
                        "bg-taupe/20 text-stone",
                    )}
                  >
                    {m.state}
                  </span>
                </div>
                <div className="mt-2">
                  <StateRail state={m.state} />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
