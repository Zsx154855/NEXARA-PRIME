"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";
import { useRuntimeData } from "@/lib/runtime-context";

/**
 * NEXARA TopBar — 健康默认静默，异常才出现状态条。
 * 无心跳轮询姿态（10s 轮询对用户不可见）。
 */
type TopBarProps = {
  onOpenCommandPalette: () => void;
};

export function TopBar({ onOpenCommandPalette }: TopBarProps) {
  const pathname = usePathname();
  const { overview, loading, error } = useRuntimeData();

  const current = NAV_ITEMS.find(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  );
  const title = current?.label ?? "首页";

  const isOffline = error !== null;
  const isUnhealthy = overview !== null && overview.system.healthy === false;

  return (
    <header className="flex h-14 items-center justify-between border-b border-border-subtle bg-surface-base px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold tracking-tight text-text-primary">{title}</h1>
        {/* 异常才出现：状态条（不打扰正常态） */}
        {(isOffline || isUnhealthy) && !loading && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
              isOffline
                ? "border-danger/20 bg-danger/10 text-danger"
                : "border-warning/20 bg-warning/10 text-warning",
            )}
            role="status"
            aria-live="polite"
          >
            {isOffline ? "运行时未连接" : "运行时异常"}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* ⌘K 产品动作入口 */}
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="hidden items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-subtle px-2.5 py-1.5 text-xs text-text-tertiary transition-colors duration-[var(--duration-micro)] hover:bg-surface-hover hover:text-text-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)] sm:flex"
          aria-label="打开命令面板 (⌘K)"
        >
          <Search className="size-3.5" aria-hidden="true" />
          <span className="hidden md:inline">搜索与操作</span>
          <kbd className="ml-1 rounded border border-border-subtle bg-surface-elevated px-1 py-0.5 text-xs text-text-tertiary">
            ⌘K
          </kbd>
        </button>

        {/* 设置入口（移动端导航无设置项） */}
        <Link
          href="/settings"
          className="rounded-lg p-1.5 text-text-tertiary transition-colors duration-[var(--duration-micro)] hover:bg-surface-hover hover:text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
          title="设置"
          aria-label="设置"
        >
          <Settings className="size-4" aria-hidden="true" />
        </Link>
      </div>
    </header>
  );
}
