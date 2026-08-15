import { Rocket } from "lucide-react";
import { Badge, badgeVariants } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { MessageMetaView } from "./utils";

type ConversationMetaProps = {
  meta: MessageMetaView;
  onMissionSelect: (missionId: string) => void;
  onViewApprovals: () => void;
};

function percent(value: number | null): string {
  return value === null ? "" : ` · ${Math.round(value * 100)}%`;
}

/** 意图依据（reasons 真实字段）以 tooltip 呈现，绝不编造。 */
function intentTooltip(meta: MessageMetaView): string | undefined {
  if (meta.intentReasons.length === 0) return undefined;
  const confidence =
    meta.intentConfidence === null
      ? ""
      : `置信度 ${Math.round(meta.intentConfidence * 100)}%；`;
  return `${confidence}依据：${meta.intentReasons.join("、")}`;
}

/**
 * 助手消息元数据（product truth，非装饰）：
 *  - 意图 Badge（intent / confidence / reasons 真实字段）
 *  - 使命链接 Badge（完整 mission_id，font-data mono，点击跳使命）
 *  - 「需人工审批」琥珀 Badge（点击跳审批中心）
 *  - 记忆如实呈现：仅当 metadata 含记忆字段才显示「已按置信度自动沉淀到记忆」
 *    （ADR-UI-003：禁止「你批准后才写入」叙事）
 */
export function ConversationMeta({
  meta,
  onMissionSelect,
  onViewApprovals,
}: ConversationMetaProps) {
  const intent = meta.intent;
  const missionId = meta.missionId;
  const showBadges = intent !== null || missionId !== null || meta.approvalRequired;
  if (!showBadges && !meta.memoryDeposited) return null;

  return (
    <div className="mt-2">
      {showBadges && (
        <div className="flex flex-wrap items-center gap-1.5">
          {intent !== null && (
            <Badge
              tone={intent === "mission" ? "gold" : "neutral"}
              title={intentTooltip(meta)}
            >
              意图 · {intent === "mission" ? "使命" : "对话"}
              {percent(meta.intentConfidence)}
            </Badge>
          )}
          {missionId !== null && (
            <button
              type="button"
              onClick={() => onMissionSelect(missionId)}
              title="打开使命详情"
              aria-label={`打开使命 ${missionId}`}
              className={cn(
                badgeVariants({ tone: "success" }),
                "cursor-pointer font-data hover:bg-success/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring",
              )}
            >
              <Rocket className="h-3 w-3" aria-hidden="true" />
              使命 {missionId}
            </button>
          )}
          {meta.approvalRequired && (
            <button
              type="button"
              onClick={onViewApprovals}
              title="前往审批中心"
              className={cn(
                badgeVariants({ tone: "warning" }),
                "cursor-pointer hover:bg-warning/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring",
              )}
            >
              需人工审批 · 查看
            </button>
          )}
        </div>
      )}
      {meta.memoryDeposited && (
        <p className="mt-1.5 text-xs text-text-secondary">
          已按置信度自动沉淀到记忆
        </p>
      )}
    </div>
  );
}
