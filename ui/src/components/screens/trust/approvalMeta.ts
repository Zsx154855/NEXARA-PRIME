// ─── 审批元数据：风险等级与决定状态的语义映射 ───
// 状态语义只映射到 success / warning / danger / info / neutral 五个 token。
// 装饰色（champagne / moss / amber / warm-red）不承载任何状态语义。

import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ApprovalStatus, RiskLevel } from "@/types";

export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

/** 可在收件箱中由人类做出的决定（POST /api/missions/:id/approve）。 */
export type DecisionKind = "approved" | "rejected" | "changes_requested";

export const RISK_META: Record<
  RiskLevel,
  { label: string; tone: StatusTone; icon: LucideIcon }
> = {
  R0: { label: "无风险", tone: "success", icon: Info },
  R1: { label: "低风险", tone: "success", icon: Info },
  R2: { label: "中等风险", tone: "warning", icon: AlertTriangle },
  R3: { label: "高风险", tone: "danger", icon: ShieldAlert },
  R4: { label: "极高风险", tone: "danger", icon: ShieldAlert },
};

/** 接受后端原样字符串（未知等级回退 R2 中位展示）。 */
export function riskMeta(level: string): {
  label: string;
  tone: StatusTone;
  icon: LucideIcon;
} {
  return RISK_META[level as RiskLevel] ?? RISK_META.R2;
}

const DECISION_META: Record<
  ApprovalStatus,
  { label: string; tone: StatusTone }
> = {
  pending: { label: "待审批", tone: "warning" },
  approved: { label: "已批准", tone: "success" },
  rejected: { label: "已拒绝", tone: "danger" },
  changes_requested: { label: "要求修改", tone: "warning" },
  paused: { label: "已暂停", tone: "warning" },
  expired: { label: "已过期", tone: "warning" },
  consumed: { label: "已消费", tone: "info" },
};

/** 接受受控枚举或后端原样字符串。 */
export function decisionMeta(
  status: ApprovalStatus | string,
): { label: string; tone: StatusTone } {
  return DECISION_META[status as ApprovalStatus] ?? { label: status, tone: "neutral" };
}

/** 审批时间格式化：MM-DD HH:mm；非法输入返回 —。 */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
