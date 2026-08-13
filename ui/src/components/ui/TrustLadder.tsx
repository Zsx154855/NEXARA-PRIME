import { cn } from "@/lib/utils";

/**
 * NEXARA TrustLadder — 信任阶梯（品牌签名组件）。
 * 五级：许可 → 审批 → 执行 → 证据 → 记忆。
 * 灰=未到达，琥珀=等待/关注，绿=已验证，红=失败。
 * 任一级红则整体红并给出 FailureCode 分类原因。
 * 第五级记忆按 ADR-UI-003 如实呈现 auto_commit 机制。
 */

type LadderTone = "pending" | "waiting" | "verified" | "failed";

type LadderLevel = {
  id: string;
  label: string;
  description: string;
  tone: LadderTone;
};

const toneDotClass: Record<LadderTone, string> = {
  pending: "bg-taupe",
  waiting: "bg-warning",
  verified: "bg-success",
  failed: "bg-danger",
};

const toneTextClass: Record<LadderTone, string> = {
  pending: "text-text-tertiary",
  waiting: "text-warning",
  verified: "text-success",
  failed: "text-danger",
};

type TrustLadderProps = {
  levels: LadderLevel[];
  /** 阶梯整体失败原因（FailureCode 分类，人话） */
  failureReason?: string;
  className?: string;
};

export function TrustLadder({ levels, failureReason, className }: TrustLadderProps) {
  const hasFailure = levels.some((level) => level.tone === "failed");
  return (
    <div
      className={cn("flex flex-col gap-0", className)}
      role="list"
      aria-label="信任阶梯"
    >
      {levels.map((level, index) => (
        <div key={level.id} role="listitem" className="relative flex gap-3 pb-4 last:pb-0">
          {index < levels.length - 1 && (
            <span
              className="absolute left-[3.5px] top-4 h-full w-px bg-border-subtle"
              aria-hidden="true"
            />
          )}
          <span
            className={cn(
              "relative mt-1.5 inline-block size-2 shrink-0 rounded-full",
              toneDotClass[level.tone],
            )}
            aria-hidden="true"
          />
          <div className="flex flex-col gap-0.5">
            <span className={cn("text-sm font-medium", toneTextClass[level.tone])}>
              {level.label}
            </span>
            <span className="text-xs leading-relaxed text-text-secondary">
              {level.description}
            </span>
          </div>
        </div>
      ))}
      {hasFailure && failureReason && (
        <p className="mt-2 border-l-2 border-danger pl-3 text-sm text-danger" role="alert">
          信任链不完整：{failureReason}
        </p>
      )}
    </div>
  );
}

export type { LadderLevel, LadderTone };
