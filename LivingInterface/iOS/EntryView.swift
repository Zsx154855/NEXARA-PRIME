import SwiftUI

// MARK: - NEXARA iOS Entry View V3
// Four-layer architecture:
//   LAYER 1 — App Background (full screen, no black bar)
//   LAYER 2 — Page Content (safe area, scrollable, priority-ordered)
//   LAYER 3 — Composer (safeAreaInset, keyboard-aware)
//   LAYER 4 — Navigation (independent tab bar via safeAreaInset)

struct EntryView: View {
    @StateObject private var engine = LivingEngine()
    @State private var selectedTab = 0
    @State private var composerText = ""
    @FocusState private var isComposerFocused: Bool

    private let tabs: [(title: String, icon: String)] = [
        ("今日", NXIcon.tabToday),
        ("记忆", NXIcon.tabMemory),
        ("学习", NXIcon.tabLearning),
        ("审批", NXIcon.tabApproval),
        ("状态", NXIcon.tabStatus),
    ]

    private var skinColors: SkinColors { engine.skinProfile.colors }

    // MARK: - Body

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // ══════════════════════════════════════
                // LAYER 1: App Background
                // ══════════════════════════════════════
                skinColors.background
                    .ignoresSafeArea()

                // Subtle ambient gradient
                LinearGradient(
                    gradient: Gradient(colors: [
                        skinColors.ambientTint.opacity(0.3),
                        Color.clear,
                        skinColors.ambientTint.opacity(0.15),
                    ]),
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()
                .allowsHitTesting(false)

                // ══════════════════════════════════════
                // LAYER 2: Page Content
                // ══════════════════════════════════════
                VStack(spacing: 0) {
                    ScrollViewReader { scrollProxy in
                        ScrollView(.vertical, showsIndicators: false) {
                            VStack(spacing: NXSpacing.moduleGap) {
                                // 1. Page identity / status
                                headerSection
                                    .id("top")

                                // 2. Living brain — primary visual anchor
                                brainSection(geometry: geometry)

                                // 3. Current mode indicator
                                modeSection

                                // 4. Current state + key content
                                tabContentSection

                                // 5. Secondary: skin switcher
                                skinSection

                                // Bottom spacer for scroll comfort
                                Spacer().frame(height: NXSpacing.xxxl)
                            }
                            .padding(.top, NXSpacing.lg)
                        }
                        .scrollDismissesKeyboard(.interactively)
                        .onChange(of: isComposerFocused) { _, focused in
                            if focused {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                                    withAnimation {
                                        scrollProxy.scrollTo("top", anchor: .top)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            // ══════════════════════════════════════
            // LAYER 3: Composer (safeAreaInset)
            // ══════════════════════════════════════
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: NXSpacing.sm) {
                    GlassComposer(
                        text: $composerText,
                        placeholder: "输入你的想法…",
                        accentColor: skinColors.accent,
                        onSubmit: submitComposer,
                        isFocused: $isComposerFocused
                    )

                    // ══════════════════════════════════════
                    // LAYER 4: Navigation (inside safeAreaInset)
                    // ══════════════════════════════════════
                    GlassTabBar(
                        selectedTab: $selectedTab,
                        tabs: tabs,
                        accentColor: skinColors.accent,
                        textSecondary: skinColors.textSecondary
                    )
                    .accessibilityIdentifier("living.tabbar")
                }
                .padding(.top, NXSpacing.sm)
                .background(
                    // Blend tab bar background into safe area
                    Rectangle()
                        .fill(skinColors.background.opacity(0.85))
                        .background(.ultraThinMaterial)
                        .environment(\.colorScheme, .light)
                        .ignoresSafeArea(edges: .bottom)
                )
            }
        }
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: NXMotion.transitionDefault),
                   value: engine.state)
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: NXMotion.transitionDefault),
                   value: selectedTab)
        .accessibilityIdentifier("living.root")
    }

    // MARK: - Submit Composer

    private func submitComposer() {
        let trimmed = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        engine.setTask(trimmed)
        composerText = ""
        isComposerFocused = false
    }

    // MARK: - Header Section

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: NXSpacing.xs) {
                HStack(spacing: NXSpacing.sm) {
                    Circle()
                        .fill(engine.state.color)
                        .frame(width: 8, height: 8)
                        .accessibilityHidden(true)
                    Text(engine.state.label)
                        .font(NXTypography.sectionTitleFont)
                        .foregroundColor(skinColors.textPrimary)
                }
                if let task = engine.currentTask {
                    Text(task)
                        .font(NXTypography.secondaryFont)
                        .foregroundColor(skinColors.textSecondary)
                        .lineLimit(2)
                }
            }
            Spacer()
        }
        .padding(.horizontal, NXSpacing.pageHorizontal)
        .accessibilityIdentifier("living.status.content")
    }

    // MARK: - Brain Section

    private func brainSection(geometry: GeometryProxy) -> some View {
        let contentWidth = geometry.size.width - NXSpacing.pageHorizontal * 2
        return LivingCore(engine: engine, containerWidth: contentWidth)
            .frame(maxWidth: .infinity)
            .padding(.vertical, NXSpacing.md)
            .accessibilityIdentifier("living.brain")
    }

    // MARK: - Mode Section

    private var modeSection: some View {
        HStack(spacing: NXSpacing.sm) {
            ForEach(LivingState.allCases.prefix(4), id: \.self) { st in
                GlassChip(
                    text: st.label,
                    color: st.color,
                    isSelected: engine.state == st,
                    action: {
                        engine.transition(to: st)
                    }
                )
                .disabled(!LivingEngine.isValidTransition(from: engine.state, to: st))
            }
        }
        .padding(.horizontal, NXSpacing.pageHorizontal)
        .accessibilityIdentifier("living.mode.selector")
    }

    // MARK: - Tab Content

    private var tabContentSection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
                switch selectedTab {
                case 0: todayContent
                case 1: memoryContent
                case 2: learningContent
                case 3: approvalContent
                case 4: statusContent
                default: EmptyView()
                }
            }
        }
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }

    // MARK: - Skin Section

    private var skinSection: some View {
        HStack(spacing: NXSpacing.sm) {
            Text("生命皮肤")
                .font(NXTypography.labelFont)
                .foregroundColor(skinColors.textSecondary)
            ForEach(LifeSkin.allCases, id: \.self) { skin in
                GlassChip(
                    text: skin.rawValue,
                    color: skin.primary,
                    isSelected: engine.currentSkin == skin,
                    action: { engine.switchSkin(to: skin) }
                )
            }
        }
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }

    // MARK: - Today Content

    private var todayContent: some View {
        Group {
            NXTypography.sectionTitle("今日任务")
                .foregroundColor(skinColors.textPrimary)

            if let task = engine.currentTask {
                taskRow(task, isActive: true)
            } else {
                NXTypography.secondary("暂无活跃任务")
                    .foregroundColor(skinColors.textSecondary)
            }
        }
    }

    private func taskRow(_ task: String, isActive: Bool) -> some View {
        HStack(spacing: NXSpacing.sm) {
            Circle()
                .fill(isActive ? engine.state.color : Color.gray.opacity(0.3))
                .frame(width: 8, height: 8)
            Text(task)
                .font(NXTypography.secondaryFont)
                .foregroundColor(skinColors.textPrimary)
            Spacer()
        }
        .padding(NXSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: NXRadius.control)
                .fill(skinColors.glassOverlay)
        )
    }

    // MARK: - Memory Content

    private var memoryContent: some View {
        Group {
            NXTypography.sectionTitle("记忆")
                .foregroundColor(skinColors.textPrimary)

            NXTypography.secondary("知识图谱 · 长期记忆 · 经验回放")
                .foregroundColor(skinColors.textSecondary)

            if engine.recentLearnings.isEmpty {
                NXTypography.secondary("暂无记忆条目")
                    .foregroundColor(skinColors.textSecondary.opacity(0.5))
            } else {
                ForEach(engine.recentLearnings, id: \.self) { learning in
                    HStack(spacing: NXSpacing.sm) {
                        Image(systemName: "sparkle")
                            .font(.system(size: 12))
                            .foregroundColor(skinColors.accent)
                        Text(learning)
                            .font(NXTypography.secondaryFont)
                            .foregroundColor(skinColors.textSecondary)
                    }
                    .padding(NXSpacing.md)
                    .background(
                        RoundedRectangle(cornerRadius: NXRadius.control)
                            .fill(skinColors.glassOverlay)
                    )
                }
            }
        }
    }

    // MARK: - Learning Content

    private var learningContent: some View {
        Group {
            NXTypography.sectionTitle("学习")
                .foregroundColor(skinColors.textPrimary)

            if engine.state == .learning {
                HStack(spacing: NXSpacing.md) {
                    LivingCore(engine: engine, containerWidth: 60)
                    VStack(alignment: .leading, spacing: NXSpacing.xs) {
                        Text("知识节点生长中")
                            .font(NXTypography.secondaryFont.weight(.medium))
                            .foregroundColor(skinColors.textPrimary)
                        NXTypography.label("从最近任务中提取模式")
                            .foregroundColor(skinColors.textSecondary)
                    }
                }
                .padding(NXSpacing.md)
                .background(
                    RoundedRectangle(cornerRadius: NXRadius.control)
                        .fill(skinColors.glassOverlay)
                )
            } else {
                NXTypography.secondary("就绪 · 等待新任务完成后自动学习")
                    .foregroundColor(skinColors.textSecondary)
            }
        }
    }

    // MARK: - Approval Content

    private var approvalContent: some View {
        Group {
            NXTypography.sectionTitle("审批")
                .foregroundColor(skinColors.textPrimary)

            if engine.state == .awaitingApproval {
                VStack(spacing: NXSpacing.md) {
                    Text("需要人类决断")
                        .font(NXTypography.secondaryFont.weight(.medium))
                        .foregroundColor(skinColors.textPrimary)

                    HStack(spacing: NXSpacing.md) {
                        GlassButton(label: "批准", icon: NXIcon.approve, color: NXColor.approveGreen) {
                            engine.approve()
                        }
                        GlassButton(label: "拒绝", icon: NXIcon.reject, color: NXColor.rejectRed) {
                            engine.reject()
                        }
                    }
                }
                .padding(NXSpacing.md)
                .background(
                    RoundedRectangle(cornerRadius: NXRadius.control)
                        .fill(skinColors.glassOverlay)
                )
            } else {
                VStack(alignment: .leading, spacing: NXSpacing.sm) {
                    NXTypography.secondary("暂无待审批项")
                        .foregroundColor(skinColors.textSecondary)
                    if engine.pendingApprovalCount > 0 {
                        Text("\(engine.pendingApprovalCount) 项等待中")
                            .font(NXTypography.labelFont)
                            .foregroundColor(NXColor.amberAttention)
                    }
                }
            }
        }
    }

    // MARK: - Status Content

    private var statusContent: some View {
        Group {
            NXTypography.sectionTitle("状态")
                .foregroundColor(skinColors.textPrimary)

            statusRow("当前状态", engine.state.label)
            statusRow("生命皮肤", engine.currentSkin.rawValue)
            statusRow("待审批", "\(engine.pendingApprovalCount) 项")
            statusRow("记忆条目", "\(engine.recentLearnings.count) 条")
            statusRow("麦克风", engine.microphoneEnabled ? "已开启" : "已关闭")
            statusRow("降低动态", engine.isReducedMotion ? "是" : "否")

            Button {
                engine.toggleMicrophone()
            } label: {
                HStack(spacing: NXSpacing.sm) {
                    Image(systemName: engine.microphoneEnabled ? NXIcon.micOn : NXIcon.micOff)
                    Text(engine.microphoneEnabled ? "关闭麦克风" : "开启麦克风（仅本地）")
                        .font(NXTypography.secondaryFont)
                }
                .foregroundColor(skinColors.textSecondary)
                .padding(NXSpacing.sm)
                .background(
                    RoundedRectangle(cornerRadius: NXRadius.control)
                        .fill(skinColors.glassOverlay)
                )
            }
            .buttonStyle(.plain)
            .accessibilityLabel(engine.microphoneEnabled ? "关闭麦克风" : "开启麦克风")
        }
    }

    private func statusRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(NXTypography.secondaryFont)
                .foregroundColor(skinColors.textSecondary)
            Spacer()
            Text(value)
                .font(NXTypography.secondaryFont.weight(.medium))
                .foregroundColor(skinColors.textPrimary)
        }
    }
}

#Preview {
    EntryView()
}
