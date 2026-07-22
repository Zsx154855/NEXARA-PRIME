import type { Config } from "tailwindcss";

// Tailwind v4 uses CSS-based configuration via @theme in globals.css.
// This file exists for tooling compatibility (IDE extension, PostCSS).
// All design tokens are defined in src/app/globals.css.
//
// The @tailwindcss/postcss plugin reads @theme from the CSS entry point
// directly — no theme extension needed here.

const tailwindConfig: Config = {
  // CSS entry point — Tailwind v4 scans this for @theme blocks
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
};

export default tailwindConfig;
