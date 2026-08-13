// ─── HOME 时间与问候工具 ───
// 问候语按时段；时间展示「今日显示时分，更早显示月日」。

/** 基于当前时段的问候语（早上好 / 下午好 / 晚上好）。 */
export function greetingForHour(hour: number): string {
  if (hour >= 5 && hour < 12) return "早上好";
  if (hour >= 12 && hour < 18) return "下午好";
  return "晚上好";
}

/** 编辑式日期行，如「8月14日 星期四」。 */
export function todayLine(): string {
  return new Date().toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

/** 今日 → HH:mm；更早 → M月D日；非法输入返回空串。 */
export function formatShortTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

/** 按 updated_at 倒序（最新的在前）。 */
export function byUpdatedAtDesc(
  a: { updated_at: string },
  b: { updated_at: string },
): number {
  return Date.parse(b.updated_at) - Date.parse(a.updated_at);
}
