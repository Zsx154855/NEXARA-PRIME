import SwiftUI

/// Glass-morphic living panel with liquid breath animation.
struct LivingPanel<Content: View>: View {
    @ObservedObject var engine: LivingEngine
    @ViewBuilder let content: () -> Content

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 24)
                .fill(engine.skinProfile.colors.primary.opacity(
                    engine.isReducedMotion ? 0.08 : 0.06 + abs(engine.breathPhase) * 0.04))
                .background(
                    RoundedRectangle(cornerRadius: 24)
                        .fill(.ultraThinMaterial)
                        .environment(\.colorScheme, .light)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(engine.skinProfile.colors.secondary.opacity(0.3), lineWidth: 0.5)
                )

            content()
                .padding(24)
        }
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .shadow(color: engine.skinProfile.colors.shadow, radius: 20, x: 0, y: 4)
    }
}

// MARK: - NEXARA Glass Material System V3
// Unified glass components using system materials with consistent depth treatment.

enum GlassLevel {
    case subtle, standard, elevated, prominent
    var material: Material {
        switch self {
        case .subtle: .ultraThinMaterial
        case .standard: .thinMaterial
        case .elevated: .regularMaterial
        case .prominent: .thickMaterial
        }
    }
    var highlightOpacity: Double {
        switch self {
        case .subtle: 0.15; case .standard: 0.25
        case .elevated: 0.35; case .prominent: 0.4
        }
    }
}

struct GlassSurface<Content: View>: View {
    let level: GlassLevel; let cornerRadius: CGFloat
    @ViewBuilder let content: () -> Content
    var body: some View {
        content()
            .background(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .fill(level.material).environment(\.colorScheme, .light)
            )
            .overlay(RoundedRectangle(cornerRadius: cornerRadius).stroke(NXColor.glassBorder, lineWidth: 0.5))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .stroke(NXColor.glassHighlight.opacity(level.highlightOpacity), lineWidth: 0.5).padding(1)
            )
            .shadow(color: NXColor.glassShadow, radius: 12, x: 0, y: 2)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
    }
}

struct GlassComposer: View {
    @Binding var text: String
    let placeholder: String; let accentColor: Color
    let onSubmit: () -> Void
    @FocusState.Binding var isFocused: Bool
    var body: some View {
        HStack(alignment: .bottom, spacing: NXSpacing.sm) {
            TextField(placeholder, text: $text, axis: .vertical)
                .focused($isFocused).font(NXTypography.bodyFont)
                .foregroundColor(NXColor.graphite)
                .padding(.horizontal, NXSpacing.lg).padding(.vertical, NXSpacing.md)
                .lineLimit(1...5).accessibilityLabel("指令输入框")
            Button {
                onSubmit()
            } label: {
                Image(systemName: NXIcon.send).font(.system(size: 28))
                    .foregroundColor(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? NXColor.graphiteSecondary.opacity(0.3) : accentColor)
                    .symbolRenderingMode(.hierarchical)
            }
            .buttonStyle(.plain)
            .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .frame(width: NXHitTarget.minimum, height: NXHitTarget.minimum)
            .accessibilityLabel("发送指令").padding(.trailing, NXSpacing.sm).padding(.bottom, NXSpacing.xs)
        }
        .background(RoundedRectangle(cornerRadius: NXRadius.composer).fill(.regularMaterial).environment(\.colorScheme, .light))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.composer).stroke(NXColor.glassBorder, lineWidth: 0.5))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.composer).stroke(NXColor.glassHighlight.opacity(0.3), lineWidth: 0.5).padding(1))
        .shadow(color: Color.black.opacity(0.06), radius: 16, x: 0, y: 4)
        .clipShape(RoundedRectangle(cornerRadius: NXRadius.composer))
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }
}

struct GlassTabBar: View {
    @Binding var selectedTab: Int
    let tabs: [(title: String, icon: String)]
    let accentColor: Color; let textSecondary: Color
    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(tabs.enumerated()), id: \.offset) { index, tab in
                Button {
                    withAnimation(.easeInOut(duration: NXMotion.transitionDefault)) { selectedTab = index }
                } label: {
                    VStack(spacing: NXSpacing.xs) {
                        Image(systemName: tab.icon).font(.system(size: 18, weight: .regular))
                            .symbolRenderingMode(.hierarchical).frame(height: 22)
                        Text(tab.title).font(NXTypography.captionFont)
                    }
                    .foregroundColor(selectedTab == index ? accentColor : textSecondary.opacity(0.5))
                    .frame(maxWidth: .infinity).frame(height: NXHitTarget.minimum + 8)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(tab.title)标签")
                .accessibilityAddTraits(selectedTab == index ? .isSelected : [])
            }
        }
        .padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
        .background(RoundedRectangle(cornerRadius: NXRadius.tabBar).fill(.thickMaterial).environment(\.colorScheme, .light))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.tabBar).stroke(NXColor.glassBorder, lineWidth: 0.5))
        .shadow(color: Color.black.opacity(0.05), radius: 12, x: 0, y: -2)
        .clipShape(RoundedRectangle(cornerRadius: NXRadius.tabBar))
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }
}

struct GlassChip: View {
    let text: String; let color: Color; let isSelected: Bool; let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(text).font(NXTypography.labelFont)
                .foregroundColor(isSelected ? NXColor.graphite : NXColor.graphiteSecondary)
                .padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
                .background(Capsule().fill(isSelected ? color.opacity(0.15) : .clear))
                .overlay(Capsule().stroke(isSelected ? color.opacity(0.35) : NXColor.graphiteSecondary.opacity(0.15), lineWidth: 0.5))
        }.buttonStyle(.plain)
    }
}

struct GlassButton: View {
    let label: String; let icon: String; let color: Color; let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: NXSpacing.xs) {
                Image(systemName: icon).font(.system(size: 13))
                Text(label).font(NXTypography.secondaryFont.weight(.medium))
            }
            .foregroundColor(color).padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
            .background(Capsule().fill(color.opacity(0.12)))
            .overlay(Capsule().stroke(color.opacity(0.3), lineWidth: 0.5))
        }.buttonStyle(.plain)
    }
}
