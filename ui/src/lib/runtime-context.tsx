"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { NexaraAPI, configureApi } from "@/lib/api";
import type { MemoryRecord, MemoryStats, RuntimeOverview, RuntimeStats } from "@/types";

/**
 * Runtime 数据上下文 — 10s 轮询（不可见化：无心跳 UI，
 * 异常由页面按需呈现）。shell 层单点取数，页面消费。
 */
type RuntimeData = {
  overview: RuntimeOverview | null;
  stats: RuntimeStats | null;
  memories: MemoryRecord[];
  memoryStats: MemoryStats | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  api: NexaraAPI;
};

const RuntimeDataContext = createContext<RuntimeData | null>(null);

const api = new NexaraAPI();

const POLL_INTERVAL_MS = 10_000;

export function RuntimeDataProvider({ children }: { children: React.ReactNode }) {
  const [overview, setOverview] = useState<RuntimeOverview | null>(null);
  const [stats, setStats] = useState<RuntimeStats | null>(null);
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    configureApi({
      baseUrl:
        window.location.hostname === "localhost" ? "http://127.0.0.1:8765" : "",
    });
  }, []);

  const load = useCallback(async () => {
    try {
      const [ov, st] = await Promise.all([api.getOverview(), api.getStats()]);
      setOverview(ov);
      setStats(st);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接到 NEXARA Runtime");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMemories = useCallback(async () => {
    try {
      const [mems, memStats] = await Promise.all([
        api.getMemory(),
        api.getMemoryStats(),
      ]);
      setMemories(mems);
      setMemoryStats(memStats);
    } catch {
      // Memory fetch is best-effort; don't surface errors globally
    }
  }, []);

  useEffect(() => {
    load();
    loadMemories();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load, loadMemories]);

  return (
    <RuntimeDataContext.Provider
      value={{ overview, stats, memories, memoryStats, loading, error, refresh: load, api }}
    >
      {children}
    </RuntimeDataContext.Provider>
  );
}

export function useRuntimeData(): RuntimeData {
  const data = useContext(RuntimeDataContext);
  if (data === null) {
    throw new Error("useRuntimeData must be used within RuntimeDataProvider");
  }
  return data;
}
