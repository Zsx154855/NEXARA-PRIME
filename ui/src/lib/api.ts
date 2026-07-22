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
  Event,
  RecoveryStateResponse,
  ReceiptChainResponse,
  ReceiptsResponse,
  MissionCreateRequest,
  ApprovalBody,
  SafeModeBody,
  ApiResult,
  ToolInvocation,
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
  timeoutMs: 30_000,
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

// ── Class wrapper (convenience for React components) ──

export class NexaraAPI {
  getOverview() { return fetchOverview(); }
  getHealth() { return fetchHealth(); }
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
  getEvents(id: string) { return fetchEvents(id); }
  fetchEvents(id: string) { return fetchEvents(id); }
  fetchTools(id: string) { return fetchTools(id); }
  getReceipts(id?: string) { return fetchReceipts(id); }
  checkRecovery() { return checkRecovery(); }
  getAdaptiveStatus() { return fetchAdaptiveStatus(); }
}
