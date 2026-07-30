import SwiftUI

struct LivingCoreHome: View {
    @ObservedObject var model: RuntimeViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                identityCard
                healthSummary
                quickActions
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("NEXARA 运行总览")
    }

    private var identityCard: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.md) {
                HStack {
                    breathingDot(color: model.projection.connection == .connected ? NXColor.moss : NXColor.rose)
                    Text("NEXARA PRIME").font(NXFont.heading).foregroundColor(NXColor.graphite)
                }
                if let id = model.projection.identity {
                    Text("身份指纹: \(String(id.fingerprint.prefix(12)))…").font(NXFont.code).foregroundColor(NXColor.graphiteSoft)
                    Text("Owner: \(id.ownerId)").font(NXFont.body).foregroundColor(NXColor.graphiteSoft)
                    HStack {
                        Image(systemName: "checkmark.shield.fill").foregroundColor(NXColor.moss)
                        Text("Soul 完整性: 已验证").font(NXFont.caption).foregroundColor(NXColor.moss)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial)
        .cornerRadius(NXRadius.lg)
    }

    private var healthSummary: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.sm) {
                Text("Runtime 健康").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                if let h = model.projection.health {
                    HStack { Text("运行时间:").foregroundColor(NXColor.graphiteSoft); Text("\(Int(h.uptime))s").foregroundColor(NXColor.graphite) }
                    HStack { Text("活跃 Mission:").foregroundColor(NXColor.graphiteSoft); Text("\(h.activeMissions)").foregroundColor(NXColor.graphite) }
                    ForEach(Array(h.providerStatus.sorted(by: <)), id: \.key) { k, v in
                        HStack {
                            Text(k).foregroundColor(NXColor.graphiteSoft)
                            Circle().fill(v == "healthy" ? NXColor.moss : NXColor.amber).frame(width: 8)
                            Text(v).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial)
        .cornerRadius(NXRadius.lg)
    }

    private var quickActions: some View {
        HStack(spacing: NXSpacing.md) {
            quickButton("plus.circle.fill", "新 Mission") { model.selectedScreen = "composer" }
            quickButton("checkmark.shield.fill", "审批中心") { model.selectedScreen = "approval" }
            quickButton("doc.text.magnifyingglass", "证据") { model.selectedScreen = "evidence" }
            quickButton("brain.head.profile", "记忆") { model.selectedScreen = "memory" }
        }
    }

    private func quickButton(_ icon: String, _ label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: NXSpacing.xs) {
                Image(systemName: icon).font(.title2)
                Text(label).font(NXFont.caption)
            }
            .frame(maxWidth: .infinity)
            .padding(NXSpacing.md)
        }
        .buttonStyle(.plain)
        .background(.regularMaterial)
        .cornerRadius(NXRadius.md)
        .foregroundColor(NXColor.graphite)
    }

    private func breathingDot(color: Color) -> some View {
        Circle().fill(color).frame(width: 10, height: 10)
            .scaleEffect(model.projection.connection == .connected ? 1.2 : 1.0)
            .animation(.easeInOut(duration: NXDuration.breathe).repeatForever(), value: model.projection.connection)
    }
}
