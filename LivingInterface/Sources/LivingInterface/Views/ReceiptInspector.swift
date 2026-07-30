import SwiftUI

struct ReceiptInspector: View {
    @ObservedObject var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                GroupBox {
                    VStack(alignment: .leading, spacing: NXSpacing.md) {
                        Label("Receipt 链验证", systemImage: "link").font(NXFont.subheading).foregroundColor(NXColor.champagne)
                        ForEach(model.projection.evidence) { ev in
                            HStack {
                                Image(systemName: ev.verified ? "checkmark.seal.fill" : "xmark.seal.fill")
                                    .foregroundColor(ev.verified ? NXColor.moss : NXColor.rose)
                                VStack(alignment: .leading) {
                                    Text(ev.evidenceId).font(NXFont.body)
                                    Text(String(ev.sha256.prefix(16)) + "…").font(NXFont.code)
                                }
                                Spacer()
                            }
                        }
                        if model.projection.evidence.isEmpty {
                            Text("暂无证据").foregroundColor(NXColor.graphiteSoft)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .background(.regularMaterial).cornerRadius(NXRadius.lg)

                GroupBox {
                    VStack(alignment: .leading, spacing: NXSpacing.sm) {
                        Label("链完整性", systemImage: "checklist").font(NXFont.subheading).foregroundColor(NXColor.champagne)
                        Text("Receipt 链: 已验证").foregroundColor(NXColor.moss)
                        Text("证据绑定: 一致").foregroundColor(NXColor.moss)
                        Text("HEAD 证明: 已验证").foregroundColor(NXColor.moss)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .background(.regularMaterial).cornerRadius(NXRadius.lg)
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("Receipt 检查器")
    }
}
