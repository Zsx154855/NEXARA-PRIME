"use client";

import { useState, useEffect, useCallback } from "react";
import type { RuntimeOverview, EvidenceArtifact } from "@/types";
import { cn } from "@/lib/utils";
import {
  FileSearch,
  Copy,
  Check,
  ExternalLink,
  Filter,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Clock,
  User,
  Hash,
  Link2,
} from "lucide-react";

interface EvidenceViewerProps {
  api: { getEvidence: (missionId?: string) => Promise<EvidenceArtifact[]> };
  overview: RuntimeOverview | null;
}

function EvidenceRow({
  ev,
  onCopy,
}: {
  ev: EvidenceArtifact;
  onCopy: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy(ev.evidence_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="surface-card overflow-hidden transition-all">
      {/* Header row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-hover-overlay"
      >
        <div className="flex-shrink-0 text-text-tertiary">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </div>
        <div
          className={cn(
            "badge flex-shrink-0",
            ev.verification_status === "verified"
              ? "badge-success"
              : ev.verification_status === "pending"
                ? "badge-warning"
                : "badge-error"
          )}
        >
          <ShieldCheck className="mr-1 h-3 w-3" />
          {ev.verification_status === "verified"
            ? "已验证"
            : ev.verification_status === "pending"
              ? "待验证"
              : "未通过"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-text-primary">
            {ev.title || ev.evidence_id.slice(0, 24)}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-text-tertiary">
            <span className="badge badge-neutral">{ev.kind}</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(ev.timestamp).toLocaleString("zh-CN", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleCopy();
          }}
          className="btn btn-ghost flex-shrink-0 p-1.5"
          title="复制证据 ID"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border px-4 py-3 text-xs text-text-secondary">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <div className="flex items-center gap-2">
              <Hash className="h-3.5 w-3.5 text-text-tertiary" />
              <span className="text-text-tertiary">证据 ID：</span>
              <code className="font-mono text-text-primary">{ev.evidence_id}</code>
            </div>
            <div className="flex items-center gap-2">
              <User className="h-3.5 w-3.5 text-text-tertiary" />
              <span className="text-text-tertiary">来源：</span>
              <span>{ev.source}</span>
            </div>
            <div className="flex items-center gap-2 col-span-2">
              <span className="text-text-tertiary">SHA256：</span>
              <code className="truncate font-mono text-text-primary">{ev.sha256}</code>
            </div>
          </div>

          {/* Receipt chain */}
          {ev.parent_evidence && ev.parent_evidence.length > 0 && (
            <div className="mt-3">
              <div className="mb-1 flex items-center gap-1.5 text-text-tertiary">
                <Link2 className="h-3.5 w-3.5" />
                回执链（{ev.parent_evidence.length} 条）
              </div>
              <div className="space-y-1">
                {ev.parent_evidence.map((pid) => (
                  <code
                    key={pid}
                    className="block truncate rounded bg-bg-secondary px-2 py-1 font-mono"
                  >
                    {pid}
                  </code>
                ))}
              </div>
            </div>
          )}

          {/* Memory-evidence binding */}
          {ev.source_event_id && (
            <div className="mt-3 flex items-center gap-2 rounded bg-bg-secondary px-2 py-1.5">
              <ExternalLink className="h-3.5 w-3.5 text-accent" />
              <span className="text-text-tertiary">内存绑定事件：</span>
              <code className="font-mono">{ev.source_event_id}</code>
            </div>
          )}

          {/* Content preview */}
          <div className="mt-3">
            <div className="mb-1 text-text-tertiary">内容预览：</div>
            <pre className="max-h-32 overflow-auto rounded bg-bg-secondary p-2 font-mono text-xs leading-relaxed text-text-secondary">
              {ev.content.length > 500
                ? ev.content.slice(0, 500) + "…"
                : ev.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function EvidenceViewer({ api, overview }: EvidenceViewerProps) {
  const [evidence, setEvidence] = useState<EvidenceArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMission, setFilterMission] = useState<string>("__all__");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const loadEvidence = useCallback(async (missionId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEvidence(missionId);
      setEvidence(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载证据失败");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadEvidence(filterMission === "__all__" ? undefined : filterMission);
  }, [loadEvidence, filterMission]);

  const handleCopy = (id: string) => {
    navigator.clipboard.writeText(id).catch(() => {});
    setCopyFeedback(id);
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  // Loading state
  if (loading && evidence.length === 0) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="surface-card animate-pulse p-4">
            <div className="skeleton mb-2 h-4 w-3/4" />
            <div className="skeleton h-3 w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error && evidence.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-3 py-12 text-center">
        <FileSearch className="h-10 w-10 text-error" />
        <div className="text-sm font-medium text-error">{error}</div>
        <button
          onClick={() => loadEvidence(filterMission === "__all__" ? undefined : filterMission)}
          className="btn btn-secondary"
        >
          重试
        </button>
      </div>
    );
  }

  // Empty state
  if (!loading && evidence.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-3 py-16 text-center">
        <FileSearch className="h-12 w-12 text-text-tertiary" />
        <div className="text-base font-medium text-text-primary">暂无证据数据</div>
        <div className="text-sm text-text-tertiary">
          任务执行完成后，证据与回执将显示在此处
        </div>
      </div>
    );
  }

  const missions = overview?.missions ?? [];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-text-tertiary" />
          <span className="text-sm text-text-secondary">按任务筛选：</span>
        </div>
        <select
          value={filterMission}
          onChange={(e) => setFilterMission(e.target.value)}
          className="input max-w-xs"
        >
          <option value="__all__">全部任务</option>
          {missions.map((m) => (
            <option key={m.mission_id} value={m.mission_id}>
              {m.title || m.mission_id.slice(0, 24)}
            </option>
          ))}
        </select>
        <div className="text-xs text-text-tertiary">
          共 {evidence.length} 条证据
        </div>
      </div>

      {/* Copy feedback toast */}
      {copyFeedback && (
        <div className="fixed bottom-6 right-6 z-50 animate-slide-up rounded-lg bg-text-primary px-4 py-2 text-sm text-text-on-dark shadow-lg">
          已复制证据 ID
        </div>
      )}

      {/* Evidence list */}
      <div className="space-y-2">
        {evidence.map((ev) => (
          <EvidenceRow key={ev.evidence_id} ev={ev} onCopy={handleCopy} />
        ))}
      </div>
    </div>
  );
}
