import SwiftUI

// MARK: - NEXARA iOS Entry View V4 — Phase 12 Six-Zone IA
// Six-zone information architecture (V11_PRODUCT_GAP_MATRIX):
//   首页 / 对话 / 使命 / 治理 / 记忆 / 设置
// Navigation adapts to device form factor:
//   - iPhone (compact):  system TabView, one page per zone
//   - iPad (regular):    NavigationSplitView (sidebar + detail)
// View logic is reused from V3 (four-layer glass language); only
// navigation chrome and zone titles changed.
//
// TODO(phase-12, brand): 主图标待「门+金点」品牌资产替换。
// 当前 CFBundlePrimaryIcon 仍使用 d01_product_liquid 占位（见 iOS/Info.plist 注释）。
// 不生成 PNG —— 等正式资产到位后替换。

enum NEXARAZone: String, CaseIterable, Identifiable {
    case home, conversation, mission, governance, memory, settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .home: return "首页"
        case .conversation: return "对话"
        case .mission: return "使命"
        case .governance: return "治理"
        case .memory: return "记忆"
        case .settings: return "设置"
        }
    }

    var icon: String {
        switch self {
        case .home: return "house.fill"
        case .conversation: return "bubble.left.and.bubble.right.fill"
        case .mission: return "scope"
        case .governance: return "checkmark.shield.fill"
        case .memory: return NXIcon.tabMemory
        case .settings: return "gearshape.fill"
        }
    }
}

struct EntryView: View {
    @StateObject private var engine = LivingEngine()
    @State private var selectedZone: NEXARAZone? = .home
    @State private var composerText = ""
    @FocusState private var isComposerFocused: Bool

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    private var skinColors: SkinColors { engine.skinProfile.colors }
    private var activeZone: NEXARAZone { selectedZone ?? .home }

    // MARK: - Body

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                ipadSplitView
            } else {
                iphoneTabView
            }
        }
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: NXMotion.transitionDefault),
                   value: selectedZone)
        .accessibilityIdentifier("living.root")
    }

    // MARK: - iPhone: TabView

    private var iphoneTabView: some View {
        TabView(selection: $selectedZone) {
            ForEach(NEXARAZone.allCases) { zone in
                NavigationStack {
                    zonePage(zone)
                        .navigationTitle(zone.title)
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar(zone == .home ? .hidden : .visible, for: .navigationBar)
                }
                .tabItem { Label(zone.title, systemImage: zone.icon) }
                .tag(zone)
            }
        }
        .accessibilityIdentifier("living.tabbar")
    }

    // MARK: - iPad: NavigationSplitView

    private var ipadSplitView: some View {
        NavigationSplitView {
            List(NEXARAZone.allCases, selection: $selectedZone) { zone in
                Label(zone.title, systemImage: zone.icon)
                    .tag(zone)
            }
            .listStyle(.sidebar)
            .navigationTitle("NEXARA")
            .accessibilityIdentifier("living.sidebar")
        } detail: {
            NavigationStack {
                zonePage(activeZone)
                    .navigationTitle(activeZone.title)
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar(activeZone == .home ? .hidden : .visible, for: .navigationBar)
            }
        }
    }

    // MARK: - Zone Pages

    @ViewBuilder
    private func zonePage(_ zone: NEXARAZone) -> some View {
        switch zone {
        case .home: homePage
        case .conversation: ConversationListView()
        case .mission: missionPage
        case .governance: governancePage
        case .memory: memoryPage
        case .settings: settingsPage
        }
    }

    /// LAYER 1: shared atmosphere background (per zone).
    private func atmosphericPage<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        ZStack {
            skinColors.background
                .ignoresSafeArea()

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

            content()
        }
    }

    // MARK: - 首页 (Home)

    private var homePage: some View {
        atmosphericPage {
            GeometryReader { geometry in
                // LAYER 2: Page Content
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

                            // 4. Today focus
                            todaySection

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
            // LAYER 3: Composer (home zone only)
            .safeAreaInset(edge: .bottom, spacing: 0) {
                GlassComposer(
                    text: $composerText,
                    placeholder: "输入你的想法…",
                    accentColor: skinColors.accent,
                    onSubmit: submitComposer,
                    isFocused: $isComposerFocused
                )
                .padding(.top, NXSpacing.sm)
                .background(
                    Rectangle()
                        .fill(skinColors.background.opacity(0.85))
                        .background(.ultraThinMaterial)
                        .environment(\.colorScheme, .light)
                        .ignoresSafeArea(edges: .bottom)
                )
            }
        }
        .accessibilityIdentifier("living.zone.home")
    }

    // MARK: - 使命 (Mission)

    private var missionPage: some View {
        atmosphericPage {
            ScrollView(.vertical, showsIndicators: false) {
                missionSection
                    .padding(.top, NXSpacing.lg)
            }
        }
        .accessibilityIdentifier("living.zone.mission")
    }

    // MARK: - 治理 (Governance)

    private var governancePage: some View {
        atmosphericPage {
            ScrollView(.vertical, showsIndicators: false) {
                governanceSection
                    .padding(.top, NXSpacing.lg)
            }
        }
        .accessibilityIdentifier("living.zone.governance")
    }

    // MARK: - 记忆 (Memory)

    private var memoryPage: some View {
        atmosphericPage {
            ScrollView(.vertical, showsIndicators: false) {
                memorySection
                    .padding(.top, NXSpacing.lg)
            }
        }
        .accessibilityIdentifier("living.zone.memory")
    }

    // MARK: - 设置 (Settings)

    private var settingsPage: some View {
        atmosphericPage {
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: NXSpacing.moduleGap) {
                    settingsSection
                    skinSection
                    Spacer().frame(height: NXSpacing.xxxl)
                }
                .padding(.top, NXSpacing.lg)
            }
        }
        .accessibilityIdentifier("living.zone.settings")
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

    // MARK: - 首页 Content

    private var todaySection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
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
        .padding(.horizontal, NXSpacing.pageHorizontal)
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

    // MARK: - 记忆 Content

    private var memorySection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
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
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }

    // MARK: - 使命 Content

    private var missionSection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
                NXTypography.sectionTitle("使命 · 知识生长")
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
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }

    // MARK: - 治理 Content

    private var governanceSection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
                NXTypography.sectionTitle("治理 · 人类决断")
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
                                .foregroundColor(NXColor.pauseAmber)
                        }
                    }
                }
            }
        }
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }

    // MARK: - 设置 Content

    private var settingsSection: some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.card) {
            VStack(alignment: .leading, spacing: NXSpacing.lg) {
                NXTypography.sectionTitle("设置")
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
        .padding(.horizontal, NXSpacing.pageHorizontal)
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
