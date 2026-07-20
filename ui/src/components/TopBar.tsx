"use client";

import { cn } from "@/lib/utils";
import { RefreshCw, Circle } from "lucide-react";
import type { RuntimeOverview } from "@/types";
import type { Screen } from "@/components/DashboardShell";

interface TopBarProps {
  screen: Screen;
  overview: RuntimeOverview | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

const SCREEN_LABELS: Record<Screen, string> = {
  overview: "主脑总览",
  "mission-creator": "任务创建",
  "mission-workspace": "任务工作区",
  "agent-team": "智能体团队",
  approvals: "审批中心",
  evidence: "证据与回执",
  capabilities: "能力注册",
  health: "系统健康",
};

export function TopBar({ screen, overview, loading, error, onRefresh }: TopBarProps) {
  const statusColor = error
    ? "bg-warm-red/10 text-warm-red border-warm-red/20"
    : !overview && loading
      ? "bg-taupe/30 text-stone border-taupe/40"
      : overview?.system.healthy
        ? "bg-moss-green/10 text-moss-green border-moss-green/20"
        : "bg-amber/10 text-amber border-amber/20";

  const statusText = error
    ? "离线"
    : !overview && loading
      ? "连接中…"
      : overview?.system.healthy
        ? "在线"
        : "异常";

  const mode = overview?.system.mode ?? "unknown";
  const isMock = overview?.system.mock_default ?? false;

  return (
    <header className="flex h-14 items-center justify-between border-b border-taupe bg-ivory px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold tracking-tight text-graphite">
          {SCREEN_LABELS[screen]}
        </h1>
        {overview && (
          <span
            className={cn(
              "rounded-full px-3 py-0.5 text-[11px] font-medium border",
              isMock
                ? "bg-amber/10 text-amber border-amber/20"
                : "bg-champagne/10 text-champagne border-champagne/20"
            )}
          >
            {isMock ? "安全模式" : mode}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium border",
            statusColor
          )}
        >
          <Circle className={cn("h-2 w-2 fill-current", loading && "animate-pulse")} />
          {statusText}
        </span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded-lg p-1.5 text-stone/60 hover:bg-mist-gray hover:text-graphite transition-colors"
          title="刷新数据"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>
    </header>
  );
}
