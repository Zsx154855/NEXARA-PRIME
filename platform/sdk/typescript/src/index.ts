/** NEXARA PRIME TypeScript SDK — Runtime Truth API client */

export interface MissionSpec {
  mission_id: string;
  title: string;
  objective: string;
  state: MissionState;
  risk_level: RiskLevel;
  boundaries: string[];
  constraints: string[];
  created_at: string;
}

export type MissionState =
  | "DRAFT" | "CONTEXT_READY" | "CONTRACTED" | "PLANNED"
  | "SIMULATED" | "APPROVAL_REQUIRED" | "READY" | "RUNNING"
  | "VERIFYING" | "COMPLETED" | "PAUSED" | "BLOCKED"
  | "FAILED" | "ROLLING_BACK" | "ROLLED_BACK" | "CANCELLED";

export type RiskLevel = "R0" | "R1" | "R2" | "R3" | "R4";

export interface Mission {
  mission_id: string;
  spec: MissionSpec;
}

export interface RuntimeOverview {
  system: {
    name: string;
    mode: string;
    healthy: boolean;
    human_control: boolean;
    mock_default: boolean;
  };
  missions: Array<Record<string, unknown>>;
  approvals: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  tools: Array<Record<string, unknown>>;
  capabilities: Array<Record<string, unknown>>;
}

export interface PluginManifest {
  plugin_id: string;
  name: string;
  version: string;
  capabilities: string[];
  permissions: string[];
  network_scope: string[];
  secret_scope: string[];
  risk_level: RiskLevel;
  signature_required: boolean;
  isolation: "process" | "sandbox" | "none";
}

export class NexaraClient {
  private baseURL: string;

  constructor(host = "127.0.0.1", port = 8765) {
    this.baseURL = `http://${host}:${port}`;
  }

  async health(): Promise<Record<string, unknown>> {
    return this.get("/health");
  }

  async overview(): Promise<RuntimeOverview> {
    return this.get("/api/runtime/overview");
  }

  async listMissions(): Promise<Mission[]> {
    return this.get("/api/missions");
  }

  async getMission(id: string): Promise<Mission> {
    return this.get(`/api/missions/${id}`);
  }

  async createMission(objective: string): Promise<Mission> {
    return this.post("/api/missions", { objective });
  }

  async planMission(id: string): Promise<Mission> {
    return this.post(`/api/missions/${id}/plan`, {});
  }

  async approveMission(id: string, approved = true): Promise<Mission> {
    return this.post(`/api/missions/${id}/approve`, {
      approved,
      decision: approved ? "approve_mission" : "reject",
    });
  }

  async runMission(id: string): Promise<Mission> {
    return this.post(`/api/missions/${id}/run`, {});
  }

  async pauseMission(id: string): Promise<Mission> {
    return this.post(`/api/missions/${id}/pause`, {});
  }

  private async get<T>(path: string): Promise<T> {
    const r = await fetch(`${this.baseURL}${path}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    return r.json();
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const r = await fetch(`${this.baseURL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    return r.json();
  }
}
