import SwiftUI

struct IdentitySoulIntegrity: View {
    @ObservedObject var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                if let id = model.projection.identity {
                    identitySection(id)
                    soulSection(id.soulStatus)
                } else {
                    Text("未连接到 Runtime").foregroundColor(NXColor.graphiteSoft)
                }
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("身份与 Soul")
    }

    private func identitySection(_ id: IdentitySnapshot) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.md) {
                Label("身份指纹", systemImage: "fingerprint").font(NXFont.subheading).foregroundColor(NXColor.champagne)
                Text(id.fingerprint).font(NXFont.code).foregroundColor(NXColor.graphite)
                Divider()
                row("名称", id.name)
                row("Owner ID", id.ownerId)
                row("创建时间", id.createdAt)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private func soulSection(_ s: SoulIntegrity) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.md) {
                Label("Soul 完整性", systemImage: "shield.lefthalf.filled").font(NXFont.subheading).foregroundColor(NXColor.champagne)
                HStack {
                    statCard("不可变", "\(s.immutableCount)", NXColor.rose)
                    statCard("稳定", "\(s.stableCount)", NXColor.amber)
                    statCard("已验证", s.integrityVerified ? "是" : "否", s.integrityVerified ? NXColor.moss : NXColor.rose)
                }
                row("最后验证", s.lastVerifiedAt)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private func statCard(_ label: String, _ value: String, _ color: Color) -> some View {
        VStack(spacing: NXSpacing.xs) {
            Text(value).font(NXFont.heading).foregroundColor(color)
            Text(label).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
        }
        .frame(maxWidth: .infinity)
        .padding(NXSpacing.md)
        .background(.ultraThinMaterial)
        .cornerRadius(NXRadius.md)
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack { Text(label).foregroundColor(NXColor.graphiteSoft); Spacer(); Text(value).foregroundColor(NXColor.graphite) }
    }
}
