"use client";

import { useState, useEffect, useCallback, useRef, type KeyboardEvent } from "react";
import { Search, Rocket, Play, Brain, CornerDownLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MissionSnapshot, MemoryRecord } from "@/types";

// ── Types ──

interface SearchResult {
  type: "mission" | "memory" | "action";
  id: string;
  title: string;
  subtitle?: string;
  action?: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  missions: MissionSnapshot[];
  memories: MemoryRecord[];
  onMissionSelect: (id: string) => void;
  onCreateMission: () => void;
  onContinueMission: () => void;
  onViewMemory: () => void;
  onViewRuntime: () => void;
  onViewEvidence: () => void;
}

// ── Component ──

export function CommandPalette({
  open,
  onClose,
  missions,
  memories,
  onMissionSelect,
  onCreateMission,
  onContinueMission,
  onViewMemory,
  onViewRuntime,
  onViewEvidence,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // ESC to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Build results
  const results = useCallback((): SearchResult[] => {
    const q = query.toLowerCase().trim();

    // Always show actions when no query or matching
    const actions: SearchResult[] = [
      { type: "action", id: "create-mission", title: "创建使命", subtitle: "开始新的自主任务", action: onCreateMission },
      { type: "action", id: "continue-mission", title: "继续任务", subtitle: "恢复当前活跃使命", action: onContinueMission },
      { type: "action", id: "view-memory", title: "查看记忆", subtitle: "浏览所有记忆记录", action: onViewMemory },
      { type: "action", id: "view-runtime", title: "运行时状态", subtitle: "查看系统健康与性能", action: onViewRuntime },
      { type: "action", id: "view-evidence", title: "查看证据", subtitle: "浏览证据链与收据", action: onViewEvidence },
    ];

    if (!q) {
      // No query: show recent missions + all actions
      const recent = missions.slice(-5).reverse().map((m) => ({
        type: "mission" as const,
        id: m.mission_id,
        title: m.title,
        subtitle: m.state,
      }));
      return [...recent, ...actions];
    }

    // Filter missions
    const matchedMissions = missions
      .filter((m) => m.title.toLowerCase().includes(q) || m.objective.toLowerCase().includes(q))
      .slice(0, 5)
      .map((m) => ({
        type: "mission" as const,
        id: m.mission_id,
        title: m.title,
        subtitle: m.state,
      }));

    // Filter memories
    const matchedMemories = memories
      .filter((m) => m.key.toLowerCase().includes(q) || m.content.toLowerCase().includes(q))
      .slice(0, 5)
      .map((m) => ({
        type: "memory" as const,
        id: m.memory_id,
        title: m.key,
        subtitle: m.kind,
      }));

    // Filter actions
    const matchedActions = actions.filter((a) =>
      a.title.toLowerCase().includes(q) || a.subtitle?.toLowerCase().includes(q),
    );

    return [...matchedMissions, ...matchedMemories, ...matchedActions];
  }, [query, missions, memories, onCreateMission, onContinueMission, onViewMemory, onViewRuntime, onViewEvidence]);

  const allResults = results();

  const handleKeyDown = (e: KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIdx((prev) => (prev + 1) % Math.max(allResults.length, 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIdx((prev) => (prev - 1 + allResults.length) % Math.max(allResults.length, 1));
        break;
      case "Enter":
        e.preventDefault();
        selectResult(allResults[activeIdx]);
        break;
    }
  };

  const selectResult = (r: SearchResult | undefined) => {
    if (!r) return;
    if (r.type === "mission") onMissionSelect(r.id);
    else if (r.action) r.action();
    onClose();
  };

  if (!open) return null;

  const grouped: Record<string, SearchResult[]> = {};
  for (const r of allResults) {
    const g = r.type === "mission" ? "使命"
      : r.type === "memory" ? "记忆"
      : "操作";
    (grouped[g] ??= []).push(r);
  }

  let globalIdx = 0;
  const groupEntries = Object.entries(grouped);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      role="dialog"
      aria-modal="true"
      aria-label="命令面板"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-graphite/20 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="relative w-full max-w-lg rounded-2xl border border-border-subtle bg-surface-elevated shadow-2xl overflow-hidden"
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-border-subtle px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-text-tertiary" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
            placeholder="搜索使命、记忆或操作…"
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-disabled outline-none"
            aria-label="搜索 NEXARA"
          />
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded-md border border-border-subtle bg-surface-subtle px-1.5 py-0.5 text-[10px] text-text-tertiary">
            <CornerDownLeft className="h-3 w-3" />
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-auto p-2" role="listbox">
          {allResults.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center">
              <Search className="h-8 w-8 text-text-disabled" />
              <p className="text-sm text-text-tertiary">未找到匹配结果</p>
            </div>
          ) : (
            groupEntries.map(([group, items]) => {
              const startIdx = globalIdx;
              globalIdx += items.length;

              return (
                <div key={group} className="mb-1">
                  <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-tertiary">
                    {group}
                  </div>
                  {items.map((item, j) => {
                    const idx = startIdx + j;
                    const isActive = idx === activeIdx;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        role="option"
                        aria-selected={isActive}
                        onClick={() => selectResult(item)}
                        onMouseEnter={() => setActiveIdx(idx)}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                          isActive
                            ? "bg-surface-active text-text-primary"
                            : "text-text-secondary hover:bg-surface-hover",
                        )}
                      >
                        {item.type === "mission" && <Rocket className="h-4 w-4 shrink-0" />}
                        {item.type === "memory" && <Brain className="h-4 w-4 shrink-0" />}
                        {item.type === "action" && <Play className="h-4 w-4 shrink-0" />}
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-medium">{item.title}</div>
                          {item.subtitle && (
                            <div className="truncate text-xs text-text-tertiary">
                              {item.subtitle}
                            </div>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 border-t border-border-subtle px-4 py-2 text-[10px] text-text-tertiary">
          <span><kbd className="text-text-secondary">↑↓</kbd> 导航</span>
          <span><kbd className="text-text-secondary">↵</kbd> 选择</span>
          <span><kbd className="text-text-secondary">Esc</kbd> 关闭</span>
        </div>
      </div>
    </div>
  );
}
