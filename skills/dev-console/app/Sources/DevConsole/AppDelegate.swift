import AppKit
import ConsoleCore
import WebKit

/// One window, one WKWebView on the dev-console page. Reads `command.json` (written only by
/// `scripts/window.sh`) and is the only writer of `state.json`.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    private static let baseAutosaveName = "DevConsoleWindow"

    private var window: NSWindow!
    private var webView: WKWebView!
    private var watcher: DispatchSourceFileSystemObject?
    private var observations: [NSKeyValueObservation] = []
    private var gate = CommandGate()
    private var state = WindowState()
    private var pendingFrameWrite: DispatchWorkItem?
    private var idleTimer: Timer?
    private var palette: PaletteController!
    private let statusLine = StatusLineController()

    private let stateDir: URL = {
        if let o = ProcessInfo.processInfo.environment["DEV_CONSOLE_WINDOW_STATE_DIR"], !o.isEmpty {
            return URL(fileURLWithPath: o, isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/state/dev-console-window", isDirectory: true)
    }()
    /// One saved frame per state directory: a second window (an agent's own, window.sh --owner) must not
    /// inherit or overwrite the first one's place. The default directory keeps the original name.
    private var autosaveName: String {
        stateDir.lastPathComponent == "dev-console-window" ? Self.baseAutosaveName
            : "\(Self.baseAutosaveName).\(stateDir.lastPathComponent)"
    }
    private var stateFile: URL { stateDir.appendingPathComponent("state.json") }
    private var commandFile: URL { stateDir.appendingPathComponent("command.json") }

    private var defaultURL: URL {
        let text = ProcessInfo.processInfo.environment["DEV_CONSOLE_URL"] ?? "http://127.0.0.1:5057/"
        return URL(string: text) ?? URL(string: "http://127.0.0.1:5057/")!
    }

    // MARK: launch

    func applicationDidFinishLaunching(_ notification: Notification) {
        try? FileManager.default.createDirectory(at: stateDir, withIntermediateDirectories: true)
        // Start from the last id this app wrote, so a command.json left on disk is not replayed.
        state = WindowState.decode(try? Data(contentsOf: stateFile))
        gate = CommandGate(lastApplied: state.lastCommandId)

        buildMenu()
        buildWindow()
        palette = PaletteController(parent: { [weak self] in self?.window }, currentURL: { [weak self] in self?.webView.url ?? self?.defaultURL },
                                    open: { [weak self] in self?.webView.load(URLRequest(url: $0)) })
        statusLine.onPalette = { [weak self] in self?.palette.show($0) }
        watchDirectory()
        webView.load(URLRequest(url: state.url.flatMap(URL.init(string:)) ?? defaultURL))
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        syncWindowState()
        pollCommand()
        startIdleReports()
    }

    /// Every 5 s the page learns how long the Mac has been idle (the money bar stops its clock after 5 minutes).
    /// The page defines `window.devconsoleIdle` only when it has a bar; without it the script does nothing.
    private func startIdleReports() {
        idleTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.webView.evaluateJavaScript(idleScript(seconds: systemIdleSeconds()), completionHandler: nil)
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// A click on the Dock icon brings a hidden or closed window back.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { showWindow() }
        return true
    }

    private func buildWindow() {
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "devconsole")
        webView = WKWebView(frame: .zero, configuration: config)
        webView.isInspectable = true

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 960, height: 800),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.title = "Dev Console"
        window.contentView = statusLine.install(webView: webView)  // the chrome: the web view above, the status line under it
        // First launch only (no saved frame): two thirds of the screen, docked to the right.
        if !window.setFrameUsingName(autosaveName) {
            applyDock(.right)
        }
        window.setFrameAutosaveName(autosaveName)

        let nc = NotificationCenter.default
        for name in [NSWindow.didResizeNotification, NSWindow.didMoveNotification] {
            nc.addObserver(forName: name, object: window, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.scheduleWindowSync() }
            }
        }
        for name in [NSWindow.didMiniaturizeNotification, NSWindow.didDeminiaturizeNotification,
                     NSWindow.didChangeOcclusionStateNotification] {
            nc.addObserver(forName: name, object: window, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.syncWindowState() }
            }
        }
        nc.addObserver(forName: NSWindow.willCloseNotification, object: window, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.syncWindowState(visible: false) }
        }

        // KVO on webView.url catches in-page `pushState` changes too, not only navigations.
        observations.append(webView.observe(\.url, options: [.new]) { [weak self] _, _ in
            MainActor.assumeIsolated { self?.syncPage() }
        })
        observations.append(webView.observe(\.title, options: [.new]) { [weak self] _, _ in
            MainActor.assumeIsolated { self?.syncPage() }
        })
    }

    private func buildMenu() {
        let main = NSMenu()
        func add(_ title: String, _ items: [(String, Selector, String)]) {
            let host = NSMenuItem()
            let menu = NSMenu(title: title)
            for (t, sel, key) in items { menu.addItem(withTitle: t, action: sel, keyEquivalent: key) }
            host.submenu = menu
            main.addItem(host)
        }
        add("DevConsole", [("Quit DevConsole", #selector(NSApplication.terminate(_:)), "q")])
        add("Edit", [("Cut", #selector(NSText.cut(_:)), "x"), ("Copy", #selector(NSText.copy(_:)), "c"),
                     ("Paste", #selector(NSText.paste(_:)), "v"), ("Select All", #selector(NSText.selectAll(_:)), "a")])
        add("View", [("Reload", #selector(reloadAction), "r")])
        // ⌘P is Print in AppKit and the page's module switcher here; ⌘K is the domain switcher. No Print item exists, and the
        // menu owns both keys, so the page's overlays open and no print panel can.
        let overlays = NSMenuItem()
        let overlayMenu = NSMenu(title: "Go")
        for o in [PageOverlay.domains, PageOverlay.modules] {
            let item = NSMenuItem(title: o.title, action: #selector(openOverlay(_:)), keyEquivalent: o.keyEquivalent)
            item.target = self
            item.representedObject = o.rawValue
            overlayMenu.addItem(item)
        }
        overlays.submenu = overlayMenu
        main.addItem(overlays)
        add("Window", [("Close", #selector(NSWindow.performClose(_:)), "w"),
                       ("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m")])
        NSApp.mainMenu = main
    }

    @objc private func reloadAction() { webView.reload() }

    @objc private func openOverlay(_ sender: NSMenuItem) {
        // The palette is native chrome: the page's own overlays are off inside the app.
        guard let raw = sender.representedObject as? String, let overlay = PageOverlay(rawValue: raw) else { return }
        palette.toggle(overlay == .domains ? .domains : .modules)
    }

    // MARK: state out (the app is the only writer)

    private func syncPage() {
        state.url = webView.url?.absoluteString
        state.title = webView.title
        if let title = webView.title, !title.isEmpty { window.title = title }
        writeState()
    }

    private func scheduleWindowSync() {
        pendingFrameWrite?.cancel()
        let item = DispatchWorkItem { [weak self] in
            MainActor.assumeIsolated { self?.syncWindowState() }
        }
        pendingFrameWrite = item
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2, execute: item)
    }

    private func syncWindowState(visible: Bool? = nil) {
        state.visible = visible ?? (window.isVisible && !window.isMiniaturized)
        state.width = Double(window.frame.width)
        state.height = Double(window.frame.height)
        writeState()
    }

    private func writeState() {
        state.updatedAt = Date().timeIntervalSince1970
        guard let data = state.encoded() else { return }
        try? data.write(to: stateFile, options: .atomic)
    }

    // MARK: bridge page -> agent

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        // the status line's click on the domain or module asks for the native palette
        if let body = message.body as? [String: Any], body["palette"] != nil, let mode = (body["palette"] as? String).flatMap(PaletteMode.init(rawValue:)) {
            palette.show(mode)
            return
        }
        if statusLine.handle(message: message.body) { return }  // a status push is not an agent message
        state.lastMessage = JSONValue(any: message.body)
        writeState()
    }

    // MARK: commands in

    /// kqueue on the directory fd: `mv` replaces the file, so the file itself would go stale.
    private func watchDirectory() {
        let fd = open(stateDir.path, O_EVTONLY)
        guard fd >= 0 else { return }
        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fd, eventMask: [.write, .rename, .delete], queue: .main)
        source.setEventHandler { [weak self] in
            MainActor.assumeIsolated { self?.pollCommand() }
        }
        source.setCancelHandler { close(fd) }
        source.resume()
        watcher = source
    }

    /// Fires on every write in the directory, state.json included; the gate lets each id through once.
    private func pollCommand() {
        guard let command = WindowCommand.decode(try? Data(contentsOf: commandFile)) else { return }
        guard gate.accept(command) else { return }
        apply(command)
    }

    private func apply(_ command: WindowCommand) {
        if let problem = command.validationError() {
            finish(command, result: "error: \(problem)")
            return
        }
        switch command.action! {
        case .open:
            webView.load(URLRequest(url: URL(string: command.url!)!))
            showWindow()
            finish(command, result: "ok")
        case .reload:
            webView.reload()
            finish(command, result: "ok")
        case .show:
            showWindow()
            finish(command, result: "ok")
        case .hide:
            window.orderOut(nil)
            syncWindowState(visible: false)
            finish(command, result: "ok")
        case .resize:
            window.setFrame(resizedFrame(window.frame, width: command.width!, height: command.height!), display: true)
            finish(command, result: "ok")
        case .dock:
            applyDock(command.dockSide!)
            finish(command, result: "ok")
        case .eval:
            webView.evaluateJavaScript(command.js!) { [weak self] value, error in
                // Reduce to a String before crossing back: the callback value is not Sendable.
                let result = error.map { "error: \($0.localizedDescription)" } ?? renderEvalResult(value)
                MainActor.assumeIsolated { self?.finish(command, result: result) }
            }
        }
    }

    private func finish(_ command: WindowCommand, result: String) {
        state.lastCommandId = command.id
        state.lastResult = result
        syncWindowState()
    }

    private func showWindow() {
        window.deminiaturize(nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        syncWindowState()
    }

    private func applyDock(_ side: WindowCommand.Side) {
        guard let screen = window.screen ?? NSScreen.main else { return }
        window.setFrame(dockFrame(in: screen.visibleFrame, side: side), display: true)
    }
}
