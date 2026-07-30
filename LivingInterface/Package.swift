// swift-tools-version: 6.0
import PackageDescription

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
