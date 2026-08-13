import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "柏韩 · NEXARA",
  description:
    "把你想做的事说给 NEXARA。它把它变成一份你看得懂的计划、一道道你说了算的门、一条条能查证的结果，以及它记住的东西。",
  icons: {
    icon: "/icon.svg",
  },
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
