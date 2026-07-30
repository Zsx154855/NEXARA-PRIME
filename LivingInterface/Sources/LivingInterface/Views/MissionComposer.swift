import SwiftUI

struct MissionComposer: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var objective = ""
    @State private var risk = "R2"
    @State private var submitted = false

    let riskLevels = ["R0", "R1", "R2", "R3", "R4"]

    var body: some View {
        ScrollView {
            VStack(spacing: NXSpacing.xl) {
                objectiveSection
                riskSection
                submitSection
            }
            .padding(NXSpacing.xl)
        }
        .background(NXColor.ivory)
        .navigationTitle("Mission Composer")
    }

    private var objectiveSection: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.md) {
                Text("任务目标").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                TextEditor(text: $objective)
                    .font(NXFont.body)
                    .frame(minHeight: 100)
                    .padding(NXSpacing.sm)
                    .background(.ultraThinMaterial)
                    .cornerRadius(NXRadius.sm)
                    .overlay(RoundedRectangle(cornerRadius: NXRadius.sm).stroke(NXColor.graphiteSoft.opacity(0.3)))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private var riskSection: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: NXSpacing.md) {
                Text("风险等级").font(NXFont.subheading).foregroundColor(NXColor.graphite)
                Picker("风险等级", selection: $risk) {
                    ForEach(riskLevels, id: \.self) { r in Text(r).tag(r) }
                }
                .pickerStyle(.segmented)
                riskDescription
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.regularMaterial).cornerRadius(NXRadius.lg)
    }

    private var riskDescription: some View {
        let desc: [String: (String, Color)] = [
            "R0": ("无风险 — 纯信息操作", NXColor.moss),
            "R1": ("低风险 — 只读系统状态", NXColor.moss),
            "R2": ("中等风险 — 文件写入 / 本地修改", NXColor.amber),
            "R3": ("高风险 — 外部 API / 网络操作", NXColor.amber),
            "R4": ("关键风险 — 需要独立验证者", NXColor.rose),
        ]
        let (text, color) = desc[risk] ?? ("", .gray)
        return Text(text).font(NXFont.caption).foregroundColor(color)
    }

    private var submitSection: some View {
        Button(action: { submitted = true }) {
            Label(submitted ? "已提交" : "创建 Mission", systemImage: submitted ? "checkmark.circle.fill" : "paperplane.fill")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .tint(submitted ? NXColor.moss : NXColor.champagne)
        .controlSize(.large)
        .disabled(objective.trimmingCharacters(in: .whitespaces).isEmpty || submitted)
    }
}
