import Foundation
import Combine

@MainActor
final class RuntimeViewModel: ObservableObject {
    @Published var projection = RuntimeProjection(connection: .disconnected)
    @Published var newObjective = ""
    @Published var selectedRisk = "R2"
    @Published var selectedScreen = "home"
    @Published var loadingMessage = ""

    private var timer: Timer?
    private let apiURL = URL(string: "http://127.0.0.1:8420")!

    func connect() async {
        projection.connection = .connecting
        loadingMessage = "正在连接 NEXARA Runtime..."
        do {
            let (data, _) = try await URLSession.shared.data(from: apiURL.appendingPathComponent("/api/overview"))
            if let p = try? JSONDecoder().decode(RuntimeProjection.self, from: data) {
                projection = p
                projection.connection = .connected
                loadingMessage = ""
                startPolling()
            }
        } catch {
            projection.connection = .disconnected
            loadingMessage = "无法连接到 NEXARA Runtime"
        }
    }

    private func startPolling() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
    }

    func refresh() async {
        guard let url = URL(string: "http://127.0.0.1:8420/api/overview") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if var p = try? JSONDecoder().decode(RuntimeProjection.self, from: data) {
                p.connection = .connected
                projection = p
            }
        } catch {
            projection.connection = .degraded
        }
    }

    func stop() { timer?.invalidate() }
}

#if DEBUG
extension RuntimeViewModel {
    static var preview: RuntimeViewModel {
        let vm = RuntimeViewModel()
        vm.projection = RuntimeProjection(
            identity: IdentitySnapshot(
                fingerprint: "a1b2c3d4e5f6",
                name: "NEXARA PRIME",
                ownerId: "shunxin.zhang",
                soulStatus: SoulIntegrity(immutableCount: 4, stableCount: 12, integrityVerified: true, lastVerifiedAt: "2026-07-30T17:00:00Z"),
                createdAt: "2026-07-01T00:00:00Z"
            ),
            missions: [
                MissionSummary(missionId: "m-001", objective: "系统健康检查", state: "COMPLETED", riskLevel: "R2", createdAt: "2026-07-30T16:00:00Z"),
                MissionSummary(missionId: "m-002", objective: "First Contact 对话", state: "COMPLETED", riskLevel: "R1", createdAt: "2026-07-30T16:30:00Z"),
            ],
            approvals: [
                ApprovalRequest(approvalId: "a-001", missionId: "m-003", riskLevel: "R3", scope: ["file_write_report"], status: "pending", createdAt: "2026-07-30T17:00:00Z"),
            ],
            evidence: [
                EvidenceSummary(evidenceId: "ev-001", missionId: "m-001", sha256: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890", verified: true, createdAt: "2026-07-30T16:05:00Z"),
            ],
            memory: [
                MemoryCategory(category: "Identity", count: 4, records: [
                    MemoryRecord(memoryId: "mem-001", key: "identity", kind: "identity", sourceEvidenceId: nil, content: "NEXARA PRIME", deletable: false, createdAt: "2026-07-01T00:00:00Z"),
                ]),
            ],
            health: RuntimeHealth(uptime: 3600, providerStatus: ["deepseek": "healthy"], circuitBreaker: ["deepseek": false], activeMissions: 1, lastRestartAt: "2026-07-30T10:00:00Z"),
            connection: .connected
        )
        return vm
    }
}
#endif
