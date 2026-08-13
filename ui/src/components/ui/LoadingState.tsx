import { cn } from "@/lib/utils";

type LoadingStateProps = {
  /** 正在发生什么（步骤级描述，10s 轮询约束下无 token 级承诺） */
  label?: string;
  /** 唯一允许的持续动画 = 进度条；无总量时细线推进 */
  progress?: number;
  className?: string;
};

/**
 * NEXARA LoadingState — 静止优先。
 * 禁 spinner 永转 / pulse-soft / 无限闪烁。
 */
export function LoadingState({ label, progress, className }: LoadingStateProps) {
  return (
    <div
      className={cn("flex flex-col gap-3", className)}
      role="status"
      aria-live="polite"
    >
      {label && <p className="text-sm text-text-secondary">{label}</p>}
      <div
        className="h-px w-full overflow-hidden rounded-full bg-taupe"
        aria-hidden="true"
      >
        <div
          className={cn(
            "h-full rounded-full bg-gold-text",
            progress === undefined
              ? "w-1/3 animate-[slide-progress_1.6s_var(--ease-standard)_infinite]"
              : "transition-[width] duration-[var(--duration-small)]",
          )}
          style={progress !== undefined ? { width: `${Math.min(100, Math.max(0, progress))}%` } : undefined}
        />
      </div>
    </div>
  );
}
