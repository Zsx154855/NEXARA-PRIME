// 信任阶梯面板（使命详情顶部信息区，始终可见）。
// 五级：许可 → 审批 → 执行 → 证据 → 记忆。
// 任一级失败 → 整体红 + failureReason（FailureCode 中文映射，人话）。
// 数据来源：api.getMission + getApprovals / fetchTools / getEvidence / getMemory。
import { useMemo } from "react";
import { Clock } from "lucide-react";
import {
  TrustLadder,
  type LadderLevel,
} from "@/components/ui/TrustLadder";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type {
  ApprovalRequest,
  EvidenceArtifact,
  MemoryRecord,
  MissionSnapshot,
  ToolInvocation,
} from "@/types";
import {
  RISK_LABELS,
  TERMINAL_STATES,
  failureLabel,
  formatTimestamp,
  stateLabel,
} from "./constants";

/** 侧路数据源加载状态（container 侧 Promise.allSettled 结果） */
export interface SideDataStatus {
  loaded: boolean;
  error: string | null;
}

interface TrustLadderPanelProps {
  mission: MissionSnapshot;
  approvals: ApprovalRequest[];
  tools: ToolInvocation[];
  evidence: EvidenceArtifact[];
  memory: MemoryRecord[];
  sideStatus: Record<string, SideDataStatus>;
  onDecide: (approval: ApprovalRequest) => void;
}

export function TrustLadderPanel({
  mission,
  approvals,
  tools,
  evidence,
  memory,
  sideStatus,
  onDecide,
}: TrustLadderPanelProps) {
  const { levels, failureReason } = useMemo(() => {
    const levels: LadderLevel[] = [];
    const state = mission.state ?? mission.current_state;
    const isTerminal = TERMINAL_STATES.includes(state);

    // 1 许可 —— 本地单用户模式如实标注，无假权限列表
    const toolsStatus = sideStatus.tools;
    if (toolsStatus?.error) {
      levels.push({
        id: "permission",
        label: "许可",
        description: `工具范围读取失败：${toolsStatus.error}`,
        tone: "failed",
      });
    } else if (toolsStatus?.loaded) {
      levels.push({
        id: "permission",
        label: "许可",
        description: `本地单用户模式，权限默认全开；工具范围已投影（${tools.length} 项）。角色/权限面接线 = AUTH BACKEND REQUIRED`,
        tone: "verified",
      });
    } else {
      levels.push({
        id: "permission",
        label: "许可",
        description: "本地单用户模式（工具范围读取中…）",
        tone: "pending",
      });
    }

    // 2 审批 —— pending → 琥珀 / approved → verified / rejected → failed
    const approvalsStatus = sideStatus.approvals;
    const pendingApproval = approvals.find((a) => a.status === "pending");
    if (approvalsStatus?.error && !pendingApproval) {
      levels.push({
        id: "approval",
        label: "审批",
        description: `审批状态读取失败：${approvalsStatus.error}`,
        tone: "failed",
      });
    } else if (pendingApproval) {
      levels.push({
        id: "approval",
        label: "审批",
        description: `等待审批：${pendingApproval.action}（${pendingApproval.risk_level} · ${RISK_LABELS[pendingApproval.risk_level].slice(4)}）`,
        tone: "waiting",
      });
    } else if (
      mission.approval_status === "pending" ||
      mission.approval_status === "expired" ||
      mission.approval_status === "paused" ||
      mission.approval_status === "changes_requested"
    ) {
      levels.push({
        id: "approval",
        label: "审批",
        description: `等待审批（${mission.approval_status}）`,
        tone: "waiting",
      });
    } else if (mission.approval_status === "rejected") {
      levels.push({
        id: "approval",
        label: "审批",
        description: "审批被拒绝",
        tone: "failed",
      });
    } else if (mission.approval_status === "integrity_error") {
      levels.push({
        id: "approval",
        label: "审批",
        description: "审批完整性校验失败",
        tone: "failed",
      });
    } else if (mission.approval_status === "not_required") {
      levels.push({
        id: "approval",
        label: "审批",
        description: "无需审批（本地单用户模式）",
        tone: "verified",
      });
    } else if (
      mission.approval_status === "approved" ||
      mission.approval_status === "consumed" ||
      (approvalsStatus?.loaded && approvals.length > 0)
    ) {
      levels.push({
        id: "approval",
        label: "审批",
        description: "审批已通过",
        tone: "verified",
      });
    } else if (approvalsStatus?.loaded) {
      levels.push({
        id: "approval",
        label: "审批",
        description: `未到达（暂无审批要求；当前：${stateLabel(state)}）`,
        tone: "pending",
      });
    } else {
      levels.push({
        id: "approval",
        label: "审批",
        description: "审批状态读取中…",
        tone: "pending",
      });
    }

    // 3 执行 —— ToolInvocation 状态（有失败码 → failed）
    const failedTool = tools.find(
      (t) => t.failure_code || t.status === "error" || t.status === "failed",
    );
    const lastTool = tools[tools.length - 1];
    if (failedTool) {
      levels.push({
        id: "execution",
        label: "执行",
        description: `工具调用失败：${failureLabel(failedTool.failure_code) ?? failedTool.status}（${failedTool.tool_name}）`,
        tone: "failed",
      });
    } else if (state === "Completed") {
      levels.push({
        id: "execution",
        label: "执行",
        description: `已完成（${tools.length} 次工具调用）`,
        tone: "verified",
      });
    } else if (state === "Failed" || state === "Blocked" || state === "Cancelled") {
      levels.push({
        id: "execution",
        label: "执行",
        description: `${stateLabel(state)}${mission.terminal_reason ? `：${mission.terminal_reason}` : ""}`,
        tone: "failed",
      });
    } else if (state === "Paused") {
      levels.push({
        id: "execution",
        label: "执行",
        description: "已暂停，等待恢复",
        tone: "waiting",
      });
    } else if (
      state === "AwaitingApproval" ||
      state === "Approval"
    ) {
      levels.push({
        id: "execution",
        label: "执行",
        description: "等待审批后执行",
        tone: "waiting",
      });
    } else if (
      state === "Running" ||
      state === "Execution" ||
      state === "Verifying" ||
      state === "Verification" ||
      state === "Evidence" ||
      state === "MemoryPatch" ||
      state === "Evaluation" ||
      state === "Degraded" ||
      state === "RollingBack"
    ) {
      levels.push({
        id: "execution",
        label: "执行",
        description: `${stateLabel(state)}${lastTool ? `：正在调用 ${lastTool.tool_name}` : ""}`,
        tone: "waiting",
      });
    } else {
      levels.push({
        id: "execution",
        label: "执行",
        description: `未到达（当前：${stateLabel(state)}）`,
        tone: "pending",
      });
    }

    // 4 证据 —— verification_status: verified / corrupt
    const evidenceStatus = sideStatus.evidence;
    const corrupt = evidence.find(
      (e) => e.verification_status === "corrupt",
    );
    const anyVerified = evidence.some(
      (e) => e.verification_status === "verified",
    );
    if (evidenceStatus?.error) {
      levels.push({
        id: "evidence",
        label: "证据",
        description: `证据读取失败：${evidenceStatus.error}`,
        tone: "failed",
      });
    } else if (corrupt) {
      levels.push({
        id: "evidence",
        label: "证据",
        description: `证据校验失败：${corrupt.title}（sha256 不匹配，已标记 corrupt）`,
        tone: "failed",
      });
    } else if (anyVerified || mission.evidence_count > 0) {
      levels.push({
        id: "evidence",
        label: "证据",
        description: `已留痕 ${mission.evidence_count} 条${anyVerified ? "，校验通过" : "，等待校验"}`,
        tone: anyVerified ? "verified" : "waiting",
      });
    } else {
      levels.push({
        id: "evidence",
        label: "证据",
        description: "未到达（执行并验证后自动入链）",
        tone: "pending",
      });
    }

    // 5 记忆 —— auto_commit 如实呈现（ADR-UI-003，禁「你批准后才写入」）
    const memoryStatus = sideStatus.memory;
    if (memoryStatus?.error) {
      levels.push({
        id: "memory",
        label: "记忆",
        description: `记忆读取失败：${memoryStatus.error}`,
        tone: "failed",
      });
    } else if (
      mission.memory_patch_status === "patched" ||
      memory.some((r) => r.status === "committed" || r.verified)
    ) {
      levels.push({
        id: "memory",
        label: "记忆",
        description: `已沉淀 ${memory.length} 条 · 运行时机按置信度 auto_commit 自动写入，UI 只读呈现`,
        tone: "verified",
      });
    } else if (isTerminal) {
      levels.push({
        id: "memory",
        label: "记忆",
        description: "使命已结束但无记忆沉淀（auto_commit 未写入）",
        tone: "waiting",
      });
    } else {
      levels.push({
        id: "memory",
        label: "记忆",
        description:
          "未到达（记忆由运行时机按置信度 auto_commit 自动沉淀；人工审批记忆为规划中）",
        tone: "pending",
      });
    }

    const failedLevel = levels.find((l) => l.tone === "failed");
    return {
      levels,
      failureReason: failedLevel?.description,
    };
  }, [mission, approvals, tools, evidence, memory, sideStatus]);

  const pendingApproval = approvals.find((a) => a.status === "pending");

  return (
    <div className="space-y-4">
      <section
        aria-labelledby="trust-ladder-heading"
        className="rounded-xl border border-border-subtle bg-surface-elevated p-4"
      >
        <h2
          id="trust-ladder-heading"
          className="text-sm font-semibold text-text-primary"
        >
          治理
        </h2>
        <p className="mt-0.5 text-xs text-text-secondary">
          五级信任阶梯：许可 → 审批 → 执行 → 证据 → 记忆
        </p>
        <TrustLadder levels={levels} failureReason={failureReason} className="mt-4" />
      </section>

      {pendingApproval && (
        <section
          aria-label="待审批提案"
          className="rounded-xl border border-warning/40 bg-warning/5 p-4"
        >
          <div className="flex items-center gap-2">
            <Badge tone="warning">{pendingApproval.risk_level}</Badge>
            <h3 className="min-w-0 truncate text-sm font-medium text-text-primary">
              {pendingApproval.action}
            </h3>
          </div>
          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-text-secondary">
            {pendingApproval.rationale}
          </p>
          <p className="mt-1.5 flex items-center gap-1 text-xs text-text-tertiary">
            <Clock className="h-3 w-3" />
            {pendingApproval.expires_at
              ? `过期：${formatTimestamp(pendingApproval.expires_at)}`
              : `创建：${formatTimestamp(pendingApproval.created_at)}`}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="quiet"
              onClick={() => onDecide(pendingApproval)}
            >
              审阅
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
