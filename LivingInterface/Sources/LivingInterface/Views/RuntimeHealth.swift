import SwiftUI

struct RuntimeHealthView: View {
    @ObservedObject var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                connectionCard
                if let h = model.projection.health {
                    providerCard(h)
                    breakerCard(h)
                }
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("Runtime 健康")
    }

    private var connectionCard: some View {
        GroupBox {
            HStack {
                VStack(alignment: .leading, spacing: NXSpacing.xs) {
                    Text("连接状态").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                    Text(model.projection.connection.rawValue).font(NXFont.body).foregroundColor(connColor)
                }
                Spacer()
                Circle().fill(connColor).frame(width: 12)
            }
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private func providerCard(_ h: RuntimeHealth) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.sm) {
                Text("Provider 状态").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                ForEach(Array(h.providerStatus.sorted(by: <)), id: \.key) { k, v in
                    HStack {
                        Text(k).foregroundColor(NXColor.graphiteSoft)
                        Spacer()
                        Circle().fill(v == "healthy" ? NXColor.moss : v == "degraded" ? NXColor.amber : NXColor.rose).frame(width: 8)
                        Text(v).font(NXFont.caption)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private func breakerCard(_ h: RuntimeHealth) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.sm) {
                Text("断路保护器").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                ForEach(Array(h.circuitBreaker.sorted(by: { $0.key < $1.key })), id: \.key) { k, open in
                    HStack {
                        Text(k).foregroundColor(NXColor.graphiteSoft)
                        Spacer()
                        Circle().fill(open ? NXColor.rose : NXColor.moss).frame(width: 8)
                        Text(open ? "已断开" : "正常").font(NXFont.caption)
                    }
                }
                row("活跃 Mission", "\(h.activeMissions)")
                if let r = h.lastRestartAt { row("上次重启", r) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private var connColor: Color {
        switch model.projection.connection {
        case .connected: return NXColor.moss
        case .degraded, .recovering: return NXColor.amber
        default: return NXColor.rose
        }
    }
    private func row(_ l: String, _ v: String) -> some View {
        HStack { Text(l).foregroundColor(NXColor.graphiteSoft); Spacer(); Text(v).foregroundColor(NXColor.graphite) }
    }
}
