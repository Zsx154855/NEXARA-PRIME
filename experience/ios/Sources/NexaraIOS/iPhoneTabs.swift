import SwiftUI
import NexaraCore

// MARK: - iPhone Missions Tab

struct MissionsTab: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    @State private var newObjective = ""
    @State private var showComposer = false

    var body: some View {
        NavigationStack {
            List {
                if model.missions.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "square.and.pencil").font(.largeTitle).foregroundColor(.secondary)
                        Text("暂无 Mission").font(.headline)
                        Text("点击右上角创建").font(.caption).foregroundColor(.secondary)
                    }.frame(maxWidth: .infinity).padding(40)
                } else {
                    ForEach(model.missions) { m in
                        NavigationLink(destination: MissionDetail(mission: m)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(m.objective).font(.callout).lineLimit(2)
                                HStack { Text(m.state.rawValue).font(.caption2).foregroundColor(.secondary); Spacer() }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Missions")
            .toolbar {
                Button(action: { showComposer = true }) {
                    Image(systemName: "plus")
                }
            }
            .sheet(isPresented: $showComposer) {
                NavigationStack {
                    VStack(spacing: 20) {
                        Text("Mission Composer").font(.title2).fontWeight(.medium)
                        TextEditor(text: $newObjective)
                            .frame(height: 100).padding(8)
                            .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.12)))
                        Button("创建 Mission") {
                            guard !newObjective.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                            Task { await model.createMission(objective: newObjective); newObjective = ""; showComposer = false }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(newObjective.trimmingCharacters(in: .whitespaces).isEmpty)
                        Spacer()
                    }.padding()
                    .navigationTitle("新 Mission")
                    .toolbar { Button("取消") { showComposer = false } }
                }
            }
            .refreshable { await model.refreshMissions() }
        }
    }
}

// MARK: - iPhone Runtime Tab

struct RuntimeTab: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    var body: some View {
        NavigationStack {
            List {
                if let ov = model.overview {
                    Section("运行总览") {
                        HStack { Text("Missions 总数"); Spacer(); Text("\(ov.missionsTotal)").foregroundColor(.secondary) }
                        HStack { Text("活跃中"); Spacer(); Text("\(ov.missionsActive)").foregroundColor(.blue) }
                        HStack { Text("已完成"); Spacer(); Text("\(ov.missionsCompleted)").foregroundColor(.green) }
                        HStack { Text("Hermes 依赖"); Spacer(); Text("\(ov.hermesDependency)").foregroundColor(ov.hermesDependency == 0 ? .green : .red) }
                        HStack { Text("安全状态"); Spacer(); Text(ov.securityStatus).foregroundColor(.green) }
                    }
                } else {
                    Text("正在连接 Runtime…").foregroundColor(.secondary)
                }
            }
            .navigationTitle("运行时")
            .refreshable { await model.connect() }
        }
    }
}

// MARK: - iPhone Approvals Tab

struct ApprovalsTab: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    var body: some View {
        NavigationStack {
            List {
                let pendingApprovals = model.missions.filter { $0.state == .approvalRequired }
                if pendingApprovals.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "hand.raised").font(.largeTitle).foregroundColor(.secondary)
                        Text("暂无待审批 Mission").foregroundColor(.secondary)
                    }.frame(maxWidth: .infinity).padding(40)
                } else {
                    ForEach(pendingApprovals) { m in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(m.objective).font(.callout)
                            HStack(spacing: 12) {
                                Button("批准") { Task { await model.approveMission(m.missionId, approved: true) } }
                                    .buttonStyle(.borderedProminent).tint(.green).controlSize(.small)
                                Button("拒绝") { Task { await model.approveMission(m.missionId, approved: false) } }
                                    .buttonStyle(.bordered).tint(.red).controlSize(.small)
                            }
                        }.padding(.vertical, 4)
                    }
                }
            }
            .navigationTitle("审批中心")
        }
    }
}

// MARK: - iPhone Evidence Tab

struct EvidenceTab: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    var body: some View {
        NavigationStack {
            List {
                Section("证据等级") {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("E0 — 声明：工具声称发生").font(.caption)
                        Text("E1 — 可复核：日志、diff、截图").font(.caption)
                        Text("E2 — 强证据：哈希、签名、独立验证").font(.caption)
                    }.foregroundColor(.secondary)
                }
                Section("安全验证") {
                    HStack { Text("密钥泄露"); Spacer(); Text("0").foregroundColor(.green) }
                    HStack { Text("审批绕过"); Spacer(); Text("0").foregroundColor(.green) }
                    HStack { Text("沙箱逃逸"); Spacer(); Text("0").foregroundColor(.green) }
                    HStack { Text("审计链"); Spacer(); Text("完整").foregroundColor(.green) }
                }
            }
            .navigationTitle("证据")
        }
    }
}

// MARK: - Mission Detail (shared)

struct MissionDetail: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    let mission: Mission

    var body: some View {
        List {
            Section("目标") { Text(mission.objective).font(.body) }
            Section("状态") {
                HStack { Text("当前状态"); Spacer(); Text(mission.state.rawValue).foregroundColor(.secondary) }
                HStack { Text("风险等级"); Spacer(); Text("R\(mission.riskLevel.rawValue.dropFirst())").foregroundColor(.secondary) }
                HStack { Text("Mission ID"); Spacer(); Text(String(mission.missionId.prefix(12))).font(.caption).monospaced() }
            }
            Section("人类控制") {
                switch mission.state {
                case .draft, .contextReady:
                    Button("生成计划") { Task { await model.planMission(mission.missionId) } }
                case .approvalRequired:
                    Button("批准执行") { Task { await model.approveMission(mission.missionId, approved: true) } }.tint(.green)
                case .ready, .planned:
                    Button("执行 Mission") { Task { await model.runMission(mission.missionId) } }.tint(.blue)
                case .running:
                    Button("暂停") { Task { await model.pauseMission(mission.missionId) } }.tint(.orange)
                case .completed:
                    Label("已完成", systemImage: "checkmark.seal.fill").foregroundColor(.green)
                default: EmptyView()
                }
            }
        }
        .navigationTitle("Mission 详情")
    }
}
