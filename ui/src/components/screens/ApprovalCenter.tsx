"use client";

// ─── 审批收件箱 ───
// GET /api/approvals 的投影 + POST /api/missions/:id/approve 的触发面。
// 三 Tab：待审批（pending + paused 如实呈现）/ 已处理（人的决定）/
// 历史（过期、已消费、暂停等终态）。决定一律走确认弹窗，
// actor 固定为 "human"，备注可写可不写。决定成功后重新拉取投影，不做本地猜测。

import { useCallback, useEffect, useState } from "react";
import type { ApprovalRequest } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { TrustHeader } from "./trust/TrustHeader";
import { ApprovalCard } from "./trust/ApprovalCard";
import { DecisionDialog } from "./trust/ApprovalDecisionDialog";
import {
  decisionMeta,
  formatDateTime,
  type DecisionKind,
} from "./trust/approvalMeta";
import { Archive, History, Inbox, RefreshCw } from "lucide-react";

interface ApprovalCenterProps {
  api: NexaraAPI;
}

type TabId = "pending" | "processed" | "history";

const TABS: { id: TabId; label: string }[] = [
  { id: "pending", label: "待审批" },
  { id: "processed", label: "已处理" },
  { id: "history", label: "历史" },
];

type DialogTarget = { approval: ApprovalRequest; decision: DecisionKind } | null;

/** 待审批按到期时间升序（最急在前），无到期时间的排最后。 */
function byUrgency(a: ApprovalRequest, b: ApprovalRequest): number {
  const ae = a.expires_at ? Date.parse(a.expires_at) : Number.POSITIVE_INFINITY;
  const be = b.expires_at ? Date.parse(b.expires_at) : Number.POSITIVE_INFINITY;
  if (ae !== be) return ae - be;
  return Date.parse(a.created_at) - Date.parse(b.created_at);
}

function byDecidedAtDesc(a: ApprovalRequest, b: ApprovalRequest): number {
  return (
    Date.parse(b.decided_at ?? b.created_at) -
    Date.parse(a.decided_at ?? a.created_at)
  );
}

/** 已处理 / 历史：一行一个决定的紧凑行。 */
function DecisionRow({ approval }: { approval: ApprovalRequest }) {
  const meta = decisionMeta(approval.status);
  const showsDecidedAt = approval.status !== "expired";
  const shownTime = showsDecidedAt ? approval.decided_at : approval.expires_at;

  return (
    <li className="flex items-start justify-between gap-4 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Status tone={meta.tone} label={meta.label} />
          <span className="text-sm font-medium text-text-primary">
            {approval.action}
          </span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-secondary">
          {approval.decision_note ?? approval.rationale}
        </p>
        <p className="mt-1 font-data text-xs text-text-tertiary">
          mission:{approval.mission_id}
        </p>
      </div>
      <div className="shrink-0 text-right text-xs text-text-tertiary">
        <time dateTime={shownTime ?? undefined}>
          {formatDateTime(shownTime)}
        </time>
        {approval.decided_by && (
          <p className="mt-0.5">由 {approval.decided_by}</p>
        )}
      </div>
    </li>
  );
}

export function ApprovalCenter({ api }: ApprovalCenterProps) {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("pending");
  const [target, setTarget] = useState<DialogTarget>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const load = useCallback(async () => {
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
    void load();
  }, [load]);

  // ── 派生：三 Tab 的数据投影 ──
  const pending = approvals
    .filter((a) => a.status === "pending" || a.status === "paused")
    .sort(byUrgency);
  const processed = approvals
    .filter(
      (a) =>
        a.status === "approved" ||
        a.status === "rejected" ||
        a.status === "changes_requested",
    )
    .sort(byDecidedAtDesc);
  const history = approvals
    .filter(
      (a) =>
        a.status !== "pending" &&
        a.status !== "paused" &&
        a.status !== "approved" &&
        a.status !== "rejected" &&
        a.status !== "changes_requested",
    )
    .sort(byDecidedAtDesc);

  const handleDecide = (approval: ApprovalRequest, decision: DecisionKind) => {
    setSubmitError(null);
    setTarget({ approval, decision });
  };

  const handleConfirm = async (note: string) => {
    if (!target?.approval.mission_id) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.approveMission(target.approval.mission_id, {
        decision: target.decision,
        actor: "human",
        note: note || undefined,
      });
      setTarget(null);
      // 决定落库后重新投影 GET /api/approvals，不做本地猜测。
      void load();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const tabCount = (id: TabId): number =>
    id === "pending"
      ? pending.length
      : id === "processed"
        ? processed.length
        : history.length;

  const renderPanel = () => {
    if (tab === "pending") {
      if (loading && approvals.length === 0) {
        return <LoadingState label="正在读取审批收件箱…" />;
      }
      if (error && approvals.length === 0) {
        return (
          <ErrorState
            title="审批收件箱加载失败"
            details={error}
            actionLabel="重试"
            onAction={() => void load()}
          />
        );
      }
      if (pending.length === 0) {
        return (
          <EmptyState
            icon={<Inbox className="size-6" aria-hidden="true" />}
            title="收件箱已清空"
            description="所有审批已处理——NEXARA 正在等你委派下一个任务。"
            actionLabel="刷新"
            onAction={() => void load()}
          />
        );
      }
      return (
        <ul className="space-y-3">
          {pending.map((approval) => (
            <li key={approval.approval_id}>
              <ApprovalCard
                approval={approval}
                isBusy={submitting}
                onDecide={handleDecide}
              />
            </li>
          ))}
        </ul>
      );
    }

    const items = tab === "processed" ? processed : history;
    const emptyCopy =
      tab === "processed"
        ? {
            icon: <History className="size-6" aria-hidden="true" />,
            title: "还没有已处理的决定",
            description:
              "你在此作出的批准、拒绝与要求修改会汇集到这里，可随时回溯。",
          }
        : {
            icon: <Archive className="size-6" aria-hidden="true" />,
            title: "历史为空",
            description:
              "已过期、已消费与已暂停的审批会出现在这里，如实保留到被清理。",
          };

    if (items.length === 0) {
      return (
        <EmptyState
          icon={emptyCopy.icon}
          title={emptyCopy.title}
          description={emptyCopy.description}
        />
      );
    }
    return (
      <ul className="divide-y divide-border-subtle border-b border-border-subtle">
        {items.map((approval) => (
          <DecisionRow key={approval.approval_id} approval={approval} />
        ))}
      </ul>
    );
  };

  return (
    <div className="space-y-6">
      <TrustHeader
        overline="治理"
        title="审批收件箱"
        subtitle="NEXARA 在改变外部世界之前先问你。每项请求说明做什么、为什么、访问什么、风险与是否可回滚——由你决定。"
        action={
          <Button
            variant="quiet"
            size="sm"
            isBusy={loading}
            onClick={() => void load()}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            刷新
          </Button>
        }
      />

      {/* Tab 栏 */}
      <div role="tablist" aria-label="审批视图" className="flex gap-1 border-b border-border-subtle">
        {TABS.map((t) => {
          const active = tab === t.id;
          const count = tabCount(t.id);
          return (
            <button
              key={t.id}
              role="tab"
              id={`approval-tab-${t.id}`}
              aria-selected={active}
              aria-controls={`approval-panel-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors duration-[var(--duration-micro)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]",
                active
                  ? "border-gold-text font-semibold text-text-primary"
                  : "border-transparent text-text-secondary hover:text-text-primary",
              )}
            >
              {t.label}
              <span
                className={cn(
                  "rounded-full px-1.5 py-0.5 text-xs tabular-nums",
                  active
                    ? "bg-gold-soft text-gold-text"
                    : "bg-surface-subtle text-text-secondary",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* 当前面板 */}
      <div
        role="tabpanel"
        id={`approval-panel-${tab}`}
        aria-labelledby={`approval-tab-${tab}`}
      >
        {renderPanel()}
      </div>

      {/* 决定确认弹窗 */}
      {target && (
        <DecisionDialog
          key={`${target.approval.approval_id}-${target.decision}`}
          approval={target.approval}
          decision={target.decision}
          isBusy={submitting}
          error={submitError}
          onConfirm={(note) => void handleConfirm(note)}
          onCancel={() => {
            if (!submitting) {
              setTarget(null);
              setSubmitError(null);
            }
          }}
        />
      )}
    </div>
  );
}
