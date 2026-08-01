import SwiftUI

/// Horizontal pill skin switcher with morph transition.
struct SkinSwitcher: View {
    @ObservedObject var engine: LivingEngine

    var body: some View {
        HStack(spacing: 6) {
            ForEach(LifeSkin.allCases, id: \.self) { skin in
                Button {
                    engine.switchSkin(to: skin)
                } label: {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(skin.primary)
                            .frame(width: 6, height: 6)
                        Text(skin.rawValue)
                            .font(.system(size: 12, weight: engine.currentSkin == skin ? .semibold : .regular))
                            .foregroundColor(engine.skinProfile.colors.textPrimary)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(
                        Capsule()
                            .fill(engine.currentSkin == skin ? skin.primary.opacity(0.2) : .clear)
                    )
                    .overlay(
                        Capsule()
                            .stroke(
                                engine.currentSkin == skin
                                    ? skin.primary.opacity(0.4)
                                    : engine.skinProfile.colors.textSecondary.opacity(0.1),
                                lineWidth: 0.5
                            )
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }
}
