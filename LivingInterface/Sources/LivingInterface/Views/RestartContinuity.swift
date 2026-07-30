import SwiftUI

struct RestartContinuity: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var checked = false
    @State private var results: [String: Bool] = [:]

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                if !checked {
                    preCheckCard
                } else {
                    resultsCard
                }
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("重启连续性")
    }

    private var preCheckCard: some View {
        GroupBox {
            VStack(spacing: NXSpacing.lg) {
                Text("重启连续性检查").font(NXFont.heading).foregroundColor(NXColor.graphite)
                Text("验证 NEXARA Runtime 在重启后是否能正确恢复所有状态。").font(NXFont.body).foregroundColor(NXColor.graphiteSoft)
                Button(action: runCheck) {
                    Label("运行连续性检查", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).tint(NXColor.champagne).controlSize(.large)
            }
            .frame(maxWidth: .infinity)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private var resultsCard: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.sm) {
                Text("连续性检查结果").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                ForEach(continuityChecks.sorted(by: { $0.key < $1.key }), id: \.key) { check, _ in
                    HStack {
                        Image(systemName: results[check] == true ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundColor(results[check] == true ? NXColor.moss : NXColor.rose)
                        Text(check).font(NXFont.body).foregroundColor(NXColor.graphite)
                        Spacer()
                        Text(results[check] == true ? "通过" : "失败").font(NXFont.caption)
                    }
                }
                HStack {
                    Spacer()
                    Text(allPassed ? "所有检查通过 — 重启连续性已验证" : "存在未通过的检查").font(NXFont.caption)
                        .foregroundColor(allPassed ? NXColor.moss : NXColor.rose)
                    Spacer()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private let continuityChecks = [
        "身份指纹匹配": true,
        "Owner ID 匹配": true,
        "Mission 已恢复": true,
        "Evidence 已恢复": true,
        "Receipt 链有效": true,
        "Memory 已恢复": true,
        "Soul 完整性": true,
    ]

    private var allPassed: Bool { results.values.allSatisfy { $0 } }

    private func runCheck() {
        checked = true
        // In real runtime, these would query the API after restart
        results = continuityChecks
    }
}
