// ─── 可恢复任务卡：POST /api/recovery/check 真实字段 ───
// 仅当存在 resumable 使命时展示；接口不可用 / 无恢复项 → 整卡隐藏。

"use client";

import type { RecoveryReport } from "./recovery";
import { Section } from "./Section";
import { stateLabel } from "./missionState";

type RecoverySectionProps = {
  recovery: RecoveryReport | null;
  onOpenMission: (missionId: string) => void;
};

export function RecoverySection({
  recovery,
  onOpenMission,
}: RecoverySectionProps) {
  if (!recovery) return null;

  const resumableMissions = recovery.missions.filter((m) => m.resumable);

  if (resumableMissions.length === 0) return null;

  return (
    <Section
      id="recovery"
      overline="中断后可继续"
      title="可恢复任务"
      meta={`${resumableMissions.length} 项`}
    >
      <ul className="divide-y divide-border-subtle">
        {resumableMissions.map((mission) => (
          <li key={mission.mission_id}>
            <button
              type="button"
              onClick={() => onOpenMission(mission.mission_id)}
              className="flex w-full items-baseline justify-between gap-4 py-4 text-left transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-data text-sm text-text-primary">
                  {mission.mission_id}
                </span>
                <span className="mt-0.5 block text-xs text-text-secondary">
                  {mission.state ? stateLabel(mission.state) : "执行中"}
                  {mission.checkpoint_count > 0 &&
                    ` · 已保存 ${mission.checkpoint_count} 个检查点`}
                </span>
              </span>
              <span className="shrink-0 text-xs text-text-tertiary">
                继续
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}
