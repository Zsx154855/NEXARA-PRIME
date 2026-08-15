/**
 * NEXARA 六区导航（ADR-UI-004：TRUST 区用户可见标签=「治理」）。
 * 顶层 = 旅程 + 两个系统级保留区（记忆沉淀、设置配置）。
 */
export type NavSectionId =
  | "home"
  | "conversation"
  | "missions"
  | "trust"
  | "memory"
  | "settings";

export type NavItem = {
  id: NavSectionId;
  label: string;
  path: string;
  /** 匹配规则：路径前缀 */
  prefix: string;
};

export const NAV_ITEMS: NavItem[] = [
  { id: "home", label: "首页", path: "/", prefix: "/" },
  { id: "conversation", label: "对话", path: "/conversation", prefix: "/conversation" },
  { id: "missions", label: "使命", path: "/missions", prefix: "/missions" },
  { id: "trust", label: "治理", path: "/trust", prefix: "/trust" },
  { id: "memory", label: "记忆", path: "/memory", prefix: "/memory" },
  { id: "settings", label: "设置", path: "/settings", prefix: "/settings" },
];

export const MOBILE_NAV_ITEMS = NAV_ITEMS.filter((item) => item.id !== "settings");

/** 详情深链：/missions?id=、/conversation?id= */
export function missionDetailPath(missionId: string): string {
  return `/missions?id=${encodeURIComponent(missionId)}`;
}

export function conversationDetailPath(conversationId: string): string {
  return `/conversation?id=${encodeURIComponent(conversationId)}`;
}
