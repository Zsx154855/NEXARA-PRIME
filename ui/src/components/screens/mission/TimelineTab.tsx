// 时间线 Tab：Event 流（event_type / timestamp / actor / trace_id），按时间倒序。
import { History, User } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Event } from "@/types";
import { formatTimestamp, stateLabel } from "./constants";

interface TimelineTabProps {
  events: Event[];
  currentState: string;
}

const MAX_VISIBLE = 100;

export function TimelineTab({ events, currentState }: TimelineTabProps) {
  const sorted = [...events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
  const visible = sorted.slice(0, MAX_VISIBLE);

  if (visible.length === 0) {
    return (
      <EmptyState
        title="还没有事件记录。"
        description={`当前状态：${stateLabel(currentState)}。执行开始后，事件（类型 / 时间 / 执行者）会按时间倒序如实入流。`}
      />
    );
  }

  return (
    <section className="rounded-xl border border-border-subtle bg-surface-elevated p-4">
      <div className="flex items-center gap-1.5">
        <History className="h-4 w-4 text-gold-text" />
        <h2 className="text-sm font-semibold text-text-primary">事件流</h2>
        <span className="ml-auto text-xs text-text-tertiary">
          {events.length} 条{events.length > MAX_VISIBLE ? `（显示最近 ${MAX_VISIBLE} 条）` : ""}
        </span>
      </div>
      <ol className="mt-3 space-y-1" aria-label="事件时间线">
        {visible.map((event) => (
          <li key={event.event_id ?? `${event.timestamp}-${event.event_type}`} className="flex gap-3 px-1 py-1.5">
            <div className="flex flex-col items-center">
              <span className="mt-1.5 inline-block size-1.5 rounded-full bg-gold-text/60" />
              <span className="mt-1 w-px flex-1 bg-border-subtle" />
            </div>
            <div className="min-w-0 flex-1 pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <code className="font-data text-xs font-medium text-text-primary">
                  {event.event_type}
                </code>
                <span className="text-xs text-text-tertiary">
                  {formatTimestamp(event.timestamp)}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {event.actor}
                </span>
                {event.trace_id && (
                  <code className="font-data text-text-tertiary">
                    {event.trace_id.slice(0, 12)}
                  </code>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
