// ─── 记忆候选提示：四层统计如实展示 + 待审阅候选提示 ───
// 记忆为 auto_commit：候选是已自动提交的记录，审阅是其后置跟进——
// 文案不得暗示「批准后才写入」。

"use client";

import type { MemoryStats } from "@/types";
import { Status } from "@/components/ui/Status";
import { Section } from "./Section";

type MemoryOverviewProps = {
  memoryStats: MemoryStats | null;
  onViewMemory: () => void;
};

const LAYERS: Array<{ key: keyof MemoryStats["layers"]; label: string }> = [
  { key: "working", label: "工作记忆" },
  { key: "episodic", label: "情景记忆" },
  { key: "semantic", label: "语义记忆" },
  { key: "procedural", label: "程序记忆" },
];

export function MemoryOverview({
  memoryStats,
  onViewMemory,
}: MemoryOverviewProps) {
  if (!memoryStats) return null;

  return (
    <Section
      id="memory"
      overline="沉淀"
      title="记忆"
      meta={`共 ${memoryStats.total} 条`}
      actionLabel="查看记忆"
      onAction={onViewMemory}
    >
      <dl className="flex flex-wrap gap-x-10 gap-y-4">
        {LAYERS.map(({ key, label }) => (
          <div key={key}>
            <dt className="text-xs text-text-tertiary">{label}</dt>
            <dd className="mt-0.5 font-data text-sm text-text-primary">
              {memoryStats.layers[key] ?? 0}
            </dd>
          </div>
        ))}
      </dl>
      {memoryStats.pending_reviews > 0 && (
        <p className="mt-5">
          <Status
            tone="info"
            label={`${memoryStats.pending_reviews} 条候选已自动提交，待审阅`}
          />
        </p>
      )}
    </Section>
  );
}
