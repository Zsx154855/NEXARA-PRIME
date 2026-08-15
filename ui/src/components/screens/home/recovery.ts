// ─── 可恢复任务：POST /api/recovery/check 响应的窄化解析 ───
// 后端返回 RecoveryResult.__dict__：
//   checked / resumable / completed / duplicate_steps / missions[]
//   missions 项含 mission_id / state / resumable / checkpoint_count。
// 字段缺失或不可信时返回 null —— 调用方整卡隐藏（不可用则隐藏）。

export type RecoveryMission = {
  mission_id: string;
  state: string;
  resumable: boolean;
  checkpoint_count: number;
};

export type RecoveryReport = {
  checked: number;
  resumable: number;
  completed: number;
  duplicate_steps: number;
  missions: RecoveryMission[];
};

function toNumber(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

export function parseRecovery(value: unknown): RecoveryReport | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (typeof record.resumable !== "number" || !Array.isArray(record.missions)) {
    return null;
  }

  const items = record.missions as unknown[];
  const missions: RecoveryMission[] = items.flatMap((item): RecoveryMission[] => {
    if (typeof item !== "object" || item === null) return [];
    const m = item as Record<string, unknown>;
    if (typeof m.mission_id !== "string" || m.mission_id.length === 0) return [];
    return [
      {
        mission_id: m.mission_id,
        state: typeof m.state === "string" ? m.state : "",
        resumable: m.resumable === true,
        checkpoint_count: toNumber(m.checkpoint_count),
      },
    ];
  });

  return {
    checked: toNumber(record.checked),
    resumable: record.resumable,
    completed: toNumber(record.completed),
    duplicate_steps: toNumber(record.duplicate_steps),
    missions,
  };
}
