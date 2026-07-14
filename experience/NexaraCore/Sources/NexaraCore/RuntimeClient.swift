import Foundation

/// Connects to local NEXARA Runtime Truth API (default: http://127.0.0.1:8765)
public actor RuntimeClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder

    public init(host: String = "127.0.0.1", port: Int = 8765) {
        self.baseURL = URL(string: "http://\(host):\(port)")!
        self.session = URLSession(configuration: .default)
        self.decoder = JSONDecoder()
    }

    // MARK: - Health

    public func health() async throws -> [String: String] {
        let data = try await get("/health")
        return try decoder.decode([String: String].self, from: data)
    }

    // MARK: - Runtime Overview

    public func overview() async throws -> RuntimeOverview {
        let data = try await get("/api/runtime/overview")
        return try decoder.decode(RuntimeOverview.self, from: data)
    }

    // MARK: - Missions

    public func listMissions() async throws -> [Mission] {
        let data = try await get("/api/missions")
        return try decoder.decode([Mission].self, from: data)
    }

    public func getMission(_ id: String) async throws -> Mission {
        let data = try await get("/api/missions/\(id)")
        return try decoder.decode(Mission.self, from: data)
    }

    public func createMission(objective: String, sourceDir: String? = nil) async throws -> Mission {
        var body: [String: String] = ["objective": objective]
        if let dir = sourceDir { body["source_dir"] = dir }
        let data = try await post("/api/missions", body: body)
        return try decoder.decode(Mission.self, from: data)
    }

    // MARK: - Actions

    public func planMission(_ id: String) async throws -> Mission {
        let data = try await post("/api/missions/\(id)/plan", body: [:])
        return try decoder.decode(Mission.self, from: data)
    }

    public func approveMission(_ id: String, approved: Bool) async throws -> Mission {
        let body: [String: Any] = ["approved": approved, "decision": approved ? "approve_mission" : "reject"]
        let jsonData = try JSONSerialization.data(withJSONObject: body)
        let data = try await post("/api/missions/\(id)/approve", rawBody: jsonData)
        return try decoder.decode(Mission.self, from: data)
    }

    public func runMission(_ id: String) async throws -> Mission {
        let data = try await post("/api/missions/\(id)/run", body: [:])
        return try decoder.decode(Mission.self, from: data)
    }

    public func pauseMission(_ id: String) async throws -> Mission {
        let data = try await post("/api/missions/\(id)/pause", body: [:])
        return try decoder.decode(Mission.self, from: data)
    }

    // MARK: - HTTP helpers

    private func get(_ path: String) async throws -> Data {
        let url = baseURL.appendingPathComponent(path)
        let (data, response) = try await session.data(from: url)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            throw RuntimeError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    private func post(_ path: String, body: [String: Any]) async throws -> Data {
        let jsonData = try JSONSerialization.data(withJSONObject: body)
        return try await post(path, rawBody: jsonData)
    }

    private func post(_ path: String, rawBody: Data) async throws -> Data {
        let url = baseURL.appendingPathComponent(path)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = rawBody
        let (data, response) = try await session.data(for: req)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            throw RuntimeError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }
}

public enum RuntimeError: Error, LocalizedError {
    case http(Int, String)
    case disconnected

    public var errorDescription: String? {
        switch self {
        case .http(let code, let body): "HTTP \(code): \(body)"
        case .disconnected: "Runtime 未连接 — 请确认 NEXARA 服务已启动"
        }
    }
}
