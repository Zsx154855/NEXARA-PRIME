"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { House, MessageSquare, Rocket, ShieldCheck, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import { MOBILE_NAV_ITEMS } from "@/lib/navigation";

const MOBILE_ICONS = {
  home: House,
  conversation: MessageSquare,
  missions: Rocket,
  trust: ShieldCheck,
  memory: Database,
} as const;

/**
 * 390px 底部导航 5 项（首页/对话/使命/治理/记忆）；
 * 设置移至 TopBar。触控目标 ≥44px。
 */
export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around border-t border-border-subtle bg-surface-elevated px-2 pb-[env(safe-area-inset-bottom)] lg:hidden"
      aria-label="移动导航"
    >
      {MOBILE_NAV_ITEMS.map((item) => {
        const Icon = MOBILE_ICONS[item.id as keyof typeof MOBILE_ICONS];
        const active = pathname === item.path || pathname.startsWith(`${item.path}/`);
        return (
          <Link
            key={item.id}
            href={item.path}
            className={cn(
              "flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg text-xs transition-colors duration-[var(--duration-micro)]",
              active ? "text-gold-text" : "text-text-tertiary",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="size-5" aria-hidden="true" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
