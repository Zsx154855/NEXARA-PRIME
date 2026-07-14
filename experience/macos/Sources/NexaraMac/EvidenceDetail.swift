import NexaraCore
import SwiftUI

struct EvidenceDetail: View {
    @EnvironmentObject private var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("证据与验证")
                    .font(.title).fontWeight(.medium).padding(.top, 32)

                if let ov = model.overview {
                    VStack(alignment: .leading, spacing: 12) {
                        EvidenceRow(label: "安全状态", value: ov.securityStatus, ok: ov.securityStatus == "CLOSED")
                        EvidenceRow(label: "Hermes 运行依赖", value: "\(ov.hermesDependency)", ok: ov.hermesDependency == 0)
                        EvidenceRow(label: "Missions 完成", value: "\(ov.missionsCompleted) / \(ov.missionsTotal)", ok: true)
                    }
                    .padding()
                    .background(RoundedRectangle(cornerRadius: 10).fill(Color(.controlBackgroundColor)))
                }

                VStack(alignment: .leading, spacing: 8) {
                    Label("证据等级 (E0-E2)", systemImage: "shield.lefthalf.filled").font(.title3)
                    Text("E0 — 声明：模型或工具声称发生，不得作为完成依据").font(.caption).foregroundColor(.secondary)
                    Text("E1 — 可复核证据：日志、diff、截图、测试结果").font(.caption).foregroundColor(.secondary)
                    Text("E2 — 强证据：哈希、签名、不可变链、独立验证器").font(.caption).foregroundColor(.secondary)
                }
                .padding()

                Spacer()
            }.padding(.horizontal, 32)
        }
    }
}

struct EvidenceRow: View {
    let label: String; let value: String; let ok: Bool
    var body: some View {
        HStack {
            Image(systemName: ok ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundColor(ok ? .green : .red)
            Text(label).font(.callout)
            Spacer()
            Text(value).font(.callout).monospaced().foregroundColor(ok ? .green : .red)
        }
    }
}
