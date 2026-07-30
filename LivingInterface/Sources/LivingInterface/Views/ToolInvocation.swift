import SwiftUI

struct ToolInvocation: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var sessions: [ToolSession] = [
        ToolSession(id: "t-001", tool: "file_write_report", status: "completed", detail: "报告已写入 First Contact Workspace"),
        ToolSession(id: "t-002", tool: "read_system_state", status: "running", detail: "读取 Runtime 状态..."),
    ]

    var body: some View {
        List(sessions) { s in
            HStack(spacing: NXSpacing.md) {
                Image(systemName: s.status == "completed" ? "checkmark.circle.fill" : "arrow.triangle.2.circlepath")
                    .foregroundColor(s.status == "completed" ? NXColor.moss : .blue)
                VStack(alignment: .leading, spacing: NXSpacing.xs) {
                    Text(s.tool).font(NXFont.body).foregroundColor(NXColor.graphite)
                    Text(s.detail).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                }
                Spacer()
                Text(s.status).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
            }
            .padding(.vertical, NXSpacing.xs)
        }
        .scrollContentBackground(.hidden)
        .background(NXColor.ivory)
        .navigationTitle("工具调用")
    }
}

struct ToolSession: Identifiable { let id: String; let tool: String; let status: String; let detail: String }
