import SwiftUI

struct MemoryInspector: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var selectedCategory: String? = nil
    @State private var exportMessage = ""

    var body: some View {
        VStack(spacing: 0) {
            Picker("分类", selection: $selectedCategory) {
                Text("全部").tag(nil as String?)
                ForEach(model.projection.memory) { cat in
                    Text("\(cat.category) (\(cat.count))").tag(cat.category as String?)
                }
            }
            .pickerStyle(.segmented)
            .padding()

            List {
                ForEach(filteredRecords) { rec in
                    VStack(alignment: .leading, spacing: NXSpacing.xs) {
                        HStack {
                            Text(rec.key).font(NXFont.body).foregroundColor(NXColor.graphite)
                            Spacer()
                            Text(rec.kind).font(NXFont.caption).foregroundColor(kindColor(rec.kind))
                        }
                        Text(rec.content).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft).lineLimit(2)
                        if let evId = rec.sourceEvidenceId {
                            Text("来源证据: \(evId)").font(NXFont.code).foregroundColor(NXColor.graphiteSoft)
                        }
                        if rec.deletable {
                            HStack(spacing: NXSpacing.md) {
                                Button("导出") { exportMessage = "已导出记忆 \(rec.memoryId)" }.buttonStyle(.borderless)
                                Button("纠正") {}.buttonStyle(.borderless)
                                Button("删除") {}.buttonStyle(.borderless).foregroundColor(NXColor.rose)
                            }
                            .font(NXFont.caption)
                        }
                    }
                    .padding(.vertical, NXSpacing.xs)
                }
            }
            .scrollContentBackground(.hidden)
            .background(NXColor.ivory)
        }
        .background(NXColor.ivory)
        .navigationTitle("记忆检查器")
        .onChange(of: exportMessage) { if !$0.isEmpty { print($0) } }
    }

    private var filteredRecords: [MemoryRecord] {
        guard let cat = selectedCategory else {
            return model.projection.memory.flatMap(\.records)
        }
        return model.projection.memory.first(where: { $0.category == cat })?.records ?? []
    }

    private func kindColor(_ k: String) -> Color {
        switch k {
        case "identity": return NXColor.rose
        case "learned": return NXColor.amber
        case "working": return NXColor.moss
        default: return NXColor.graphiteSoft
        }
    }
}
