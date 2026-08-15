// ─── 治理区页面头：编辑式单列 ───
// overline 归类 → 宋体标题 → 一句副标题说明「这个页面回答什么问题」。
// 右侧 slot 留给轻量动作（如刷新）。

import type { ReactNode } from "react";

type TrustHeaderProps = {
  /** 归类小上标，如「治理」 */
  overline: string;
  title: string;
  /** 一句话说明本页回答的问题 */
  subtitle: string;
  /** 右上角动作（如刷新按钮） */
  action?: ReactNode;
};

export function TrustHeader({ overline, title, subtitle, action }: TrustHeaderProps) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-border-subtle pb-6">
      <div className="min-w-0">
        <p className="text-xs text-text-tertiary">{overline}</p>
        <h1 className="mt-1 font-editorial text-2xl text-text-primary">{title}</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-text-secondary">
          {subtitle}
        </p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}
