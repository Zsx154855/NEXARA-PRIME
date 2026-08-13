"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { House, MessageSquare, Rocket, ShieldCheck, Database, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, type NavSectionId } from "@/lib/navigation";
import { useRuntimeData } from "@/lib/runtime-context";
import { BrandMark } from "@/components/brand/BrandMark";

const SECTION_ICONS: Record<NavSectionId, typeof House> = {
  home: House,
  conversation: MessageSquare,
  missions: Rocket,
  trust: ShieldCheck,
  memory: Database,
  settings: Settings,
};

/**
 * NEXARA 侧栏 — 六区单层导航（无分组标签轰炸，最小 12px）。
 * 品牌区：App Icon + 柏韩·NEXARA + 本地单用户模式（诚实标注）。
 */
export function NavSidebar() {
  const pathname = usePathname();
  const { overview } = useRuntimeData();

  const pendingApprovals = overview
    ? overview.approvals?.filter((a) => a.status === "pending").length ?? 0
    : 0;

  const activeMissions = overview
    ? overview.missions?.filter(
        (m) =>
          m.state !== "Completed" && m.state !== "Failed" && m.state !== "RolledBack",
      ).length ?? 0
    : 0;

  const sectionOf = (path: string): NavSectionId | null => {
    const match = NAV_ITEMS.find((item) => path === item.path || path.startsWith(`${item.path}/`));
    return match?.id ?? null;
  };
  const activeSection = sectionOf(pathname);

  return (
    <aside className="hidden w-60 flex-col border-r border-border-subtle bg-surface-subtle lg:flex">
      {/* Brand */}
      <Link
        href="/"
        className="flex h-16 items-center gap-3 border-b border-border-subtle px-5"
      >
        <BrandMark className="rounded-[7px]" />
        <div>
          <div className="text-sm font-semibold tracking-wide text-text-primary">
            柏韩 · NEXARA
          </div>
          <div className="text-xs text-text-tertiary">本地单用户模式</div>
        </div>
      </Link>

      {/* Live counts */}
      <div className="flex items-center gap-4 border-b border-border-subtle px-5 py-3">
        <span className="text-xs text-text-secondary">
          活跃使命{" "}
          <span className="font-semibold text-text-primary tabular-nums">{activeMissions}</span>
        </span>
        <span className="text-xs text-text-secondary">
          待审批{" "}
          <span
            className={cn(
              "font-semibold tabular-nums",
              pendingApprovals > 0 ? "text-warning" : "text-text-primary",
            )}
          >
            {pendingApprovals}
          </span>
        </span>
      </div>

      {/* Navigation — 六区单层 */}
      <nav className="flex-1 overflow-auto px-3 py-4" aria-label="主导航">
        <div className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = SECTION_ICONS[item.id];
            const active = activeSection === item.id;
            return (
              <Link
                key={item.id}
                href={item.path}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors duration-[var(--duration-micro)]",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]",
                  active
                    ? "bg-surface-active font-semibold text-text-primary"
                    : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                )}
                aria-current={active ? "page" : undefined}
              >
                <Icon
                  className={cn(
                    "size-4 shrink-0",
                    active ? "text-gold-text" : "text-text-tertiary",
                  )}
                  aria-hidden="true"
                />
                {item.label}
                {item.id === "trust" && pendingApprovals > 0 && (
                  <span
                    className="ml-auto inline-flex size-4 items-center justify-center rounded-full bg-warning text-[10px] font-semibold text-ivory"
                    aria-label={`${pendingApprovals} 项待审批`}
                  >
                    {pendingApprovals}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-border-subtle px-5 py-3">
        <div className="text-xs text-text-tertiary">NSEC V2.1 · 人类控制</div>
      </div>
    </aside>
  );
}
