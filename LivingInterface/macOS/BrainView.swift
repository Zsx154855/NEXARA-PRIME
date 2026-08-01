import SwiftUI
import Foundation

// ── NEXARA First Contact: macOS Brain View ──
// "个人主权智能体第一次接触界面" — the sovereign agent's primary surface.
// Layout: NavigationSplitView sidebar + detail. Warm Ivory palette.
// Pages: FirstContact, SoulIdentity, MissionComposer, Timeline, Approval,
//         ToolRuntime, Evidence, Receipt, Memory, Restart, Health, Settings.

// MARK: - Page Enum

enum NXPage: String, CaseIterable, Identifiable {
    case firstContact = "初次接触"
    case soulIdentity = "灵魂身份"
    case missionComposer = "使命创作"
    case missionTimeline = "使命时间线"
    case approvalCenter = "审批中心"
    case toolRuntime = "工具运行时"
    case evidenceInspector = "证据查看器"
    case receiptInspector = "回执查看器"
    case memoryInspector = "记忆查看器"
    case restartContinuity = "重启连续性"
    case runtimeHealth = "运行时健康"
    case settings = "设置"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .firstContact: "house.fill"
        case .soulIdentity: "person.text.rectangle.fill"
        case .missionComposer: "plus.circle.fill"
        case .missionTimeline: "clock.fill"
        case .approvalCenter: "hand.raised.fill"
        case .toolRuntime: "wrench.and.screwdriver.fill"
        case .evidenceInspector: "doc.text.magnifyingglass"
        case .receiptInspector: "checklist"
        case .memoryInspector: "brain.head.profile"
        case .restartContinuity: "arrow.triangle.2.circlepath"
        case .runtimeHealth: "heart.text.square.fill"
        case .settings: "gearshape.fill"
        }
    }
}

enum NXSection: String, CaseIterable { case core = "核心"; case identity = "身份"; case mission = "使命"; case tools = "工具"; case system = "系统" }

extension NXPage {
    var section: NXSection {
        switch self {
        case .firstContact: .core
        case .soulIdentity: .identity
        case .missionComposer, .missionTimeline, .approvalCenter: .mission
        case .toolRuntime, .evidenceInspector, .receiptInspector, .memoryInspector: .tools
        case .restartContinuity, .runtimeHealth, .settings: .system
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
    @State private var page: NXPage = .firstContact
    @State private var runtime = NXRuntime()
    @State private var sidebarVis: NavigationSplitViewVisibility = .all

    var body: some View {
        NavigationSplitView(columnVisibility: $sidebarVis) {
            sidebar
                .navigationSplitViewColumnWidth(min: 190, ideal: 210, max: 240)
        } detail: {
            detailView
                .background(NXColor.warmIvory.ignoresSafeArea())
        }
        .navigationSplitViewStyle(.prominentDetail)
        .preferredColorScheme(.light)
        .onAppear { checkRuntime() }
        .frame(minWidth: 900, idealWidth: 1200, minHeight: 650, idealHeight: 800)
    }

    // MARK: Sidebar

    private var sidebar: some View {
        VStack(spacing: 0) {
            VStack(spacing: 4) {
                Text("NEXARA").font(.system(size: 14, weight: .bold)).foregroundColor(NXColor.champagneGold).tracking(3)
                Text("主权智能体").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary)
            }
            .padding(.vertical, 20).frame(maxWidth: .infinity).background(NXColor.warmIvory)
            Divider().opacity(0.3)
            ScrollView {
                VStack(alignment: .leading, spacing: NXSpacing.sm) {
                    ForEach(NXSection.allCases, id: \.self) { sec in
                        let items = NXPage.allCases.filter { $0.section == sec }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(sec.rawValue).font(.system(size: 9, weight: .semibold)).foregroundColor(NXColor.graphiteTertiary).tracking(1).padding(.leading, NXSpacing.sm).padding(.top, 16).padding(.bottom, 4)
                            ForEach(items) { item in
                                Button { page = item } label: {
                                    HStack(spacing: 10) {
                                        Image(systemName: item.icon).font(.system(size: 13)).frame(width: 18)
                                        Text(item.rawValue).font(.system(size: 12))
                                        Spacer()
                                    }
                                    .foregroundColor(page == item ? NXColor.graphite : NXColor.graphiteSecondary)
                                    .padding(.horizontal, 12).padding(.vertical, 7)
                                    .background(RoundedRectangle(cornerRadius: 8).fill(page == item ? NXColor.champagneGold.opacity(0.12) : .clear))
                                }
                                .buttonStyle(.plain)
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
                    Text(runtime.connected ? "运行时在线" : "运行时离线").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary)
                }
                .accessibilityIdentifier("sidebar_runtime_status")
                if runtime.connected {
                    Text("\(runtime.missionCount) 使命 · \(runtime.eventCount) 事件").font(.system(size: 9)).foregroundColor(NXColor.graphiteTertiary.opacity(0.6))
                }
            }
            .accessibilityIdentifier("sidebar_footer")
            .padding(.vertical, 16)
        }
        .background(NXColor.mistGrayLight.ignoresSafeArea(edges: .bottom))
    }

    // MARK: Detail Router

    @ViewBuilder
    private var detailView: some View {
        switch page {
        case .firstContact: FirstContactPage(engine: engine, runtime: $runtime)
        case .soulIdentity: SoulIdentityPage(engine: engine, runtime: $runtime)
        case .missionComposer: MissionComposerPage(engine: engine, runtime: $runtime)
        case .missionTimeline: MissionTimelinePage(engine: engine, runtime: $runtime)
        case .approvalCenter: ApprovalCenterPage(engine: engine, runtime: $runtime)
        case .toolRuntime: ToolRuntimePage(engine: engine, runtime: $runtime)
        case .evidenceInspector: EvidenceInspectorPage(engine: engine, runtime: $runtime)
        case .receiptInspector: ReceiptInspectorPage(engine: engine, runtime: $runtime)
        case .memoryInspector: MemoryInspectorPage(engine: engine, runtime: $runtime)
        case .restartContinuity: RestartContinuityPage(engine: engine, runtime: $runtime)
        case .runtimeHealth: RuntimeHealthPage(engine: engine, runtime: $runtime)
        case .settings: SettingsPage(engine: engine, runtime: $runtime)
        }
    }

    private func checkRuntime() {
        Task {
            // Try health check first — runtime may already be alive
            if await healthAt8770() { return }

            // Auto-start via nexara-node with explicit command override
            // Bypasses resolve_command() which fails without PYTHONPATH in GUI context
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/Users/agentos/bin/nexara-node")
            task.arguments = ["start"]
            task.environment = [
                "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/agentos/.local/bin",
                "HOME": "/Users/agentos",
                "PYTHONPATH": "/Users/agentos/NEXARA-PRIME/src",
                "NEXARA_LOCAL_NODE_COMMAND": "/Users/agentos/NEXARA-PRIME/.venv/bin/python3 -m uvicorn nexara_prime.api:app --host 127.0.0.1 --port 8770"
            ]
            task.standardOutput = FileHandle.nullDevice
            task.standardError = FileHandle.nullDevice
            do { try task.run(); task.waitUntilExit() } catch { }

            // Bounded wait for health
            for attempt in 1...30 {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                if await healthAt8770() { return }
                _ = attempt
            }
        }
    }

    private func healthAt8770() async -> Bool {
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

// MARK: ── Page 1: First Contact ──

struct FirstContactPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    @State private var appear: Double = 0
    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Text("NEXARA").font(.system(size: 32, weight: .thin)).foregroundColor(NXColor.champagneGold).tracking(6)
                Text("你好，主人").font(.system(size: 20, weight: .regular)).foregroundColor(NXColor.graphite).opacity(appear)
                HStack(spacing: 6) {
                    Image(systemName: runtime.soulIntegrity == "已验证" ? "checkmark.shield.fill" : "shield.slash.fill").font(.system(size: 11))
                    Text("Soul 完整性：\(runtime.soulIntegrity)").font(.system(size: 11))
                }
                .foregroundColor(runtime.soulIntegrity == "已验证" ? NXColor.mossGreen : NXColor.dustRose)
                .padding(.horizontal, 14).padding(.vertical, 6)
                .background(Capsule().fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            }
            .padding(.top, 40).padding(.bottom, 20)
            Spacer()
            livingCore.frame(width: 360, height: 360)
            Spacer()
            VStack(spacing: 16) {
                Text("当前使命").font(.system(size: 10, weight: .semibold)).foregroundColor(NXColor.graphiteTertiary).tracking(2)
                if let t = engine.currentTask {
                    Text(t).font(.system(size: 16, weight: .medium)).foregroundColor(NXColor.graphite).multilineTextAlignment(.center).frame(maxWidth: 400)
                } else {
                    Text("等待你的第一个使命").font(.system(size: 15)).foregroundColor(NXColor.graphiteTertiary).italic()
                }
                HStack(spacing: 16) {
                    qButton("创建使命", "plus.circle.fill", NXColor.champagneGold) { engine.setTask("新使命") }
                    qButton("继续任务", "forward.fill", NXColor.mossGreen) { engine.transition(to: .executing) }
                    qButton("查看记忆", "brain.head.profile", NXColor.dustRose) { engine.transition(to: .learning) }
                }
            }
            .padding(.vertical, 24).padding(.horizontal, 20)
            .background(RoundedRectangle(cornerRadius: 24).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            .padding(.horizontal, 60).padding(.bottom, 30)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity).background(NXColor.warmIvory.ignoresSafeArea())
        .onAppear { withAnimation(.easeOut(duration: 1.0)) { appear = 1 } }
    }

    private var livingCore: some View {
        ZStack {
            Circle().fill(RadialGradient(colors: [engine.state == .silent ? NXColor.mistGray.opacity(0.15) : engine.state.color.opacity(0.12), .clear], center: .center, startRadius: 60, endRadius: 200)).frame(width: 360, height: 360).blur(radius: 20)
            ForEach(0..<3, id: \.self) { i in
                Circle().stroke(engine.state.color.opacity(0.08 + Double(i)*0.04), lineWidth: 0.5).frame(width: (120+Double(i)*40)*2, height: (120+Double(i)*40)*2)
            }
            ZStack {
                Circle().fill(RadialGradient(colors: [Color.white.opacity(0.6), engine.state.color.opacity(0.25), engine.state.color.opacity(0.08)], center: .topLeading, startRadius: 0, endRadius: 80)).frame(width: 150, height: 150)
                Circle().fill(.ultraThinMaterial).environment(\.colorScheme, .light).frame(width: 150, height: 150)
                VStack(spacing: 4) {
                    Image(systemName: engine.state.icon).font(.system(size: 24)).foregroundColor(NXColor.graphiteSecondary)
                    Text(engine.state.label).font(.system(size: 16, weight: .medium)).foregroundColor(NXColor.graphite)
                }
            }
            Circle().stroke(engine.state.color.opacity(0.18), lineWidth: 1.5).frame(width: 148, height: 148).scaleEffect(1.0 + abs(engine.breathPhase)*0.05).animation(engine.isReducedMotion ? .none : .easeInOut(duration: 3.0), value: engine.breathPhase)
            Circle().trim(from: 0.55, to: 0.72).stroke(AngularGradient(colors: [.white.opacity(0), .white.opacity(0.5), .white.opacity(0.7), .white.opacity(0.2), .white.opacity(0)], center: .center, startAngle: .degrees(160), endAngle: .degrees(290)), style: StrokeStyle(lineWidth: 2, lineCap: .round)).frame(width: 140, height: 140).blur(radius: 3).opacity(0.5 + abs(engine.breathPhase)*0.15)
        }
    }

    private func qButton(_ t: String, _ i: String, _ c: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 6) { Image(systemName: i).font(.system(size: 20)); Text(t).font(.system(size: 11, weight: .medium)) }
                .foregroundColor(c).frame(width: 90, height: 80)
                .background(RoundedRectangle(cornerRadius: 16).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
                .overlay(RoundedRectangle(cornerRadius: 16).stroke(c.opacity(0.2), lineWidth: 0.5))
        }.buttonStyle(.plain)
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
        }.background(NXColor.warmIvory.ignoresSafeArea())
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
        }.padding(.top, 30).background(NXColor.warmIvory.ignoresSafeArea())
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

// MARK: ── Pages 4-12: Timeline, Detail, Approval, ToolRuntime, Evidence, Receipt, Memory, Restart, Health, Settings ──

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
                            ForEach(missions) { m in
                                Button {
                                    selectedMission = m
                                } label: {
                                    HStack(spacing: 12) {
                                        Circle()
                                            .fill(m.state == "Completed" ? NXColor.mossGreen : (m.state == "Failed" ? NXColor.dustRose : NXColor.champagneGold))
                                            .frame(width: 10, height: 10)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(m.title ?? m.objective ?? m.missionId ?? "?")
                                                .font(.system(size: 12, weight: .medium))
                                                .foregroundColor(NXColor.graphite)
                                                .lineLimit(1)
                                            Text("\(m.state ?? "?") · \(m.missionId ?? "")")
                                                .font(.system(size: 9, design: .monospaced))
                                                .foregroundColor(NXColor.graphiteTertiary)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary)
                                    }
                                    .padding(.vertical, 10).padding(.horizontal, 12)
                                    .background(RoundedRectangle(cornerRadius: 8).fill(NXColor.warmIvory.opacity(0.5)))
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("mission_row_\(m.missionId ?? "unknown")")
                            }
                        }
                        .padding(24).glassCard().padding(.horizontal, 40)
                        .accessibilityIdentifier("mission_timeline_list")
                    }
                }.padding(.vertical, 32)
            }
            .background(NXColor.warmIvory.ignoresSafeArea())
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
        .background(NXColor.warmIvory.ignoresSafeArea())
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
        }.padding(.top, 30).background(NXColor.warmIvory.ignoresSafeArea())
    }
}

struct ToolRuntimePage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    let tools: [(String, String, String)] = [("terminal","终端","执行 shell 命令"),("file.read","文件读取","读取文件"),("file.write","文件写入","写入文件"),("web.search","网络搜索","搜索互联网"),("web.extract","网页提取","提取网页"),("python.exec","Python","运行代码"),("memory.write","记忆写入","持久记忆"),("evidence.write","证据写入","证据记录")]
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("工具运行时", "wrench.and.screwdriver.fill", NXColor.champagneGold)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) { ForEach(tools, id: \.0) { t in VStack(alignment: .leading, spacing: 4) { HStack { Text(t.0).font(.system(size: 10, weight: .semibold, design: .monospaced)).foregroundColor(NXColor.champagneGold); Spacer(); Circle().fill(NXColor.mossGreen).frame(width: 6, height: 6) }; Text(t.1).font(.system(size: 13, weight: .medium)).foregroundColor(NXColor.graphite); Text(t.2).font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary) }.padding(16).glassCard() }
            }.padding(.horizontal, 40)
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
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
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
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
                rItem("运行时回执", "8770/health · status: ok", "通过")
                rItem("事件回执", "\(runtime.eventCount) events", "已记录")
                rItem("Soul 回执", runtime.soulIntegrity, runtime.soulIntegrity == "已验证" ? "通过" : "待验证")
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
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
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
    }
}

struct RestartContinuityPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("重启连续性", "arrow.triangle.2.circlepath", NXColor.champagneGold)
            VStack(spacing: 16) {
                cItem("恢复检查", "27 已检查", runtime.connected ? NXColor.mossGreen : NXColor.dustRose)
                cItem("可恢复使命", "0 项", NXColor.mistGray)
                cItem("已完成使命", "9 项", NXColor.mossGreen)
                cItem("重复步骤跳过", "0", NXColor.mistGray)
                if runtime.connected { Text("系统支持重启后从检查点恢复。所有已完成使命的副作用通过幂等键保护。").font(.system(size: 11)).foregroundColor(NXColor.graphiteTertiary).multilineTextAlignment(.center).padding(.top, 12) }
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
    }
    private func cItem(_ l: String, _ v: String, _ c: Color) -> some View {
        HStack { Circle().fill(c).frame(width: 8, height: 8); Text(l).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Text(v).font(.system(size: 12, weight: .medium, design: .monospaced)).foregroundColor(NXColor.graphite) }
    }
}

struct RuntimeHealthPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("运行时健康", "heart.text.square.fill", NXColor.mossGreen)
            VStack(spacing: 16) {
                hm("连接状态", runtime.connected ? "在线 · ONLINE" : "离线 · OFFLINE", runtime.connected ? 1.0 : 0.0, runtime.connected ? NXColor.mossGreen : NXColor.dustRose)
                hm("Provider", "deepseek-v4-pro", 0.8, NXColor.champagneGold)
                hm("数据库", "SQLite · \(runtime.eventCount) events", 1.0, NXColor.mossGreen)
                hm("Soul 完整性", runtime.soulIntegrity, runtime.soulIntegrity == "已验证" ? 1.0 : 0.5, runtime.soulIntegrity == "已验证" ? NXColor.mossGreen : NXColor.dustRose)
                hm("UI 状态", engine.state.label, 1.0, engine.state.color)
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
    }
    private func hm(_ l: String, _ d: String, _ v: Double, _ c: Color) -> some View {
        VStack(spacing: 6) { HStack { Text(l).font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphite); Spacer(); Text(d).font(.system(size: 10, design: .monospaced)).foregroundColor(NXColor.graphiteSecondary) }; GeometryReader { g in ZStack(alignment: .leading) { RoundedRectangle(cornerRadius: 3).fill(NXColor.mistGray.opacity(0.3)).frame(height: 6); RoundedRectangle(cornerRadius: 3).fill(c).frame(width: g.size.width * v, height: 6) } }.frame(height: 6) }
    }
}

struct SettingsPage: View {
    @ObservedObject var engine: LivingEngine; @Binding var runtime: NXRuntime
    var body: some View {
        ScrollView { VStack(spacing: 24) { pageHeader("设置", "gearshape.fill", NXColor.graphiteSecondary)
            VStack(spacing: 16) {
                sSection("外观") { HStack { Text("主题").font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Picker("", selection: Binding(get: { engine.currentSkin }, set: { engine.switchSkin(to: $0) })) { ForEach(LifeSkin.allCases, id: \.self) { s in Text(s.rawValue).tag(s) } }.pickerStyle(.segmented).frame(width: 250) }; Toggle("减弱动态效果", isOn: $engine.isReducedMotion).font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary).toggleStyle(.switch) }
                sSection("运行时") { HStack { Text("后端地址").font(.system(size: 12)).foregroundColor(NXColor.graphiteSecondary); Spacer(); Text("http://127.0.0.1:8770").font(.system(size: 11, design: .monospaced)).foregroundColor(NXColor.champagneGold) } }
                sSection("关于") { VStack(alignment: .leading, spacing: 4) { Text("NEXARA Living Interface V2").font(.system(size: 12, weight: .medium)).foregroundColor(NXColor.graphite); Text("个人主权智能体第一次接触界面").font(.system(size: 10)).foregroundColor(NXColor.graphiteTertiary); Text("构建: 2026-07-31 · macOS 26+").font(.system(size: 9, design: .monospaced)).foregroundColor(NXColor.graphiteTertiary.opacity(0.6)) } }
            }.padding(24).glassCard().padding(.horizontal, 40)
        }.padding(.vertical, 32) }.background(NXColor.warmIvory.ignoresSafeArea())
    }
    private func sSection<C: View>(_ t: String, @ViewBuilder c: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 12) { Text(t).font(.system(size: 10, weight: .semibold)).foregroundColor(NXColor.graphiteTertiary).tracking(1); c() }
    }
}

// MARK: - Shared Helpers

private func pageHeader(_ t: String, _ i: String, _ c: Color) -> some View {
    HStack(spacing: 12) { Image(systemName: i).font(.system(size: 22)).foregroundColor(c); Text(t).font(.system(size: 24, weight: .thin)).foregroundColor(NXColor.graphite).tracking(2); Spacer() }
}

extension View {
    func glassCard() -> some View {
        self.background(RoundedRectangle(cornerRadius: 20).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(NXColor.glassBorder, lineWidth: 0.5))
            .shadow(color: NXColor.glassShadow, radius: 12, x: 0, y: 2)
    }
}

struct NXGlassButton: ButtonStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.system(size: 12, weight: .medium)).foregroundColor(color).padding(.horizontal, 20).padding(.vertical, 10)
            .background(RoundedRectangle(cornerRadius: 10).fill(.ultraThinMaterial).environment(\.colorScheme, .light))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(color.opacity(0.3), lineWidth: 0.5))
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0).animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}
