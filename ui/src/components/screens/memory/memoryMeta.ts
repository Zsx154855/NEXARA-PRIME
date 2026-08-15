// ─── 记忆区元数据：14 种 MemoryKind 中文映射 + 四层分类 ───
// 四层分类镜像后端 MemoryLayer.from_kind（src/nexara_prime/memory.py），
// 本文件不引入任何象限/轮盘隐喻。

import type { MemoryKind, MemoryStats } from "@/types";

/** 四层记忆（与后端 MemoryLayer 常量一致）。 */
export type MemoryLayerKey = keyof MemoryStats["layers"];

/** 14 种记忆种类的中文映射（含后端枚举中的 experience）。 */
const MEMORY_KIND_LABELS: Record<string, string> = {
  short_term: "短期记忆",
  fact: "事实",
  decision: "决策",
  failure: "失败",
  patch: "修补",
  user_fact: "用户事实",
  project_fact: "项目事实",
  experience: "经验",
  preference: "偏好",
  temporary_context: "临时上下文",
  failure_experience: "失败经验",
  system_rule: "系统规则",
  skill_improvement: "技能改进",
  unverified_inference: "未验证推断",
};

export function memoryKindLabel(kind: MemoryKind | string): string {
  return MEMORY_KIND_LABELS[kind] ?? kind;
}

/** 种类 → 分层（镜像后端 MemoryLayer.from_kind；未知种类默认 semantic）。 */
const LAYER_BY_KIND: Record<string, MemoryLayerKey> = {
  short_term: "working",
  temporary_context: "working",
  unverified_inference: "working",
  decision: "episodic",
  failure: "episodic",
  fact: "semantic",
  failure_experience: "semantic",
  user_fact: "semantic",
  project_fact: "semantic",
  preference: "semantic",
  experience: "semantic",
  patch: "procedural",
  skill_improvement: "procedural",
  system_rule: "procedural",
};

export function memoryLayerOf(kind: MemoryKind | string): MemoryLayerKey {
  return LAYER_BY_KIND[kind] ?? "semantic";
}

export const MEMORY_LAYERS: Array<{
  key: MemoryLayerKey;
  label: string;
  note: string;
}> = [
  { key: "working", label: "工作记忆", note: "当下上下文与未验证推断" },
  { key: "episodic", label: "情景记忆", note: "事件与决策记录" },
  { key: "semantic", label: "语义记忆", note: "事实、偏好与项目知识" },
  { key: "procedural", label: "程序记忆", note: "流程、规则与技能改进" },
];

export function memoryLayerLabel(layer: MemoryLayerKey): string {
  return MEMORY_LAYERS.find((item) => item.key === layer)?.label ?? layer;
}

export type MemoryStatusTone = "success" | "info" | "warning" | "neutral";

/** 记录状态（与后端 memory.py 一致：committed/candidate/conflict/superseded）。 */
export function memoryStatusMeta(status: string): {
  tone: MemoryStatusTone;
  label: string;
} {
  switch (status) {
    case "committed":
      return { tone: "success", label: "已提交" };
    case "candidate":
      return { tone: "info", label: "候选" };
    case "conflict":
      return { tone: "warning", label: "冲突" };
    case "superseded":
      return { tone: "neutral", label: "已取代" };
    default:
      return { tone: "neutral", label: status || "未知" };
  }
}

/** 置信度 0–1 → 百分比；非比例值原样加 %。 */
export function formatConfidence(confidence: number): string {
  const ratio =
    confidence >= 0 && confidence <= 1
      ? Math.round(confidence * 100)
      : Math.round(confidence);
  return `${ratio}%`;
}

/** 按 created_at 倒序（最新的在前）。 */
export function byCreatedAtDesc(
  a: { created_at: string },
  b: { created_at: string },
): number {
  return Date.parse(b.created_at) - Date.parse(a.created_at);
}
