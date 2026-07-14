// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NexaraMac",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(path: "../NexaraCore"),
    ],
    targets: [
        .executableTarget(
            name: "NexaraMac",
            dependencies: ["NexaraCore"],
            path: "Sources/NexaraMac"
        ),
    ]
)
