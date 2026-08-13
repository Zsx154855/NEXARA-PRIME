// ─── 记忆浏览：/api/memory 投影 ───
// 四层筛选为客户端过滤（分层由记忆种类映射，镜像后端 MemoryLayer）。
// canonical / verified / conflict_keys 如实呈现：冲突用 warning Status。

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Database, ExternalLink } from "lucide-react";
import type { MemoryRecord } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { formatShortTime } from "../home/time";
import { MemoryHeader } from "./MemoryHeader";
import { MemorySubNav } from "./MemorySubNav";
import {
  MEMORY_LAYERS,
  byCreatedAtDesc,
  formatConfidence,
  memoryKindLabel,
  memoryLayerLabel,
  memoryLayerOf,
  memoryStatusMeta,
  type MemoryLayerKey,
} from "./memoryMeta";

type MemoryBrowseScreenProps = {
  api: NexaraAPI;
};

type LayerFilter = MemoryLayerKey | "all";

type LayerPillProps = {
  label: string;
  count: number;
  isActive: boolean;
  onSelect: () => void;
};

function LayerPill({ label, count, isActive, onSelect }: LayerPillProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isActive}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-micro)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]",
        isActive
          ? "border-graphite bg-graphite text-ivory"
          : "border-border-default bg-surface-base text-text-secondary hover:bg-surface-hover hover:text-text-primary",
      )}
    >
      {label}
      <span
        className={cn(
          "font-data text-xs",
          isActive ? "text-ivory/70" : "text-text-tertiary",
        )}
      >
        {count}
      </span>
    </button>
  );
}

function MemoryRecordRow({ record }: { record: MemoryRecord }) {
  const layer = memoryLayerOf(record.kind);
  const statusMeta = memoryStatusMeta(record.status);
  const hasConflicts =
    record.status === "conflict" || record.conflict_keys.length > 0;

  return (
    <li className="py-6 first:pt-4 last:pb-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Badge tone="neutral">{memoryKindLabel(record.kind)}</Badge>
        <Badge tone="info">{memoryLayerLabel(layer)}</Badge>
        {record.canonical && <Badge tone="gold">规范记忆</Badge>}
        <Status
          tone={record.verified ? "success" : "neutral"}
          label={record.verified ? "已验证" : "未验证"}
        />
        {record.status !== "committed" && (
          <Status tone={statusMeta.tone} label={statusMeta.label} />
        )}
        {hasConflicts && (
          <Status tone="warning" label={`${record.conflict_keys.length} 处冲突`} />
        )}
      </div>

      <p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-relaxed text-text-primary">
        {record.content}
      </p>

      {record.conflict_keys.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {record.conflict_keys.map((key) => (
            <li key={key} className="font-data text-xs text-warning">
              冲突键 {key}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
        <span>
          置信度{" "}
          <span className="font-data text-text-primary">
            {formatConfidence(record.confidence)}
          </span>
        </span>
        <span>记录于 {formatShortTime(record.created_at)}</span>
        {record.source_evidence_id ? (
          <Link
            href="/trust/evidence"
            className="inline-flex items-center gap-1 text-info hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
          >
            查看证据
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </Link>
        ) : (
          <span className="text-text-tertiary">无证据绑定</span>
        )}
      </div>
    </li>
  );
}

export function MemoryBrowseScreen({ api }: MemoryBrowseScreenProps) {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [layerFilter, setLayerFilter] = useState<LayerFilter>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMemory();
      setRecords([...data].sort(byCreatedAtDesc));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const layerCounts = useMemo(() => {
    const counts: Record<MemoryLayerKey, number> = {
      working: 0,
      episodic: 0,
      semantic: 0,
      procedural: 0,
    };
    for (const record of records) {
      const layer = memoryLayerOf(record.kind);
      counts[layer] = (counts[layer] ?? 0) + 1;
    }
    return counts;
  }, [records]);

  const visible = useMemo(
    () =>
      layerFilter === "all"
        ? records
        : records.filter((record) => memoryLayerOf(record.kind) === layerFilter),
    [records, layerFilter],
  );

  return (
    <div className="space-y-8">
      <MemoryHeader
        title="记忆浏览"
        subtitle="运行时按置信度与证据绑定自动沉淀的全部记忆。按四层分类浏览，验证状态与冲突如实呈现。"
      />
      <MemorySubNav />

      <div role="group" aria-label="按记忆分层筛选" className="flex flex-wrap gap-2">
        <LayerPill
          label="全部"
          count={records.length}
          isActive={layerFilter === "all"}
          onSelect={() => setLayerFilter("all")}
        />
        {MEMORY_LAYERS.map((layer) => (
          <LayerPill
            key={layer.key}
            label={layer.label}
            count={layerCounts[layer.key] ?? 0}
            isActive={layerFilter === layer.key}
            onSelect={() => setLayerFilter(layer.key)}
          />
        ))}
      </div>

      {error && records.length > 0 && (
        <ErrorState
          isInline
          title="记忆刷新失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load()}
        />
      )}

      {loading && records.length === 0 ? (
        <LoadingState label="正在读取记忆…" />
      ) : error && records.length === 0 ? (
        <ErrorState
          title="记忆读取失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load()}
        />
      ) : records.length === 0 ? (
        <EmptyState
          icon={<Database className="size-6" aria-hidden="true" />}
          title="记忆库还没有内容"
          description="NEXARA 在使命执行与验证完成后，会按置信度与证据绑定自动沉淀记忆。当前还没有已提交的记忆——可以创建并运行一个使命，或稍后再回来。"
          actionLabel="重新加载"
          onAction={() => void load()}
        />
      ) : visible.length === 0 ? (
        <EmptyState
          title={`${memoryLayerLabel(layerFilter as MemoryLayerKey)}目前为空`}
          description="分层由记忆种类映射而来，并非所有层在运行初期都会有内容。其他层已有记录，可以切回「全部」查看。"
          actionLabel="查看全部层"
          onAction={() => setLayerFilter("all")}
        />
      ) : (
        <ol className="divide-y divide-border-subtle">
          {visible.map((record) => (
            <MemoryRecordRow key={record.memory_id} record={record} />
          ))}
        </ol>
      )}
    </div>
  );
}
