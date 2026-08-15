/**
 * Presentation boundary — 产品默认视图与内部数据的隔离层（P1-DATA-BOUNDARY-001）。
 *
 * 背景：NEXARA_MOCK_MODEL 开启时后端 MockProvider（冻结区）生成的
 * DETERMINISTIC_MOCK_RESULT 文本会进入对话历史；QA/E2E 测试使命是真实
 * DB 记录且无字段级标记。本模块只做「默认产品视图」的映射隔离：
 * 原始数据（API/DB/Evidence/Audit）一律不动、不删。
 */

/** 内部 mock 回复标记（后端 MockProvider 生成，冻结区不可改） */
const MOCK_MARKER = "DETERMINISTIC_MOCK_RESULT";

/** 内部元数据行前缀（出现在 mock 文本或结构化回显中） */
const INTERNAL_LINE_PREFIXES = [
  "Objective:",
  "Context keys:",
  "Decision:",
  "Conversation transcript:",
  "Runtime intent:",
  "Intent confidence:",
  "Execution mode:",
  "Approval required:",
];

/** QA/测试使命标题前缀（现存数据无字段标记，只能按标题文本识别） */
const QA_TITLE_PATTERN = /^QA-(E2E|VIS|GEO|SMOKE|FIXTURE)(-|\s|$)/i;

export function isMockContent(content: string): boolean {
  return content.startsWith(MOCK_MARKER);
}

/**
 * 默认产品视图的 assistant 内容映射：
 * - mock 回复 → 诚实占位（原始内容仍完整存在于数据与治理/审计路径）
 * - 普通内容 → 原样透传
 */
export function sanitizeAssistantContent(content: string): string {
  if (isMockContent(content)) {
    return "（模拟回复 · 内部测试数据）此消息的原始内容仅用于测试验证，未在产品视图展示。";
  }
  return content;
}

/** 默认视图内剥离内部元数据行（防御性：非 mock 前缀但含内部字段的内容） */
export function stripInternalLines(content: string): string {
  return content
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim();
      return !INTERNAL_LINE_PREFIXES.some((prefix) => trimmed.startsWith(prefix));
    })
    .join("\n")
    .trim();
}

/** 按标题文本判定 QA/测试使命（现存数据无 type/tags 字段） */
export function isQaMission(title: string | null | undefined): boolean {
  if (!title) return false;
  return QA_TITLE_PATTERN.test(title.trim());
}

type MissionLike = {
  mission_id: string;
  title?: string | null;
  objective?: string | null;
};

/** 默认产品使命列表：排除 QA/测试使命（不删除数据，仅视图过滤） */
export function filterProductMissions<T extends MissionLike>(missions: T[]): T[] {
  return missions.filter(
    (m) => !isQaMission(m.title) && !isQaMission(m.objective),
  );
}
