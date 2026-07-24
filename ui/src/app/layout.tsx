import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "柏韩 — 主脑控制台",
  description: "柏韩 · 人类中心的自主智能体核心 · 主权工程宪章 NSEC V2.1",
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
