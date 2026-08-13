"use client";

import { cn } from "@/lib/utils";
import { RefreshCw, Circle, Search } from "lucide-react";
import type { RuntimeOverview } from "@/types";
import type { Screen } from "@/components/DashboardShell";

interface TopBarProps {
  screen: Screen;
  overview: RuntimeOverview | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onOpenCommandPalette: () => void;
}

const SCREEN_LABELS: Record<Screen, string> = {
  dashboard: "控制台",
  missions: "使命",
  "mission-workspace": "使命详情",
  conversation: "对话",
  evidence: "证据",
  governance: "治理",
  "runtime-health": "运行时健康",
  memory: "记忆",
};

export function TopBar({
  screen,
  overview,
  loading,
  error,
  onRefresh,
  onOpenCommandPalette,
}: TopBarProps) {
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

  return (
    <header className="flex h-14 items-center justify-between border-b border-taupe bg-ivory px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold tracking-tight text-graphite">
          {SCREEN_LABELS[screen] ?? "控制台"}
        </h1>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* ⌘K search trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="hidden sm:flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-subtle px-2.5 py-1 text-xs text-text-tertiary hover:bg-surface-hover hover:text-text-secondary transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          aria-label="打开命令面板 (⌘K)"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden md:inline">搜索</span>
          <kbd className="ml-1 rounded bg-surface-elevated px-1 py-0.5 text-[10px] text-text-tertiary border border-border-subtle">
            ⌘K
          </kbd>
        </button>

        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium border",
            statusColor,
          )}
          role="status"
        >
          <Circle className={cn("h-2 w-2 fill-current", loading && "animate-pulse")} />
          {statusText}
        </span>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded-lg p-1.5 text-stone/60 hover:bg-mist-gray hover:text-graphite transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          title="刷新数据"
          aria-label="刷新数据"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>
    </header>
  );
}
