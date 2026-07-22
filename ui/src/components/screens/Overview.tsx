"use client";

import type { RuntimeOverview } from "@/types";
import { LayoutDashboard, ShieldCheck, Activity, FileSearch } from "lucide-react";
import { cn } from "@/lib/utils";

interface OverviewProps {
  overview: RuntimeOverview | null;
  loading: boolean;
  error: string | null;
  onMissionSelect: (missionId: string) => void;
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
      <div className="grid grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl bg-taupe/30" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-taupe/30" />
    </div>
  );
}

export function Overview({ overview, loading, error, onMissionSelect }: OverviewProps) {
  if (loading && !overview) return <Skeleton />;
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 text-4xl">⚠</div>
        <h2 className="mb-2 text-lg font-semibold text-graphite">无法连接到 Runtime</h2>
        <p className="mb-4 max-w-md text-sm text-stone">{error}</p>
        <p className="text-xs text-stone/50">请确认 NEXARA PRIME 服务正在运行 · python -m nexara_prime</p>
      </div>
    );
  }
  if (!overview) return null;

  const { system, missions, approvals, evidence } = overview;
  const pendingApprovals = approvals.filter((a: any) => a.status === "pending").length;
  const activeMissions = missions.filter(
    (m: any) => m.state !== "Completed" && m.state !== "Failed" && m.state !== "RolledBack"
  ).length;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={LayoutDashboard} label="活跃任务" value={activeMissions} color="text-graphite" />
        <StatCard icon={ShieldCheck} label="待审批" value={pendingApprovals} color={pendingApprovals > 0 ? "text-amber" : "text-stone/40"} />
        <StatCard icon={Activity} label="系统模式" value={system.mode} color="text-champagne" />
        <StatCard icon={FileSearch} label="证据数量" value={evidence.length} color="text-moss-green" />
      </div>

      {/* System status */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-taupe bg-mist-gray px-5 py-3">
        <span className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] border",
          system.healthy ? "bg-moss-green/10 text-moss-green border-moss-green/20" : "bg-warm-red/10 text-warm-red border-warm-red/20"
        )}>
          {system.healthy ? "系统健康" : "系统异常"}
        </span>
        <span className="text-xs text-stone">Provider: {system.mode} · 人类控制: {system.human_control ? "启用" : "关闭"}</span>
        {system.mock_default && (
          <span className="rounded-full bg-amber/10 px-3 py-0.5 text-[11px] text-amber border border-amber/20">安全模式</span>
        )}
      </div>

      {/* Mission stream */}
      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-stone/70">任务流 ({missions.length})</h2>
        {missions.length === 0 ? (
          <div className="rounded-xl border border-taupe bg-ivory py-12 text-center">
            <p className="text-sm text-stone/60">暂无任务</p>
            <p className="mt-1 text-xs text-stone/40">通过 CLI 或 API 创建第一个任务</p>
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
    <div className="flex items-center gap-4 rounded-xl border border-taupe bg-ivory p-4">
      <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-mist-gray", color)}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-stone/60">{label}</div>
        <div className={cn("text-xl font-bold", color)}>{value}</div>
      </div>
    </div>
  );
}
