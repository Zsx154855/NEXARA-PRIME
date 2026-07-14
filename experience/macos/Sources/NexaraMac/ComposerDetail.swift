import SwiftUI

struct ComposerDetail: View {
    @EnvironmentObject private var model: RuntimeViewModel
    @Binding var newObjective: String
    @State private var inProgress = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Text("Mission Composer")
                    .font(.title).fontWeight(.medium)
                    .padding(.top, 32)

                VStack(spacing: 16) {
                    Text("输入目标，NEXARA 将自动编译为结构化 Mission")
                        .font(.subheadline).foregroundColor(.secondary)

                    TextEditor(text: $newObjective)
                        .font(.body)
                        .frame(height: 120)
                        .padding(12)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color(.controlBackgroundColor)))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.secondary.opacity(0.2)))

                    HStack {
                        Button(action: {
                            guard !newObjective.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                            inProgress = true
                            Task {
                                await model.createMission(objective: newObjective)
                                newObjective = ""
                                inProgress = false
                            }
                        }) {
                            Label(inProgress ? "创建中…" : "创建 Mission",
                                  systemImage: inProgress ? "hourglass" : "plus.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(newObjective.trimmingCharacters(in: .whitespaces).isEmpty || inProgress)
                        .keyboardShortcut(.return, modifiers: [.command])
                    }
                }
                .frame(maxWidth: 560)
                .padding(32)

                // Human Controls
                VStack(alignment: .leading, spacing: 12) {
                    Label("人类控制", systemImage: "person.badge.shield").font(.title3)
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                        ControlButton(title: "批准 Approve", icon: "checkmark.shield", color: .green)
                        ControlButton(title: "修改 Modify", icon: "pencil", color: .blue)
                        ControlButton(title: "暂停 Pause", icon: "pause.circle", color: .orange)
                        ControlButton(title: "接管 Take Over", icon: "hand.raised", color: .purple)
                        ControlButton(title: "撤销 Revoke", icon: "arrow.uturn.backward", color: .red)
                        ControlButton(title: "回滚 Rollback", icon: "arrow.counterclockwise", color: .red)
                        ControlButton(title: "安全模式 Safe", icon: "lock.shield", color: .gray)
                    }
                }
                .frame(maxWidth: 560)
                .padding(.horizontal)

                Text("← 选择 Mission → 工作区查看详情与执行")
                    .font(.caption).foregroundColor(.secondary)
                    .padding(.bottom, 32)
            }
        }
    }
}

struct ControlButton: View {
    let title: String; let icon: String; let color: Color
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon).foregroundColor(color)
            Text(title).font(.caption)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 8).fill(color.opacity(0.08)))
    }
}
