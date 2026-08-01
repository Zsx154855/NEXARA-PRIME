import SwiftUI

// ── Human Control View V2: 人类控制平面 ──
// Always-visible human authority interface.
// Permanent controls: pause, approve, reject, modify goal.
// Rendered prominently in spatial layout.
// Never hidden, never bypassed — NEXARA's ethical anchor.

struct HumanControlView: View {
    @ObservedObject var engine: LivingEngine
    @State private var goalText: String = ""

    private var profile: SkinProfile { engine.skinProfile }
    private var spatial: SpatialBrainEngine { engine.spatialBrain }
    private var theme: SpatialTheme { engine.skinEngine.spatialTheme() }

    var body: some View {
        VStack(spacing: 12) {
            // ── Header ──
            HStack(spacing: 6) {
                Image(systemName: "person.crop.circle.badge.checkmark")
                    .font(.system(size: 11))
                Text("人类控制")
                    .font(.system(size: 11, weight: .semibold))
            }
            .foregroundColor(profile.colors.textPrimary)
            .padding(.top, 4)

            // ── Approval row ──
            if engine.state == .awaitingApproval {
                approvalRow
            }

            // ── Goal modification ──
            goalModifyRow

            // ── Pause control ──
            pauseRow
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(.ultraThinMaterial)
                .environment(\.colorScheme, .light)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(theme.controlPlaneTint.opacity(0.4), lineWidth: 0.5)
        )
        .shadow(color: profile.colors.shadow, radius: 12, x: 0, y: 2)
        .accessibilityLabel("人类控制面板")
    }

    // MARK: - Approval Row

    private var approvalRow: some View {
        HStack(spacing: 10) {
            Button(action: { engine.approve() }) {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 14))
                    Text("批准")
                        .font(.system(size: 12, weight: .medium))
                }
                .foregroundColor(Color(hex: "4A8C5C"))
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(
                    Capsule()
                        .fill(Color(hex: "A8D4B8").opacity(0.3))
                )
            }
            .buttonStyle(.plain)
            .accessibilityLabel("批准当前操作")

            Button(action: { engine.reject() }) {
                HStack(spacing: 4) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 14))
                    Text("拒绝")
                        .font(.system(size: 12, weight: .medium))
                }
                .foregroundColor(Color(hex: "B85C4A"))
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(
                    Capsule()
                        .fill(Color(hex: "E0B4A8").opacity(0.3))
                )
            }
            .buttonStyle(.plain)
            .accessibilityLabel("拒绝当前操作")

            if engine.pendingApprovalCount > 0 {
                Text("\(engine.pendingApprovalCount) 项待审批")
                    .font(.system(size: 10))
                    .foregroundColor(profile.colors.textSecondary)
            }
        }
    }

    // MARK: - Goal Modify Row

    private var goalModifyRow: some View {
        HStack(spacing: 8) {
            TextField("修改目标...", text: $goalText)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(profile.colors.background.opacity(0.5))
                )
                .accessibilityLabel("修改任务目标输入框")

            Button(action: {
                if !goalText.isEmpty {
                    engine.modifyGoal(goalText)
                    goalText = ""
                }
            }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(profile.colors.accent)
            }
            .buttonStyle(.plain)
            .disabled(goalText.isEmpty)
            .accessibilityLabel("提交修改的目标")
        }
    }

    // MARK: - Pause Row

    private var pauseRow: some View {
        Button(action: { engine.pause() }) {
            HStack(spacing: 4) {
                Image(systemName: "pause.circle.fill")
                    .font(.system(size: 14))
                Text("暂停")
                    .font(.system(size: 11, weight: .medium))
            }
            .foregroundColor(profile.colors.textSecondary)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(profile.colors.secondary.opacity(0.3))
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("暂停 NEXARA 执行")
    }
}
