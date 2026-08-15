// 使命详情 · Tab 栏（计划 / 执行 / 结果 / 时间线；移动端横向滚动）
import { cn } from "@/lib/utils";
import { TAB_ITEMS, type MissionTabId } from "./constants";

interface TabBarProps {
  active: MissionTabId;
  onChange: (tab: MissionTabId) => void;
}

export function TabBar({ active, onChange }: TabBarProps) {
  return (
    <div
      role="tablist"
      aria-label="使命详情"
      className="flex overflow-x-auto border-b border-border-subtle"
    >
      {TAB_ITEMS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={cn(
              "-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm transition-colors",
              isActive
                ? "border-gold-text font-medium text-text-primary"
                : "border-transparent text-text-secondary hover:text-text-primary",
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
