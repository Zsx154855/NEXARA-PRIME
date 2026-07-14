import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: RuntimeViewModel
    @State private var newObjective: String = ""
    @State private var sidebarSelection: SidebarItem? = .overview

    enum SidebarItem: String, CaseIterable, Identifiable {
        case overview = "运行总览"
        case composer = "Mission Composer"
        case workspace = "工作区"
        case evidence = "证据与验证"
        var id: String { rawValue }
        var icon: String {
            switch self {
            case .overview: "chart.bar"
            case .composer: "square.and.pencil"
            case .workspace: "rectangle.split.2x1"
            case .evidence: "checkmark.shield"
            }
        }
    }

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(min: 200, ideal: 240)
        } detail: {
            detailView
        }
        .toolbar { toolbarContent }
        .task { await model.connect() }
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        List(selection: $sidebarSelection) {
            Section("NEXARA PRIME") {
                ForEach(SidebarItem.allCases) { item in
                    Label(item.rawValue, systemImage: item.icon).tag(item)
                }
            }

            Section("Missions") {
                if model.missions.isEmpty {
                    Text("暂无 Mission").foregroundColor(.secondary).font(.caption)
                } else {
                    ForEach(model.missions) { m in
                        MissionRow(mission: m, isSelected: model.selectedMission?.missionId == m.missionId)
                            .onTapGesture { model.selectedMission = m }
                    }
                }
            }

            Section("状态") {
                HStack {
                    Circle().fill(model.connectionStatus == .connected ? Color.green : Color.red).frame(width: 8)
                    Text(connectionLabel).font(.caption)
                }
                if let err = model.errorMessage {
                    Text(err).font(.caption2).foregroundColor(.red).lineLimit(2)
                }
            }
        }
        .listStyle(.sidebar)
    }

    // MARK: - Detail

    @ViewBuilder
    private var detailView: some View {
        switch sidebarSelection {
        case .overview: OverviewDetail()
        case .composer: ComposerDetail(newObjective: $newObjective)
        case .workspace: WorkspaceDetail()
        case .evidence: EvidenceDetail()
        case .none: Text("选择一项").foregroundColor(.secondary)
        }
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItemGroup {
            Button(action: { Task { await model.connect() } }) {
                Label("连接", systemImage: "arrow.triangle.2.circlepath")
            }
            .help("连接 NEXARA Runtime")
        }
    }

    private var connectionLabel: String {
        switch model.connectionStatus {
        case .connected: "已连接 Runtime"
        case .disconnected: "未连接"
        case .error: "连接失败"
        }
    }
}

// MARK: - Mission Row

struct MissionRow: View {
    let mission: Mission
    let isSelected: Bool

    var body: some View {
        HStack {
            Image(systemName: stateIcon)
                .foregroundColor(stateColor)
                .frame(width: 20)
            VStack(alignment: .leading, spacing: 2) {
                Text(mission.title.isEmpty ? mission.objective : mission.title)
                    .lineLimit(1).font(.callout)
                Text(mission.state.rawValue)
                    .font(.caption2).foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 2)
    }

    private var stateIcon: String {
        switch mission.state {
        case .draft: "circle"
        case .running: "arrow.triangle.2.circlepath"
        case .completed: "checkmark.circle.fill"
        case .blocked: "xmark.octagon"
        case .failed: "exclamationmark.triangle"
        case .approvalRequired: "hand.raised"
        default: "circle.dotted"
        }
    }

    private var stateColor: Color {
        switch mission.state {
        case .completed: .green
        case .running, .verifying: .blue
        case .blocked, .failed: .red
        case .approvalRequired: .orange
        default: .secondary
        }
    }
}
