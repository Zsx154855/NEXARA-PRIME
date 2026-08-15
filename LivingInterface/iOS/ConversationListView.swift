import SwiftUI

// MARK: - 对话 (Conversation) Zone — Phase 12 Six-Zone IA
// Reads real data from the local NEXARA runtime:
//   GET http://127.0.0.1:8765/api/conversations
// Contract source: src/nexara_prime/api.py → list_conversations()
// (ConversationStore records: conversation_id / title / created_at /
//  updated_at / status / message_ids, plus an inline `messages` payload
//  that is intentionally not consumed here.)
//
// Honest states only: loading / failed / empty / loaded. No local fake data.

enum ConversationAPI {
    static let baseURL = "http://127.0.0.1:8765"
    static let conversationsPath = "/api/conversations"
}

/// Mirror of the runtime ConversationStore record (conversations.py).
struct ConversationRecord: Decodable, Identifiable, Sendable {
    let conversationId: String
    let title: String
    let updatedAt: String
    let status: String
    let messageIds: [String]

    var id: String { conversationId }
}

private enum ConversationListError: LocalizedError {
    case invalidURL
    case invalidResponse
    case badStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL: "无效的对话接口地址"
        case .invalidResponse: "对话接口返回了无法识别的响应"
        case .badStatus(let code): "对话接口返回异常状态（HTTP \(code)）"
        }
    }
}

private enum ConversationLoadState: Equatable {
    case idle
    case loading
    case loaded
    case failed(String)
}

struct ConversationListView: View {
    @State private var loadState: ConversationLoadState = .idle
    @State private var conversations: [ConversationRecord] = []

    var body: some View {
        Group {
            switch loadState {
            case .idle, .loading:
                loadingView
            case .failed(let message):
                failureView(message)
            case .loaded where conversations.isEmpty:
                emptyView
            case .loaded:
                listView
            }
        }
        .task { await load() }
        .accessibilityIdentifier("living.zone.conversation")
    }

    // MARK: - Data Loading

    private func load() async {
        loadState = .loading
        do {
            conversations = try await fetchConversations()
            loadState = .loaded
        } catch {
            loadState = .failed(message(for: error))
        }
    }

    private func fetchConversations() async throws -> [ConversationRecord] {
        guard let url = URL(string: ConversationAPI.baseURL + ConversationAPI.conversationsPath) else {
            throw ConversationListError.invalidURL
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 10
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw ConversationListError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw ConversationListError.badStatus(http.statusCode)
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode([ConversationRecord].self, from: data)
    }

    private func message(for error: Error) -> String {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet, .timedOut:
                return "无法连接本地运行时（127.0.0.1:8765）——请确认 runtime 已启动。"
            default:
                return urlError.localizedDescription
            }
        }
        return error.localizedDescription
    }

    // MARK: - States

    private var loadingView: some View {
        VStack(spacing: NXSpacing.md) {
            ProgressView()
            NXTypography.secondary("正在连接本地运行时…")
                .foregroundColor(NXColor.graphiteSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func failureView(_ message: String) -> some View {
        VStack(spacing: NXSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 28))
                .foregroundColor(NXColor.rejectRed)
            NXTypography.secondary("对话加载失败")
                .foregroundColor(NXColor.graphite)
            NXTypography.label(message)
                .foregroundColor(NXColor.graphiteSecondary)
                .multilineTextAlignment(.center)
            GlassButton(label: "重试", icon: "arrow.clockwise", color: NXColor.graphite) {
                Task { await load() }
            }
        }
        .padding(NXSpacing.xl)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyView: some View {
        VStack(spacing: NXSpacing.md) {
            Image(systemName: "bubble.left")
                .font(.system(size: 28))
                .foregroundColor(NXColor.graphiteTertiary)
            NXTypography.secondary("暂无对话")
                .foregroundColor(NXColor.graphiteSecondary)
            NXTypography.label("新对话将出现在本地运行时中。")
                .foregroundColor(NXColor.graphiteTertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Loaded List

    private var listView: some View {
        ScrollView {
            LazyVStack(spacing: NXSpacing.md) {
                ForEach(conversations) { conversation in
                    conversationRow(conversation)
                }
            }
            .padding(.horizontal, NXSpacing.pageHorizontal)
            .padding(.vertical, NXSpacing.lg)
        }
        .refreshable { await load() }
    }

    private func conversationRow(_ conversation: ConversationRecord) -> some View {
        GlassSurface(level: .standard, cornerRadius: NXRadius.control) {
            VStack(alignment: .leading, spacing: NXSpacing.xs) {
                Text(conversation.title)
                    .font(NXTypography.secondaryFont.weight(.medium))
                    .foregroundColor(NXColor.graphite)
                    .lineLimit(2)
                HStack(spacing: NXSpacing.sm) {
                    Text(statusLabel(conversation.status))
                        .font(NXTypography.captionFont)
                        .foregroundColor(statusColor(conversation.status))
                    Spacer()
                    Text(formattedDate(conversation.updatedAt))
                        .font(NXTypography.captionFont)
                        .foregroundColor(NXColor.graphiteSecondary)
                }
            }
            .padding(NXSpacing.md)
        }
        .accessibilityElement(children: .combine)
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "open": return "进行中"
        case "closed": return "已结束"
        default: return status
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "open": return NXColor.mossGreen
        case "closed": return NXColor.graphiteSecondary
        default: return NXColor.pauseAmber
        }
    }

    // MARK: - Date Formatting

    private static let isoFormatter = ISO8601DateFormatter()
    private static let isoFractionalFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private func formattedDate(_ iso: String) -> String {
        for formatter in [Self.isoFormatter, Self.isoFractionalFormatter] {
            if let date = formatter.date(from: iso) {
                return date.formatted(.relative(presentation: .named))
            }
        }
        return iso
    }
}

#Preview {
    ConversationListView()
}
