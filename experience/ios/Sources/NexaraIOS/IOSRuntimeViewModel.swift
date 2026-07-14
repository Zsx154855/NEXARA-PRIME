import SwiftUI
import NexaraCore

@MainActor
final class IOSRuntimeViewModel: ObservableObject {
    private let client = RuntimeClient()
    @Published var overview: RuntimeOverview?
    @Published var missions: [Mission] = []
    @Published var selectedMission: Mission?
    @Published var connectionStatus: ConnectionStatus = .disconnected
    @Published var errorMessage: String?

    enum ConnectionStatus { case connected, disconnected, error }

    func connect() async {
        do {
            overview = try await client.overview()
            missions = try await client.listMissions()
            connectionStatus = .connected
            errorMessage = nil
        } catch {
            connectionStatus = .error
            errorMessage = error.localizedDescription
        }
    }

    func createMission(objective: String) async {
        do {
            let m = try await client.createMission(objective: objective, sourceDir: nil)
            missions.insert(m, at: 0)
            selectedMission = m
        } catch { errorMessage = error.localizedDescription }
    }

    func refreshMissions() async {
        do {
            missions = try await client.listMissions()
        } catch { errorMessage = error.localizedDescription }
    }

    func planMission(_ id: String) async {
        do { selectedMission = try await client.planMission(id); await refreshMissions() }
        catch { errorMessage = error.localizedDescription }
    }
    func runMission(_ id: String) async {
        do { selectedMission = try await client.runMission(id); await refreshMissions() }
        catch { errorMessage = error.localizedDescription }
    }
    func pauseMission(_ id: String) async {
        do { selectedMission = try await client.pauseMission(id); await refreshMissions() }
        catch { errorMessage = error.localizedDescription }
    }
    func approveMission(_ id: String, approved: Bool) async {
        do { selectedMission = try await client.approveMission(id, approved: approved); await refreshMissions() }
        catch { errorMessage = error.localizedDescription }
    }
}
