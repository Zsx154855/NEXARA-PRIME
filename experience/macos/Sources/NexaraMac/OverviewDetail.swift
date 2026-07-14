import SwiftUI

struct OverviewDetail: View {
    @EnvironmentObject private var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 4) {
                    Text("NEXARA PRIME")
                        .font(.largeTitle).fontWeight(.medium)
                        .foregroundColor(Color("Accent", bundle: .main))
                    Text("第一方主权智能体 · Runtime Truth")
                        .font(.subheadline).foregroundColor(.secondary)
                }.padding(.top, 32)

                // Stats
                if let ov = model.overview {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                        StatCard(title: "Missions", value: "\(ov.missionsTotal)", subtitle: "\(ov.missionsActive) 活跃 · \(ov.missionsCompleted) 完成", color: .blue)
                        StatCard(title: "Hermes 依赖", value: "\(ov.hermesDependency)", subtitle: "第一方主权", color: ov.hermesDependency == 0 ? .green : .red)
                        StatCard(title: "安全状态", value: ov.securityStatus, subtitle: "deny-by-default", color: ov.securityStatus == "CLOSED" ? .green : .orange)
                    }.padding(.horizontal)
                }

                // Mission list
                VStack(alignment: .leading, spacing: 12) {
                    Label("Missions", systemImage: "list.bullet.rectangle").font(.title3)
                    if model.missions.isEmpty {
                        Text("暂无 Mission — 前往 Composer 创建").foregroundColor(.secondary).padding()
                    } else {
                        ForEach(model.missions) { m in
                            MissionCard(mission: m)
                        }
                    }
                }.padding(.horizontal).frame(maxWidth: 700)

                Spacer()
            }
        }
    }
}

struct StatCard: View {
    let title: String; let value: String; let subtitle: String; let color: Color
    var body: some View {
        VStack(spacing: 8) {
            Text(value).font(.title).fontWeight(.semibold).foregroundColor(color)
            Text(title).font(.caption).foregroundColor(.secondary)
            Text(subtitle).font(.caption2).foregroundColor(.secondary).lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.controlBackgroundColor)))
    }
}

struct MissionCard: View {
    let mission: Mission
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(mission.objective).font(.body).lineLimit(2)
                HStack(spacing: 8) {
                    StateBadge(state: mission.state)
                    Text("R\(mission.riskLevel.rawValue.dropFirst())").font(.caption2).foregroundColor(.secondary)
                    Text(mission.missionId.prefix(8)).font(.caption2).foregroundColor(.secondary).monospaced()
                }
            }
            Spacer()
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.controlBackgroundColor)))
    }
}

struct StateBadge: View {
    let state: MissionState
    var body: some View {
        Text(state.rawValue)
            .font(.caption2).fontWeight(.medium)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(RoundedRectangle(cornerRadius: 4).fill(stateColor.opacity(0.15)))
            .foregroundColor(stateColor)
    }
    private var stateColor: Color {
        switch state {
        case .completed: .green
        case .running, .verifying: .blue
        case .blocked, .failed: .red
        case .approvalRequired: .orange
        default: .secondary
        }
    }
}
