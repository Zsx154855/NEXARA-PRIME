import SwiftUI

struct MissionTimeline: View {
    @ObservedObject var model: RuntimeViewModel
    @State private var selectedMission: MissionSummary?

    var body: some View {
        List(model.projection.missions) { mission in
            VStack(alignment: .leading, spacing: NXSpacing.xs) {
                HStack {
                    statusDot(mission.state)
                    Text(mission.objective).font(NXFont.body).foregroundColor(NXColor.graphite)
                    Spacer()
                    Text(mission.riskLevel).font(NXFont.caption).foregroundColor(riskColor(mission.riskLevel))
                }
                HStack {
                    Text(mission.state).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                    Text("·").foregroundColor(NXColor.graphiteSoft)
                    Text(mission.missionId).font(NXFont.code).foregroundColor(NXColor.graphiteSoft)
                    Spacer()
                    Text(mission.createdAt).font(NXFont.caption).foregroundColor(NXColor.graphiteSoft)
                }
            }
            .padding(.vertical, NXSpacing.xs)
            .onTapGesture { selectedMission = mission }
        }
        .scrollContentBackground(.hidden)
        .background(NXColor.ivory)
        .navigationTitle("Mission 时间线")
        .sheet(item: $selectedMission) { mission in
            missionDetail(mission)
        }
    }

    private func missionDetail(_ m: MissionSummary) -> some View {
        VStack(spacing: NXSpacing.lg) {
            Text(m.objective).font(NXFont.heading).foregroundColor(NXColor.graphite)
            Text("ID: \(m.missionId)").font(NXFont.code).foregroundColor(NXColor.graphiteSoft)
            Text("状态: \(m.state)").font(NXFont.body)
            Text("风险: \(m.riskLevel)").font(NXFont.body).foregroundColor(riskColor(m.riskLevel))
            Text("创建: \(m.createdAt)").font(NXFont.caption)
        }
        .padding()
        .frame(width: 400, height: 300)
        .background(NXColor.ivory)
    }

    private func statusDot(_ state: String) -> some View {
        let c: Color = {
            switch state {
            case "COMPLETED": return NXColor.moss
            case "EXECUTING": return .blue
            case "APPROVAL_REQUIRED": return NXColor.amber
            case "FAILED": return NXColor.rose
            default: return NXColor.graphiteSoft
            }
        }()
        return Circle().fill(c).frame(width: 8, height: 8)
    }

    private func riskColor(_ r: String) -> Color {
        switch r {
        case "R0", "R1": return NXColor.moss
        case "R2", "R3": return NXColor.amber
        case "R4": return NXColor.rose
        default: return NXColor.graphiteSoft
        }
    }
}
