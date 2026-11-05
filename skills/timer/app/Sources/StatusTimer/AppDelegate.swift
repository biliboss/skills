import AppKit
import TimerCore
import UserNotifications

/// Display only. Watches the state file written by `scripts/timer.sh`; never writes it.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private var state = TimerState()
    private var watcher: DispatchSourceFileSystemObject?
    private var ticker: Timer?
    private var alerted = false

    private let stateDir: URL = {
        if let o = ProcessInfo.processInfo.environment["STATUS_TIMER_STATE_DIR"], !o.isEmpty {
            return URL(fileURLWithPath: o, isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/state/status-timer", isDirectory: true)
    }()
    private var stateFile: URL { stateDir.appendingPathComponent("state.json") }

    func applicationDidFinishLaunching(_ notification: Notification) {
        item.button?.font = .monospacedDigitSystemFont(ofSize: NSFont.systemFontSize, weight: .regular)
        try? FileManager.default.createDirectory(at: stateDir, withIntermediateDirectories: true)
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert]) { _, _ in }
        watchDirectory()
        reload()
    }

    /// kqueue on the directory fd: `mv` replaces the file, so the file itself would go stale.
    private func watchDirectory() {
        let fd = open(stateDir.path, O_EVTONLY)
        guard fd >= 0 else { return }
        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fd, eventMask: [.write, .rename, .delete], queue: .main)
        source.setEventHandler { [weak self] in
            MainActor.assumeIsolated { self?.reload() }
        }
        source.setCancelHandler { close(fd) }
        source.resume()
        watcher = source
    }

    private func reload() {
        state = TimerState.decode(try? Data(contentsOf: stateFile))
        alerted = false
        ticker?.invalidate()
        ticker = nil
        if state.status == .running {
            let t = Timer(timeInterval: 1, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.tick() }
            }
            RunLoop.main.add(t, forMode: .common)
            ticker = t
        }
        render()
        // Already past zero when the file is read (app started late): alert once.
        if state.isExpired(now: Date()) { tick() }
    }

    private func tick() {
        render()
        if state.isExpired(now: Date()) {
            ticker?.invalidate()
            ticker = nil
            if !alerted {
                alerted = true
                NSSound(named: "Glass")?.play()
                notify()
            }
        }
    }

    private func render() {
        guard let button = item.button else { return }
        switch display(for: state, now: Date()) {
        case .idle:
            button.title = ""
            button.image = NSImage(systemSymbolName: "timer", accessibilityDescription: "Timer")
        case .text(let text):
            button.image = nil
            button.title = text
        }
        button.toolTip = state.label.isEmpty ? nil : state.label
    }

    private func notify() {
        let content = UNMutableNotificationContent()
        content.title = "Tempo esgotado"
        content.body = state.label
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
    }
}
