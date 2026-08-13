// ─── 使命状态 → 中文标签与语义色 ───
// 状态语义色只映射到 success / warning / danger / info 四个 token。

import type { MissionState } from "@/types";

const STATE_LABELS: Partial<Record<MissionState, string>> = {
  Intent: "意图",
  Context: "上下文",
  Contract: "合约",
  Plan: "计划",
  Simulation: "仿真",
  Approval: "待审批",
  Execution: "执行中",
  Verification: "验证中",
  Evidence: "证据整理",
  MemoryPatch: "记忆回写",
  Evaluation: "评估中",
  Completed: "已完成",
  Blocked: "已阻塞",
  Failed: "已失败",
  RolledBack: "已回滚",
  Created: "已创建",
  Triaged: "已分诊",
  Contracted: "已签约",
  Planned: "已规划",
  Scheduled: "已排期",
  AwaitingApproval: "等待审批",
  Running: "运行中",
  Verifying: "验证中",
  Degraded: "降级运行",
  Paused: "已暂停",
  Cancelled: "已取消",
  RollingBack: "回滚中",
};

/** 接受受控枚举或后端原样字符串（如 recovery 返回的 state）。 */
export function stateLabel(state: MissionState | string): string {
  return STATE_LABELS[state as MissionState] ?? state;
}

/** 终态：不再推进的使命。 */
export const TERMINAL_STATES = new Set<MissionState>([
  "Completed",
  "Failed",
  "RolledBack",
]);

/** 需要人介入等待的状态（琥珀 = 等待）。 */
const WAITING_STATES = new Set<MissionState>([
  "Approval",
  "AwaitingApproval",
  "Blocked",
  "Paused",
  "Degraded",
]);

export type StateTone = "success" | "warning" | "danger" | "info" | "neutral";

export function stateTone(state: MissionState): StateTone {
  if (state === "Completed") return "success";
  if (state === "Failed" || state === "RolledBack" || state === "Cancelled") {
    return "danger";
  }
  if (WAITING_STATES.has(state)) return "warning";
  return "info";
}

// ── 风险等级（R0–R4）→ 中文标签与语义色 ──

const RISK_LABELS: Record<string, string> = {
  R0: "无风险",
  R1: "低风险",
  R2: "中等风险",
  R3: "高风险",
  R4: "极高风险",
};

export function riskLabel(level: string): string {
  return RISK_LABELS[level] ?? level;
}

export function riskTone(level: string): "success" | "warning" | "danger" {
  if (level === "R0" || level === "R1") return "success";
  if (level === "R2") return "warning";
  return "danger";
}
