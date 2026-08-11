import SwiftUI

/// Horizontal scrollable family filter pills.
struct AppIconFamilyFilter: View {
    @Binding var selected: AppIconFamily?

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                // "All" pill
                familyPill(nil, label: "全部")

                ForEach(AppIconFamily.allCases) { family in
                    familyPill(family, label: family.displayName)
                }
            }
        }
    }

    @ViewBuilder
    private func familyPill(_ family: AppIconFamily?, label: String) -> some View {
        let isActive = selected == family
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                selected = isActive ? nil : family
            }
        } label: {
            Text(label)
                .font(.system(size: 12, weight: isActive ? .medium : .regular))
                .foregroundColor(isActive ? .white : Color(hex: "6B6560"))
                .padding(.horizontal, 14).padding(.vertical, 6)
                .background(
                    Capsule().fill(isActive ? Color(hex: "8BB8C9") : Color(hex: "DCE8E2").opacity(0.5))
                )
        }
        .buttonStyle(.plain)
    }
}
