// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DevConsole",
    platforms: [.macOS("13.3")],
    targets: [
        .target(name: "ConsoleCore"),
        .executableTarget(name: "DevConsole", dependencies: ["ConsoleCore"]),
        .testTarget(name: "ConsoleCoreTests", dependencies: ["ConsoleCore"]),
    ]
)
