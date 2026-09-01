import { cn } from "@/lib/utils";

type AnimatedMarkProps = {
  className?: string;
  size?: number;
};

/**
 * NEXARA 动态品牌标记 — 磨砂玻璃六边形（与桌面应用图标同源）。
 * 微动画：光斑呼吸（7-9s）、高光微动（8s）、金点沿环慢转（30s）。
 * SMIL 实现，WKWebView 兼容，无外部依赖。
 */
export function AnimatedMark({ className, size = 32 }: AnimatedMarkProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={cn("rounded-[7px]", className)}
      role="img"
      aria-label="NEXARA"
    >
      <defs>
        <radialGradient id="am-bg" cx="40%" cy="30%" r="90%">
          <stop offset="0%" stopColor="#1b3d45" />
          <stop offset="100%" stopColor="#071118" />
        </radialGradient>
        <radialGradient id="am-teal" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#2dd4bf" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#2dd4bf" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="am-amber" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="am-gold" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fcd34d" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#fcd34d" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="am-glass" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.18" />
        </linearGradient>
        <linearGradient id="am-goldring" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0%" stopColor="#fbf0cd" />
          <stop offset="100%" stopColor="#8a6626" />
        </linearGradient>
        <filter id="am-frost" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.5" numOctaves="3" seed="11" />
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.12 0"
          />
        </filter>
      </defs>

      <rect width="64" height="64" rx="13" fill="url(#am-bg)" />

      <circle cx="18" cy="20" r="22" fill="url(#am-teal)">
        <animate attributeName="opacity" values="1;0.55;1" dur="7s" repeatCount="indefinite" />
      </circle>
      <circle cx="48" cy="46" r="24" fill="url(#am-amber)">
        <animate attributeName="opacity" values="0.65;1;0.65" dur="9s" repeatCount="indefinite" />
      </circle>
      <circle cx="32" cy="32" r="18" fill="url(#am-gold)">
        <animate attributeName="opacity" values="0.8;1;0.8" dur="6s" repeatCount="indefinite" />
      </circle>

      <polygon
        points="32,14 46,23 46,41 32,50 18,41 18,23"
        fill="url(#am-glass)"
        stroke="#ffffff"
        strokeWidth="1.6"
        strokeLinejoin="round"
        opacity="0.96"
      />
      <polygon points="32,14 46,23 46,41 32,50 18,41 18,23" fill="#ffffff" filter="url(#am-frost)" opacity="0.4" />

      <polygon points="20,28 32,20 38,23 26,31" fill="#ffffff" opacity="0.22">
        <animate attributeName="opacity" values="0.22;0.08;0.22" dur="8s" repeatCount="indefinite" />
      </polygon>

      <g>
        <circle cx="32" cy="32" r="10.5" fill="none" stroke="url(#am-goldring)" strokeWidth="1.5" />
        <circle cx="32" cy="21.5" r="2" fill="#fcd34d" />
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 32 32"
          to="360 32 32"
          dur="30s"
          repeatCount="indefinite"
        />
      </g>
      <circle cx="32" cy="32" r="3.5" fill="#ffffff" opacity="0.9" />
    </svg>
  );
}
