// ─── 编辑式区块：发丝线分隔 + 宋体标题 + 右侧辅助信息 ───

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type SectionProps = {
  /** 唯一 id，用于 aria-labelledby 与锚点 */
  id: string;
  /** 小上标（归类，如「值守摘要」） */
  overline?: string;
  /** 宋体标题 */
  title: string;
  /** 右侧辅助文本（如「3 项」） */
  meta?: string;
  /** 右侧安静动作（如「查看全部」） */
  actionLabel?: string;
  onAction?: () => void;
  children: ReactNode;
  className?: string;
};

export function Section({
  id,
  overline,
  title,
  meta,
  actionLabel,
  onAction,
  children,
  className,
}: SectionProps) {
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className={cn("border-t border-border-subtle pt-8", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <div>
          {overline && (
            <p className="text-xs text-text-tertiary">{overline}</p>
          )}
          <h2
            id={`${id}-heading`}
            className="mt-1 font-editorial text-xl text-text-primary"
          >
            {title}
          </h2>
        </div>
        <div className="flex items-baseline gap-3">
          {meta && <p className="text-xs text-text-secondary">{meta}</p>}
          {actionLabel && onAction && (
            <button
              type="button"
              onClick={onAction}
              className="text-xs font-medium text-graphite underline decoration-border-default underline-offset-4 transition-colors hover:text-gold-text hover:decoration-gold-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
            >
              {actionLabel}
            </button>
          )}
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
