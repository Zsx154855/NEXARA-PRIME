import SwiftUI

/// Full app icon picker view — grid of 24 icons with family filter, preview, apply, restore.
struct AppIconPickerView: View {
    @StateObject private var store = AppIconSelectionStore()
    @State private var selectedFamily: AppIconFamily? = nil
    @State private var pendingSelection: AppIconOption?

    var body: some View {
        VStack(spacing: 0) {
            // ── Current icon preview ──
            currentIconSection

            Divider().opacity(0.3).padding(.horizontal, 20)

            // ── Family filter ──
            AppIconFamilyFilter(selected: $selectedFamily)
                .padding(.horizontal, 20)
                .padding(.vertical, 12)

            // ── Icon grid ──
            ScrollView {
                LazyVGrid(columns: [
                    GridItem(.adaptive(minimum: 80, maximum: 100), spacing: 12)
                ], spacing: 12) {
                    ForEach(filteredIcons) { icon in
                        AppIconPreviewCard(
                            icon: icon,
                            isSelected: pendingSelection?.id == icon.id || store.selectedIcon.id == icon.id,
                            isApplied: store.selectedIcon.id == icon.id && pendingSelection == nil
                        )
                        .onTapGesture {
                            pendingSelection = icon
                        }
                    }
                }
                .padding(20)
            }

            // ── Action bar ──
            if let pending = pendingSelection, pending.id != store.selectedIcon.id {
                actionBar(for: pending)
            }

            // ── Restore default ──
            if store.selectedIcon.id != AppIconCatalog.primaryIcon.id {
                restoreButton
            }

            // ── Error ──
            if let error = store.lastError {
                Text(error)
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "D48888"))
                    .padding(8)
            }

            // ── Loading ──
            if store.isApplying {
                ProgressView().padding(8)
            }

            // ── Platform note ──
            platformNote
        }
        .background(Color(hex: "F5F0EB"))
        .onAppear {
            pendingSelection = nil
        }
    }

    private var filteredIcons: [AppIconOption] {
        if let family = selectedFamily {
            return AppIconCatalog.icons(for: family)
        }
        return AppIconCatalog.allIcons
    }

    private var currentIconSection: some View {
        HStack(spacing: 16) {
            AppIconPreviewCard(
                icon: store.selectedIcon,
                isSelected: true,
                isApplied: true,
                size: 64
            )

            VStack(alignment: .leading, spacing: 4) {
                Text("当前使用")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color(hex: "6B6560"))

                Text(store.selectedIcon.displayName)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(Color(hex: "2D2A26"))

                Text(store.selectedIcon.family.displayName)
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: "9B9590"))
            }

            Spacer()
        }
        .padding(20)
    }

    private func actionBar(for icon: AppIconOption) -> some View {
        HStack(spacing: 12) {
            Button {
                pendingSelection = nil
            } label: {
                Text("取消")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "6B6560"))
            }
            .buttonStyle(.plain)

            Button {
                store.applyIcon(icon)
                pendingSelection = nil
            } label: {
                Text("应用「\(icon.displayName)」")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.white)
                    .padding(.horizontal, 20).padding(.vertical, 8)
                    .background(Capsule().fill(Color(hex: "8BB8C9")))
            }
            .buttonStyle(.plain)
            .disabled(store.isApplying)
        }
        .padding(.horizontal, 20).padding(.bottom, 8)
    }

    private var restoreButton: some View {
        Button {
            store.restoreDefault()
            pendingSelection = nil
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "arrow.counterclockwise")
                    .font(.system(size: 11))
                Text("恢复默认图标")
                    .font(.system(size: 12))
            }
            .foregroundColor(Color(hex: "9B9590"))
            .padding(8)
        }
        .buttonStyle(.plain)
        .padding(.bottom, 4)
    }

    private var platformNote: some View {
        Text(platformNoteText)
            .font(.system(size: 10))
            .foregroundColor(Color(hex: "B5B0AB"))
            .multilineTextAlignment(.center)
            .padding(.horizontal, 20)
            .padding(.bottom, 12)
    }

    private var platformNoteText: String {
        #if os(macOS)
        "macOS 切换的是 Dock 图标。Finder 中的应用包保持默认图标。"
        #else
        "iOS 切换由系统控制。切换后系统会显示确认提示。仅支持支持 Alternate Icons 的设备。"
        #endif
    }
}

#Preview {
    AppIconPickerView()
        .frame(width: 500, height: 700)
}
