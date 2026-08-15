import type { ConversationMessage } from "@/types";

/**
 * NEXARA conversation helpers — pure functions only.
 */

/** 时间戳：同日显示时:分，否则显示月/日。 */
export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export interface MessageMetaView {
  intent: string | null;
  intentConfidence: number | null;
  intentReasons: string[];
  provider: string | null;
  missionId: string | null;
  approvalRequired: boolean;
  memoryDeposited: boolean;
}

const EMPTY_META: MessageMetaView = {
  intent: null,
  intentConfidence: null,
  intentReasons: [],
  provider: null,
  missionId: null,
  approvalRequired: false,
  memoryDeposited: false,
};

/**
 * 记忆相关字段（后端可能随 metadata 返回）。
 * 命名对齐后端契约候选（memory_deposited / memory_saved / memory_key /
 * memory_ids / memory_entries / memory）。UI 只做如实呈现：有真实数据才提示。
 */
const MEMORY_FIELDS = [
  "memory_deposited",
  "memory_saved",
  "memory_key",
  "memory_ids",
  "memory_entries",
  "memory",
] as const;

function hasMemoryPayload(record: Record<string, unknown>): boolean {
  return MEMORY_FIELDS.some((key) => {
    const value = record[key];
    if (value === undefined || value === null || value === false || value === "") {
      return false;
    }
    if (Array.isArray(value)) return value.length > 0;
    return true;
  });
}

/**
 * 从真实消息 metadata 提取展示视图。
 * 后端实际写入的字段（runtime.answer_conversation）：
 *   assistant: intent / intent_confidence / intent_reasons / provider /
 *              execution_mode / mission_id / approval_required / …
 *   user:      execution_mode / intent / intent_confidence / intent_reasons
 * 类型契约之外的字段按 unknown 防御性读取，缺失时如实不显示。
 */
export function extractMeta(message: ConversationMessage): MessageMetaView {
  const record = message.metadata as Record<string, unknown> | null;
  if (record === null) return EMPTY_META;
  return {
    intent:
      typeof record.intent === "string" && record.intent !== ""
        ? record.intent
        : null,
    intentConfidence:
      typeof record.intent_confidence === "number" &&
      Number.isFinite(record.intent_confidence)
        ? record.intent_confidence
        : null,
    intentReasons: Array.isArray(record.intent_reasons)
      ? record.intent_reasons.filter((r): r is string => typeof r === "string")
      : [],
    provider:
      typeof record.provider === "string" && record.provider !== ""
        ? record.provider
        : null,
    missionId:
      typeof record.mission_id === "string" && record.mission_id !== ""
        ? record.mission_id
        : null,
    approvalRequired: record.approval_required === true,
    memoryDeposited: hasMemoryPayload(record),
  };
}
