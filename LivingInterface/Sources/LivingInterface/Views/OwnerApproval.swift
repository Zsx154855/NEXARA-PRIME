import SwiftUI

struct OwnerApproval: View {
    @ObservedObject var model: RuntimeViewModel

    var body: some View {
        List(model.projection.approvals) { req in
            VStack(alignment: .leading, spacing: NXSpacing.sm) {
                HStack {
                    Image(systemName: "exclamationmark.shield.fill").foregroundColor(NXColor.amber)
                    Text("Mission \(req.missionId)").font(NXFont.body).foregroundColor(NXColor.graphite)
                    Spacer()
                    Text(req.riskLevel).font(NXFont.caption).bold().foregroundColor(riskColor(req.riskLevel))
                }
                Text("范围: \(req.scope.joined(separator: ", "))").font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                Text("状态: \(req.status)").font(NXFont.caption).foregroundColor(statusColor(req.status))
                HStack(spacing: NXSpacing.md) {
                    Button(action: {}) {
                        Label("批准", systemImage: "checkmark.circle.fill").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent).tint(NXColor.moss)
                    Button(action: {}) {
                        Label("拒绝", systemImage: "xmark.circle.fill").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent).tint(NXColor.rose)
                }
            }
            .padding(.vertical, NXSpacing.sm)
        }
        .scrollContentBackground(.hidden)
        .background(NXColor.ivory)
        .navigationTitle("审批中心")
    }

    private func riskColor(_ r: String) -> Color {
        switch r { case "R0","R1": return NXColor.moss; case "R2","R3": return NXColor.amber; default: return NXColor.rose }
    }
    private func statusColor(_ s: String) -> Color {
        s == "pending" ? NXColor.amber : s == "approved" ? NXColor.moss : NXColor.rose
    }
}
