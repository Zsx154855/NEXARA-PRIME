// ─── MissionCreator 常量与中文映射 ───
// 状态语义只用 success / warning / danger / info / neutral 五个语义 token；
// 装饰色永不承载状态语义。

import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { MissionState } from "@/types";

export const WIZARD_STEPS = [
  { label: "目标确认", desc: "定义任务目标" },
  { label: "生成规划", desc: "AI 生成执行方案" },
  { label: "提交审批", desc: "提交人类审批" },
] as const;

export type RiskTone = "success" | "warning" | "danger";

interface RiskConfig {
  label: string;
  tone: RiskTone;
  icon: LucideIcon;
  desc: string;
}

export const RISK_CONFIG: Record<string, RiskConfig> = {
  R0: { label: "无风险", tone: "success", icon: CheckCircle2, desc: "简单信息查询，无副作用" },
  R1: { label: "低风险", tone: "success", icon: Info, desc: "只读操作，影响范围有限" },
  R2: { label: "中等风险", tone: "warning", icon: AlertTriangle, desc: "涉及写操作，但可回滚" },
  R3: { label: "高风险", tone: "danger", icon: ShieldAlert, desc: "不可逆操作或外部影响" },
  R4: { label: "极高风险", tone: "danger", icon: ShieldAlert, desc: "生产环境变更或安全敏感操作" },
};

export function riskLabel(level: string): string {
  return RISK_CONFIG[level]?.label ?? level;
}

/** 风险等级 → 语义色（R0/R1 绿，R2 琥珀，R3/R4 红）；未知等级按中等警戒处理 */
export function riskTone(level: string): RiskTone {
  return RISK_CONFIG[level]?.tone ?? "warning";
}

/** 依据目标文本的简单启发式估算风险等级（R0–R4） */
export function estimateRisk(text: string): string | null {
  if (!text || text.trim().length < 10) return null;
  const lower = text.toLowerCase();
  // R4 指标
  if (/production|deploy|prod|delete|remove|destroy|terminate|shutdown/i.test(lower)) {
    return "R4";
  }
  // R3 指标
  if (/write|modify|update|change|create file|commit|push|merge|execute|run/i.test(lower)) {
    return "R3";
  }
  // R2 指标
  if (/analyze|investigate|research|search|scan|audit|review|read|fetch/i.test(lower)) {
    return "R2";
  }
  // R1 指标
  if (/summarize|list|show|tell|what|explain|describe|check|status/i.test(lower)) {
    return "R1";
  }
  return "R0";
}

const STATE_LABELS: Record<string, string> = {
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

export function stateLabel(state: MissionState | string): string {
  return STATE_LABELS[state] ?? state;
}

export type StateTone = "success" | "warning" | "danger" | "info" | "neutral";

/** 需要人介入等待的状态（琥珀 = 等待） */
const WAITING_STATES = new Set<MissionState>([
  "Approval",
  "AwaitingApproval",
  "Blocked",
  "Paused",
  "Degraded",
]);

export function stateTone(state: MissionState): StateTone {
  if (state === "Completed") return "success";
  if (state === "Failed" || state === "RolledBack" || state === "Cancelled") {
    return "danger";
  }
  if (WAITING_STATES.has(state)) return "warning";
  return "info";
}
