"use client";

import type { RuntimeOverview, RuntimeStats } from "@/types";
import { LayoutDashboard, ShieldCheck, Rocket, Server, CheckCircle2, XCircle, Play } from "lucide-react";
import { cn } from "@/lib/utils";

interface OverviewProps {
  overview: RuntimeOverview | null;
  stats: RuntimeStats | null;
  loading: boolean;
  error: string | null;
  onMissionSelect: (missionId: string) => void;
  onCreateMission: () => void;
}

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
        <span key={s} className={cn(
          "rounded px-1.5 py-0.5 text-[9px]",
          i < idx && "bg-moss-green/10 text-moss-green",
          i === idx && "bg-champagne/20 text-champagne font-medium ring-1 ring-champagne/30",
          i > idx && "bg-taupe/20 text-stone/40",
        )}>{s}</span>
      ))}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse-soft space-y-4">
      <div className="h-8 w-48 rounded bg-taupe/50" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl bg-taupe/30" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-taupe/30" />
    </div>
  );
}

export function Overview({ overview, stats, loading, error, onMissionSelect, onCreateMission }: OverviewProps) {
  if (loading && !overview) return <Skeleton />;
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-warm-red/10">
          <Server className="h-8 w-8 text-warm-red/60" />
        </div>
        <h2 className="mb-2 text-lg font-semibold text-graphite">Runtime 不可用</h2>
        <p className="mb-4 max-w-md text-sm text-stone">{error}</p>
        <p className="text-xs text-stone/50">请确认 NEXARA PRIME 服务正在运行 · python -m nexara_prime</p>
      </div>
    );
  }
  if (!overview) return null;

  const { system, missions, approvals } = overview;
  const pendingApprovals = stats?.pending_approvals ?? approvals.filter((a: any) => a.status === "pending").length;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-graphite">控制台</h1>
          <p className="mt-0.5 text-sm text-stone">
            {stats ? `${stats.total_missions} 个任务 · ${stats.completed_missions} 已完成` : "NEXARA Control Plane"}
          </p>
        </div>
        <button
          onClick={onCreateMission}
          className="flex items-center gap-2 rounded-lg bg-champagne px-4 py-2.5 text-sm font-medium text-ivory transition-colors hover:bg-champagne/90"
          title="创建新任务"
          aria-label="创建新任务"
        >
          <Rocket className="h-4 w-4" />
          创建任务
        </button>
      </div>

      {/* Stats Row — from N1 endpoint */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
        <StatCard icon={Rocket} label="活跃任务" value={stats?.active_missions ?? overview.missions.filter((m: any) => m.state !== "Completed" && m.state !== "Failed" && m.state !== "RolledBack").length} color="text-graphite" />
        <StatCard icon={CheckCircle2} label="已完成" value={stats?.completed_missions ?? 0} color="text-moss-green" />
        <StatCard icon={Play} label="进行中" value={stats?.active_missions ?? 0} color="text-champagne" />
        <StatCard icon={XCircle} label="失败" value={stats?.failed_missions ?? 0} color={stats?.failed_missions ? "text-warm-red" : "text-stone/40"} />
        <StatCard icon={ShieldCheck} label="待审批" value={pendingApprovals} color={pendingApprovals > 0 ? "text-amber" : "text-stone/40"} />
      </div>

      {/* System status + Runtime Health */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-taupe bg-mist-gray px-5 py-3">
        <span className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] border",
          system.healthy ? "bg-moss-green/10 text-moss-green border-moss-green/20" : "bg-warm-red/10 text-warm-red border-warm-red/20"
        )}>
          {system.healthy ? "系统在线" : "系统异常"}
        </span>
        <span className="text-xs text-stone">
          Provider: {stats?.provider ?? system.mode}
          {stats?.provider_available === false && <span className="ml-1 text-warm-red">· 不可用</span>}
        </span>
        {system.mock_default && (
          <span className="rounded-full bg-amber/10 px-3 py-0.5 text-[11px] text-amber border border-amber/20">Mock 模式</span>
        )}
        {stats && (
          <>
            <span className="text-xs text-stone/50">·</span>
            <span className="text-xs text-stone">证据: {stats.total_evidence}</span>
            <span className="text-xs text-stone">恢复: {stats.recovery_state === "healthy" ? <span className="text-moss-green">健康</span> : <span className="text-warm-red">{stats.recovery_state}</span>}</span>
          </>
        )}
      </div>

      {/* Mission stream */}
      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-stone/70">最近活动 ({missions.length})</h2>
        {missions.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-taupe bg-ivory py-16 text-center">
            <Rocket className="h-10 w-10 text-stone/20" />
            <div>
              <p className="text-sm font-medium text-stone/60">还没有任务</p>
              <p className="mt-1 text-xs text-stone/40">点击"创建任务"开始，或通过 CLI 创建</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {missions.slice().reverse().map((m: any) => (
              <button key={m.mission_id} onClick={() => onMissionSelect(m.mission_id)}
                className="w-full rounded-xl border border-taupe bg-ivory p-4 text-left transition-all hover:border-champagne/30 hover:shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-semibold text-graphite">{m.title}</h3>
                    <p className="mt-1 line-clamp-2 text-xs text-stone">{m.objective}</p>
                  </div>
                  <span className={cn(
                    "ml-3 shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium",
                    m.state==="Completed"?"bg-moss-green/10 text-moss-green":
                    m.state==="Failed"?"bg-warm-red/10 text-warm-red":
                    m.state==="Blocked"?"bg-amber/10 text-amber":
                    m.state==="Execution"?"bg-champagne/10 text-champagne":
                    "bg-taupe/20 text-stone"
                  )}>{m.state}</span>
                </div>
                <div className="mt-3"><StateRail state={m.state} /></div>
                <div className="mt-2 flex items-center gap-4 text-[10px] text-stone/50">
                  <span>{m.mission_id?.slice(0,12)}…</span>
                  {m.receipt_status==="present" && <span className="text-moss-green">Receipt ✓</span>}
                  {m.paused && <span className="text-amber">已暂停</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }: {
  icon: typeof LayoutDashboard; label: string; value: string | number; color: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-taupe bg-ivory p-4">
      <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-mist-gray", color)}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-stone/60">{label}</div>
        <div className={cn("text-xl font-bold", color)}>{value}</div>
      </div>
    </div>
  );
}
