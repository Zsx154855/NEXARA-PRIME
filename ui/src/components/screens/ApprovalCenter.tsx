"use client";

import { useState, useEffect, useCallback } from "react";
import type {
  ApprovalRequest,
} from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  User,
  FileText,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Info,
  WifiOff,
} from "lucide-react";

// ─── Props ───

interface ApprovalCenterProps {
  api: NexaraAPI;
}

// ─── Chinese Labels ───

const LABELS = {
  title: "审批中心",
  subtitle: "管理所有待审批任务 — 高风险操作需额外确认",
  pendingTitle: "待审批",
  approvedTitle: "已审批",
  rejectedTitle: "已拒绝",
  notFound: "暂无待审批请求",
  notFoundDesc: "所有任务审批请求均已被处理",
  loading: "加载中…",
  error: "加载失败",
  retry: "重试",
  approve: "批准",
  reject: "拒绝",
  confirmApprove: "确认批准",
  confirmReject: "确认拒绝",
  confirmApproveMessage: "确定要批准此审批请求吗？",
  confirmRejectMessage: "确定要拒绝此审批请求吗？",
  highRiskWarning: "高风险操作需二次确认",
  highRiskMessage: "此请求的风险等级为 R3/R4。批准后可能会产生不可逆影响。请仔细确认。",
  cancel: "取消",
  confirm: "确认",
  actorLabel: "决策者",
  noteLabel: "备注说明",
  notePlaceholder: "输入审批备注（可选）…",
  action: "操作",
  riskLevel: "风险等级",
  rationale: "理由",
  scope: "影响范围",
  impact: "影响",
  missionId: "任务 ID",
  createdAt: "创建时间",
  expiresAt: "过期时间",
  reversible: "可回滚",
  externalEffect: "外部影响",
  type: "类型",
  noPending: "所有审批请求已被处理",
  processing: "处理中…",
  actionLabel: "审批操作",
  yes: "是",
  no: "否",
};

// ─── Risk Config ───

const RISK_CONFIG: Record<
  string,
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    icon: typeof AlertTriangle;
  }
> = {
  R0: {
    label: "无风险",
    color: "text-moss-green",
    bg: "bg-moss-green/5",
    border: "border-moss-green/20",
    icon: CheckCircle2,
  },
  R1: {
    label: "低风险",
    color: "text-moss-green",
    bg: "bg-moss-green/5",
    border: "border-moss-green/20",
    icon: Info,
  },
  R2: {
    label: "中等风险",
    color: "text-amber",
    bg: "bg-amber/5",
    border: "border-amber/20",
    icon: AlertTriangle,
  },
  R3: {
    label: "高风险",
    color: "text-warm-red",
    bg: "bg-warm-red/5",
    border: "border-warm-red/20",
    icon: ShieldAlert,
  },
  R4: {
    label: "极端风险",
    color: "text-warm-red",
    bg: "bg-warm-red/5",
    border: "border-warm-red/20",
    icon: ShieldAlert,
  },
};

// ─── Sub: Confirm Dialog ───

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  confirmVariant,
  onConfirm,
  onCancel,
  loading,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  confirmVariant: "danger" | "warning" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/20 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-sm animate-fade-in rounded-xl border border-taupe bg-ivory p-6 shadow-xl">
        <h3 className="text-base font-semibold text-graphite">{title}</h3>
        <p className="mt-2 text-sm text-stone">{message}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-taupe bg-ivory px-4 py-2 text-sm font-medium text-graphite transition-colors hover:bg-mist-gray disabled:cursor-not-allowed disabled:opacity-50"
          >
            {LABELS.cancel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-ivory transition-colors disabled:cursor-not-allowed disabled:opacity-50",
              confirmVariant === "danger"
                ? "bg-warm-red hover:bg-warm-red/90"
                : confirmVariant === "warning"
                  ? "bg-amber hover:bg-amber/90"
                  : "bg-champagne hover:bg-champagne/90"
            )}
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sub: Approval Card ───

function ApprovalCard({
  approval,
  onApprove,
  onReject,
  processing,
}: {
  approval: ApprovalRequest;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  processing: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const riskCfg = (RISK_CONFIG[approval.risk_level] ?? RISK_CONFIG.R2)!;
  const RiskIcon = riskCfg.icon;
  const isHighRisk = approval.risk_level === "R3" || approval.risk_level === "R4";

  return (
    <div
      className={cn(
        "rounded-xl border bg-ivory shadow-sm transition-all",
        isHighRisk ? "border-warm-red/20" : "border-taupe"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            isHighRisk ? "bg-warm-red/10" : "bg-champagne/10"
          )}
        >
          <RiskIcon
            className={cn(
              "h-5 w-5",
              isHighRisk ? "text-warm-red" : riskCfg.color
            )}
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-medium text-graphite">
              {approval.action}
            </h3>
            <div
              className={cn(
                "badge shrink-0 text-[10px]",
                isHighRisk ? "badge-error" : "badge-warning"
              )}
            >
              {riskCfg.label}
            </div>
          </div>

          <p className="mt-0.5 text-xs text-stone line-clamp-2">
            {approval.rationale}
          </p>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-stone">
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />
              {new Date(approval.created_at).toLocaleString("zh-CN", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            {approval.expires_at && (
              <span className="flex items-center gap-0.5 text-amber">
                <Clock className="h-3 w-3" />
                过期：
                {new Date(approval.expires_at).toLocaleString("zh-CN", {
                  month: "2-digit",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-0.5 text-champagne hover:text-champagne/80"
            >
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              详情
            </button>
          </div>
        </div>

        {/* Action buttons */}
        {approval.status === "pending" && (
          <div className="flex shrink-0 gap-2">
            <button
              onClick={() => onReject(approval.approval_id)}
              disabled={processing}
              className="flex items-center gap-1 rounded-lg border border-warm-red/20 bg-warm-red/5 px-3 py-1.5 text-xs font-medium text-warm-red transition-colors hover:bg-warm-red/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <XCircle className="h-3.5 w-3.5" />
              {LABELS.reject}
            </button>
            <button
              onClick={() => onApprove(approval.approval_id)}
              disabled={processing}
              className={cn(
                "flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-ivory transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                isHighRisk
                  ? "bg-warm-red hover:bg-warm-red/90"
                  : "bg-moss-green hover:bg-moss-green/90"
              )}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {LABELS.approve}
            </button>
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-taupe px-4 py-3 text-xs text-stone">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <div className="flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5 text-stone" />
              <span className="text-stone">{LABELS.type}：</span>
              <code className="font-mono text-graphite">{approval.approval_scope}</code>
            </div>
            <div className="flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-stone" />
              <span className="text-stone">{LABELS.riskLevel}：</span>
              <span className={riskCfg.color}>{approval.risk_level} — {riskCfg.label}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="h-3.5 w-3.5 text-stone" />
              <span className="text-stone">{LABELS.reversible}：</span>
              <span>{approval.reversible ? "是" : "否"}</span>
              {!approval.reversible && (
                <span className="text-warm-red">（不可回滚）</span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-stone" />
              <span className="text-stone">{LABELS.externalEffect}：</span>
              <span>{approval.external_effect ? "是" : "否"}</span>
              {approval.external_effect && (
                <span className="text-warm-red">（外部系统影响）</span>
              )}
            </div>
          </div>

          {/* Impact scope */}
          {approval.impact.length > 0 && (
            <div className="mt-3">
              <span className="text-stone">{LABELS.impact}：</span>
              <div className="mt-1 flex flex-wrap gap-1">
                {approval.impact.map((item, i) => (
                  <span
                    key={i}
                    className="rounded-md bg-mist-gray px-2 py-0.5 font-mono text-[10px] text-graphite"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Affected resources */}
          {approval.affected_resources.length > 0 && (
            <div className="mt-3">
              <span className="text-stone">{LABELS.scope}：</span>
              <div className="mt-1 flex flex-wrap gap-1">
                {approval.affected_resources.map((r, i) => (
                  <span
                    key={i}
                    className="rounded-md bg-mist-gray px-2 py-0.5 font-mono text-[10px] text-graphite"
                  >
                    {r}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Cost */}
          {approval.estimated_cost > 0 && (
            <div className="mt-3 text-stone">
              预估成本：{approval.estimated_cost} 积分
            </div>
          )}

          {/* Evidence refs */}
          {approval.evidence_refs.length > 0 && (
            <div className="mt-3">
              <span className="text-stone">证据引用：</span>
              <div className="mt-1 space-y-0.5">
                {approval.evidence_refs.map((ref) => (
                  <code
                    key={ref}
                    className="block truncate rounded bg-mist-gray px-2 py-0.5 font-mono text-[10px] text-graphite"
                  >
                    {ref}
                  </code>
                ))}
              </div>
            </div>
          )}

          {/* ID */}
          <div className="mt-3 flex items-center gap-1.5 text-[10px]">
            <code className="font-mono text-stone/60">{approval.approval_id}</code>
            {approval.mission_id && (
              <>
                <span className="text-taupe">·</span>
                <code className="font-mono text-stone/60">mission: {approval.mission_id}</code>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub: History Card ───

function HistoryCard({ approval }: { approval: ApprovalRequest }) {
  const riskCfg = (RISK_CONFIG[approval.risk_level] ?? RISK_CONFIG.R2)!;
  const RiskIcon = riskCfg.icon;

  const statusLabel =
    approval.status === "approved"
      ? "已批准"
      : approval.status === "rejected"
        ? "已拒绝"
        : approval.status === "changes_requested"
          ? "需修改"
          : approval.status === "expired"
            ? "已过期"
            : approval.status === "consumed"
              ? "已消费"
              : approval.status;

  const statusColor =
    approval.status === "approved" || approval.status === "consumed"
      ? "text-moss-green bg-moss-green/5 border-moss-green/20"
      : approval.status === "rejected" || approval.status === "expired"
        ? "text-warm-red bg-warm-red/5 border-warm-red/20"
        : "text-amber bg-amber/5 border-amber/20";

  return (
    <div className="flex items-start gap-3 rounded-lg border border-taupe bg-ivory p-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-mist-gray">
        <RiskIcon className={cn("h-4 w-4", riskCfg.color)} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-graphite">
            {approval.action}
          </span>
          <span className={cn("badge text-[10px]", statusColor)}>
            {statusLabel}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-stone line-clamp-1">
          {approval.decision_note ?? approval.rationale}
        </p>
        <div className="mt-1 flex items-center gap-3 text-[11px] text-stone">
          {approval.decided_by && (
            <span className="flex items-center gap-0.5">
              <User className="h-3 w-3" />
              {approval.decided_by}
            </span>
          )}
          {approval.decided_at && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />
              {new Date(approval.decided_at).toLocaleString("zh-CN", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
          <span className={cn("text-[10px]", riskCfg.color)}>
            {approval.risk_level}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───

export function ApprovalCenter({ api }: ApprovalCenterProps) {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);

  // Actor name and note for approvals
  const [actorName, setActorName] = useState("");
  const [approvalNote, setApprovalNote] = useState("");

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTitle, setConfirmTitle] = useState("");
  const [confirmMessage, setConfirmMessage] = useState("");
  const [confirmLabel, setConfirmLabel] = useState("");
  const [confirmVariant, setConfirmVariant] = useState<
    "danger" | "warning" | "default"
  >("default");
  const [pendingAction, setPendingAction] = useState<() => Promise<void>>(
    () => async () => {}
  );

  // ── Tab state ──
  type Tab = "pending" | "history";
  const [tab, setTab] = useState<Tab>("pending");

  // ── Load approvals ──
  const loadApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getApprovals();
      setApprovals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  // ── Approval actions ──
  const showConfirm = (
    title: string,
    message: string,
    label: string,
    variant: "danger" | "warning" | "default",
    action: () => Promise<void>
  ) => {
    setConfirmTitle(title);
    setConfirmMessage(message);
    setConfirmLabel(label);
    setConfirmVariant(variant);
    setPendingAction(() => action);
    setConfirmOpen(true);
  };

  const handleApprove = async (approvalId: string) => {
    const approval = approvals.find((a) => a.approval_id === approvalId);
    if (!approval) return;

    const isHighRisk =
      approval.risk_level === "R3" || approval.risk_level === "R4";

    if (isHighRisk) {
      // Show high-risk warning first
      showConfirm(
        LABELS.highRiskWarning,
        LABELS.highRiskMessage,
        LABELS.confirm,
        "danger",
        async () => {
          await doApprove(approvalId);
        }
      );
    } else {
      showConfirm(
        LABELS.confirmApprove,
        LABELS.confirmApproveMessage,
        LABELS.approve,
        "default",
        async () => {
          await doApprove(approvalId);
        }
      );
    }
  };

  const doApprove = async (approvalId: string) => {
    const approval = approvals.find((a) => a.approval_id === approvalId);
    if (!approval?.mission_id) return;
    setProcessing(approvalId);
    try {
      await api.approveMission(approval.mission_id, {
        approved: true,
        actor: actorName || undefined,
        note: approvalNote || undefined,
        decision: "approved",
      });
      // Update local state
      setApprovals((prev) =>
        prev.map((a) =>
          a.approval_id === approvalId
            ? {
                ...a,
                status: "approved" as const,
                decided_by: actorName || a.decided_by,
                decision_note: approvalNote || a.decision_note,
              }
            : a
        )
      );
      setConfirmOpen(false);
    } catch (err) {
      console.error(err);
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (approvalId: string) => {
    const approval = approvals.find((a) => a.approval_id === approvalId);
    if (!approval) return;

    showConfirm(
      LABELS.confirmReject,
      LABELS.confirmRejectMessage,
      LABELS.reject,
      "warning",
      async () => {
        setProcessing(approvalId);
        try {
          if (!approval.mission_id) return;
          await api.approveMission(approval.mission_id, {
            approved: false,
            actor: actorName || undefined,
            note: approvalNote || undefined,
            decision: "rejected",
          });
          setApprovals((prev) =>
            prev.map((a) =>
              a.approval_id === approvalId
                ? {
                    ...a,
                    status: "rejected" as const,
                    decided_by: actorName || a.decided_by,
                    decision_note: approvalNote || a.decision_note,
                  }
                : a
            )
          );
          setConfirmOpen(false);
        } catch (err) {
          console.error(err);
        } finally {
          setProcessing(null);
        }
      }
    );
  };

  // ── Derived data ──
  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  const historyApprovals = approvals.filter(
    (a) => a.status !== "pending"
  );

  // ── Loading State ──
  if (loading && approvals.length === 0) {
    return (
      <div className="space-y-3 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl border border-taupe bg-ivory p-5 animate-pulse-soft">
            <div className="skeleton h-5 w-2/3 mb-2 rounded" />
            <div className="skeleton h-4 w-full mb-2 rounded" />
            <div className="skeleton h-3 w-1/3 rounded" />
          </div>
        ))}
      </div>
    );
  }

  // ── Error State ──
  if (error && approvals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-taupe bg-ivory px-8 py-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-warm-red/10">
            <WifiOff className="h-7 w-7 text-warm-red" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-graphite">{LABELS.error}</h3>
            <p className="mt-1 text-sm text-stone">{error}</p>
          </div>
          <button
            onClick={loadApprovals}
            className="flex items-center gap-1.5 rounded-lg bg-champagne px-4 py-2 text-sm font-medium text-ivory transition-colors hover:bg-champagne/90"
          >
            <RefreshCw className="h-4 w-4" />
            {LABELS.retry}
          </button>
        </div>
      </div>
    );
  }

  // ── Render ──
  return (
    <div className="animate-fade-in space-y-6">
      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel={confirmLabel}
        confirmVariant={confirmVariant}
        onConfirm={pendingAction}
        onCancel={() => setConfirmOpen(false)}
        loading={processing !== null}
      />

      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-champagne/10">
            <ShieldCheck className="h-5 w-5 text-champagne" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-graphite">{LABELS.title}</h1>
            <p className="mt-0.5 text-sm text-stone">{LABELS.subtitle}</p>
          </div>
        </div>
      </div>

      {/* Actor and Note Fields */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <label className="mb-1 flex items-center gap-1 text-xs font-medium text-stone">
            <User className="h-3.5 w-3.5" />
            {LABELS.actorLabel}
          </label>
          <input
            value={actorName}
            onChange={(e) => setActorName(e.target.value)}
            placeholder="输入您的姓名…"
            className="w-full rounded-lg border border-taupe bg-ivory px-3 py-2 text-sm text-graphite placeholder:text-stone/40 focus:border-champagne focus:outline-none focus:ring-1 focus:ring-champagne/30"
          />
        </div>
        <div className="flex-1">
          <label className="mb-1 flex items-center gap-1 text-xs font-medium text-stone">
            <FileText className="h-3.5 w-3.5" />
            {LABELS.noteLabel}
          </label>
          <input
            value={approvalNote}
            onChange={(e) => setApprovalNote(e.target.value)}
            placeholder={LABELS.notePlaceholder}
            className="w-full rounded-lg border border-taupe bg-ivory px-3 py-2 text-sm text-graphite placeholder:text-stone/40 focus:border-champagne focus:outline-none focus:ring-1 focus:ring-champagne/30"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-taupe">
        <button
          onClick={() => setTab("pending")}
          className={cn(
            "relative px-4 py-2 text-sm font-medium transition-colors",
            tab === "pending"
              ? "text-champagne"
              : "text-stone hover:text-graphite"
          )}
        >
          {LABELS.pendingTitle}
          {pendingApprovals.length > 0 && (
            <span className="ml-1.5 rounded-full bg-champagne/15 px-1.5 py-0.5 text-[10px] text-champagne">
              {pendingApprovals.length}
            </span>
          )}
          {tab === "pending" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-champagne" />
          )}
        </button>
        <button
          onClick={() => setTab("history")}
          className={cn(
            "relative px-4 py-2 text-sm font-medium transition-colors",
            tab === "history"
              ? "text-champagne"
              : "text-stone hover:text-graphite"
          )}
        >
          {LABELS.approvedTitle}
          {historyApprovals.length > 0 && (
            <span className="ml-1.5 text-[10px] text-stone">
              {historyApprovals.length}
            </span>
          )}
          {tab === "history" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-champagne" />
          )}
        </button>
      </div>

      {/* ── Pending Tab ── */}
      {tab === "pending" && (
        <>
          {pendingApprovals.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-moss-green/10">
                <ShieldCheck className="h-7 w-7 text-moss-green" />
              </div>
              <div>
                <h3 className="text-base font-medium text-graphite">
                  {LABELS.notFound}
                </h3>
                <p className="mt-1 text-sm text-stone">{LABELS.notFoundDesc}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {pendingApprovals.map((approval) => (
                <ApprovalCard
                  key={approval.approval_id}
                  approval={approval}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  processing={processing === approval.approval_id}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ── History Tab ── */}
      {tab === "history" && (
        <>
          {historyApprovals.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-mist-gray">
                <Clock className="h-7 w-7 text-stone" />
              </div>
              <div>
                <h3 className="text-base font-medium text-graphite">
                  {LABELS.noPending}
                </h3>
                <p className="mt-1 text-sm text-stone">
                  所有审批请求均已被处理，暂无历史记录
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {historyApprovals.map((approval) => (
                <HistoryCard key={approval.approval_id} approval={approval} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Summary bar */}
      {approvals.length > 0 && (
        <div className="flex items-center gap-4 rounded-lg border border-taupe bg-mist-gray px-4 py-2 text-xs text-stone">
          <span>
            总计 <strong className="text-graphite">{approvals.length}</strong> 条
          </span>
          <span>
            待审批 <strong className="text-amber">{pendingApprovals.length}</strong> 条
          </span>
          <span>
            已处理 <strong className="text-moss-green">{historyApprovals.length}</strong> 条
          </span>
          <button
            onClick={loadApprovals}
            className="ml-auto flex items-center gap-1 text-champagne transition-colors hover:text-champagne/80"
          >
            <RefreshCw className="h-3 w-3" />
            刷新
          </button>
        </div>
      )}
    </div>
  );
}
