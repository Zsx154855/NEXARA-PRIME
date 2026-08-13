"use client";

import { MemoryKnowledgeScreen } from "@/components/screens/memory/MemoryKnowledgeScreen";

/** 记忆 — 知识（/api/knowledge-universe 投影；模块未就绪时如实呈现 503） */
export default function MemoryKnowledgePage() {
  return <MemoryKnowledgeScreen />;
}
