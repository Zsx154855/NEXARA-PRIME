import SwiftUI

struct FirstContactConversation: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var confirmed = false

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                if !confirmed {
                    welcomeView
                } else {
                    healthCheckView
                }
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("初次接触")
    }

    private var welcomeView: some View {
        VStack(spacing: NXSpacing.lg) {
            Image(systemName: "sparkles").font(.system(size: 48)).foregroundColor(NXColor.champagne)
            Text("欢迎来到 NEXARA").font(NXFont.display).foregroundColor(NXColor.graphite)
            Text("我是 NEXARA，一个受治理的第一方 AI Runtime。").font(NXFont.body).foregroundColor(NXColor.graphiteSoft)
            if let id = model.projection.identity {
                VStack(spacing: NXSpacing.sm) {
                    Text("身份指纹").font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                    Text(id.fingerprint).font(NXFont.code).foregroundColor(NXColor.graphite)
                    Text("Owner: \(id.ownerId)").font(NXFont.body).foregroundColor(NXColor.graphite)
                    HStack {
                        Image(systemName: "checkmark.shield.fill").foregroundColor(NXColor.moss)
                        Text("Soul 完整性: 已验证 — \(id.soulStatus.immutableCount) 条不可变锚点").font(NXFont.caption).foregroundColor(NXColor.moss)
                    }
                }
                .padding()
                .background(.regularMaterial)
                .cornerRadius(NXRadius.md)
            }
            Button(action: { withAnimation { confirmed = true } }) {
                Label("确认身份并继续", systemImage: "checkmark.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(NXColor.champagne)
            .controlSize(.large)
        }
    }

    private var healthCheckView: some View {
        VStack(spacing: NXSpacing.lg) {
            Image(systemName: "heart.circle.fill").font(.system(size: 48)).foregroundColor(NXColor.moss)
            Text("系统健康检查完成").font(NXFont.heading).foregroundColor(NXColor.graphite)
            Text("NEXARA Runtime 运行正常。你可以开始创建 Mission、审批操作和管理记忆。").font(NXFont.body).foregroundColor(NXColor.graphiteSoft)
                .multilineTextAlignment(.center)
            Button(action: { model.selectedScreen = "composer" }) {
                Label("创建第一个 Mission", systemImage: "plus.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(NXColor.moss)
            .controlSize(.large)
        }
    }
}
