// ─── 记忆统计：/api/memory/stats 投影 ───
// MemoryStats 真实字段（layers 四层统计）语义化展示：
// 总数与待审阅在前，四层以占比条呈现，不设象限/轮盘隐喻。

"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import type { MemoryStats } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { MemoryHeader } from "./MemoryHeader";
import { MemorySubNav } from "./MemorySubNav";
import { MEMORY_LAYERS } from "./memoryMeta";

type MemoryStatsScreenProps = {
  api: NexaraAPI;
};

export function MemoryStatsScreen({ api }: MemoryStatsScreenProps) {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStats(await api.getMemoryStats());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-8">
      <MemoryHeader
        title="记忆统计"
        subtitle="四层记忆的真实计数与构成。每一层都对应运行时的 MemoryLayer 分类，不设隐喻。"
      />
      <MemorySubNav />

      {loading ? (
        <LoadingState label="正在读取记忆统计…" />
      ) : error ? (
        <ErrorState
          title="统计读取失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load()}
        />
      ) : !stats ? (
        <EmptyState
          icon={<BarChart3 className="size-6" aria-hidden="true" />}
          title="统计为空"
          description="后端未返回记忆统计。可稍后重试。"
          actionLabel="重新加载"
          onAction={() => void load()}
        />
      ) : (
        <>
          <dl className="flex flex-wrap gap-x-12 gap-y-4">
            <div>
              <dt className="text-xs text-text-tertiary">记忆总数</dt>
              <dd className="mt-0.5 font-data text-2xl text-text-primary">
                {stats.total}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-tertiary">待审阅候选</dt>
              <dd className="mt-0.5 font-data text-2xl text-text-primary">
                {stats.pending_reviews}
              </dd>
            </div>
          </dl>

          {stats.pending_reviews > 0 && (
            <p>
              <Status
                tone="info"
                label={`${stats.pending_reviews} 条候选已自动提交，待审阅`}
              />
            </p>
          )}

          <section aria-labelledby="memory-layer-breakdown-heading" className="max-w-2xl">
            <h2
              id="memory-layer-breakdown-heading"
              className="border-t border-border-subtle pt-8 text-sm font-medium text-text-primary"
            >
              四层构成
            </h2>
            <ol className="mt-6 space-y-5">
              {MEMORY_LAYERS.map((layer) => {
                const count = stats.layers[layer.key] ?? 0;
                const pct =
                  stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
                return (
                  <li key={layer.key}>
                    <div className="flex items-baseline justify-between gap-4">
                      <div>
                        <h3 className="text-sm font-medium text-text-primary">
                          {layer.label}
                        </h3>
                        <p className="mt-0.5 text-xs text-text-tertiary">
                          {layer.note}
                        </p>
                      </div>
                      <p className="font-data text-sm text-text-primary">
                        {count}
                        <span className="text-xs text-text-tertiary"> · {pct}%</span>
                      </p>
                    </div>
                    <div
                      className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-subtle"
                      role="img"
                      aria-label={`${layer.label}占全部记忆 ${pct}%`}
                    >
                      <div
                        className="h-full rounded-full bg-gold-text"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>

          <p className="max-w-2xl text-xs leading-relaxed text-text-tertiary">
            分层由记忆种类（MemoryKind）按运行时的分类映射而来；占比随自动提交逐步成形。
          </p>
        </>
      )}
    </div>
  );
}
