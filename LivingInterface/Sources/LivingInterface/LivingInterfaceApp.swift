import SwiftUI

@main
struct LivingInterfaceApp: App {
    @StateObject private var model = RuntimeViewModel()

    var body: some Scene {
        WindowGroup {
            ContentShell()
                .environmentObject(model)
                .frame(minWidth: 900, minHeight: 600)
                .task { await model.connect() }
        }
        .windowStyle(.titleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) {}
            SidebarCommands()
        }
    }
}

struct ContentShell: View {
    @EnvironmentObject var model: RuntimeViewModel
    @State private var selection: String = "home"

    let screens: [(String, String, String)] = [
        ("home", "运行总览", "house.fill"),
        ("first-contact", "初次接触", "sparkles"),
        ("identity", "身份与 Soul", "person.text.rectangle.fill"),
        ("composer", "Mission Composer", "square.and.pencil"),
        ("timeline", "Mission 时间线", "list.bullet.rectangle"),
        ("approval", "审批中心", "checkmark.shield.fill"),
        ("tools", "工具调用", "hammer.fill"),
        ("evidence", "证据检查器", "doc.text.magnifyingglass"),
        ("receipt", "Receipt 检查器", "link"),
        ("memory", "记忆检查器", "brain.head.profile"),
        ("health", "Runtime 健康", "heart.text.square.fill"),
        ("restart", "重启连续性", "arrow.triangle.2.circlepath"),
    ]

    var body: some View {
        NavigationSplitView {
            List(screens, id: \.0, selection: $selection) { (id, label, icon) in
                Label(label, systemImage: icon)
                    .tag(id)
                    .foregroundColor(NXColor.graphite)
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)
            .background(NXColor.ivoryLight)
            .navigationSplitViewColumnWidth(min: 200, ideal: 220)
        } detail: {
            detailView
        }
        .background(NXColor.ivory)
    }

    @ViewBuilder
    private var detailView: some View {
        Group {
            if selection == "home" { LivingCoreHome(model: model) }
            else if selection == "first-contact" { FirstContactConversation(model: model) }
            else if selection == "identity" { IdentitySoulIntegrity(model: model) }
            else if selection == "composer" { MissionComposer(model: model) }
            else if selection == "timeline" { MissionTimeline(model: model) }
            else if selection == "approval" { OwnerApproval(model: model) }
            else if selection == "tools" { ToolInvocation(model: model) }
            else if selection == "evidence" { EvidenceInspector(model: model) }
            else if selection == "receipt" { ReceiptInspector(model: model) }
            else if selection == "memory" { MemoryInspector(model: model) }
            else if selection == "health" { RuntimeHealthView(model: model) }
            else if selection == "restart" { RestartContinuity(model: model) }
            else { LivingCoreHome(model: model) }
        }
    }
}
