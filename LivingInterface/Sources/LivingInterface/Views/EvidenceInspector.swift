import SwiftUI

struct EvidenceInspector: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var selectedEvidence: EvidenceSummary?

    var body: some View {
        List(model.projection.evidence) { ev in
            HStack {
                Image(systemName: ev.verified ? "checkmark.shield.fill" : "xmark.shield.fill")
                    .foregroundColor(ev.verified ? NXColor.moss : NXColor.rose)
                VStack(alignment: .leading, spacing: NXSpacing.xs) {
                    Text("证据 \(ev.evidenceId)").font(NXFont.body).foregroundColor(NXColor.graphite)
                    Text(String(ev.sha256.prefix(24)) + "…").font(NXFont.code).foregroundColor(NXColor.graphiteSoft)
                }
                Spacer()
            }
            .contentShape(Rectangle())
            .onTapGesture { selectedEvidence = ev }
        }
        .scrollContentBackground(.hidden)
        .background(NXColor.ivory)
        .navigationTitle("证据检查器")
        .sheet(item: $selectedEvidence) { ev in
            evidenceDetail(ev)
        }
    }

    private func evidenceDetail(_ ev: EvidenceSummary) -> some View {
        VStack(alignment: .leading, spacing: NXSpacing.lg) {
            Text("证据详情").font(NXFont.heading)
            row("ID", ev.evidenceId)
            row("Mission", ev.missionId)
            row("SHA-256", ev.sha256)
            row("验证状态", ev.verified ? "已验证" : "验证失败")
            row("创建时间", ev.createdAt)
            Button(action: { NSWorkspace.shared.open(URL(string: "https://github.com/Zsx154855/NEXARA-PRIME")!) }) {
                Label("在证据库中验证", systemImage: "magnifyingglass")
            }
        }
        .padding()
        .frame(width: 500, height: 350)
    }

    private func row(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading) {
            Text(label).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
            Text(value).font(value.count > 40 ? NXFont.code : NXFont.body).foregroundColor(NXColor.graphite)
        }
    }
}
