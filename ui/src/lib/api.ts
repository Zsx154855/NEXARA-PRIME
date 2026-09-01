// ─── NEXARA PRIME API Client ───
// Real HTTP client that calls NEXARA Runtime API endpoints.
// Every method returns typed responses; errors are never silently caught.

import type {
  RuntimeOverview,
  MissionSnapshot,
  MissionListItem,
  HealthResponse,
  AdaptiveStatusResponse,
  AdaptiveMissionProfile,
  ApprovalRequest,
  EvidenceArtifact,
  MemoryRecord,
  MemoryStats,
  Event,
  RecoveryStateResponse,
  ReceiptChainResponse,
  ReceiptsResponse,
  MissionCreateRequest,
  ApprovalBody,
  SafeModeBody,
  ApiResult,
  ToolInvocation,
  RuntimeStats,
  ConversationDetail,
  ConversationSendRequest,
  ConversationSendResponse,
  ConversationAttachment,
  AttachablesResponse,
} from "../types";

// ── Configuration ──

interface ApiConfig {
  /** Base URL for the API, e.g. "" (same-origin) or "http://localhost:8080". */
  baseUrl: string;
  /** Fetch timeout in milliseconds. */
  timeoutMs: number;
}

const DEFAULT_CONFIG: ApiConfig = {
  baseUrl: "",
  // Provider agentic tool loops can exceed 30s; keep the client patient.
  timeoutMs: 120_000,
};

// ── Internal Helpers ──

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let _config: ApiConfig = { ...DEFAULT_CONFIG };

/** Configure the API client. Call once at app bootstrap. */
export function configureApi(overrides: Partial<ApiConfig>): void {
  _config = { ..._config, ...overrides };
}

function url(path: string): string {
  const base = _config.baseUrl.replace(/\/+$/, "");
  const cleaned = path.replace(/^\/?\/*/, "/");
  return `${base}${cleaned}`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), _config.timeoutMs);

  try {
    const headers: Record<string, string> = {};
    if (body !== undefined && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const res = await fetch(url(path), {
      method,
      headers,
      body:
        body instanceof FormData
          ? body
          : body !== undefined
            ? JSON.stringify(body)
            : undefined,
      signal: controller.signal,
    });

    // Try parsing JSON regardless of status; the backend returns JSON errors.
    let parsed: unknown;
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      parsed = await res.json();
    } else {
      const text = await res.text();
      parsed = text;
    }

    if (!res.ok) {
      const detail =
        parsed && typeof parsed === "object" && "detail" in parsed
          ? String((parsed as Record<string, unknown>).detail)
          : `HTTP ${res.status}`;
      throw new ApiError(detail, res.status, parsed);
    }

    return parsed as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(`Request timed out after ${_config.timeoutMs}ms`, 0);
    }
    throw new ApiError(
      err instanceof Error ? err.message : "Unknown network error",
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

/** Create a reactive ApiResult<T> wrapper — never silent fail. */
export async function apiResult<T>(
  promise: Promise<T>,
): Promise<ApiResult<T>> {
  try {
    const data = await promise;
    return { type: "success", data };
  } catch (err) {
    const apiErr = err as ApiError;
    return { type: "error", error: apiErr.message, status: apiErr.status };
  }
}

// ── Runtime / Health ──

/** GET /api/runtime/overview — full runtime dashboard snapshot. */
export function fetchOverview(): Promise<RuntimeOverview> {
  return request<RuntimeOverview>("GET", "/api/runtime/overview");
}

export function fetchOverviewSafe(): Promise<ApiResult<RuntimeOverview>> {
  return apiResult(fetchOverview());
}

/** GET /health — runtime health check. */
export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("GET", "/health");
}

export function fetchHealthSafe(): Promise<ApiResult<HealthResponse>> {
  return apiResult(fetchHealth());
}

/** GET /api/runtime/stats — aggregated runtime statistics (lightweight). */
export function fetchStats(): Promise<RuntimeStats> {
  return request<RuntimeStats>("GET", "/api/runtime/stats");
}

export function fetchStatsSafe(): Promise<ApiResult<RuntimeStats>> {
  return apiResult(fetchStats());
}

// ── Missions ──

/** GET /api/missions — list all missions. */
export function fetchMissions(): Promise<MissionListItem[]> {
  return request<MissionListItem[]>("GET", "/api/missions");
}

export function fetchMissionsSafe(): Promise<ApiResult<MissionListItem[]>> {
  return apiResult(fetchMissions());
}

/** GET /api/missions/:id — inspect a single mission snapshot. */
export function fetchMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>("GET", `/api/missions/${encodeURIComponent(missionId)}`);
}

export function fetchMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(fetchMission(missionId));
}

/** POST /api/missions — create a new mission. */
export function createMission(body: MissionCreateRequest): Promise<MissionSnapshot> {
  return request<MissionSnapshot>("POST", "/api/missions", body);
}

export function createMissionSafe(
  body: MissionCreateRequest,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(createMission(body));
}

/** POST /api/missions/:id/plan — plan an existing mission. */
export function planMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/plan`,
  );
}

export function planMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(planMission(missionId));
}

/** POST /api/missions/:id/approve — approve/reject a mission. */
export function approveMission(
  missionId: string,
  body: ApprovalBody,
): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/approve`,
    body,
  );
}

export function approveMissionSafe(
  missionId: string,
  body: ApprovalBody,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(approveMission(missionId, body));
}

/** POST /api/missions/:id/run — execute a mission. */
export function runMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/run`,
  );
}

export function runMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(runMission(missionId));
}

/** POST /api/missions/:id/pause — pause a mission. */
export function pauseMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/pause`,
  );
}

export function pauseMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(pauseMission(missionId));
}

/** POST /api/missions/:id/resume — resume a paused mission. */
export function resumeMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/resume`,
  );
}

export function resumeMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(resumeMission(missionId));
}

/** POST /api/missions/:id/rollback — roll back a mission. */
export function rollbackMission(missionId: string): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/rollback`,
  );
}

export function rollbackMissionSafe(
  missionId: string,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(rollbackMission(missionId));
}

/** POST /api/missions/:id/safe-mode — toggle safe mode on a mission. */
export function setSafeMode(
  missionId: string,
  body: SafeModeBody,
): Promise<MissionSnapshot> {
  return request<MissionSnapshot>(
    "POST",
    `/api/missions/${encodeURIComponent(missionId)}/safe-mode`,
    body,
  );
}

export function setSafeModeSafe(
  missionId: string,
  body: SafeModeBody,
): Promise<ApiResult<MissionSnapshot>> {
  return apiResult(setSafeMode(missionId, body));
}

// ── Approvals ──

/** GET /api/approvals — list approvals (optionally filtered by mission). */
export function fetchApprovals(
  missionId?: string,
): Promise<ApprovalRequest[]> {
  const params = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
  return request<ApprovalRequest[]>("GET", `/api/approvals${params}`);
}

export function fetchApprovalsSafe(
  missionId?: string,
): Promise<ApiResult<ApprovalRequest[]>> {
  return apiResult(fetchApprovals(missionId));
}

// ── Evidence ──

/** GET /api/evidence — list evidence (optionally filtered by mission). */
export function fetchEvidence(
  missionId?: string,
): Promise<EvidenceArtifact[]> {
  const params = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
  return request<EvidenceArtifact[]>("GET", `/api/evidence${params}`);
}

export function fetchEvidenceSafe(
  missionId?: string,
): Promise<ApiResult<EvidenceArtifact[]>> {
  return apiResult(fetchEvidence(missionId));
}

// ── Memory ──

/** GET /api/memory — list memory records (optionally filtered by mission). */
export function fetchMemory(
  missionId?: string,
): Promise<MemoryRecord[]> {
  const params = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
  return request<MemoryRecord[]>("GET", `/api/memory${params}`);
}

export function fetchMemorySafe(
  missionId?: string,
): Promise<ApiResult<MemoryRecord[]>> {
  return apiResult(fetchMemory(missionId));
}

/** GET /api/memory/stats — aggregated memory statistics grouped by layer. */
export function fetchMemoryStats(): Promise<MemoryStats> {
  return request<MemoryStats>("GET", "/api/memory/stats");
}

export function fetchMemoryStatsSafe(): Promise<ApiResult<MemoryStats>> {
  return apiResult(fetchMemoryStats());
}

/** GET /api/memory/candidates — list uncommitted memory candidates. */
export function fetchMemoryCandidates(
  missionId?: string,
): Promise<MemoryRecord[]> {
  const params = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
  return request<MemoryRecord[]>("GET", `/api/memory/candidates${params}`);
}

export function fetchMemoryCandidatesSafe(
  missionId?: string,
): Promise<ApiResult<MemoryRecord[]>> {
  return apiResult(fetchMemoryCandidates(missionId));
}

// ── Events ──

/** GET /api/events/:mission_id — replay events for a mission. */
export function fetchEvents(missionId: string): Promise<Event[]> {
  return request<Event[]>(
    "GET",
    `/api/events/${encodeURIComponent(missionId)}`,
  );
}

export function fetchEventsSafe(
  missionId: string,
): Promise<ApiResult<Event[]>> {
  return apiResult(fetchEvents(missionId));
}

// ── Recovery ──

/** POST /api/recovery/check — run recovery check. */
export function checkRecovery(): Promise<RecoveryStateResponse> {
  return request<RecoveryStateResponse>("POST", "/api/recovery/check");
}

export function checkRecoverySafe(): Promise<ApiResult<RecoveryStateResponse>> {
  return apiResult(checkRecovery());
}

// ── Adaptive Runtime ──

/** GET /adaptive/status — adaptive runtime status. */
export function fetchAdaptiveStatus(): Promise<AdaptiveStatusResponse> {
  return request<AdaptiveStatusResponse>("GET", "/adaptive/status");
}

export function fetchAdaptiveStatusSafe(): Promise<
  ApiResult<AdaptiveStatusResponse>
> {
  return apiResult(fetchAdaptiveStatus());
}

/** GET /adaptive/missions/:id — adaptive mission profile. */
export function fetchAdaptiveMission(
  missionId: string,
): Promise<AdaptiveMissionProfile> {
  return request<AdaptiveMissionProfile>(
    "GET",
    `/adaptive/missions/${encodeURIComponent(missionId)}`,
  );
}

export function fetchAdaptiveMissionSafe(
  missionId: string,
): Promise<ApiResult<AdaptiveMissionProfile>> {
  return apiResult(fetchAdaptiveMission(missionId));
}

/** GET /adaptive/missions/:id/explain — adaptive decision explanation. */
export function fetchAdaptiveExplain(
  missionId: string,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    "GET",
    `/adaptive/missions/${encodeURIComponent(missionId)}/explain`,
  );
}

export function fetchAdaptiveExplainSafe(
  missionId: string,
): Promise<ApiResult<Record<string, unknown>>> {
  return apiResult(fetchAdaptiveExplain(missionId));
}

/** GET /adaptive/missions/:id/budget — adaptive budget status. */
export function fetchAdaptiveBudget(
  missionId: string,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    "GET",
    `/adaptive/missions/${encodeURIComponent(missionId)}/budget`,
  );
}

export function fetchAdaptiveBudgetSafe(
  missionId: string,
): Promise<ApiResult<Record<string, unknown>>> {
  return apiResult(fetchAdaptiveBudget(missionId));
}

/** GET /adaptive/missions/:id/agents — adaptive agent assignments. */
export function fetchAdaptiveAgents(
  missionId: string,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    "GET",
    `/adaptive/missions/${encodeURIComponent(missionId)}/agents`,
  );
}

export function fetchAdaptiveAgentsSafe(
  missionId: string,
): Promise<ApiResult<Record<string, unknown>>> {
  return apiResult(fetchAdaptiveAgents(missionId));
}

/** GET /adaptive/missions/:id/routing — adaptive routing decisions. */
export function fetchAdaptiveRouting(
  missionId: string,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    "GET",
    `/adaptive/missions/${encodeURIComponent(missionId)}/routing`,
  );
}

export function fetchAdaptiveRoutingSafe(
  missionId: string,
): Promise<ApiResult<Record<string, unknown>>> {
  return apiResult(fetchAdaptiveRouting(missionId));
}

/** POST /adaptive/missions/:id/triage — trigger adaptive triage. */
export function triageAdaptiveMission(
  missionId: string,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    "POST",
    `/adaptive/missions/${encodeURIComponent(missionId)}/triage`,
  );
}

export function triageAdaptiveMissionSafe(
  missionId: string,
): Promise<ApiResult<Record<string, unknown>>> {
  return apiResult(triageAdaptiveMission(missionId));
}

// ── Receipts ──

export function fetchReceipts(missionId?: string): Promise<ReceiptsResponse | ReceiptChainResponse> {
  const params = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
  return request<ReceiptsResponse | ReceiptChainResponse>("GET", `/api/receipts${params}`);
}

export function fetchTools(missionId: string): Promise<ToolInvocation[]> {
  return request<ToolInvocation[]>(
    "GET",
    `/api/missions/${encodeURIComponent(missionId)}/tools`,
  );
}

// ── Conversation ──

/** POST /api/conversations — create a durable conversation. */
export function createConversation(title?: string): Promise<ConversationDetail> {
  return request<ConversationDetail>("POST", "/api/conversations", {
    title: title ?? null,
  });
}

export function createConversationSafe(
  title?: string,
): Promise<ApiResult<ConversationDetail>> {
  return apiResult(createConversation(title));
}

/** GET /api/conversations — list conversations with messages. */
export function fetchConversations(): Promise<ConversationDetail[]> {
  return request<ConversationDetail[]>("GET", "/api/conversations");
}

export function fetchConversationsSafe(): Promise<ApiResult<ConversationDetail[]>> {
  return apiResult(fetchConversations());
}

/** GET /api/conversations/:id — one conversation with messages. */
export function fetchConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return request<ConversationDetail>(
    "GET",
    `/api/conversations/${encodeURIComponent(conversationId)}`,
  );
}

export function fetchConversationSafe(
  conversationId: string,
): Promise<ApiResult<ConversationDetail>> {
  return apiResult(fetchConversation(conversationId));
}

/** POST /api/conversations/:id/messages — send one user turn, await assistant reply. */
export function sendConversationMessage(
  conversationId: string,
  body: ConversationSendRequest,
): Promise<ConversationSendResponse> {
  return request<ConversationSendResponse>(
    "POST",
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    body,
  );
}

export function sendConversationMessageSafe(
  conversationId: string,
  body: ConversationSendRequest,
): Promise<ApiResult<ConversationSendResponse>> {
  return apiResult(sendConversationMessage(conversationId, body));
}

/** POST /api/conversations/:id/close — close (read-only until reopened). */
export function closeConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return request<ConversationDetail>(
    "POST",
    `/api/conversations/${encodeURIComponent(conversationId)}/close`,
  );
}

export function closeConversationSafe(
  conversationId: string,
): Promise<ApiResult<ConversationDetail>> {
  return apiResult(closeConversation(conversationId));
}

/** POST /api/conversations/:id/reopen — reopen a closed conversation. */
export function reopenConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return request<ConversationDetail>(
    "POST",
    `/api/conversations/${encodeURIComponent(conversationId)}/reopen`,
  );
}

export function reopenConversationSafe(
  conversationId: string,
): Promise<ApiResult<ConversationDetail>> {
  return apiResult(reopenConversation(conversationId));
}

/** POST /api/conversations/:id/attachments — upload one file (multipart). */
export function uploadConversationAttachment(
  conversationId: string,
  file: File,
): Promise<ConversationAttachment> {
  const form = new FormData();
  form.append("file", file);
  return request<ConversationAttachment>(
    "POST",
    `/api/conversations/${encodeURIComponent(conversationId)}/attachments`,
    form,
  );
}

/** GET /api/conversations/:id/attachments — list uploaded attachments. */
export function fetchConversationAttachments(
  conversationId: string,
): Promise<ConversationAttachment[]> {
  return request<ConversationAttachment[]>(
    "GET",
    `/api/conversations/${encodeURIComponent(conversationId)}/attachments`,
  );
}

/** GET /api/attachables — plugins and connections that can be referenced from a message. */
export function fetchAttachables(): Promise<AttachablesResponse> {
  return request<AttachablesResponse>("GET", "/api/attachables");
}

/** Absolute URL used to render/download an uploaded attachment. */
export function attachmentContentUrl(
  conversationId: string,
  attachmentId: string,
): string {
  return url(
    `/api/conversations/${encodeURIComponent(conversationId)}/attachments/${encodeURIComponent(attachmentId)}/content`,
  );
}

// ── Class wrapper (convenience for React components) ──

export class NexaraAPI {
  getOverview() { return fetchOverview(); }
  getHealth() { return fetchHealth(); }
  getStats() { return fetchStats(); }
  getMissions() { return fetchMissions(); }
  getMission(id: string) { return fetchMission(id); }
  createMission(body: MissionCreateRequest) { return createMission(body); }
  planMission(id: string) { return planMission(id); }
  approveMission(id: string, body: ApprovalBody) { return approveMission(id, body); }
  runMission(id: string) { return runMission(id); }
  pauseMission(id: string) { return pauseMission(id); }
  resumeMission(id: string) { return resumeMission(id); }
  rollbackMission(id: string) { return rollbackMission(id); }
  setSafeMode(id: string, body: SafeModeBody) { return setSafeMode(id, body); }
  getApprovals(id?: string) { return fetchApprovals(id); }
  getEvidence(id?: string) { return fetchEvidence(id); }
  getMemory(id?: string) { return fetchMemory(id); }
  getMemoryStats() { return fetchMemoryStats(); }
  getEvents(id: string) { return fetchEvents(id); }
  fetchEvents(id: string) { return fetchEvents(id); }
  fetchTools(id: string) { return fetchTools(id); }
  getReceipts(id?: string) { return fetchReceipts(id); }
  checkRecovery() { return checkRecovery(); }
  getAdaptiveStatus() { return fetchAdaptiveStatus(); }
  createConversation(title?: string) { return createConversation(title); }
  getConversations() { return fetchConversations(); }
  getConversation(id: string) { return fetchConversation(id); }
  sendMessage(id: string, body: ConversationSendRequest) { return sendConversationMessage(id, body); }
  closeConversation(id: string) { return closeConversation(id); }
  reopenConversation(id: string) { return reopenConversation(id); }
  uploadAttachment(id: string, file: File) { return uploadConversationAttachment(id, file); }
  listAttachments(id: string) { return fetchConversationAttachments(id); }
  getAttachables() { return fetchAttachables(); }
}
