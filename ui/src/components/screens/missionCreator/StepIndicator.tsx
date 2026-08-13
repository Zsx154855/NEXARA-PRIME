// 三步向导进度指示（目标确认 → 生成规划 → 提交审批）
// 进度语义走语义 token：已完成 = success，当前 = 仪式金，未到 = neutral。

import { CheckCircle2, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepIndicatorProps {
  current: number;
  steps: readonly { label: string; desc: string }[];
}

export function StepIndicator({ current, steps }: StepIndicatorProps) {
  return (
    <ol className="flex items-center" aria-label="创建流程">
      {steps.map((step, i) => {
        const isDone = i < current;
        const isActive = i === current;
        return (
          <li key={i} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-colors",
                  isDone && "bg-success/10 text-success",
                  isActive && "bg-gold-soft text-gold-text ring-1 ring-gold-text/30",
                  !isDone && !isActive && "bg-surface-subtle text-text-tertiary",
                )}
              >
                {isDone ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> : i + 1}
              </span>
              <div className="hidden sm:block">
                <div
                  className={cn(
                    "text-xs font-medium",
                    isActive
                      ? "text-text-primary"
                      : isDone
                        ? "text-success"
                        : "text-text-secondary",
                  )}
                >
                  {step.label}
                </div>
                <div className="text-xs text-text-tertiary">{step.desc}</div>
              </div>
            </div>
            {i < steps.length - 1 && (
              <ChevronRight
                className={cn(
                  "mx-2 h-3.5 w-3.5",
                  isDone ? "text-success/40" : "text-text-tertiary",
                )}
                aria-hidden="true"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
