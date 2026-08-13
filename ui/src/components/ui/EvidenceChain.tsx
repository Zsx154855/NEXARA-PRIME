import { cn } from "@/lib/utils";
import { Status } from "./Status";
import type { EvidenceArtifact } from "@/types";

/**
 * NEXARA EvidenceChain — 证据链（品牌签名组件）。
 * mono 数据原貌排版 sha256；verified/corrupt 如实呈现。
 * 「能信结果吗」的答案入口：谁、何时、什么、怎么验证。
 */
type EvidenceChainProps = {
  evidence: EvidenceArtifact[];
  /** 逐条懒加载；列表只渲染真实后端字段 */
  className?: string;
};

function truncateSha(sha: string): string {
  return sha.length > 20 ? `${sha.slice(0, 10)}…${sha.slice(-8)}` : sha;
}

export function EvidenceChain({ evidence, className }: EvidenceChainProps) {
  return (
    <ol className={cn("flex flex-col gap-3", className)} aria-label="证据链">
      {evidence.map((item) => {
        const isVerified = item.verification_status === "verified";
        return (
          <li
            key={item.evidence_id}
            className="rounded-md border border-border-subtle bg-surface-elevated px-4 py-3"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <Status
                  tone={isVerified ? "success" : "danger"}
                  label={isVerified ? "已验证" : "校验未通过"}
                />
                <span className="truncate text-sm font-medium text-text-primary">
                  {item.title}
                </span>
              </div>
              <span className="shrink-0 text-xs text-text-secondary">
                {item.actor} · {item.timestamp}
              </span>
            </div>
            <p className="mt-1.5 break-all font-data text-xs leading-relaxed text-text-secondary">
              sha256:{item.sha256}
            </p>
            {item.parent_evidence.length > 0 && (
              <p className="mt-1 text-xs text-text-tertiary">
                上级证据：{item.parent_evidence.map(truncateSha).join(" · ")}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
