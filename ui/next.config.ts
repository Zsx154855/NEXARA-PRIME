import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/console",
  trailingSlash: true,
  distDir: "out",
  images: { unoptimized: true },
};

export default nextConfig;
