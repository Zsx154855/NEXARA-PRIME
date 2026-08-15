// ─── 记忆区页面头：编辑式单列（与治理区同构）───
// overline 归入「记忆」→ 宋体标题 → 一句副标题说明本页回答的问题。

import type { ReactNode } from "react";

type MemoryHeaderProps = {
  title: string;
  /** 一句话说明本页回答的问题 */
  subtitle: string;
  /** 右上角动作（如刷新按钮） */
  action?: ReactNode;
};

export function MemoryHeader({ title, subtitle, action }: MemoryHeaderProps) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-border-subtle pb-6">
      <div className="min-w-0">
        <p className="text-xs text-text-tertiary">记忆</p>
        <h1 className="mt-1 font-editorial text-2xl text-text-primary">{title}</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-text-secondary">
          {subtitle}
        </p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}
