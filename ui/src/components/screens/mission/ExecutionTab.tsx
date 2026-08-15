// 执行 Tab：当前动作 + 下一步（AgentIndicator subtle presence）、
// ToolInvocation 流（tool_name / status / failure_code / duration_ms / risk_level）、
// 控制动作（开始 / 暂停 / 恢复 / 回滚 / 安全模式，按状态机可用性）。
import {
  PauseCircle,
  PlayCircle,
  RotateCcw,
  Shield,
  Zap,
} from "lucide-react";
import { AgentIndicator } from "@/components/ui/AgentIndicator";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Status } from "@/components/ui/Status";
import { cn } from "@/lib/utils";
import type {
  MissionSnapshot,
  PlanStep,
  ToolInvocation,
} from "@/types";
import {
  PRE_EXECUTION_STATES,
  TERMINAL_STATES,
  failureLabel,
  formatDuration,
  stateLabel,
} from "./constants";

interface ExecutionTabProps {
  mission: MissionSnapshot;
  tools: ToolInvocation[];
  planSteps: PlanStep[];
  toolsError?: string | null;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onRollback: () => void;
  onToggleSafeMode: () => void;
}

function toolStatusTone(status: string): "success" | "danger" | "info" {
  if (status === "success" || status === "completed" || status === "done") {
    return "success";
  }
  if (status === "error" || status === "failed") {
    return "danger";
  }
  return "info";
}

export function ExecutionTab({
  mission,
  tools,
  planSteps,
  toolsError,
  onRun,
  onPause,
  onResume,
  onRollback,
  onToggleSafeMode,
}: ExecutionTabProps) {
  const state = mission.state ?? mission.current_state;
  const isTerminal = TERMINAL_STATES.includes(state);
  const lastTool = tools[tools.length - 1];
  const doneSteps = planSteps.filter(
    (s) => s.status !== "pending" && s.status !== "waiting",
  ).length;
  const step = planSteps.length > 0 ? `第 ${doneSteps} 步 / ${planSteps.length}` : undefined;
  const activity = lastTool
    ? lastTool.status === "running" || lastTool.status === "pending"
      ? `正在调用 ${lastTool.tool_name}`
      : `最近调用 ${lastTool.tool_name}`
    : undefined;
  const isWaiting =
    state === "Paused" ||
    state === "Blocked" ||
    state === "Degraded" ||
    state === "AwaitingApproval" ||
    state === "Approval";

  return (
    <div className="space-y-4">
      {/* 当前动作 + 下一步 */}
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <h2 className="text-sm font-semibold text-text-primary">当前动作</h2>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <AgentIndicator
            actor={undefined}
            activity={activity}
            step={step}
            isWaiting={isWaiting}
          />
          <p className="text-xs text-text-secondary">
            下一步：
            <code className="ml-1 font-data text-text-primary">
              {mission.pending_action ?? "—"}
            </code>
          </p>
        </div>
      </section>

      {/* 控制动作（按状态机可用性） */}
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <h2 className="text-sm font-semibold text-text-primary">控制</h2>
        {isTerminal ? (
          <p className="mt-2 text-xs text-text-secondary">
            使命已结束（{stateLabel(state)}），控制动作不可用。
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {PRE_EXECUTION_STATES.includes(state) && (
              <Button size="sm" onClick={onRun}>
                <PlayCircle className="h-3.5 w-3.5" />
                开始执行
              </Button>
            )}
            {mission.paused ? (
              <Button size="sm" onClick={onResume}>
                <PlayCircle className="h-3.5 w-3.5" />
                恢复
              </Button>
            ) : (
              <Button size="sm" variant="quiet" onClick={onPause}>
                <PauseCircle className="h-3.5 w-3.5" />
                暂停
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onRollback}>
              <RotateCcw className="h-3.5 w-3.5" />
              回滚
            </Button>
            <Button size="sm" variant="ghost" onClick={onToggleSafeMode}>
              <Shield className="h-3.5 w-3.5" />
              {mission.safe_mode ? "关闭安全模式" : "启用安全模式"}
            </Button>
          </div>
        )}
        {mission.safe_mode && !isTerminal && (
          <p className="mt-2 text-xs text-warning">
            安全模式已开启：未经批准的使命不会自动运行。
          </p>
        )}
      </section>

      {/* ToolInvocation 流 */}
      <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
        <div className="flex items-center gap-1.5">
          <Zap className="h-4 w-4 text-gold-text" />
          <h2 className="text-sm font-semibold text-text-primary">工具调用</h2>
          <span className="ml-auto text-xs text-text-tertiary">
            {tools.length} 次
          </span>
        </div>
        <div className="mt-3">
          {tools.length === 0 ? (
            toolsError ? (
              <EmptyState
                title="工具调用记录加载失败。"
                description={`数据未变，仅此视图未刷新：${toolsError}。执行开始后会如实记录每次工具调用。`}
              />
            ) : (
              <EmptyState
                title="还没有工具调用。"
                description={`当前状态：${stateLabel(state)}。执行开始后，每次工具调用（名称、状态、耗时、失败码）会如实记录在这里。`}
              />
            )
          ) : (
            <ol className="space-y-1.5">
              {tools.map((tool) => {
                const isError = !!tool.failure_code || tool.status === "error" || tool.status === "failed";
                return (
                  <li
                    key={tool.invocation_id}
                    className={cn(
                      "flex items-center gap-3 rounded-md border px-3 py-2.5",
                      isError
                        ? "border-danger/30 bg-danger/5"
                        : "border-border-subtle bg-surface-subtle",
                    )}
                  >
                    <Zap
                      className={cn(
                        "h-3.5 w-3.5 shrink-0",
                        isError ? "text-danger" : "text-gold-text",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="font-data text-sm font-medium text-text-primary">
                          {tool.tool_name}
                        </code>
                        <Status
                          tone={toolStatusTone(tool.status)}
                          label={tool.status}
                        />
                        {tool.risk_level && (
                          <Badge tone="neutral">{tool.risk_level}</Badge>
                        )}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-text-tertiary">
                        <span>{formatDuration(tool.duration_ms)}</span>
                        {tool.failure_code && (
                          <span className="text-danger">
                            {failureLabel(tool.failure_code)}
                          </span>
                        )}
                        {tool.reason_code && (
                          <span className="font-data">{tool.reason_code}</span>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </section>
    </div>
  );
}
