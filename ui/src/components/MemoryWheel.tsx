"use client";

import { useState, useCallback, type KeyboardEvent } from "react";
import { Brain, Eye, Wrench, Globe, Users } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Types ──

export type MemoryQuadrant = "perceptual" | "procedural" | "world" | "relational";

interface QuadrantDef {
  key: MemoryQuadrant;
  label: string;
  icon: typeof Brain;
}

const QUADRANTS: QuadrantDef[] = [
  { key: "perceptual", label: "感知记忆", icon: Eye },
  { key: "procedural", label: "程序记忆", icon: Wrench },
  { key: "world", label: "世界记忆", icon: Globe },
  { key: "relational", label: "关系记忆", icon: Users },
];

interface MemoryWheelProps {
  activeQuadrant?: MemoryQuadrant | null;
  onSelectQuadrant?: (q: MemoryQuadrant) => void;
  memoryCounts?: Partial<Record<MemoryQuadrant, number>>;
  runtimeStatus: "healthy" | "degraded" | "offline";
}

// ── Component ──

export function MemoryWheel({
  activeQuadrant = null,
  onSelectQuadrant,
  memoryCounts,
  runtimeStatus,
}: MemoryWheelProps) {
  const [focusedIdx, setFocusedIdx] = useState<number>(-1);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent, idx: number) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const quadrant = QUADRANTS[idx];
        if (quadrant) onSelectQuadrant?.(quadrant.key);
      }
    },
    [onSelectQuadrant],
  );

  const statusLabel =
    runtimeStatus === "healthy" ? "活跃"
    : runtimeStatus === "degraded" ? "降级"
    : "离线";

  return (
    <div
      className="flex flex-col items-center gap-6 select-none"
      role="region"
      aria-label="柏韩 记忆系统"
    >
      {/* Wheel */}
      <div
        className="relative grid grid-cols-2 gap-3 sm:gap-4"
        style={{ width: "min(320px, 80vw)", height: "min(320px, 80vw)" }}
      >
        {/* Center — NEXARA Core */}
        <div
          className={cn(
            "absolute inset-0 m-auto flex h-20 w-20 sm:h-24 sm:w-24 flex-col items-center justify-center rounded-full",
            "bg-surface-elevated border border-border-subtle shadow-sm z-10",
            "transition-all duration-300 motion-reduce:transition-none",
          )}
        >
          <Brain className="h-6 w-6 sm:h-7 sm:w-7 text-accent-primary" />
          <span className="mt-0.5 text-[10px] font-semibold text-text-primary tracking-wider">
            柏韩
          </span>
          <span
            className={cn(
              "text-[9px] font-medium",
              runtimeStatus === "healthy" && "text-success",
              runtimeStatus === "degraded" && "text-warning",
              runtimeStatus === "offline" && "text-danger",
            )}
          >
            {statusLabel}
          </span>
        </div>

        {/* Quadrants */}
        {QUADRANTS.map((q, i) => {
          const isActive = activeQuadrant === q.key;
          const isFocused = focusedIdx === i;
          const count = memoryCounts?.[q.key] as number | undefined;

          return (
            <button
              key={q.key}
              type="button"
              aria-label={`${q.label}${count !== undefined ? ` · ${count} 条记录` : ""}`}
              tabIndex={0}
              onFocus={() => setFocusedIdx(i)}
              onBlur={() => setFocusedIdx(-1)}
              onKeyDown={(e) => handleKeyDown(e, i)}
              onMouseEnter={() => setFocusedIdx(i)}
              onMouseLeave={() => setFocusedIdx(-1)}
              onClick={() => onSelectQuadrant?.(q.key)}
              className={cn(
                "relative flex flex-col items-center justify-center gap-1.5 rounded-2xl",
                "border border-border-subtle bg-surface-subtle",
                "transition-all duration-300 motion-reduce:transition-none",
                "hover:bg-surface-hover hover:border-border-default",
                "focus:outline-none",
                // Active state
                isActive && [
                  "bg-surface-active border-accent-primary/40",
                  "ring-1 ring-accent-primary/20",
                ],
                // Focus state
                isFocused && !isActive && [
                  "bg-surface-hover border-border-default",
                  "ring-1 ring-border-focus/30",
                ],
              )}
            >
              <q.icon
                className={cn(
                  "h-5 w-5 sm:h-6 sm:w-6 transition-colors duration-300",
                  isActive ? "text-accent-primary" : "text-text-secondary",
                  isFocused && !isActive && "text-text-primary",
                )}
              />
              <span
                className={cn(
                  "text-[11px] sm:text-xs font-medium transition-colors duration-300",
                  isActive ? "text-text-primary" : "text-text-secondary",
                  isFocused && !isActive && "text-text-primary",
                )}
                style={{
                  textShadow: isActive
                    ? "0 0 8px rgba(196, 164, 90, 0.15)"
                    : undefined,
                }}
              >
                {q.label}
              </span>
              {count !== undefined && (
                <span className="text-[10px] text-text-tertiary tabular-nums">
                  {count}
                </span>
              )}
            </button>
          );
        })}

        {/* Connecting lines — subtle crosshair from center */}
        <div
          className="pointer-events-none absolute inset-0 z-0"
          aria-hidden="true"
        >
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border-subtle" />
          <div className="absolute top-1/2 left-0 right-0 h-px bg-border-subtle" />
        </div>
      </div>

      {/* Hint tooltip */}
      <p className="text-[11px] text-text-tertiary text-center max-w-xs">
        点击记忆象限浏览对应记忆记录
      </p>
    </div>
  );
}
