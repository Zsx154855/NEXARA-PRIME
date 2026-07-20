import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEXARA PRIME — 主脑控制台",
  description: "人类中心的自主智能体核心 · 主权工程宪章 NSEC V2.0",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="antialiased">
      <body className="min-h-screen bg-ivory font-sans text-graphite">
        {children}
      </body>
    </html>
  );
}
