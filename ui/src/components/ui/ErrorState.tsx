import { cn } from "@/lib/utils";
import { Button } from "./Button";

type ErrorStateProps = {
  /** 发生了什么（标题级 danger，扫视不漏） */
  title: string;
  /** 影响是什么 / NEXARA 做了什么 / 我现在可以做什么 */
  details?: string;
  actionLabel?: string;
  onAction?: () => void;
  /** 默认占主内容区顶部；嵌入卡片内可关 */
  isInline?: boolean;
  className?: string;
};

/**
 * NEXARA ErrorState — 「失败也要礼貌」：
 * 版面 calm、语气克制，但优先级必须可见——
 * danger 关键词为标题级、动作是实心主按钮、默认置顶。
 */
export function ErrorState({
  title,
  details,
  actionLabel,
  onAction,
  isInline,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-2 border-l-2 border-danger bg-danger/5 px-5 py-4",
        isInline ? "rounded-r-md" : "rounded-md",
        className,
      )}
    >
      <h2 className="text-sm font-semibold text-danger">{title}</h2>
      {details && (
        <p className="text-sm leading-relaxed text-text-secondary">{details}</p>
      )}
      {actionLabel && onAction && (
        <Button variant="danger" size="sm" onClick={onAction} className="mt-1 self-start">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
