"use client";

import type { Screen } from "./DashboardShell";
import type { RuntimeOverview } from "@/types";
import {
  LayoutDashboard,
  Rocket,
  FileSearch,
  ShieldCheck,
  Activity,
  Brain,
  MessageSquare,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Nav definition ──

interface NavGroup {
  label: string;
  items: NavItem[];
}

interface NavItem {
  id: Screen;
  label: string;
  icon: typeof LayoutDashboard;
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "使命",
    items: [
      { id: "dashboard", label: "控制台", icon: LayoutDashboard },
      { id: "missions", label: "使命", icon: Rocket },
    ],
  },
  {
    label: "协作",
    items: [
      { id: "conversation", label: "对话", icon: MessageSquare },
    ],
  },
  {
    label: "工具",
    items: [
      { id: "evidence", label: "证据", icon: FileSearch },
      { id: "memory", label: "记忆", icon: Brain },
    ],
  },
  {
    label: "系统",
    items: [
      { id: "governance", label: "治理", icon: ShieldCheck },
      { id: "runtime-health", label: "健康", icon: Activity },
    ],
  },
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
          m.state !== "RolledBack",
      ).length ?? 0
    : 0;

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-60 flex-col border-r border-border-subtle bg-surface-subtle">
        {/* Brand */}
        <div className="flex h-16 items-center gap-3 border-b border-border-subtle px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-graphite text-xs font-bold text-ivory">
            柏
          </div>
          <div>
            <div className="text-sm font-bold tracking-wider text-text-primary">
              Nexara-柏韩
            </div>
            <div className="text-[10px] uppercase tracking-widest text-text-tertiary">
              Control Plane
            </div>
          </div>
        </div>

        {/* Live Stats */}
        <div className="border-b border-border-subtle px-5 py-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-tertiary">活跃使命</span>
            <span className="text-sm font-bold text-text-primary tabular-nums">
              {activeMissions}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-[11px] text-text-tertiary">待审批</span>
            <span
              className={cn(
                "text-sm font-bold tabular-nums",
                pendingApprovals > 0 ? "text-warning" : "text-text-disabled",
              )}
            >
              {pendingApprovals}
            </span>
          </div>
        </div>

        {/* Navigation — grouped */}
        <nav className="flex-1 space-y-5 overflow-auto px-3 py-4" aria-label="主导航">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <h3 className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-text-tertiary">
                {group.label}
              </h3>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = screen === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => onNavigate(item.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all",
                        "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus-ring",
                        active
                          ? [
                              "bg-surface-active text-text-primary font-semibold",
                              "shadow-[inset_2px_0_0_var(--accent-primary)]",
                            ]
                          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                      )}
                      aria-current={active ? "page" : undefined}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          active ? "text-accent-primary" : "text-text-tertiary",
                        )}
                      />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Recent Missions */}
        {overview?.missions?.length ? (
          <div className="border-t border-border-subtle px-3 py-3">
            <h3 className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-text-tertiary">
              最近使命
            </h3>
            {overview.missions.slice(-4).reverse().map((m) => (
              <button
                key={m.mission_id}
                onClick={() => onMissionSelect(m.mission_id)}
                className="block w-full truncate rounded-md px-2 py-1.5 text-left text-xs text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus-ring"
                title={m.title ?? m.mission_id}
              >
                <span
                  className={cn(
                    "mr-1.5 inline-block h-1.5 w-1.5 rounded-full",
                    m.state === "Completed" && "bg-success",
                    m.state === "Failed" && "bg-danger",
                    m.state === "Blocked" || m.state === "Approval" && "bg-warning",
                    !["Completed", "Failed", "Blocked", "Approval"].includes(m.state) && "bg-accent-primary",
                  )}
                />
                {m.title ?? m.mission_id?.slice(0, 18)}
              </button>
            ))}
          </div>
        ) : null}

        {/* Footer */}
        <div className="border-t border-border-subtle px-5 py-3">
          <div className="text-[10px] text-text-disabled">NSEC V2.1 · 人类控制</div>
        </div>
      </aside>

      {/* Mobile Bottom Navigation */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-border-subtle bg-surface-elevated px-2 py-1.5 lg:hidden shadow-lg"
        aria-label="移动导航"
      >
        {NAV_GROUPS.flatMap((g) => g.items).slice(0, 5).map((item) => {
          const Icon = item.icon;
          const active = screen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                "flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] transition-colors",
                active ? "text-accent-primary" : "text-text-tertiary",
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-5 w-5" />
              <span className="leading-tight">{item.label}</span>
            </button>
          );
        })}
      </nav>
      {/* Spacer for mobile bottom nav */}
      <div className="h-14 lg:hidden" />
    </>
  );
}
