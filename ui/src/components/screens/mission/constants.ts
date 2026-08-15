// ─── NEXARA 使命详情屏 · 常量与中文映射 ───
// 全部映射自真实后端字段；失败码人话映射用于信任阶梯「整体红」原因。

import type { ApprovalStatus, FailureCode, RiskLevel } from "@/types";

export const TAB_ITEMS = [
  { id: "plan", label: "计划" },
  { id: "execution", label: "执行" },
  { id: "result", label: "结果" },
  { id: "timeline", label: "时间线" },
] as const;

export type MissionTabId = (typeof TAB_ITEMS)[number]["id"];

export const STATE_LABELS: Record<string, string> = {
  Intent: "意图",
  Context: "上下文",
  Contract: "合约",
  Plan: "规划",
  Simulation: "模拟",
  Approval: "审批中",
  Execution: "执行中",
  Verification: "验证中",
  Evidence: "证据收集",
  MemoryPatch: "记忆沉淀",
  Evaluation: "评估",
  Completed: "已完成",
  Blocked: "已阻塞",
  Failed: "已失败",
  RolledBack: "已回滚",
  Created: "已创建",
  Triaged: "已分类",
  Contracted: "已签约",
  Planned: "已规划",
  Scheduled: "已调度",
  AwaitingApproval: "等待审批",
  Running: "运行中",
  Verifying: "验证中",
  Degraded: "降级",
  Paused: "已暂停",
  Cancelled: "已取消",
  RollingBack: "回滚中",
};

/** 终态：控制动作不可用 */
export const TERMINAL_STATES: readonly string[] = [
  "Completed",
  "Failed",
  "RolledBack",
  "Cancelled",
];

/** 执行前状态：状态机允许 run 推进 */
export const PRE_EXECUTION_STATES: readonly string[] = [
  "Intent",
  "Context",
  "Contract",
  "Plan",
  "Simulation",
  "Approval",
  "Created",
  "Triaged",
  "Contracted",
  "Planned",
  "Scheduled",
  "AwaitingApproval",
];

export const RISK_LABELS: Record<RiskLevel, string> = {
  R0: "R0 无风险",
  R1: "R1 低风险",
  R2: "R2 中风险",
  R3: "R3 高风险",
  R4: "R4 极高风险",
};

export const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending: "待审批",
  approved: "已批准",
  rejected: "已拒绝",
  changes_requested: "要求修改",
  paused: "审批暂停",
  expired: "已过期",
  consumed: "已处理",
};

/** FailureCode → 人话（失败原因给用户看，禁裸代码） */
export const FAILURE_CODE_LABELS: Record<FailureCode, string> = {
  PROVIDER_UNAVAILABLE: "模型服务不可用",
  PROVIDER_TIMEOUT: "模型服务超时",
  PROVIDER_QUOTA_EXCEEDED: "模型配额已用尽",
  PROVIDER_AUTH_INVALID: "模型服务密钥无效",
  TOOL_UNKNOWN: "工具不存在",
  TOOL_TIMEOUT: "工具执行超时",
  TOOL_SANDBOX_UNAVAILABLE: "工具沙箱不可用",
  TOOL_POLICY_REJECTED: "工具调用被策略拒绝",
  TOOL_ARGUMENT_INVALID: "工具参数不合法",
  TOOL_OUTPUT_TOO_LARGE: "工具输出超出上限",
  APPROVAL_MISSING: "缺少必要审批",
  APPROVAL_INVALID: "审批无效",
  APPROVAL_EXPIRED: "审批已过期",
  APPROVAL_MISMATCH: "审批与提案不匹配",
  INTEGRITY_ENVELOPE_INVALID: "完整性信封校验失败",
  INTEGRITY_IDEMPOTENCY_CONFLICT: "重复提交冲突",
  INTEGRITY_RECEIPT_CHAIN_BROKEN: "收据链断裂",
  INTEGRITY_HASH_MISMATCH: "内容哈希不匹配",
  EVIDENCE_MISSING: "证据缺失",
  EVIDENCE_UNVERIFIABLE: "证据无法验证",
  RECEIPT_MISSING: "收据缺失",
  RECEIPT_UNVERIFIABLE: "收据无法验证",
  MEMORY_EVIDENCE_UNBOUND: "记忆未绑定证据",
  MEMORY_CONFLICT_UNRESOLVED: "记忆冲突未解决",
  RUNTIME_INTERNAL: "运行时内部错误",
  RUNTIME_STATE_CORRUPT: "运行时状态损坏",
  IO_NOT_FOUND: "文件不存在",
  IO_PERMISSION_DENIED: "文件访问被拒绝",
  IO_PATH_TRAVERSAL: "路径越界已被拒绝",
  EXTERNAL_UNREACHABLE: "外部服务不可达",
  EXTERNAL_RATE_LIMITED: "外部服务限流",
};

/** 失败码 → 人话；非枚举值原样返回（不伪造） */
export function failureLabel(code: string | null | undefined): string | null {
  if (!code) return null;
  return FAILURE_CODE_LABELS[code as FailureCode] ?? code;
}

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

export function formatDuration(ms: number): string {
  if (!ms || ms <= 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** 计划步骤状态 → 语义色 */
export function stepStatusTone(
  status: string,
): "success" | "info" | "danger" | "neutral" {
  switch (status) {
    case "completed":
    case "done":
      return "success";
    case "running":
    case "in_progress":
      return "info";
    case "failed":
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}
