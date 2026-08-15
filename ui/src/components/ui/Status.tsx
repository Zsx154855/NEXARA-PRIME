import { cn } from "@/lib/utils";

/**
 * NEXARA Status — 状态三重编码（色 + 图标 + 文字）。
 * 状态语义用达标加深色（success #4E7A55 / warning #8F5F2A /
 * danger #B34A4A / info #5B6B78），装饰色永不承载状态语义。
 */
const toneDot = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  neutral: "bg-taupe",
  gold: "bg-champagne",
} as const;

const toneText = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
  neutral: "text-text-secondary",
  gold: "text-gold-text",
} as const;

type StatusProps = {
  tone: keyof typeof toneDot;
  label: string;
  icon?: React.ReactNode;
  className?: string;
  /** 事件性状态点：一次成形动画 */
  isEvent?: boolean;
};

export function Status({ tone, label, icon, className, isEvent }: StatusProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs",
        toneText[tone],
        className,
      )}
      role="status"
    >
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          toneDot[tone],
          isEvent && "animate-dot-form",
        )}
        aria-hidden="true"
      />
      {icon}
      <span>{label}</span>
    </span>
  );
}

export { toneDot, toneText };
