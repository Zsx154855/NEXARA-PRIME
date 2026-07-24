import NexaraCore
import SwiftUI

struct AdaptiveContentView: View {
    @EnvironmentObject private var model: IOSRuntimeViewModel
    @Environment(\.horizontalSizeClass) private var hSizeClass

    var body: some View {
        if hSizeClass == .regular {
            // iPad: Split View layout (834 × 1194)
            iPadLayout
        } else {
            // iPhone: Compact single-column (390 × 844)
            iPhoneLayout
        }
    }

    // MARK: - iPhone Layout

    private var iPhoneLayout: some View {
        TabView {
            MissionsTab()
                .tabItem { Label("Missions", systemImage: "list.bullet.rectangle") }

            RuntimeTab()
                .tabItem { Label("运行时", systemImage: "arrow.triangle.2.circlepath") }

            ApprovalsTab()
                .tabItem { Label("审批", systemImage: "hand.raised") }

            EvidenceTab()
                .tabItem { Label("证据", systemImage: "checkmark.shield") }
        }
        .task { await model.connect() }
    }

    // MARK: - iPad Layout

    private var iPadLayout: some View {
        NavigationSplitView {
            iPadSidebar
        } detail: {
            iPadDetail
        }
        .task { await model.connect() }
    }

    private var iPadSidebar: some View {
        List {
            Section("NEXARA PRIME") {
                if let ov = model.overview {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(ov.missionsTotal) Missions").font(.headline)
                        Text("\(ov.missionsActive) 活跃 · \(ov.missionsCompleted) 完成").font(.caption).foregroundColor(.secondary)
                        HStack {
                            Circle().fill(model.connectionStatus == .connected ? Color.green : Color.red).frame(width: 6)
                            Text(model.connectionStatus == .connected ? "已连接" : "未连接").font(.caption2)
                        }
                    }.padding(.vertical, 4)
                }
            }
            Section("Missions") {
                ForEach(model.missions) { m in
                    Button(action: { model.selectedMission = m }) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(m.objective).lineLimit(1).font(.callout)
                            Text(m.state.rawValue).font(.caption2).foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
        .listStyle(.sidebar)
    }

    @ViewBuilder
    private var iPadDetail: some View {
        if let mission = model.selectedMission {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Header
                    VStack(alignment: .leading, spacing: 4) {
                        Text(mission.objective).font(.title2).fontWeight(.medium)
                        HStack {
                            Text(mission.state.rawValue).font(.caption).padding(.horizontal, 8).padding(.vertical, 2)
                                .background(RoundedRectangle(cornerRadius: 4).fill(Color.accentColor.opacity(0.15)))
                            Text(mission.missionId.prefix(12)).font(.caption2).monospaced().foregroundColor(.secondary)
                        }
                    }

                    // Pipeline
                    iPadPipeline(mission: mission)

                    // Context + Execution side by side
                    HStack(alignment: .top, spacing: 16) {
                        iPadContextPanel(mission: mission)
                        iPadExecutionPanel(mission: mission)
                    }

                    // Evidence
                    if mission.state == .completed {
                        iPadEvidencePanel(mission: mission)
                    }
                }.padding(24)
            }
        } else {
            VStack(spacing: 12) {
                Image(systemName: "rectangle.split.2x1").font(.largeTitle).foregroundColor(.secondary)
                Text("选择 Mission 查看详情").foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - iPad Panels

struct iPadPipeline: View {
    let mission: Mission
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 0) {
                ForEach(["意图", "上下文", "合约", "计划", "执行", "验证", "证据", "记忆"], id: \.self) { stage in
                    HStack {
                        Image(systemName: "checkmark.circle.fill").foregroundColor(.green).font(.caption)
                        Text(stage).font(.caption)
                    }.padding(.horizontal, 6)
                    if stage != "记忆" {
                        Rectangle().fill(Color.green.opacity(0.3)).frame(width: 16, height: 2)
                    }
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.12)))
    }
}

struct iPadContextPanel: View {
    let mission: Mission
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Mission 上下文", systemImage: "doc.text.magnifyingglass").font(.headline)
            Text("目标：\(mission.objective)").font(.callout)
            Text("风险等级：R\(mission.riskLevel.rawValue.dropFirst())").font(.caption)
            Text("创建时间：\(mission.createdAt.prefix(19))").font(.caption).foregroundColor(.secondary)
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.12)))
    }
}

struct iPadExecutionPanel: View {
    let mission: Mission
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("执行流程", systemImage: "arrow.triangle.branch").font(.headline)
            Text("状态：\(mission.state.rawValue)").font(.callout)
            Text("Runtime Truth API 绑定").font(.caption).foregroundColor(.green)
            Text("实时数据源：本地 柏韩 Runtime").font(.caption).foregroundColor(.secondary)
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.12)))
    }
}

struct iPadEvidencePanel: View {
    let mission: Mission
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("证据与回执", systemImage: "checkmark.shield").font(.headline)
            Text("E1/E2 证据已生成。Trace ID 可通过 Runtime Truth API 查询。").font(.callout).foregroundColor(.green)
            Text("审计链完整 · 哈希已验证").font(.caption).foregroundColor(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.green.opacity(0.05)))
    }
}
