// ─── 知识宇宙取数（GET /api/knowledge-universe）───
// api.ts 尚未封装该端点；此模块按相同语义取数（超时、JSON 错误解析），
// 错误不静默：503 时如实呈现「知识库模块未就绪」。

import { resolveApiBaseUrl } from "@/lib/platform";
import type { ApiResult } from "@/types";

const TIMEOUT_MS = 30_000;

/** 与 runtime-context 的 configureApi 相同的 baseUrl 规则。 */
function knowledgeBaseUrl(): string {
  return resolveApiBaseUrl();
}

export async function fetchKnowledgeUniverse(): Promise<
  ApiResult<Record<string, unknown>>
> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(`${knowledgeBaseUrl()}/api/knowledge-universe`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    let parsed: unknown = null;
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      parsed = await res.json();
    } else {
      parsed = await res.text();
    }

    if (!res.ok) {
      const detail =
        parsed && typeof parsed === "object" && "detail" in parsed
          ? String((parsed as Record<string, unknown>).detail)
          : `HTTP ${res.status}`;
      return { type: "error", error: detail, status: res.status };
    }

    return {
      type: "success",
      data: parsed as Record<string, unknown>,
    };
  } catch (err) {
    const message =
      err instanceof DOMException && err.name === "AbortError"
        ? `请求超时（${TIMEOUT_MS / 1000}s）`
        : err instanceof Error
          ? err.message
          : "未知网络错误";
    return { type: "error", error: message, status: 0 };
  } finally {
    clearTimeout(timer);
  }
}
