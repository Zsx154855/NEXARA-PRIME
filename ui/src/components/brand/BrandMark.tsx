import { cn } from "@/lib/utils";

type BrandMarkProps = {
  className?: string;
};

/**
 * NEXARA 品牌标记 — 门 + 金点（ADR-UI-001）。
 * 与 /icon.svg 同源，内联渲染避免 img 请求。
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn("size-8", className)}
      role="img"
      aria-label="NEXARA"
    >
      <rect x="2" y="2" width="60" height="60" rx="13" fill="#322F2A" />
      <path d="M20 20h14" stroke="#FDFAF5" strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M44 26v18" stroke="#FDFAF5" strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M20 44v-24" stroke="#FDFAF5" strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M20 44h24" stroke="#FDFAF5" strokeWidth="4" strokeLinecap="round" fill="none" />
      <circle cx="32" cy="33" r="5" fill="#C4A45A" />
    </svg>
  );
}
