import { cn } from "@/lib/utils";

/**
 * NEXARA AgentIndicator — presence 四信号（subtle presence）。
 * 数据全部来自真实端点：
 *  - 当前动作：/api/tools（ToolInvocation.tool_name）+ 状态机
 *  - 状态表达：MissionState + adaptive explain 退化呈现
 *    （SoulExpression/SoulDisposition 无 HTTP 端点，接线前不渲染）
 *  - identity 徽章：表达式层数据源 UNRESOLVED——未提供时如实显示「未提供」
 * 禁拟人机器人头像。
 */
type AgentIndicatorProps = {
  /** 当前执行者（persona/role 名；无数据时显示「未提供」） */
  actor?: string | null;
  /** 当前动作短语（如「正在写入报告」） */
  activity?: string;
  /** 步骤进度（如「第 3 步 / 7」）；仅当有真实数据 */
  step?: string;
  /** 是否处于等待用户的状态（琥珀色） */
  isWaiting?: boolean;
  className?: string;
};

export function AgentIndicator({
  actor,
  activity,
  step,
  isWaiting,
  className,
}: AgentIndicatorProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-elevated px-3 py-1.5",
        className,
      )}
    >
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          isWaiting ? "bg-warning animate-dot-form" : "bg-success",
        )}
        aria-hidden="true"
      />
      <span className="text-xs text-text-secondary">
        {actor ?? "未提供"}
        {activity && ` · ${activity}`}
        {step && ` · ${step}`}
      </span>
    </div>
  );
}
