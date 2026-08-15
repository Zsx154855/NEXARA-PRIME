"use client";

import { MemoryBrowseScreen } from "@/components/screens/memory/MemoryBrowseScreen";
import { useRuntimeData } from "@/lib/runtime-context";

/** 记忆 — 浏览（/api/memory 投影：四层分类、验证与冲突如实呈现） */
export default function MemoryBrowsePage() {
  const { api } = useRuntimeData();
  return <MemoryBrowseScreen api={api} />;
}
