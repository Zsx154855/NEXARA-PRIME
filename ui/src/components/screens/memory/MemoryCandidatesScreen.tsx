// ─── 记忆候选：/api/memory/candidates 投影 ───
// 如实呈现：候选由运行时机按置信度与证据绑定自动提交；
// 人工审批为 PLANNED 能力（后端无对应端点），不做「审批后才写入」暗示。

"use client";

import { useCallback, useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import { fetchMemoryCandidatesSafe } from "@/lib/api";
import type { MemoryRecord } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { formatShortTime } from "../home/time";
import { MemoryHeader } from "./MemoryHeader";
import { MemorySubNav } from "./MemorySubNav";
import {
  byCreatedAtDesc,
  formatConfidence,
  memoryKindLabel,
  memoryLayerLabel,
  memoryLayerOf,
  memoryStatusMeta,
} from "./memoryMeta";

function CandidateRow({ record }: { record: MemoryRecord }) {
  const statusMeta = memoryStatusMeta(record.status);
  const hasEvidence = Boolean(record.source_evidence_id);

  return (
    <li className="py-6 first:pt-4 last:pb-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Badge tone="neutral">{memoryKindLabel(record.kind)}</Badge>
        <Badge tone="info">{memoryLayerLabel(memoryLayerOf(record.kind))}</Badge>
        <Status tone={statusMeta.tone} label={statusMeta.label} />
        {hasEvidence ? (
          <Status tone="success" label="已绑定证据" />
        ) : (
          <Status tone="info" label="未绑定证据" />
        )}
      </div>

      <p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-relaxed text-text-primary">
        {record.content}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
        <span>
          置信度{" "}
          <span className="font-data text-text-primary">
            {formatConfidence(record.confidence)}
          </span>
        </span>
        <span>提交于 {formatShortTime(record.created_at)}</span>
        {hasEvidence && record.source_evidence_id && (
          <span className="max-w-full truncate font-data text-text-tertiary">
            证据 {record.source_evidence_id}
          </span>
        )}
        {record.evidence_refs.length > 0 && (
          <span>证据引用 {record.evidence_refs.length} 条</span>
        )}
      </div>
    </li>
  );
}

export function MemoryCandidatesScreen() {
  const [candidates, setCandidates] = useState<MemoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchMemoryCandidatesSafe();
    if (result.type === "success" && result.data) {
      setCandidates([...result.data].sort(byCreatedAtDesc));
    } else {
      setError(result.error ?? "未知错误");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-8">
      <MemoryHeader
        title="记忆候选"
        subtitle="运行时观察到的、等待按置信度与证据绑定规则处理的新记忆。"
      />
      <MemorySubNav />

      <div className="rounded-r-md border-l-2 border-info bg-info/5 px-5 py-4">
        <p className="text-sm leading-relaxed text-text-secondary">
          记忆由运行时机按置信度与证据绑定自动提交；人工审批记忆为{" "}
          <Badge tone="gold">PLANNED</Badge> 能力（后端无对应端点）。
        </p>
      </div>

      {error && candidates.length > 0 && (
        <ErrorState
          isInline
          title="候选刷新失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load()}
        />
      )}

      {loading && candidates.length === 0 ? (
        <LoadingState label="正在读取候选记忆…" />
      ) : error && candidates.length === 0 ? (
        <ErrorState
          title="候选读取失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load()}
        />
      ) : candidates.length === 0 ? (
        <EmptyState
          icon={<Inbox className="size-6" aria-hidden="true" />}
          title="当前没有候选记忆"
          description="运行时按置信度与证据绑定自动提交候选，提交后即转入记忆库。列表为空，说明近期没有达到提交阈值的观察——记忆沉淀处于静止状态。"
          actionLabel="刷新"
          onAction={() => void load()}
        />
      ) : (
        <ol className="divide-y divide-border-subtle">
          {candidates.map((record) => (
            <CandidateRow key={record.memory_id} record={record} />
          ))}
        </ol>
      )}
    </div>
  );
}
