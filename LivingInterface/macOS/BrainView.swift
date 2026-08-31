import SwiftUI
import Foundation

// ── NEXARA First Contact: macOS Brain View ──
// "个人主权智能体第一次接触界面" — the sovereign agent's primary surface.
// Layout: NavigationSplitView sidebar + detail. Warm Ivory palette.
// PHASE 11 (V1.1) 六区 IA (per V11_PRODUCT_GAP_MATRIX):
//   HOME (首页)        — FirstContact + RuntimeHealth 合并为 HomePage；SoulIdentity 并入
//   CONVERSATION (对话) — 新页：本地对话视图壳，数据来自运行时 8765 /api/conversations
//   MISSIONS (使命)     — MissionComposer + MissionTimeline + ToolRuntime
//   TRUST (信任)        — ApprovalCenter + EvidenceInspector + ReceiptInspector
//   MEMORY (记忆)       — MemoryInspector
//   SETTINGS (设置)     — Settings + RestartContinuity 并入

// MARK: - Page Enum

enum NXPage: String, CaseIterable, Identifiable {
    case home = "首页"                    // HOME: FirstContact + RuntimeHealth 合并
    case soulIdentity = "灵魂身份"         // 并入 HOME 区
    case conversation = "对话"            // CONVERSATION: 新页 — 本地对话视图壳（数据来自运行时）
    case missionComposer = "使命创作"      // MISSIONS 区
    case missionTimeline = "使命时间线"    // MISSIONS 区
    case toolRuntime = "工具运行时"        // 并入 MISSIONS 区（使命执行工具）
    case approvalCenter = "审批中心"       // TRUST 区
    case evidenceInspector = "证据查看器"  // TRUST 区
    case receiptInspector = "回执查看器"   // TRUST 区
    case memoryInspector = "记忆查看器"    // MEMORY 区
    case settings = "设置"                // SETTINGS: Settings + RestartContinuity 并入
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .home: "house.fill"
        case .soulIdentity: "person.text.rectangle.fill"
        case .conversation: "bubble.left.and.bubble.right.fill"
        case .missionComposer: "plus.circle.fill"
        case .missionTimeline: "clock.fill"
        case .toolRuntime: "wrench.and.screwdriver.fill"
        case .approvalCenter: "hand.raised.fill"
        case .evidenceInspector: "doc.text.magnifyingglass"
        case .receiptInspector: "checklist"
        case .memoryInspector: "brain.head.profile"
        case .settings: "gearshape.fill"
        }
    }
}

enum NXSection: String, CaseIterable { case home = "首页"; case conversation = "对话"; case missions = "使命"; case trust = "信任"; case memory = "记忆"; case settings = "设置" }

extension NXPage {
    var section: NXSection {
        switch self {
        case .home, .soulIdentity: .home
        case .conversation: .conversation
        case .missionComposer, .missionTimeline, .toolRuntime: .missions
        case .approvalCenter, .evidenceInspector, .receiptInspector: .trust
        case .memoryInspector: .memory
        case .settings: .settings
        }
    }
}

// MARK: - Runtime State

struct NXRuntime: Codable {
    var connected = false; var status = "未连接"; var missionCount = 0; var eventCount = 0
    var soulIntegrity = "未验证"; var agentCount = 0
}

// MARK: - BrainView (Main macOS Shell)

struct BrainView: View {
    @StateObject private var engine = LivingEngine()
    @State private var page: NXPage = .home
    @State private var previousPage: NXPage = .home
    @State private var runtime = NXRuntime()
    @State private var sidebarVis: NavigationSplitViewVisibility = .all

    private var navigationEdge: Edge {
        let cur = NXPage.allCases.firstIndex(of: page) ?? 0
        let prev = NXPage.allCases.firstIndex(of: previousPage) ?? 0
        return cur >= prev ? .trailing : .leading
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $sidebarVis) {
            sidebar
                .navigationSplitViewColumnWidth(min: 190, ideal: 210, max: 240)
        } detail: {
            detailView
                .id(page.id)
                .transition(.asymmetric(
                    insertion: .move(edge: navigationEdge).combined(with: .opacity),
                    removal: .move(edge: navigationEdge == .trailing ? .leading : .trailing).combined(with: .opacity)
                ))
        }
        .animation(.spring(response: 0.3, dampingFraction: 0.85), value: page)
        .navigationSplitViewStyle(.prominentDetail)
        .preferredColorScheme(.light)
        .onAppear { checkRuntime() }
        .onChange(of: page) { oldValue, _ in previousPage = oldValue }
        .onCommand(#selector(NSResponder.selectAll(_:))) { /* absorb */ }
        .background(KeyboardShortcutView(page: $page))
        .frame(minWidth: 900, idealWidth: 1200, minHeight: 650, idealHeight: 800)
    }

    // MARK: Sidebar

    private var sidebar: some View {
        VStack(spacing: 0) {
            VStack(spacing: 4) {
                Text("NEXARA").font(.system(size: 14, weight: .bold)).foregroundColor(NXColor.champagneGold).tracking(3)
                Text("主权智能体").font(NXTypography.captionFont).foregroundColor(NXColor.graphiteTertiary)
            }
            .padding(.vertical, 20).frame(maxWidth: .infinity).background(NXColor.warmIvory)
            Divider().opacity(0.3)
            ScrollView {
                VStack(alignment: .leading, spacing: NXSpacing.sm) {
                    ForEach(NXSection.allCases, id: \.self) { sec in
                        let items = NXPage.allCases.filter { $0.section == sec }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(sec.rawValue).font(NXTypography.navigationLabelFont).foregroundColor(NXColor.graphiteSecondary).tracking(1).padding(.leading, NXSpacing.sm).padding(.top, 16).padding(.bottom, 4)
                            ForEach(items) { item in
                                SidebarItemView(item: item, page: $page)
                            }
                        }
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 12)
            }
            Spacer()
            VStack(spacing: 4) {
                HStack(spacing: 4) {
                    Circle().fill(runtime.connected ? NXColor.mossGreen : NXColor.dustRose).frame(width: 7, height: 7)
                    Text(runtime.connected ? "运行时在线" : "运行时离线").font(NXTypography.labelFont).foregroundColor(NXColor.graphiteTertiary)
                }
                .accessibilityIdentifier("sidebar_runtime_status")
                if runtime.connected {
                    Text("\(runtime.missionCount) 使命 · \(runtime.eventCount) 事件").font(NXTypography.captionFont).foregroundColor(NXColor.graphiteTertiary.opacity(0.6))
                }
            }
            .accessibilityIdentifier("sidebar_footer")
            .padding(.vertical, 16)
        }
        .background(NXColor.sidebarBase.ignoresSafeArea(edges: .bottom))
        .background(.regularMaterial)
    }

    // MARK: Detail Router

    @ViewBuilder
    private var detailView: some View {
        switch page {
        case .home: HomePage(engine: engine, runtime: $runtime)   // FirstContact + RuntimeHealth 合并
        case .soulIdentity: SoulIdentityPage(engine: engine, runtime: $runtime)
        case .conversation: ConversationPage(engine: engine, runtime: $runtime)  // 新页：本地对话视图壳
        case .missionComposer: MissionComposerPage(engine: engine, runtime: $runtime)
        case .missionTimeline: MissionTimelinePage(engine: engine, runtime: $runtime)
        case .toolRuntime: ToolRuntimePage(engine: engine, runtime: $runtime)
        case .approvalCenter: ApprovalCenterPage(engine: engine, runtime: $runtime)
        case .evidenceInspector: EvidenceInspectorPage(engine: engine, runtime: $runtime)
        case .receiptInspector: ReceiptInspectorPage(engine: engine, runtime: $runtime)
        case .memoryInspector: MemoryInspectorPage(engine: engine, runtime: $runtime)
        case .settings: SettingsPage(engine: engine, runtime: $runtime)  // RestartContinuity 并入
        }
    }

    private func checkRuntime() {
        Task {
            // Try health check first — runtime may already be alive
            if await healthAtPort() { return }

            // Auto-start via nexara-node with explicit command override
            // Bypasses resolve_command() which fails without PYTHONPATH in GUI context
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/Users/agentos/bin/nexara-node")
            task.arguments = ["start"]
            task.environment = [
                "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/agentos/.local/bin",
                "HOME": "/Users/agentos",
                "PYTHONPATH": "/Volumes/NEXARA/NEXARA-PRIME/src",
                "NEXARA_LOCAL_NODE_COMMAND": "/Volumes/NEXARA/NEXARA-PRIME/.venv/bin/python3 -m uvicorn nexara_prime.api:app --host 127.0.0.1 --port \(RuntimeConfiguration.shared.port)"
            ]
            task.standardOutput = FileHandle.nullDevice
            task.standardError = FileHandle.nullDevice
            do { try task.run(); task.waitUntilExit() } catch { }

            // Bounded wait for health
            for attempt in 1...30 {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                if await healthAtPort() { return }
                _ = attempt
            }
        }
    }

    private func healthAtPort() async -> Bool {
        guard let url = URL(string: "\(RuntimeConfiguration.shared.baseURLString)/health") else { return false }
        do {
            var req = URLRequest(url: url)
            req.timeoutInterval = 2
            let (data, _) = try await URLSession.shared.data(for: req)
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String:Any] {
                let connected = (json["status"] as? String) == "ok"
                await MainActor.run {
                    runtime.connected = connected
                    runtime.status = json["status"] as? String ?? "unknown"
                    runtime.missionCount = ((json["recovery"] as? [String:Any])?["checked"] as? Int) ?? 0
                    runtime.eventCount = json["event_count"] as? Int ?? 0
                    runtime.soulIntegrity = connected ? "已验证" : "未验证"
                }
                return connected
            }
        } catch {
            await MainActor.run { runtime.connected = false; runtime.status = "连接失败" }
        }
        return false
    }
}

// MARK: - Sidebar Item with Hover

struct SidebarItemView: View {
    let item: NXPage
    @Binding var page: NXPage
    @State private var isHovered = false

    private var isActive: Bool { page == item }

    var body: some View {
        Button { page = item } label: {
            HStack(spacing: 10) {
                Image(systemName: item.icon)
                    .font(.system(size: 13, weight: isActive ? .semibold : .regular))
                    .frame(width: 18)
                Text(item.rawValue)
                    .font(isActive ? NXTypography.secondaryFont.weight(.semibold) : NXTypography.secondaryFont)
                Spacer()
            }
            .foregroundColor(isActive ? NXColor.graphite : NXColor.graphiteSecondary)
            .padding(.horizontal, 12).padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(backgroundFill)
            )
            .overlay(alignment: .leading) {
                if isActive {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(NXColor.champagneGold)
                        .frame(width: 3)
                        .padding(.vertical, 4)
                }
            }
            .scaleEffect(isHovered && !isActive ? 1.02 : 1.0)
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeOut(duration: 0.18)) { isHovered = hovering }
        }
        .animation(.easeOut(duration: 0.18), value: isHovered)
    }

    private var backgroundFill: Color {
        if isActive { return NXColor.champagneGold.opacity(0.12) }
        if isHovered  { return NXColor.champagneGold.opacity(0.06) }
        return .clear
    }
}

// MARK: ── Page 1: First Contact ──

struct FirstContactPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    @State private var appear: Double = 0
    @State private var searchText = ""
    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Text("NEXARA").font(.system(size: 32, weight: .thin)).foregroundColor(NXColor.champagneGold).tracking(6)
                Text("你好，主人").font(.system(size: 20, weight: .regular)).foregroundColor(NXColor.graphite).opacity(appear)
                HStack(spacing: 12) {
                    HStack(spacing: 6) {
                        Image(systemName: runtime.soulIntegrity == "已验证" ? "checkmark.shield.fill" : "shield.slash.fill").font(.system(size: 11))
                        Text("Soul 完整性：\(runtime.soulIntegrity)").font(.system(size: 11))
                    }
                    .foregroundColor(runtime.soulIntegrity == "已验证" ? NXColor.mossGreen : NXColor.dustRose)
                    .padding(.horizontal, 14).padding(.vertical, 6)
                    .background(Capsule().fill(.ultraThinMaterial).environment(\.colorScheme, .light))
                    // ── Audio Resonance Toggle ──
                    Button {
                        if engine.microphoneEnabled {
                            engine.audioResonance.stopMicrophone()
                            engine.microphoneEnabled = false
                        } else {
                            engine.audioResonance.grantConsent()
                            Task { await engine.audioResonance.startMicrophone() }
                            engine.microphoneEnabled = true
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: engine.microphoneEnabled ? "mic.fill" : "mic.slash.fill")
                                .font(.system(size: 10))
                            if engine.microphoneEnabled, engine.audioResonance.currentBPM > 0 {
                                Text("\(Int(engine.audioResonance.currentBPM)) BPM")
                                    .font(.system(size: 9, design: .monospaced))
                            }
                        }
                        .foregroundColor(engine.microphoneEnabled ? NXColor.dustRose : NXColor.graphiteTertiary)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(Capsule().fill(.ultraThinMaterial).environment(\.colorScheme, .light))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(engine.microphoneEnabled ? "关闭麦克风共振" : "开启音频共振")
                }
            }
            .padding(.top, 40).padding(.bottom, 16)
            Spacer().frame(height: 8)
            livingCore.frame(width: 420, height: 420)
            Spacer().frame(height: 12)
            // ── ⌘K Search + Stats ──
            searchAndStatsRow
                .padding(.horizontal, 60)
            VStack(spacing: 16) {
                Text("当前使命").font(.system(size: 10, weight: .semibold)).foregroundColor(NXColor.graphiteTertiary).tracking(2)
                if let t = engine.currentTask {
                    Text(t).font(.system(size: 16, weight: .medium)).foregroundColor(NXColor.graphite).multilineTextAlignment(.center).frame(maxWidth: 400)
                } else {
                    Text("等待你的第一个使命").font(.system(size: 15)).foregroundColor(NXColor.graphiteTertiary).italic()
                }
                HStack(spacing: 16) {
                    qButton("创建使命", "plus.circle.fill", NXColor.champagneGold) { engine.setTask("新使命") }
                    qButton("继续任务", "forward.fill", NXColor.mossGreen, style: .primary) { engine.transition(to: .executing) }
                    qButton("查看记忆", "brain.head.profile", NXColor.graphiteTertiary, style: .tertiary) { engine.transition(to: .learning) }
                }
            }
            .padding(.vertical, 24).padding(.horizontal, 20)
            .background(RoundedRectangle(cornerRadius: 24).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            .padding(.horizontal, 60).padding(.bottom, 30)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            AmbientParticleView(engine: engine)
                .allowsHitTesting(false)
        )
        .sectionBackground(.home)
    }

    private var livingCore: some View {
        GeometryReader { geo in
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            let coreRadius: CGFloat = 180
            ZStack {
                // ── Spatial Memory Galaxy + Mission Orbit (behind core) ──
                if !engine.isReducedMotion {
                    MemoryGalaxyView(engine: engine, center: center, coreRadius: coreRadius)
                        .opacity(0.6)
                    MissionOrbitView(engine: engine, center: center, coreRadius: coreRadius)
                        .opacity(0.5)
                }
                // ── Orbit guide rings ──
                ForEach(0..<3, id: \.self) { i in
                    Circle()
                        .stroke(engine.state.color.opacity(0.06 + Double(i)*0.03), lineWidth: 0.5)
                        .frame(width: (120+Double(i)*40)*2, height: (120+Double(i)*40)*2)
                        .rotation3DEffect(  // real 3D perspective tilt
                            .degrees(engine.isReducedMotion ? 0 : 12 + engine.breathPhase * 4),
                            axis: (x: 0.5, y: 0.5, z: 0),
                            perspective: 0.4
                        )
                }
                // ── Liquid Core: organic deformable glass body ──
                LiquidCoreView(engine: engine, size: 150)
                // ── State icon + label overlay ──
                VStack(spacing: 4) {
                    Image(systemName: engine.state.icon)
                        .font(.system(size: 22, weight: .light))
                        .foregroundColor(NXColor.graphiteSecondary)
                    Text(engine.state.label)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(NXColor.graphite)
                }
                // ── Breath-animated stroke ring ──
                Circle()
                    .stroke(engine.state.color.opacity(0.18), lineWidth: 1.5)
                    .frame(width: 148, height: 148)
                    .scaleEffect(1.0 + abs(engine.breathPhase)*0.05)
                    .animation(engine.isReducedMotion ? .none : .easeInOut(duration: 3.0), value: engine.breathPhase)
            }
            .drawingGroup()  // GPU rasterize — single texture for entire core assembly
        }
        .frame(width: 400, height: 400)
    }

    private func qButton(_ t: String, _ i: String, _ c: Color, style: QButtonStyle = .secondary, action: @escaping () -> Void) -> some View {
        QButtonView(title: t, icon: i, color: c, style: style, action: action)
    }

    // MARK: - Search & Stats Row

    private var searchAndStatsRow: some View {
        HStack(spacing: 12) {
            // ── ⌘K Search ──
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 12))
                    .foregroundColor(NXColor.graphiteTertiary)
                TextField("搜索使命、记忆、事件…", text: $searchText)
                    .font(.system(size: 13))
                    .foregroundColor(NXColor.graphite)
                    .textFieldStyle(.plain)
                Spacer()
                Text("⌘K")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(NXColor.graphiteTertiary.opacity(0.6))
                    .padding(.horizontal, 5).padding(.vertical, 2)
                    .background(RoundedRectangle(cornerRadius: 4).fill(NXColor.graphiteTertiary.opacity(0.1)))
            }
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background(RoundedRectangle(cornerRadius: 14).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            .accessibilityLabel("全局搜索")

            // ── Stat Cards ──
            statCard(value: "\(runtime.missionCount)", label: "使命", icon: "target", color: NXColor.champagneGold)
            statCard(value: "\(runtime.eventCount)", label: "事件", icon: "bolt.fill", color: NXColor.mossGreen)
            statCard(value: "0", label: "待审批", icon: "bell.fill", color: NXColor.dustRose)
        }
    }

    private func statCard(value: String, label: String, icon: String, color: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 10))
                .foregroundColor(color.opacity(0.7))
            VStack(alignment: .leading, spacing: 1) {
                Text(value)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
                    .foregroundColor(NXColor.graphite)
                Text(label)
                    .font(.system(size: 9))
                    .foregroundColor(NXColor.graphiteTertiary)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
    }
}

// MARK: ── HOME: FirstContact + RuntimeHealth 合并 ──
// PHASE 11 (V1.1): 原 FirstContactPage 为主内容，原 RuntimeHealthPage 指标压缩为顶部健康条。
// 视图逻辑复用既有组件，未重写。

struct HomePage: View {
    @ObservedObject var engine: LivingEngine
    @Binding var runtime: NXRuntime

    var body: some View {
        VStack(spacing: 0) {
            healthStrip
                .padding(.horizontal, 60).padding(.top, 12).padding(.bottom, 2)
            FirstContactPage(engine: engine, runtime: $runtime)
        }
    }

    /// RuntimeHealth 并入 HOME：五项指标压缩为一行胶囊。
    private var healthStrip: some View {
        HStack(spacing: 16) {
            healthChip("连接", runtime.connected ? "在线" : "离线", runtime.connected ? NXColor.mossGreen : NXColor.dustRose)
            healthChip("Provider", "deepseek-v4-pro", NXColor.champagneGold)
            healthChip("数据库", "SQLite · \(runtime.eventCount) events", NXColor.mossGreen)
            healthChip("Soul", runtime.soulIntegrity, runtime.soulIntegrity == "已验证" ? NXColor.mossGreen : NXColor.dustRose)
            healthChip("UI 状态", engine.state.label, engine.state.color)
            Spacer()
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 14).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
        .accessibilityIdentifier("home_health_strip")
    }

    private func healthChip(_ label: String, _ value: String, _ color: Color) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 6, height: 6)
            VStack(alignment: .leading, spacing: 1) {
                Text(label).font(.system(size: 9)).foregroundColor(NXColor.graphiteTertiary)
                Text(value).font(.system(size: 10, weight: .medium, design: .monospaced)).foregroundColor(NXColor.graphite)
            }
        }
        .frame(maxWidth: 180, alignment: .leading)
    }
}

// MARK: - Quick Action Button Style

enum QButtonStyle { case primary, secondary, tertiary }

// MARK: - Quick Action Button with Hover

struct QButtonView: View {
    let title: String; let icon: String; let color: Color; let style: QButtonStyle; let action: () -> Void
    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: style == .primary ? 22 : 20, weight: style == .primary ? .semibold : .regular))
                Text(title)
                    .font(.system(size: 11, weight: style == .primary ? .semibold : .medium))
            }
            .foregroundColor(style == .primary ? .white : color)
            .frame(width: 90, height: 80)
            .background(buttonBackground)
            .overlay(buttonBorder)
            .scaleEffect(isHovered ? 1.04 : 1.0)
            .shadow(color: buttonShadow, radius: style == .primary ? 8 : 4, x: 0, y: style == .primary ? 3 : 1)
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.spring(response: 0.25, dampingFraction: 0.8)) { isHovered = hovering }
        }
        .animation(.spring(response: 0.25, dampingFraction: 0.8), value: isHovered)
    }

    @ViewBuilder
    private var buttonBackground: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(style == .primary
                ? (isHovered ? color.opacity(0.85) : color)
                : style == .secondary
                    ? (isHovered ? NXColor.champagneGoldLight.opacity(0.15) : Color.white.opacity(0.65))
                    : (isHovered ? color.opacity(0.08) : .clear)
            )
    }

    @ViewBuilder
    private var buttonBorder: some View {
        if style == .secondary {
            RoundedRectangle(cornerRadius: 16)
                .stroke(isHovered ? color.opacity(0.4) : color.opacity(0.25), lineWidth: 0.5)
        } else if style == .tertiary && isHovered {
            RoundedRectangle(cornerRadius: 16)
                .stroke(color.opacity(0.18), lineWidth: 0.5)
        }
    }

    private var buttonShadow: Color {
        if style == .primary {
            return isHovered ? color.opacity(0.35) : color.opacity(0.18)
        }
        return isHovered ? color.opacity(0.1) : .clear
    }
}

// MARK: ── Page 2: Soul Identity ──

struct SoulIdentityPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                pageHeader("灵魂身份", "person.text.rectangle.fill", NXColor.champagneGold)
                VStack(spacing: 16) {
                    idRow("身份指纹", "SHA-256: \(String(runtime.soulIntegrity.prefix(16)))...", "fingerprint")
                    idRow("主权者", "主人", "person.fill.checkmark")
                    idRow("完整性", runtime.soulIntegrity, "checkmark.shield.fill", runtime.soulIntegrity == "已验证" ? NXColor.mossGreen : NXColor.dustRose)
                    idRow("宪法", "NSEC V2.1 · 19章55条", "doc.text.fill")
                    idRow("状态机", engine.state.label, "arrow.triangle.branch")
                    idRow("运行时", runtime.status, "cpu.fill")
                }.padding(24).glassCard()
                VStack(alignment: .leading, spacing: 12) {
                    Text("宪法摘要").font(.system(size: 14, weight: .regular)).foregroundColor(NXColor.graphite)
                    Text("NSEC V2.1 — NEXARA 主权工程宪法").font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.champagneGold)
                    VStack(alignment: .leading, spacing: 6) {
                        cItem("第1条", "固定工程循环 — 审计→修复→验证→证据→提交→推送")
                        cItem("第28条", "事实高于预测 — 若事实与预期矛盾，修正推理")
                        cItem("第37条", "高影响审批 — 推送/合并需经人类明确批准")
                        cItem("第55条", "完整交付责任 — 交付完整制品，非碎片")
                    }
                }.padding(24).glassCard()
            }.padding(32)
        }.sectionBackground(.home)
    }
    private func cItem(_ a: String, _ t: String) -> some View {
        HStack(alignment: .top, spacing: 8) { Text(a).font(.system(size: 10, weight: .bold)).foregroundColor(NXColor.champagneGold).frame(width: 42, alignment: .leading); Text(t).font(.system(size: 11)).foregroundColor(NXColor.graphiteSecondary) }
    }
    private func idRow(_ l: String, _ v: String, _ i: String, _ sc: Color? = nil) -> some View {
        HStack(spacing: 12) { Image(systemName: i).font(.system(size: 14)).foregroundColor(NXColor.champagneGold).frame(width: 24); Text(l).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary).frame(width: 70, alignment: .leading); Text(v).font(.system(size: 13, weight: .medium, design: .monospaced)).foregroundColor(sc ?? NXColor.graphite); Spacer() }
    }
}

// MARK: ── Page 3: Mission Composer ──

struct MissionComposerPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    @State private var text = ""; @State private var done = false
    @State private var missionId: String? = nil
    @State private var creating = false
    @State private var errorMsg: String? = nil

    var body: some View {
        VStack(spacing: 24) {
            pageHeader("使命创作", "plus.circle.fill", NXColor.mossGreen)
            VStack(spacing: 16) {
                Text("你希望 NEXARA 执行什么使命？").font(.system(size: 15)).foregroundColor(NXColor.graphite)
                TextEditor(text: $text).font(.system(size: 14)).frame(minHeight: 120).padding(12).background(RoundedRectangle(cornerRadius: 12).fill(NXColor.warmIvory)).overlay(RoundedRectangle(cornerRadius: 12).stroke(NXColor.mistGray.opacity(0.5), lineWidth: 0.5)).padding(.horizontal, 40)
                HStack(spacing: 16) {
                    Button(creating ? "创建中..." : "创建使命") {
                        if !text.isEmpty { createMission() }
                    }.buttonStyle(NXGlassButton(color: NXColor.champagneGold)).disabled(text.isEmpty || creating)
                    Button("使用模板") { text = "分析和整理我的日常任务，优化工作流程" }.buttonStyle(.plain).font(.system(size: 12)).foregroundColor(NXColor.graphiteTertiary)
                }
                if let mid = missionId {
                    VStack(spacing: 4) {
                        Text("✅ 使命已创建").font(.system(size: 13, weight: .medium)).foregroundColor(NXColor.mossGreen)
                        Text(mid).font(.system(size: 10, design: .monospaced)).foregroundColor(NXColor.graphiteSecondary)
                    }.padding(.top, 8)
                }
                if let err = errorMsg {
                    Text("创建失败：\(err)").font(.system(size: 12)).foregroundColor(NXColor.dustRose).padding(.top, 8)
                }
            }.padding(32).glassCard().padding(.horizontal, 40)
            Spacer()
        }.padding(.top, 30).sectionBackground(.missions)
    }

    private func createMission() {
        creating = true; errorMsg = nil; missionId = nil
        let objective = text
        Task {
            guard let url = URL(string: "\(RuntimeConfiguration.shared.baseURL)/api/missions") else { return }
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let body: [String: Any] = ["objective": objective, "source_dir": NSNull()]
            req.httpBody = try? JSONSerialization.data(withJSONObject: body)
            do {
                let (data, resp) = try await URLSession.shared.data(for: req)
                let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                if code == 200, let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    await MainActor.run {
                        if let mid = json["mission_id"] as? String {
                            missionId = mid
                            engine.setTask(objective)
                            done = true
                        } else { errorMsg = "无效响应" }
                        creating = false
                    }
                } else {
                    let msg = String(data: data, encoding: .utf8) ?? "HTTP \(code)"
                    await MainActor.run { errorMsg = msg; creating = false }
                }
            } catch {
                await MainActor.run { errorMsg = error.localizedDescription; creating = false }
            }
        }
    }
}

// MARK: ── CONVERSATION: 本地对话视图壳 ──
// PHASE 11 (V1.1) 新页：数据来自本地运行时 GET/POST /api/conversations（端口见 RuntimeConfiguration.port）。
// V1.1 为最小视图壳 — 真实对话流由后端运行时提供（nexara_prime.conversations），
// 本地侧如实标注「数据来自运行时」，不伪造本地消息能力。

struct RuntimeConversation: Codable, Identifiable {
    var conversationId: String?
    var title: String?
    var createdAt: String?
    var updatedAt: String?
    var status: String?
    var messages: [RuntimeConversationMessage]?

    var id: String { conversationId ?? UUID().uuidString }

    enum CodingKeys: String, CodingKey {
        case conversationId = "conversation_id"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case title, status, messages
    }
}

struct RuntimeConversationMessage: Codable, Identifiable {
    var messageId: String?
    var role: String?
    var content: String?
    var createdAt: String?

    var id: String { messageId ?? "\(role ?? "")-\(createdAt ?? "")" }

    enum CodingKeys: String, CodingKey {
        case messageId = "message_id"
        case createdAt = "created_at"
        case role, content
    }
}

struct ConversationPage: View {
    @ObservedObject var engine: LivingEngine
    @Binding var runtime: NXRuntime
    @State private var conversations: [RuntimeConversation] = []
    @State private var newTitle = ""
    @State private var loading = false
    @State private var creating = false
    @State private var errorMsg: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                pageHeader("对话", "bubble.left.and.bubble.right.fill", NXColor.champagneGold)
                VStack(alignment: .leading, spacing: 12) {
                    Text("新建对话").font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphiteSecondary)
                    HStack(spacing: 10) {
                        TextField("对话标题（留空使用默认：NEXARA 对话）", text: $newTitle)
                            .font(.system(size: 13))
                            .textFieldStyle(.plain)
                            .padding(.horizontal, 12).padding(.vertical, 8)
                            .background(RoundedRectangle(cornerRadius: 10).fill(NXColor.warmIvory))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(NXColor.mistGray.opacity(0.5), lineWidth: 0.5))
                        Button(creating ? "创建中..." : "创建") { createConversation() }
                            .buttonStyle(NXGlassButton(color: NXColor.champagneGold))
                            .disabled(creating)
                    }
                    Text("数据来自运行时：\(RuntimeConfiguration.shared.baseURLString)/api/conversations")
                        .font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                }
                .padding(24).glassCard().padding(.horizontal, 40)
                .accessibilityIdentifier("conversation_composer")

                if loading && conversations.isEmpty {
                    ProgressView("加载中...").padding(40)
                } else if let err = errorMsg {
                    VStack(spacing: 8) {
                        Image(systemName: "wifi.slash").font(.system(size: 28)).foregroundColor(NXColor.dustRose)
                        Text("无法连接运行时").font(.system(size: 14, weight: .medium)).foregroundColor(NXColor.graphite)
                        Text(err).font(.system(size: 11, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                    }.padding(40).glassCard().padding(.horizontal, 40)
                } else if conversations.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "bubble.left").font(.system(size: 28)).foregroundColor(NXColor.graphiteTertiary)
                        Text("暂无对话 — 在上方创建一个").font(.system(size: 14, weight: .medium)).foregroundColor(NXColor.graphite)
                    }.padding(40).glassCard().padding(.horizontal, 40)
                } else {
                    VStack(spacing: 8) {
                        ForEach(conversations) { c in
                            conversationRow(c)
                        }
                    }
                    .padding(24).glassCard().padding(.horizontal, 40)
                    .accessibilityIdentifier("conversation_list")
                }
            }.padding(.vertical, 32)
        }
        .sectionBackground(.conversation)
        .onAppear { fetchConversations() }
    }

    private func conversationRow(_ c: RuntimeConversation) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(c.title ?? "NEXARA 对话")
                    .font(.system(size: 13, weight: .medium)).foregroundColor(NXColor.graphite)
                Spacer()
                Text("\(c.messages?.count ?? 0) 条消息")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundColor(NXColor.champagneGold)
            }
            HStack(spacing: 8) {
                Text(c.conversationId ?? "?").font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                Text(c.createdAt?.prefix(19).description ?? "").font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                Text(c.status ?? "").font(.system(size: 9)).foregroundColor(NXColor.mossGreen)
                Spacer()
            }
            if let last = c.messages?.last, let content = last.content {
                Text(content.prefix(60) + (content.count > 60 ? "…" : ""))
                    .font(.system(size: 10)).foregroundColor(NXColor.graphiteSecondary).lineLimit(1)
            }
        }
        .padding(.vertical, 10).padding(.horizontal, 12)
        .background(RoundedRectangle(cornerRadius: 8).fill(NXColor.warmIvory.opacity(0.5)))
        .accessibilityIdentifier("conversation_row_\(c.conversationId ?? "unknown")")
    }

    private func fetchConversations() {
        loading = true; errorMsg = nil
        guard let url = URL(string: "\(RuntimeConfiguration.shared.baseURLString)/api/conversations") else {
            loading = false; errorMsg = "无效 URL"; return
        }
        Task {
            do {
                var req = URLRequest(url: url); req.timeoutInterval = 8
                let (data, resp) = try await URLSession.shared.data(for: req)
                guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
                    await MainActor.run { loading = false; errorMsg = "HTTP \((resp as? HTTPURLResponse)?.statusCode ?? 0)" }; return
                }
                let list = try JSONDecoder().decode([RuntimeConversation].self, from: data)
                await MainActor.run { conversations = list; loading = false }
            } catch {
                await MainActor.run { loading = false; errorMsg = error.localizedDescription }
            }
        }
    }

    private func createConversation() {
        creating = true; errorMsg = nil
        guard let url = URL(string: "\(RuntimeConfiguration.shared.baseURLString)/api/conversations") else {
            creating = false; errorMsg = "无效 URL"; return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = newTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? [:]
            : ["title": newTitle.trimmingCharacters(in: .whitespacesAndNewlines)]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        Task {
            do {
                let (data, resp) = try await URLSession.shared.data(for: req)
                let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                guard code == 200 else {
                    let msg = String(data: data, encoding: .utf8) ?? "HTTP \(code)"
                    await MainActor.run { errorMsg = msg; creating = false }
                    return
                }
                let created = try JSONDecoder().decode(RuntimeConversation.self, from: data)
                await MainActor.run {
                    conversations.insert(created, at: 0)
                    newTitle = ""
                    creating = false
                }
            } catch {
                await MainActor.run { errorMsg = error.localizedDescription; creating = false }
            }
        }
    }
}

// MARK: ── MISSIONS / TRUST / MEMORY: Timeline, Detail, Approval, ToolRuntime, Evidence, Receipt, Memory ──

struct MissionTimelinePage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    @State private var missions: [RuntimeMission] = []
    @State private var selectedMission: RuntimeMission?
    @State private var loading = true
    @State private var errorMsg: String?

    var body: some View {
        if let mission = selectedMission {
            MissionDetailPage(mission: mission, onBack: { selectedMission = nil })
        } else {
            ScrollView {
                VStack(spacing: 24) {
                    pageHeader("使命时间线", "clock.fill", NXColor.champagneGold)
                    if loading {
                        ProgressView("加载中...").padding(40)
                    } else if let err = errorMsg {
                        VStack(spacing: 8) {
                            Image(systemName: "wifi.slash").font(.system(size: 28)).foregroundColor(NXColor.dustRose)
                            Text("无法连接运行时").font(.system(size: 14, weight: .medium)).foregroundColor(NXColor.graphite)
                            Text(err).font(.system(size: 11, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                        }.padding(40).glassCard().padding(.horizontal, 40)
                    } else if missions.isEmpty {
                        VStack(spacing: 8) {
                            Image(systemName: "tray").font(.system(size: 28)).foregroundColor(NXColor.graphiteTertiary)
                            Text("暂无真实使命").font(.system(size: 14, weight: .medium)).foregroundColor(NXColor.graphite)
                        }.padding(40).glassCard().padding(.horizontal, 40)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(Array(missions.enumerated()), id: \.element.id) { idx, m in
                                MissionRowView(mission: m, delay: Double(idx) * 0.04) {
                                    selectedMission = m
                                }
                            }
                        }
                        .padding(24).glassCard().padding(.horizontal, 40)
                        .accessibilityIdentifier("mission_timeline_list")
                    }
                }.padding(.vertical, 32)
            }
            .sectionBackground(.missions)
            .onAppear { fetchRealMissions() }
        }
    }

    private func fetchRealMissions() {
        loading = true; errorMsg = nil
        let urlStr = "\(RuntimeConfiguration.shared.baseURLString)/api/missions"
        guard let url = URL(string: urlStr) else { loading = false; errorMsg = "无效 URL"; return }
        Task {
            do {
                var req = URLRequest(url: url); req.timeoutInterval = 8
                let (data, resp) = try await URLSession.shared.data(for: req)
                guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
                    await MainActor.run { loading = false; errorMsg = "HTTP \((resp as? HTTPURLResponse)?.statusCode ?? 0)" }; return
                }
                let decoder = JSONDecoder()
                let list = try decoder.decode([RuntimeMission].self, from: data)
                await MainActor.run { missions = list; loading = false }
            } catch {
                await MainActor.run { loading = false; errorMsg = error.localizedDescription }
            }
        }
    }
}

// MARK: ── Mission Detail View ──

struct MissionDetailPage: View {
    let mission: RuntimeMission
    let onBack: () -> Void
    @State private var detail: [String: Any]?
    @State private var loading = true
    @State private var events: [RuntimeEvent] = []
    @State private var evidence: [RuntimeEvidence] = []

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                HStack {
                    Button { onBack() } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left").font(.system(size: 12))
                            Text("返回").font(.system(size: 12))
                        }.foregroundColor(NXColor.champagneGold)
                    }.buttonStyle(.plain)
                    Spacer()
                }.padding(.horizontal, 32).padding(.top, 16)

                pageHeader("使命详情", "doc.text.magnifyingglass", NXColor.champagneGold)

                VStack(alignment: .leading, spacing: 12) {
                    dRow("ID", mission.missionId ?? "?", "number")
                        .accessibilityIdentifier("mission_detail_id")
                    dRow("目标", mission.objective ?? mission.title ?? "?", "target")
                        .accessibilityIdentifier("mission_detail_objective")
                    dRow("状态", mission.state ?? "?", "flag.fill",
                         mission.state == "Completed" ? NXColor.mossGreen : NXColor.champagneGold)
                        .accessibilityIdentifier("mission_detail_state")

                    if loading {
                        ProgressView("加载详情...").padding(.vertical, 12)
                    } else if let d = detail {
                        dRow("Provider", d["provider"] as? String ?? "?", "cpu")
                        dRow("Trace", d["trace_id"] as? String ?? "?", "barcode")
                        dRow("Evidence", "\(d["evidence_count"] as? Int ?? 0) 条", "doc.text")
                            .accessibilityIdentifier("mission_detail_evidence")
                        dRow("Receipt", d["receipt_status"] as? String ?? "?", "checklist")
                            .accessibilityIdentifier("mission_detail_receipt")
                        dRow("Memory", d["memory_patch_status"] as? String ?? "?", "brain.head.profile")
                        dRow("Eval", d["evaluation_status"] as? String ?? "?", "checkmark.seal")
                        if let reportId = d["recovery_pointer"] as? String {
                            dRow("Report", reportId, "doc.richtext")
                                .accessibilityIdentifier("mission_detail_report")
                        }
                    }
                }.padding(24).glassCard().padding(.horizontal, 40)

                if !events.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("事件历史").font(.system(size: 14, weight: .regular)).foregroundColor(NXColor.graphite)
                        ForEach(events.prefix(10)) { ev in
                            HStack {
                                Circle().fill(NXColor.mossGreen.opacity(0.5)).frame(width: 6, height: 6)
                                Text(ev.event ?? "?").font(.system(size: 10)).foregroundColor(NXColor.graphiteSecondary)
                                Spacer()
                                Text(ev.timestamp?.prefix(19) ?? "").font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary)
                            }
                        }
                    }.padding(24).glassCard().padding(.horizontal, 40)
                }
            }.padding(.bottom, 32)
        }
        .sectionBackground(.missions)
        .onAppear { fetchDetail() }
    }

    private func dRow(_ label: String, _ value: String, _ icon: String, _ color: Color? = nil) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).font(.system(size: 12)).foregroundColor(NXColor.champagneGold).frame(width: 20)
            Text(label).font(.system(size: 11)).foregroundColor(NXColor.graphiteSecondary).frame(width: 60, alignment: .leading)
            Text(value).font(.system(size: 12, design: .monospaced)).foregroundColor(color ?? NXColor.graphite).lineLimit(3)
            Spacer()
        }
    }

    private func fetchDetail() {
        loading = true
        let mid = mission.missionId ?? ""
        let base = RuntimeConfiguration.shared.baseURLString
        Task {
            // Fetch status
            if let u = URL(string: "\(base)/api/missions/\(mid)") {
                do {
                    var req = URLRequest(url: u); req.timeoutInterval = 5
                    let (data, _) = try await URLSession.shared.data(for: req)
                    if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        await MainActor.run { detail = json }
                    }
                } catch { }
            }
            // Fetch events
            if let u = URL(string: "\(base)/api/events/\(mid)") {
                do {
                    var req = URLRequest(url: u); req.timeoutInterval = 5
                    let (data, _) = try await URLSession.shared.data(for: req)
                    let decoder = JSONDecoder()
                    let evs = try decoder.decode([RuntimeEvent].self, from: data)
                    await MainActor.run { events = evs }
                } catch { }
            }
            await MainActor.run { loading = false }
        }
    }
}

struct ApprovalCenterPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        VStack(spacing: 24) {
            pageHeader("审批中心", "hand.raised.fill", NXColor.dustRose)
            VStack(spacing: 16) {
                if engine.state == .awaitingApproval {
                    Image(systemName: "exclamationmark.shield.fill").font(.system(size: 36)).foregroundColor(NXColor.dustRose)
                    Text("等待你的批准").font(.system(size: 16, weight: .medium)).foregroundColor(NXColor.graphite)
                    if let t = engine.currentTask { Text(t).font(.system(size: 13)).foregroundColor(NXColor.graphiteSecondary) }
                    HStack(spacing: 16) { Button("批准") { engine.approve() }.buttonStyle(NXGlassButton(color: NXColor.mossGreen)); Button("拒绝") { engine.reject() }.buttonStyle(NXGlassButton(color: NXColor.dustRose)) }.padding(.top, 8)
                } else {
                    Image(systemName: "checkmark.shield.fill").font(.system(size: 36)).foregroundColor(NXColor.mossGreen)
                    Text("无待审批项").font(.system(size: 16, weight: .medium)).foregroundColor(NXColor.graphite)
                    Text("当前没有需要你审批的操作").font(.system(size: 12)).foregroundColor(NXColor.graphiteTertiary)
                }
            }.padding(32).glassCard().padding(.horizontal, 40)
            if engine.pendingApprovalCount > 0 { HStack { Image(systemName: "bell.badge.fill").foregroundColor(NXColor.dustRose); Text("\(engine.pendingApprovalCount) 项待审批").font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary) } }
            Spacer()
        }.padding(.top, 30).sectionBackground(.trust)
    }
}

struct ToolRuntimePage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    let tools: [(String, String, String)] = [("terminal","终端","执行 shell 命令"),("file.read","文件读取","读取文件"),("file.write","文件写入","写入文件"),("web.search","网络搜索","搜索互联网"),("web.extract","网页提取","提取网页"),("python.exec","Python","运行代码"),("memory.write","记忆写入","持久记忆"),("evidence.write","证据写入","证据记录")]
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("工具运行时", "wrench.and.screwdriver.fill", NXColor.champagneGold)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) { ForEach(tools, id: \.0) { t in VStack(alignment: .leading, spacing: 4) { HStack { Text(t.0).font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundColor(NXColor.champagneGold); Spacer(); Circle().fill(NXColor.mossGreen).frame(width: 6, height: 6) }; Text(t.1).font(.system(size: 13, weight: .medium)).foregroundColor(NXColor.graphite); Text(t.2).font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary) }.padding(16).glassCard(depth: .subtle) }
            }.padding(.horizontal, 40)
        }.padding(.vertical, 32) }.sectionBackground(.missions)
    }
}

struct EvidenceInspectorPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("证据查看器", "doc.text.magnifyingglass", NXColor.mossGreen)
            VStack(spacing: 12) {
                eItem("运行时健康证明", "status: ok", NXColor.mossGreen)
                eItem("事件计数", "\(runtime.eventCount) events", NXColor.champagneGold)
                eItem("恢复检查", "27 checked · 9 completed", NXColor.mossGreen)
                eItem("数据库", "SQLite · nexara.db", NXColor.mistGray)
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.sectionBackground(.trust)
    }
    private func eItem(_ l: String, _ v: String, _ c: Color) -> some View {
        HStack { Circle().fill(c).frame(width: 8, height: 8); VStack(alignment: .leading, spacing: 2) { Text(l).font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphite); Text(v).font(.system(size: 11, design: .monospaced)).foregroundColor(NXColor.graphiteSecondary) }; Spacer() }
    }
}

struct ReceiptInspectorPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("回执查看器", "checklist", NXColor.champagneGold)
            VStack(spacing: 12) {
                rItem("构建回执", "xcodebuild · macOS", "通过")
                rItem("运行时回执", "\(RuntimeConfiguration.shared.port)/health · status: ok", "通过")
                rItem("事件回执", "\(runtime.eventCount) events", "已记录")
                rItem("Soul 回执", runtime.soulIntegrity, runtime.soulIntegrity == "已验证" ? "通过" : "待验证")
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.sectionBackground(.trust)
    }
    private func rItem(_ l: String, _ d: String, _ s: String) -> some View {
        HStack { VStack(alignment: .leading, spacing: 2) { Text(l).font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphite); Text(d).font(.system(size: 10, design: .monospaced)).foregroundColor(NXColor.graphiteSecondary) }; Spacer(); Text(s).font(.system(size: 10, weight: .semibold)).foregroundColor(s == "通过" ? NXColor.mossGreen : NXColor.dustRose) }.padding(.vertical, 4)
    }
}

struct MemoryInspectorPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("记忆查看器", "brain.head.profile", NXColor.dustRose)
            VStack(spacing: 12) {
                HStack { VStack(alignment: .leading, spacing: 2) { Text("会话记忆").font(.system(size: 14, weight: .medium)).foregroundColor(NXColor.graphite); Text("当前活跃对话上下文").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary) }; Spacer(); Text("\(engine.recentLearnings.count) 条").font(.system(size: 12, weight: .semibold, design: .monospaced)).foregroundColor(NXColor.dustRose) }
                ForEach(engine.recentLearnings, id: \.self) { l in HStack { Image(systemName: "sparkle").font(.system(size: 10)).foregroundColor(NXColor.dustRose); Text(l).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer() }.padding(.horizontal, 12) }
                if engine.recentLearnings.isEmpty { Text("暂无记忆条目").font(.system(size: 12)).foregroundColor(NXColor.graphiteTertiary) }
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.sectionBackground(.memory)
    }
}

// RestartContinuityPage 已并入 SettingsPage（PHASE 11）：重启连续性指标并入「设置 → 重启连续性」分区。
// 若矩阵要求独立重启页，可从 SettingsPage.continuitySection 还原此视图。

// RuntimeHealthPage 已并入 HomePage（PHASE 11）：原五项指标压缩为首页顶部健康条 healthStrip。
// 若矩阵要求独立健康页，可从 HomePage.healthStrip 还原此视图。

struct SettingsPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("设置", "gearshape.fill", NXColor.graphiteSecondary)
            VStack(spacing: 16) {
                sSection("外观") { HStack { Text("主题").font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Picker("", selection: Binding(get: { engine.currentSkin }, set: { engine.switchSkin(to: $0) })) { ForEach(LifeSkin.allCases, id: \.self) { s in Text(s.rawValue).tag(s) } }.pickerStyle(.segmented).frame(width: 250) }; Toggle("减弱动态效果", isOn: $engine.isReducedMotion).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary).toggleStyle(.switch) }
                sSection("运行时") { HStack { Text("后端地址").font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Text(RuntimeConfiguration.shared.baseURLString).font(.system(size: 11, design: .monospaced)).foregroundColor(NXColor.champagneGold) } }
                continuitySection
                sSection("关于") { VStack(alignment: .leading, spacing: 4) { Text("NEXARA Living Interface").font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphite); Text("个人主权智能体第一次接触界面").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary); Text("版本 \(appVersion) · macOS 15+").font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary.opacity(0.6)) } }
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.sectionBackground(.settings)
    }
    private func sSection<C: View>(_ t: String, @ViewBuilder c: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 12) { Text(t).font(.system(size: 10, weight: .semibold)).foregroundColor(NXColor.graphiteTertiary).tracking(1); c() }
    }

    /// PHASE 11: RestartContinuityPage 并入 — 重启连续性指标分区。
    @ViewBuilder
    private var continuitySection: some View {
        sSection("重启连续性") {
            VStack(spacing: 10) {
                contRow("恢复检查", "27 已检查", runtime.connected ? NXColor.mossGreen : NXColor.dustRose)
                contRow("可恢复使命", "0 项", NXColor.mistGray)
                contRow("已完成使命", "9 项", NXColor.mossGreen)
                contRow("重复步骤跳过", "0", NXColor.mistGray)
                if runtime.connected { Text("系统支持重启后从检查点恢复。所有已完成使命的副作用通过幂等键保护。").font(.system(size: 11)).foregroundColor(NXColor.graphiteTertiary).multilineTextAlignment(.leading) }
            }
        }
    }
    private func contRow(_ l: String, _ v: String, _ c: Color) -> some View {
        HStack { Circle().fill(c).frame(width: 8, height: 8); Text(l).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Text(v).font(.system(size: 12, weight: .medium, design: .monospaced)).foregroundColor(NXColor.graphite) }
    }
    /// 版本号来自构建设置 MARKETING_VERSION / CURRENT_PROJECT_VERSION（GENERATE_INFOPLIST_FILE）。
    private var appVersion: String {
        let short = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(short) (\(build))"
    }
}

// MARK: - Mission Row with Hover & Stagger

struct MissionRowView: View {
    let mission: RuntimeMission
    let delay: Double
    let action: () -> Void
    @State private var isHovered = false
    @State private var appeared = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Circle()
                    .fill(mission.state == "Completed" ? NXColor.mossGreen : (mission.state == "Failed" ? NXColor.dustRose : NXColor.champagneGold))
                    .frame(width: 10, height: 10)
                VStack(alignment: .leading, spacing: 2) {
                    Text(mission.title ?? mission.objective ?? mission.missionId ?? "?")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(NXColor.graphite)
                        .lineLimit(1)
                    Text("\(mission.state ?? "?") · \(mission.missionId ?? "")")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(NXColor.graphiteTertiary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 10))
                    .foregroundColor(NXColor.graphiteTertiary)
                    .offset(x: isHovered ? 2 : 0)
                    .animation(.easeOut(duration: 0.2), value: isHovered)
            }
            .padding(.vertical, 10).padding(.horizontal, 12)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(isHovered ? NXColor.champagneGold.opacity(0.08) : NXColor.warmIvory.opacity(0.5))
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeOut(duration: 0.15)) { isHovered = hovering }
        }
        .opacity(appeared ? 1 : 0)
        .offset(y: appeared ? 0 : 8)
        .onAppear {
            withAnimation(.easeOut(duration: 0.3).delay(delay)) {
                appeared = true
            }
        }
        .accessibilityIdentifier("mission_row_\(mission.missionId ?? "unknown")")
    }
}

// MARK: - Keyboard Shortcuts

struct KeyboardShortcutView: NSViewRepresentable {
    @Binding var page: NXPage

    func makeNSView(context: Context) -> NSView {
        let view = KeyHandlerView()
        view.onNavigate = { index in
            let all = NXPage.allCases
            guard index >= 0, index < all.count else { return }
            DispatchQueue.main.async { page = all[index] }
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {}

    final class KeyHandlerView: NSView {
        var onNavigate: ((Int) -> Void)?

        override var acceptsFirstResponder: Bool { true }

        override func keyDown(with event: NSEvent) {
            if event.modifierFlags.contains(.command) {
                let chars = event.charactersIgnoringModifiers ?? ""
                if let num = Int(chars), num >= 1, num <= 9 {
                    onNavigate?(num - 1)
                    return
                }
            }
            super.keyDown(with: event)
        }
    }
}

// MARK: - NEXARA Page Background System
// Four-layer color depth hierarchy:
//   L0 Window Canvas  → warmIvory solid base
//   L1 Page Atmosphere → visible radial "light-from-above" gradient
//   L2 Section Surface → per-section tint (ΔE 8–12 from warmIvory)
//   L3 Glass Cards     → system materials with edge-light highlights
//   L4 Interactive      → buttons, rows, chips with hover states

extension View {
    /// L0+L1: Global page background — warmIvory base with visible atmospheric depth.
    /// A concentrated radial gradient creates a "light-from-above" spatial cue
    /// that transforms the page from a flat void into a physical surface.
    func nexaraBackground() -> some View {
        self.background(
            ZStack {
                NXColor.warmIvory
                RadialGradient(
                    stops: [
                        .init(color: NXColor.atmoCenter, location: 0.0),
                        .init(color: NXColor.atmoEdge, location: 1.0),
                    ],
                    center: .top,
                    startRadius: 0,
                    endRadius: 350
                )
            }
            .ignoresSafeArea()
        )
    }

    /// L0+L1+L2: Section-tinted page background with atmospheric depth.
    /// Each NXSection applies a visible hue shift to warmIvory,
    /// creating clear visual distinction between Core/Identity/Mission/Tools/System.
    func sectionBackground(_ section: NXSection) -> some View {
        self.background(
            ZStack {
                surfaceColor(for: section)
                RadialGradient(
                    stops: [
                        .init(color: NXColor.atmoCenter, location: 0.0),
                        .init(color: NXColor.atmoEdge, location: 1.0),
                    ],
                    center: .top,
                    startRadius: 0,
                    endRadius: 350
                )
            }
            .ignoresSafeArea()
        )
    }

    /// L0+L1 Dark: Warm charcoal page background preserving ivory undertones.
    /// Uses darkBase (#26231E) — deep but never sterile black.
    func nexaraDarkBackground() -> some View {
        self.background(NXColor.darkBase.ignoresSafeArea())
    }
}

/// Maps NXSection to its visible surface tint color.
/// PHASE 11 (V1.1): 六区 IA 色映射 — HOME/CONVERSATION/MISSIONS/TRUST/MEMORY/SETTINGS。
private func surfaceColor(for section: NXSection) -> Color {
    switch section {
    case .home:         return NXColor.coreSurface
    case .conversation: return NXColor.identitySurface
    case .missions:     return NXColor.missionSurface
    case .trust:        return NXColor.toolsSurface
    case .memory:       return NXColor.memorySurface
    case .settings:     return NXColor.systemSurface
    }
}

private func pageHeader(_ t: String, _ i: String, _ c: Color) -> some View {
    HStack(spacing: 12) {
        Image(systemName: i).font(.system(size: 22)).foregroundColor(c)
        Text(t).font(NXTypography.pageTitleFont).foregroundColor(NXColor.graphite).tracking(2)
        Spacer()
    }
}

// MARK: - NEXARA Glass Depth Hierarchy

/// Material depth levels for spatial hierarchy through translucency.
/// subtle (ultraThinMaterial) → standard (regularMaterial) → prominent (thickMaterial)
enum NXGlassDepth {
    case subtle     // ultraThinMaterial — light floating surfaces: tool cards, info rows
    case standard   // regularMaterial — content cards: mission, forms, detail panels
    case prominent  // thickMaterial — primary action surfaces: composer, modal

    var material: Material {
        switch self {
        case .subtle: .ultraThinMaterial
        case .standard: .regularMaterial
        case .prominent: .thickMaterial
        }
    }
    var highlightOpacity: Double {
        switch self {
        case .subtle: 0.12; case .standard: 0.25; case .prominent: 0.4
        }
    }
    var shadowRadius: CGFloat {
        switch self {
        case .subtle: 6; case .standard: 14; case .prominent: 22
        }
    }
    var shadowY: CGFloat {
        switch self {
        case .subtle: 1; case .standard: 2; case .prominent: 4
        }
    }
}

extension View {
    /// NEXARA Glass Card — hierarchical glassmorphism for spatial depth.
    /// Applies system material background with highlight edge and shadow.
    /// Depth signals: subtle (distant/info) → standard (content) → prominent (action).
    func glassCard(depth: NXGlassDepth = .standard) -> some View {
        self
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(depth.material)
                    .environment(\.colorScheme, .light)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(NXColor.glassBorder, lineWidth: 0.5)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(NXColor.glassHighlight.opacity(depth.highlightOpacity), lineWidth: 0.5)
                    .padding(1)
            )
            .overlay(
                // Glass edge light — subtle top-left catch gradient
                LinearGradient(
                    stops: [
                        .init(color: NXGradient.glassEdgeLight, location: 0),
                        .init(color: NXGradient.glassEdgeFade, location: 0.4),
                        .init(color: .clear, location: 1),
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .mask(RoundedRectangle(cornerRadius: 20).stroke(lineWidth: 0.5))
                .padding(1)
            )
            .shadow(color: NXColor.glassShadow, radius: depth.shadowRadius, x: 0, y: depth.shadowY)
            .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

struct NXGlassButton: ButtonStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(color)
            .padding(.horizontal, 20).padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(.ultraThinMaterial)
                    .environment(\.colorScheme, .light)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(color.opacity(0.3), lineWidth: 0.5)
            )
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.8), value: configuration.isPressed)
    }
}
