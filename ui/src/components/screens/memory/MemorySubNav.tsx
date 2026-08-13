// ─── 记忆区子导航：浏览 / 候选 / 知识 / 统计 ───

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const SUB_ITEMS = [
  { href: "/memory", label: "浏览" },
  { href: "/memory/candidates", label: "候选" },
  { href: "/memory/knowledge", label: "知识" },
  { href: "/memory/stats", label: "统计" },
] as const;

export function MemorySubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="记忆分区" className="flex flex-wrap gap-x-6 border-b border-border-subtle">
      {SUB_ITEMS.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-0.5 py-2.5 text-sm transition-colors duration-[var(--duration-micro)]",
              isActive
                ? "border-gold-text font-medium text-text-primary"
                : "border-transparent text-text-secondary hover:text-text-primary",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
