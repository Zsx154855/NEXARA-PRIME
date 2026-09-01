import type { NextConfig } from "next";

const isDesktop = process.env.NEXT_PUBLIC_PLATFORM === "tauri";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  distDir: isDesktop ? "out-tauri" : "out",
  images: { unoptimized: true },
  ...(isDesktop ? {} : { basePath: "/console" }),
};

export default nextConfig;
