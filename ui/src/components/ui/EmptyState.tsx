import { cn } from "@/lib/utils";
import { Button } from "./Button";

type EmptyStateProps = {
  /** 现在是什么状态 */
  title: string;
  /** 为什么 + 下一步是什么（禁止「暂无数据」） */
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
  className?: string;
};

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-dashed border-border-default bg-surface-subtle/50 px-6 py-10",
        className,
      )}
    >
      {icon && <div className="text-text-tertiary">{icon}</div>}
      <h2 className="font-editorial text-lg text-text-primary">{title}</h2>
      <p className="max-w-md text-sm leading-relaxed text-text-secondary">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="ghost" size="sm" onClick={onAction} className="mt-2">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
