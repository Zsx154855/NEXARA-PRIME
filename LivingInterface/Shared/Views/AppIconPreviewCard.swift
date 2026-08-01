import SwiftUI

/// Single icon preview card in the picker grid.
struct AppIconPreviewCard: View {
    let icon: AppIconOption
    let isSelected: Bool
    let isApplied: Bool
    var size: CGFloat = 72

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                // Icon image
                #if os(macOS)
                if let img = NSImage(named: icon.previewAssetName) {
                    Image(nsImage: img)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: size, height: size)
                        .clipShape(RoundedRectangle(cornerRadius: size * 0.224))
                } else {
                    iconPlaceholder
                }
                #else
                if let img = UIImage(named: icon.previewAssetName) {
                    Image(uiImage: img)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: size, height: size)
                        .clipShape(RoundedRectangle(cornerRadius: size * 0.224))
                } else {
                    iconPlaceholder
                }
                #endif

                // Selection checkmark
                if isSelected {
                    RoundedRectangle(cornerRadius: size * 0.224)
                        .stroke(
                            isApplied ? Color(hex: "6BA87A") : Color(hex: "8BB8C9"),
                            lineWidth: 3
                        )
                        .frame(width: size + 4, height: size + 4)

                    if isApplied {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 18))
                            .foregroundColor(Color(hex: "6BA87A"))
                            .background(Circle().fill(Color.white))
                            .offset(x: size * 0.35, y: -size * 0.4)
                    }
                }
            }

            Text(icon.displayName)
                .font(.system(size: 10))
                .foregroundColor(Color(hex: "2D2A26"))
                .lineLimit(1)
                .frame(maxWidth: size + 10)
        }
        .accessibilityLabel(icon.accessibilityLabel)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private var iconPlaceholder: some View {
        RoundedRectangle(cornerRadius: size * 0.224)
            .fill(Color(hex: "DCE8E2"))
            .frame(width: size, height: size)
            .overlay(
                Image(systemName: "app.fill")
                    .font(.system(size: size * 0.4))
                    .foregroundColor(Color(hex: "A8BFB4"))
            )
    }
}
