import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "./Badge";

type PermissionStateProps = {
  /** 需要什么权限/许可（人话） */
  requirement: string;
  /** 为什么需要（风险上下文） */
  reason?: string;
  /** 当前权限状态标注（诚实：无假授权按钮） */
  marker?: "AUTH_BACKEND_REQUIRED" | "CONNECTOR_REQUIRED" | "PLANNED";
  className?: string;
};

/**
 * NEXARA PermissionState — 六态之「Permission Required」。
 * 无后端授权能力时如实标注，绝不渲染假授权按钮。
 */
export function PermissionState({
  requirement,
  reason,
  marker = "AUTH_BACKEND_REQUIRED",
  className,
}: PermissionStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-md border border-warning/30 bg-warning/5 px-5 py-4",
        className,
      )}
      role="status"
    >
      <div className="flex items-center gap-2">
        <ShieldAlert className="size-4 text-warning" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-warning">
          需要权限：{requirement}
        </h3>
        <Badge tone="warning">{marker}</Badge>
      </div>
      {reason && (
        <p className="text-xs leading-relaxed text-text-secondary">{reason}</p>
      )}
      <p className="text-xs text-text-tertiary">
        当前为本地单用户模式，此权限面由运行时治理引擎保障；用户级授权为 PLANNED 能力，无假授权入口。
      </p>
    </div>
  );
}
