"use client";

import { Screen } from "./DashboardShell";
import { RuntimeOverview } from "@/types";
import {
  LayoutDashboard,
  PlusCircle,
  Bot,
  ShieldCheck,
  FileSearch,
  Puzzle,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { id: Screen; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "主脑总览", icon: LayoutDashboard },
  { id: "mission-creator", label: "任务创建", icon: PlusCircle },
  { id: "agent-team", label: "智能体团队", icon: Bot },
  { id: "approvals", label: "审批中心", icon: ShieldCheck },
  { id: "evidence", label: "证据与回执", icon: FileSearch },
  { id: "capabilities", label: "能力注册", icon: Puzzle },
  { id: "health", label: "系统健康", icon: Activity },
];

interface SidebarProps {
  screen: Screen;
  onNavigate: (s: Screen) => void;
  onMissionSelect: (missionId: string) => void;
  overview: RuntimeOverview | null;
}

export function Sidebar({ screen, onNavigate, onMissionSelect, overview }: SidebarProps) {
  const pendingApprovals = overview
    ? overview.approvals?.filter((a) => a.status === "pending").length ?? 0
    : 0;

  const activeMissions = overview
    ? overview.missions?.filter(
        (m) =>
          m.state !== "Completed" &&
          m.state !== "Failed" &&
          m.state !== "RolledBack"
      ).length ?? 0
    : 0;

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-60 flex-col border-r border-taupe bg-mist-gray">
        {/* Brand */}
        <div className="flex h-16 items-center gap-3 border-b border-taupe px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-graphite text-xs font-bold text-ivory">
            N
          </div>
          <div>
            <div className="text-sm font-bold tracking-wider text-graphite">NEXARA</div>
            <div className="text-[10px] uppercase tracking-widest text-stone/60">主脑控制台</div>
          </div>
        </div>

        {/* Stats */}
        <div className="border-b border-taupe px-5 py-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-stone/60">活跃任务</span>
            <span className="text-sm font-bold text-graphite">{activeMissions}</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-xs text-stone/60">待审批</span>
            <span className={cn("text-sm font-bold", pendingApprovals > 0 ? "text-amber" : "text-stone/40")}>
              {pendingApprovals}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all",
                  active
                    ? "bg-ivory text-graphite shadow-sm ring-1 ring-taupe/50 font-medium"
                    : "text-stone/70 hover:bg-ivory/50 hover:text-graphite"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Recent Missions */}
        {overview?.missions?.length ? (
          <div className="border-t border-taupe px-3 py-4">
            <div className="mb-2 text-[10px] uppercase tracking-widest text-stone/50">最近任务</div>
            {overview.missions.slice(-5).reverse().map((m) => (
              <button
                key={m.mission_id}
                onClick={() => onMissionSelect(m.mission_id)}
                className="block w-full truncate rounded-md px-2 py-1 text-left text-xs text-stone/70 hover:bg-ivory/50 hover:text-graphite transition-colors"
                title={m.title ?? m.mission_id}
              >
                <span
                  className={cn(
                    "mr-1 inline-block h-1.5 w-1.5 rounded-full",
                    m.state === "Completed" ? "bg-moss-green"
                    : m.state === "Failed" ? "bg-warm-red"
                    : m.state === "Blocked" || m.state === "Approval" ? "bg-amber"
                    : "bg-champagne"
                  )}
                />
                {m.title ?? m.mission_id?.slice(0, 22)}
              </button>
            ))}
          </div>
        ) : null}

        {/* Footer */}
        <div className="border-t border-taupe px-5 py-3">
          <div className="text-[10px] text-stone/40">NSEC V2.0 · 人类控制</div>
        </div>
      </aside>

      {/* Mobile Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-taupe bg-ivory px-2 py-1.5 lg:hidden shadow-lg">
        {NAV_ITEMS.slice(0, 5).map((item) => {
          const Icon = item.icon;
          const active = screen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                "flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] transition-colors",
                active ? "text-champagne" : "text-stone/50"
              )}
            >
              <Icon className="h-5 w-5" />
              <span className="leading-tight">{item.label.slice(0, 3)}</span>
            </button>
          );
        })}
        {/* More menu item for remaining screens */}
        <button
          onClick={() => {
            const remaining = NAV_ITEMS.slice(5).map(i => i.id);
            const currentIdx = remaining.indexOf(screen);
            const next = remaining[(currentIdx + 1) % remaining.length] ?? remaining[0];
            if (next) onNavigate(next);
          }}
          className="flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] text-stone/50 transition-colors"
        >
          <Puzzle className="h-5 w-5" />
          <span className="leading-tight">更多</span>
        </button>
      </nav>
      {/* Spacer for mobile bottom nav */}
      <div className="h-14 lg:hidden" />
    </>
  );
}
