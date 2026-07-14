import NexaraCore
import SwiftUI

struct WorkspaceDetail: View {
    @EnvironmentObject private var model: RuntimeViewModel

    var body: some View {
        if let mission = model.selectedMission {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Header
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(mission.objective).font(.title2).fontWeight(.medium)
                            HStack(spacing: 12) {
                                StateBadge(state: mission.state)
                                Text("ID: \(mission.missionId.prefix(12))…").font(.caption).monospaced().foregroundColor(.secondary)
                            }
                        }
                        Spacer()
                        // Actions
                        HStack(spacing: 8) {
                            actionButtons(for: mission)
                        }
                    }.padding(.top, 24)

                    Divider()

                    // Pipeline
                    pipelineView(for: mission)

                    // Evidence
                    if mission.state == .completed {
                        evidenceView
                    }
                }
                .padding(.horizontal, 32)
            }
        } else {
            VStack(spacing: 12) {
                Image(systemName: "rectangle.split.2x1").font(.largeTitle).foregroundColor(.secondary)
                Text("选择左侧 Mission 查看工作区").foregroundColor(.secondary)
            }.padding(60)
        }
    }

    @ViewBuilder
    private func actionButtons(for mission: Mission) -> some View {
        switch mission.state {
        case .draft, .contextReady:
            Button("生成计划") { Task { await model.planMission(mission.missionId) } }
                .buttonStyle(.borderedProminent)
        case .approvalRequired:
            HStack {
                Button("批准") { Task { await model.approveMission(mission.missionId, approved: true) } }
                    .buttonStyle(.borderedProminent).tint(.green)
                Button("拒绝") { Task { await model.approveMission(mission.missionId, approved: false) } }
                    .buttonStyle(.bordered).tint(.red)
            }
        case .ready, .planned:
            Button("执行") { Task { await model.runMission(mission.missionId) } }
                .buttonStyle(.borderedProminent).tint(.blue)
        case .running:
            Button("暂停") { Task { await model.pauseMission(mission.missionId) } }
                .buttonStyle(.bordered).tint(.orange)
        case .completed:
            Label("已完成", systemImage: "checkmark.seal.fill").foregroundColor(.green)
        case .blocked:
            Label("已阻断", systemImage: "xmark.octagon.fill").foregroundColor(.red)
        default:
            EmptyView()
        }
    }

    /// Check if a mission state is active (past a stage boundary).
    private func isActive(_ state: MissionState, in allowedStates: Set<MissionState>) -> Bool {
        allowedStates.contains(state)
    }

    @ViewBuilder
    private func pipelineView(for mission: Mission) -> some View {
        let contractedStates: Set<MissionState> = [.contracted, .planned, .ready, .running, .verifying, .completed]
        let plannedStates: Set<MissionState> = [.planned, .ready, .running, .verifying, .completed]
        let executingStates: Set<MissionState> = [.running, .verifying, .completed]
        let verifyingStates: Set<MissionState> = [.verifying, .completed]
        let completedStates: Set<MissionState> = [.completed]

        VStack(alignment: .leading, spacing: 8) {
            Label("执行路径", systemImage: "arrow.triangle.branch").font(.title3)
            let stages: [(String, Bool)] = [
                ("意图 Intent", true),
                ("上下文 Context", mission.state != .draft),
                ("合约 Contract", isActive(mission.state, in: contractedStates)),
                ("计划 Plan", isActive(mission.state, in: plannedStates)),
                ("执行 Execute", isActive(mission.state, in: executingStates)),
                ("验证 Verify", isActive(mission.state, in: verifyingStates)),
                ("证据 Evidence", isActive(mission.state, in: completedStates)),
                ("记忆 Memory", isActive(mission.state, in: completedStates)),
            ]
            ForEach(stages, id: \.0) { stage, active in
                HStack(spacing: 10) {
                    Image(systemName: active ? "checkmark.circle.fill" : "circle")
                        .foregroundColor(active ? .green : .secondary)
                    Text(stage).font(.callout)
                        .foregroundColor(active ? .primary : .secondary)
                    if active {
                        Rectangle().fill(Color.green.opacity(0.3)).frame(height: 2)
                    }
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 10).fill(Color(.controlBackgroundColor)))
    }

    private var evidenceView: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("证据与回执", systemImage: "checkmark.shield").font(.title3)
            Text("E1/E2 证据已生成。审计链完整。").font(.callout).foregroundColor(.green)
            Text("Trace ID 可通过 Runtime Truth API 查询完整执行记录。").font(.caption).foregroundColor(.secondary)
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.green.opacity(0.05)))
    }
}
