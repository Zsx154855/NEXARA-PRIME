"use client";

// ─── HOME — 值班视角 ───
// 回答「现在 NEXARA 能为我做什么」：
// 问候语 → 当前意图 → 待审批 → 可恢复任务 → 最近（对话/结果）→ 记忆 → 建议动作。
// 编辑式单列（max-w-3xl），一屏一个主状态；系统异常才展开状态条。

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  ConversationDetail,
  MemoryStats,
  MissionSnapshot,
  RuntimeOverview,
  RuntimeStats,
} from "@/types";
import { useRuntimeData } from "@/lib/runtime-context";
import { conversationDetailPath } from "@/lib/navigation";
import { filterProductMissions } from "@/lib/presentation";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { IntentSection, type IntentState } from "./home/IntentSection";
import { MemoryOverview } from "./home/MemoryOverview";
import { PendingApprovals } from "./home/PendingApprovals";
import { RecentActivity } from "./home/RecentActivity";
import { RecoverySection } from "./home/RecoverySection";
import { SuggestedActions } from "./home/SuggestedActions";
import { parseRecovery, type RecoveryReport } from "./home/recovery";
import { TERMINAL_STATES } from "./home/missionState";
import { byUpdatedAtDesc, greetingForHour, todayLine } from "./home/time";

// ── Props（与 app/(shell)/page.tsx 传入保持一致）──

interface OverviewProps {
  overview: RuntimeOverview | null;
  stats: RuntimeStats | null;
  memoryStats: MemoryStats | null;
  loading: boolean;
  error: string | null;
  onMissionSelect: (missionId: string) => void;
  onCreateMission: () => void;
  onContinueMission: (mission: MissionSnapshot) => void;
  onViewMemory: () => void;
}

function IntentBanner({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-3 rounded-md border border-border-default bg-warning/5 px-4 py-3"
    >
      {children}
    </div>
  );
}

export function Overview({
  overview,
  memoryStats,
  loading,
  error,
  onMissionSelect,
  onCreateMission,
  onContinueMission,
  onViewMemory,
}: OverviewProps) {
  const router = useRouter();
  const { api, refresh } = useRuntimeData();
  const [conversations, setConversations] = useState<ConversationDetail[]>([]);
  const [recovery, setRecovery] = useState<RecoveryReport | null>(null);

  // 次要数据（对话 / 恢复检查）：尽力而为，失败则整区隐藏。
  useEffect(() => {
    let cancelled = false;
    async function loadSecondary(): Promise<void> {
      try {
        const list = await api.getConversations();
        if (!cancelled) setConversations(list);
      } catch {
        // 对话区不可用时隐藏
      }
      try {
        const result = await api.checkRecovery();
        if (!cancelled) setRecovery(parseRecovery(result));
      } catch {
        // 恢复区不可用时隐藏
      }
    }
    void loadSecondary();
    return () => {
      cancelled = true;
    };
  }, [api]);

  // ── 派生 ──
  // P1-DATA-BOUNDARY-001：产品视图派生仅基于非 QA 使命（数据不删除）
  const missions = filterProductMissions(overview?.missions ?? []);
  const activeMission =
    missions
      .filter((m) => !TERMINAL_STATES.has(m.state))
      .sort(byUpdatedAtDesc)[0] ?? null;
  const pendingApprovals = (overview?.approvals ?? []).filter(
    (a) => a.status === "pending",
  );
  const sortedConversations = [...conversations].sort(byUpdatedAtDesc);
  const latestConversation = sortedConversations[0] ?? null;

  // 当前意图：活跃使命与最近对话按更新时间取最新者
  const intent: IntentState = (() => {
    if (activeMission && latestConversation) {
      const missionTime = Date.parse(activeMission.updated_at);
      const conversationTime = Date.parse(latestConversation.updated_at);
      return missionTime >= conversationTime
        ? { kind: "mission", mission: activeMission }
        : { kind: "conversation", conversation: latestConversation };
    }
    if (activeMission) return { kind: "mission", mission: activeMission };
    if (latestConversation) {
      return { kind: "conversation", conversation: latestConversation };
    }
    return null;
  })();

  const greeting = greetingForHour(new Date().getHours());
  const systemUnhealthy = overview?.system.healthy === false;

  // ── 一屏一个主状态 ──
  if (loading && !overview) {
    return (
      <div className="mx-auto w-full max-w-3xl animate-fade-in py-16">
        <LoadingState label="正在连接 NEXARA Runtime…" />
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="mx-auto w-full max-w-3xl animate-fade-in py-16">
        <ErrorState
          title="无法连接 NEXARA Runtime"
          details={error}
          actionLabel="重试"
          onAction={() => void refresh()}
        />
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="mx-auto w-full max-w-3xl animate-fade-in py-8 sm:py-12">
      {/* 系统异常才展开 */}
      {error && (
        <ErrorState
          isInline
          className="mb-8"
          title="与 NEXARA 的连接中断"
          details={error}
          actionLabel="重试"
          onAction={() => void refresh()}
        />
      )}
      {systemUnhealthy && (
        <IntentBanner>
          <Status tone="warning" label="系统状态异常" />
          <span className="text-sm text-text-secondary">
            NEXARA 报告健康状态异常，部分能力可能受限。
          </span>
        </IntentBanner>
      )}

      {/* 问候语（编辑式标题，宋体） */}
      <header className="pt-2">
        <p className="text-xs text-text-tertiary">{todayLine()}</p>
        <h1 className="mt-3 font-editorial text-3xl leading-snug text-text-primary sm:text-4xl">
          {greeting}
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-secondary">
          NEXARA 正在值守。这里是此刻需要你留意的事，以及可以继续推进的下一步。
        </p>
      </header>

      <div className="mt-12 space-y-12">
        <IntentSection
          intent={intent}
          onContinueMission={onContinueMission}
          onOpenMission={onMissionSelect}
          onOpenConversation={(conversationId) =>
            router.push(conversationDetailPath(conversationId))
          }
          onCreateMission={onCreateMission}
        />
        <PendingApprovals
          approvals={pendingApprovals}
          onViewAll={() => router.push("/trust")}
          onOpenMission={onMissionSelect}
        />
        <RecoverySection recovery={recovery} onOpenMission={onMissionSelect} />
        <RecentActivity
          conversations={sortedConversations}
          missions={missions}
          onOpenConversation={(conversationId) =>
            router.push(conversationDetailPath(conversationId))
          }
          onSelectMission={onMissionSelect}
        />
        <MemoryOverview memoryStats={memoryStats} onViewMemory={onViewMemory} />
        <SuggestedActions
          pendingApprovalCount={pendingApprovals.length}
          onCreateMission={onCreateMission}
          onOpenConversation={() => router.push("/conversation")}
          onViewApprovals={() => router.push("/trust")}
          onViewMemory={onViewMemory}
        />
      </div>

      <footer className="mt-12 border-t border-border-subtle pt-6">
        <p className="text-xs text-text-tertiary">NEXARA PRIME · 值班视图</p>
      </footer>
    </div>
  );
}
