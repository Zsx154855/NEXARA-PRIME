// swift-tools-version: 6.0
import PackageDescription

// PHASE 11 (V1.1) 平台统一记录:
// xcodeproj MACOSX_DEPLOYMENT_TARGET 已由 26.0 对齐为本文件 .macOS(.v15)（macOS 15.0）。
// 若未来恢复 macOS 26+ 需求，需同步修改 project.pbxproj 的全部 MACOSX_DEPLOYMENT_TARGET。

let package = Package(
    name: "LivingInterface",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "NEXARA", targets: ["LivingInterface"]),
    ],
    targets: [
        .executableTarget(
            name: "LivingInterface",
            path: "Sources/LivingInterface"
        ),
    ]
)
