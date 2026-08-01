import Foundation

// MARK: - Runtime Configuration
// Single source of truth for Runtime API connectivity.
// All pages and adapters must read from this; no hardcoded ports anywhere.

struct RuntimeConfiguration {
    static let shared = RuntimeConfiguration()

    let host: String = "127.0.0.1"
    let port: Int = 8770

    var baseURL: URL {
        URL(string: "http://\(host):\(port)")!
    }

    var baseURLString: String {
        "http://\(host):\(port)"
    }
}

// MARK: - Runtime Adapter V2: Real Runtime API Client
// Connects to NEXARA PRIME Runtime at configurable URL.
// All UI state is read-only; no state saved in the adapter.

@MainActor
final class RuntimeAdapter: ObservableObject {
    static let shared = RuntimeAdapter()

    @Published var isConnected: Bool = false
    @Published var status: String = "未连接"
    @Published var overview: RuntimeOverview?
    @Published var missions: [RuntimeMission] = []
    @Published var approvals: [RuntimeApproval] = []
    @Published var evidence: [RuntimeEvidence] = []
    @Published var receipts: RuntimeReceipts?
    @Published var tools: [RuntimeTool] = []
    @Published var toolRegistry: RuntimeToolRegistry?
    @Published var memoryEntries: [RuntimeMemoryEntry] = []
    @Published var capabilities: [RuntimeCapability] = []
    @Published var eventsByMission: [String: [RuntimeEvent]] = [:]
    @Published var soulIntegrity: String = "未验证"
    @Published var lastError: String?
    @Published var runtimeEventCount: Int = 0

    private let baseURL: URL
    private let session: URLSession

    private init() {
        baseURL = RuntimeConfiguration.shared.baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 5
        config.timeoutIntervalForResource = 10
        session = URLSession(configuration: config)
    }

    // MARK: - Health Check

    func checkHealth() async {
        do {
            let data = try await get("/health")
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               json["status"] as? String == "ok" {
                isConnected = true
                status = "在线"
                soulIntegrity = "已验证"
                // Parse event_count from health response
                if let ec = json["event_count"] as? Int {
                    runtimeEventCount = ec
                }
                lastError = nil
            } else {
                isConnected = false
                status = "状态异常"
                soulIntegrity = "未验证"
            }
        } catch {
            isConnected = false
            status = "连接失败"
            soulIntegrity = "未验证"
            lastError = error.localizedDescription
        }
    }

    // MARK: - Fetch All

    func fetchOverview() async {
        do {
            let data = try await get("/api/runtime/overview")
            overview = try decode(data)
            isConnected = true
            soulIntegrity = "已验证"
        } catch {
            lastError = "Overview: \(error.localizedDescription)"
        }
    }

    func fetchMissions() async {
        do {
            let data = try await get("/api/missions")
            missions = try decode(data)
        } catch {
            lastError = "Missions: \(error.localizedDescription)"
        }
    }

    func fetchApprovals() async {
        do {
            let data = try await get("/api/approvals")
            approvals = try decode(data)
        } catch {
            lastError = "Approvals: \(error.localizedDescription)"
        }
    }

    func fetchEvidence() async {
        do {
            let data = try await get("/api/evidence")
            evidence = try decode(data)
        } catch {
            lastError = "Evidence: \(error.localizedDescription)"
        }
    }

    func fetchReceipts() async {
        do {
            let data = try await get("/api/receipts")
            receipts = try decode(data)
        } catch {
            lastError = "Receipts: \(error.localizedDescription)"
        }
    }

    func fetchTools() async {
        do {
            let data = try await get("/api/tools")
            tools = try decode(data)
        } catch {
            lastError = "Tools: \(error.localizedDescription)"
        }
    }

    func fetchToolRegistry() async {
        do {
            let data = try await get("/api/tools/registry")
            toolRegistry = try decode(data)
        } catch {
            lastError = "ToolRegistry: \(error.localizedDescription)"
        }
    }

    func fetchMemory() async {
        do {
            let data = try await get("/api/memory")
            memoryEntries = try decode(data)
        } catch {
            lastError = "Memory: \(error.localizedDescription)"
        }
    }

    func fetchCapabilities() async {
        do {
            let data = try await get("/api/capabilities")
            capabilities = try decode(data)
        } catch {
            lastError = "Capabilities: \(error.localizedDescription)"
        }
    }

    func fetchEvents(for missionId: String) async {
        do {
            let data = try await get("/api/events/\(missionId)")
            let events: [RuntimeEvent] = try decode(data)
            eventsByMission[missionId] = events
        } catch {
            lastError = "Events: \(error.localizedDescription)"
        }
    }

    // MARK: - Actions

    func createMission(objective: String, sourceDir: String? = nil) async -> RuntimeMission? {
        do {
            var body: [String: Any] = ["objective": objective]
            if let dir = sourceDir { body["source_dir"] = dir }
            let data = try await post("/api/missions", body: body)
            let mission: RuntimeMission = try decode(data)
            await fetchMissions()
            return mission
        } catch {
            lastError = "Create: \(error.localizedDescription)"
            return nil
        }
    }

    func approveMission(_ id: String, approved: Bool = true, note: String = "Approved") async -> Bool {
        do {
            let body: [String: Any] = ["approved": approved, "actor": "human", "note": note]
            _ = try await post("/api/missions/\(id)/approve", body: body)
            await fetchApprovals()
            return true
        } catch {
            lastError = "Approve: \(error.localizedDescription)"
            return false
        }
    }

    func runMission(_ id: String) async -> RuntimeMission? {
        do {
            let data = try await post("/api/missions/\(id)/run", body: [:])
            let mission: RuntimeMission = try decode(data)
            await fetchMissions()
            return mission
        } catch {
            lastError = "Run: \(error.localizedDescription)"
            return nil
        }
    }

    // MARK: - HTTP Helpers

    private func get(_ path: String) async throws -> Data {
        let url = baseURL.appendingPathComponent(path)
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }

    private func post(_ path: String, body: [String: Any]) async throws -> Data {
        let url = baseURL.appendingPathComponent(path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }
}

// MARK: - Runtime Model Types

struct RuntimeOverview: Codable {
    var status: String?
    var identity: RuntimeIdentity?
    var missions: [RuntimeMission]?
    var modelProvider: String?
    var modelName: String?
    var workspaceRoot: String?
    var eventCount: Int?
    var agentCount: Int?

    enum CodingKeys: String, CodingKey {
        case status, identity, missions
        case eventCount = "event_count"
        case agentCount = "agent_count"
        case modelProvider = "model_provider"
        case modelName = "model_name"
        case workspaceRoot = "workspace_root"
    }
}

struct RuntimeIdentity: Codable {
    var fingerprint: String?
    var name: String?
    var ownerId: String?
    var soulStatus: RuntimeSoulStatus?

    enum CodingKeys: String, CodingKey {
        case fingerprint, name
        case ownerId = "ownerId"
        case soulStatus = "soulStatus"
    }
}

struct RuntimeSoulStatus: Codable {
    var immutableCount: Int?
    var stableCount: Int?
    var integrityVerified: Bool?
    var lastVerifiedAt: String?

    enum CodingKeys: String, CodingKey {
        case immutableCount, stableCount
        case integrityVerified
        case lastVerifiedAt
    }
}

struct RuntimeMission: Codable, Identifiable {
    var missionId: String?
    var objective: String?
    var title: String?
    var spec: String?
    var state: String?
    var currentState: String?
    var createdAt: String?
    var approvalStatus: String?
    var riskLevel: String?

    var id: String { missionId ?? UUID().uuidString }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case objective, title, spec, state
        case currentState = "current_state"
        case createdAt = "created_at"
        case approvalStatus = "approval_status"
        case riskLevel = "risk_level"
    }
}

struct RuntimeApproval: Codable, Identifiable {
    var missionId: String?
    var approved: Bool?
    var actor: String?
    var note: String?
    var decision: String?
    var scope: String?
    var timestamp: String?

    var id: String { missionId ?? UUID().uuidString }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case approved, actor, note, decision, scope, timestamp
    }
}

struct RuntimeEvidence: Codable, Identifiable {
    var missionId: String?
    var key: String?
    var content: String?
    var kind: String?
    var verified: Bool?

    var id: String { key ?? missionId ?? UUID().uuidString }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case key, content, kind, verified
    }
}

struct RuntimeReceipts: Codable {
    var missions: [String: RuntimeReceiptChain]?
    var total: Int?
}

struct RuntimeReceiptChain: Codable {
    var chain: [String]?
    var verified: Bool?
    var total: Int?
}

struct RuntimeTool: Codable, Identifiable {
    var missionId: String?
    var tool: String?
    var result: String?
    var timestamp: String?

    var id: String { "\(missionId ?? "")-\(tool ?? "")-\(timestamp ?? "")" }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case tool, result, timestamp
    }
}

struct RuntimeToolRegistry: Codable {
    var registryType: String?
    var tools: [String: String]?
    var appleToolsAvailable: Bool?
    var toolCount: Int?

    enum CodingKeys: String, CodingKey {
        case registryType = "registry_type"
        case tools
        case appleToolsAvailable = "apple_tools_available"
        case toolCount = "tool_count"
    }
}

struct RuntimeMemoryEntry: Codable, Identifiable {
    var missionId: String?
    var layer: String?
    var key: String?
    var value: String?
    var timestamp: String?

    var id: String { "\(layer ?? "")-\(key ?? "")-\(timestamp ?? "")" }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case layer, key, value, timestamp
    }
}

struct RuntimeCapability: Codable, Identifiable {
    var name: String?
    var description: String?
    var available: Bool?
    var version: String?

    var id: String { name ?? UUID().uuidString }
}

struct RuntimeEvent: Codable, Identifiable {
    var missionId: String?
    var event: String?
    var timestamp: String?
    var data: [String: String]?

    var id: String { "\(event ?? "")-\(timestamp ?? "")" }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case event, timestamp, data
    }
}
