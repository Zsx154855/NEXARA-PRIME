"use client";

// ─── 证据链：getEvidence 投影 + EvidenceChain 组件 ───
// 按使命过滤（服务端筛选，与 /api/evidence 能力对齐）；
// 任何一条 verification_status ≠ verified 即视为链完整性异常，ErrorState 置顶提示。

import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceArtifact, RuntimeOverview } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { EvidenceChain } from "@/components/ui/EvidenceChain";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { TrustHeader } from "./TrustHeader";
import { FileSearch } from "lucide-react";

const ALL_MISSIONS = "__all__";

type EvidenceChainScreenProps = {
  api: NexaraAPI;
  overview: RuntimeOverview | null;
};

export function EvidenceChainScreen({ api, overview }: EvidenceChainScreenProps) {
  const [evidence, setEvidence] = useState<EvidenceArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missionId, setMissionId] = useState<string>(ALL_MISSIONS);

  const load = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getEvidence(id === ALL_MISSIONS ? undefined : id);
        setEvidence(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    void load(missionId);
  }, [load, missionId]);

  const missions = overview?.missions ?? [];
  const corruptCount = useMemo(
    () => evidence.filter((e) => e.verification_status !== "verified").length,
    [evidence],
  );

  return (
    <div className="space-y-6">
      <TrustHeader
        overline="治理"
        title="证据链"
        subtitle="每一次工具调用、每一份产物都留下证据与哈希。能否信任结果，先看这条链。"
      />

      {/* 按使命筛选 */}
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="evidence-mission" className="text-xs text-text-secondary">
          按使命筛选
        </label>
        <select
          id="evidence-mission"
          value={missionId}
          onChange={(e) => setMissionId(e.target.value)}
          className="h-8 max-w-xs rounded-md border border-border-default bg-surface-elevated px-2 text-sm text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
        >
          <option value={ALL_MISSIONS}>全部使命</option>
          {missions.map((m) => (
            <option key={m.mission_id} value={m.mission_id}>
              {m.title || m.mission_id}
            </option>
          ))}
        </select>
        <span className="text-xs text-text-tertiary tabular-nums">
          {evidence.length} 条证据
        </span>
      </div>

      {/* 完整性异常置顶提示 */}
      {corruptCount > 0 && (
        <ErrorState
          title="证据链完整性异常"
          details={`${corruptCount} 条证据未通过校验（verification_status ≠ verified）。以这些证据为基础的结论当前不可信任。`}
          actionLabel="重新加载"
          onAction={() => void load(missionId)}
        />
      )}

      {loading && evidence.length === 0 ? (
        <LoadingState label="正在读取证据链…" />
      ) : error && evidence.length === 0 ? (
        <ErrorState
          title="证据链加载失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load(missionId)}
        />
      ) : evidence.length === 0 ? (
        <EmptyState
          icon={<FileSearch className="size-6" aria-hidden="true" />}
          title="还没有证据"
          description="使命执行结束后，NEXARA 会把每一步的证据、来源与哈希收在这里。"
        />
      ) : (
        <EvidenceChain evidence={evidence} />
      )}
    </div>
  );
}
