import SwiftUI

/// Glass-morphic living panel with liquid breath animation.
struct LivingPanel: View {
    @ObservedObject var engine: LivingEngine
    var content: AnyView
    
    var body: some View {
        ZStack {
            // Liquid breath background
            RoundedRectangle(cornerRadius: 24)
                .fill(engine.skin.primary.opacity(engine.isReducedMotion ? 0.08 : 0.06 + abs(engine.breathPhase) * 0.04))
                .background(
                    RoundedRectangle(cornerRadius: 24)
                        .fill(.ultraThinMaterial)
                        .environment(\.colorScheme, .light)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(engine.skin.secondary.opacity(0.3), lineWidth: 0.5)
                )
            
            // Inner content
            content
                .padding(24)
        }
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .shadow(color: engine.skin.primary.opacity(0.1), radius: 20, x: 0, y: 4)
    }
}

/// State indicator capsule with breath animation.
struct StateIndicator: View {
    @ObservedObject var engine: LivingEngine
    
    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(engine.state.color)
                .frame(width: 10, height: 10)
                .scaleEffect(engine.isReducedMotion ? 1.0 : 1.0 + abs(engine.breathPhase) * 0.3)
                .animation(engine.isReducedMotion ? .none : .easeInOut(duration: engine.skin.breathPeriod / 2), value: engine.breathPhase)
            
            Text(engine.state.rawValue)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(Color(hex: "2D2A26"))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(Capsule().fill(.ultraThinMaterial))
        .overlay(Capsule().stroke(engine.state.color.opacity(0.4), lineWidth: 0.5))
    }
}

/// Horizontal pill skin switcher.
struct SkinSwitcher: View {
    @ObservedObject var engine: LivingEngine
    
    var body: some View {
        HStack(spacing: 6) {
            ForEach(LifeSkin.allCases, id: \.self) { skin in
                Button {
                    engine.switchSkin(to: skin)
                } label: {
                    Text(skin.rawValue)
                        .font(.system(size: 12, weight: engine.skin == skin ? .semibold : .regular))
                        .foregroundColor(Color(hex: "2D2A26"))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            Capsule()
                                .fill(engine.skin == skin ? skin.primary.opacity(0.2) : .clear)
                        )
                        .overlay(
                            Capsule()
                                .stroke(engine.skin == skin ? skin.primary.opacity(0.4) : Color.gray.opacity(0.15), lineWidth: 0.5)
                        )
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// Local-only audio visualizer (frequency bars from FFT — no upload).
struct AudioVisualizer: View {
    @ObservedObject var engine: LivingEngine
    private let barCount = 24
    
    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<barCount, id: \.self) { i in
                let height = engine.audioReactive && !engine.isReducedMotion
                    ? (10 + abs(sin(Double(i) * 0.4 + engine.breathPhase * 2.0)) * 30)
                    : 6.0
                RoundedRectangle(cornerRadius: 2)
                    .fill(engine.skin.primary.opacity(engine.microphoneEnabled ? 0.6 : 0.2))
                    .frame(width: 3, height: max(4, height))
            }
        }
        .frame(height: 44)
        .padding(.horizontal, 8)
    }
}

/// Approval button with gentle bounce.
struct ApprovalButton: View {
    let status: ApprovalButtonStatus
    let onTap: () -> Void
    
    enum ApprovalButtonStatus {
        case pending, approved, rejected
        
        var label: String {
            switch self {
            case .pending: "待审批"
            case .approved: "已通过"
            case .rejected: "已拒绝"
            }
        }
        
        var color: Color {
            switch self {
            case .pending: Color(hex: "E0C8B0")
            case .approved: Color(hex: "A3C4A3")
            case .rejected: Color(hex: "E8A0A0")
            }
        }
    }
    
    var body: some View {
        Button(action: onTap) {
            Text(status.label)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(Color(hex: "2D2A26"))
                .padding(.horizontal, 20)
                .padding(.vertical, 10)
                .background(Capsule().fill(status.color.opacity(0.2)))
                .overlay(Capsule().stroke(status.color.opacity(0.4), lineWidth: 0.5))
        }
        .buttonStyle(.plain)
    }
}
