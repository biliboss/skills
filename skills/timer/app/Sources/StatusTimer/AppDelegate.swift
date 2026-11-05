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

    // MARK: look (same as the macOS menu bar clock)

    /// Menu bar font with monospaced digits, so the width does not jitter while counting.
    private static let timeFont: NSFont = {
        let base = NSFont.menuBarFont(ofSize: 0)
        let descriptor = base.fontDescriptor.addingAttributes([
            .featureSettings: [[
                NSFontDescriptor.FeatureKey.typeIdentifier: kNumberSpacingType,
                NSFontDescriptor.FeatureKey.selectorIdentifier: kMonospacedNumbersSelector,
            ]],
        ])
        return NSFont(descriptor: descriptor, size: base.pointSize) ?? base
    }()

    /// PostScript names as installed (fc-list): IosevkaTermNF (proportional-width NF) and IosevkaTermNFM (Mono).
    private static let nerdFontNames = ["IosevkaTermNF", "IosevkaTermNFM", "IosevkaTermNerdFont-Regular",
                                        "IosevkaTerm Nerd Font", "IosevkaTerm NF"]

    /// The first Nerd Font that has one of the candidate glyphs, or nil when the font (or all glyphs) are missing.
    private static func nerdGlyph(_ candidates: [String]) -> (font: NSFont, glyph: String)? {
        let size = NSFont.menuBarFont(ofSize: 0).pointSize
        for name in nerdFontNames {
            guard let font = NSFont(name: name, size: size) else { continue }
            for glyph in candidates where hasGlyph(font, glyph) {
                return (font, glyph)
            }
        }
        return nil
    }

    /// The Nerd Font timer glyph (nf-md-timer U+F051B, then nf-fa-hourglass U+F252).
    private static let nerdIcon = nerdGlyph(["\u{F051B}", "\u{F252}"])
    /// The Nerd Font check glyph for the finished state (nf-fa-check U+F00C).
    private static let nerdCheck = nerdGlyph(["\u{F00C}"])

    private static func hasGlyph(_ font: NSFont, _ glyph: String) -> Bool {
        var chars = [UniChar](glyph.utf16)
        var glyphs = [CGGlyph](repeating: 0, count: chars.count)
        return CTFontGetGlyphsForCharacters(font, &chars, &glyphs, chars.count) && glyphs.allSatisfy { $0 != 0 }
    }

    private func iconString(color: NSColor) -> NSAttributedString {
        if let icon = Self.nerdIcon {
            return NSAttributedString(string: icon.glyph, attributes: [
                // The NF glyph's advance is narrower than its ink, so the space after it looks missing:
                // kern opens the gap to match the spacing between the clock's date and time.
                .font: icon.font, .foregroundColor: color, .kern: 4,
            ])
        }
        // Fallback: the SF Symbol `timer` as a template attachment.
        return symbolString("timer", description: "Timer")
    }

    /// The finished glyph: Nerd Font check, falling back to the SF Symbol `checkmark.circle`. Always red.
    private func checkString() -> NSAttributedString {
        if let check = Self.nerdCheck {
            return NSAttributedString(string: check.glyph, attributes: [
                .font: check.font, .foregroundColor: NSColor.systemRed, .kern: 4,
            ])
        }
        return symbolString("checkmark.circle", description: "Pronto", color: .systemRed)
    }

    private func symbolString(_ name: String, description: String, color: NSColor? = nil) -> NSAttributedString {
        let attachment = NSTextAttachment()
        var image = NSImage(systemSymbolName: name, accessibilityDescription: description)
        if let color, let base = image {
            // Template images take the bar's colour; tint a copy so the red survives.
            image = base.withSymbolConfiguration(.init(paletteColors: [color]))
            image?.isTemplate = false
        } else {
            image?.isTemplate = true
        }
        attachment.image = image
        let font = Self.timeFont
        let side = font.capHeight * 1.2
        attachment.bounds = CGRect(x: 0, y: (font.capHeight - side) / 2, width: side, height: side)
        return NSAttributedString(attachment: attachment)
    }

    private func render() {
        guard let button = item.button else { return }
        button.image = nil
        let result = NSMutableAttributedString()
        switch display(for: state, now: Date()) {
        case .idle:
            result.append(iconString(color: .labelColor))
        case .running(let text):
            result.append(iconString(color: .labelColor))
            result.append(NSAttributedString(string: " " + text, attributes: [
                .font: Self.timeFont, .foregroundColor: NSColor.labelColor,
            ]))
        case .finished:
            result.append(checkString())
            result.append(NSAttributedString(string: " pronto", attributes: [
                .font: Self.timeFont, .foregroundColor: NSColor.systemRed,
            ]))
        case .paused(let text):
            result.append(iconString(color: .secondaryLabelColor))
            result.append(NSAttributedString(string: " " + text, attributes: [
                .font: Self.timeFont, .foregroundColor: NSColor.secondaryLabelColor,
            ]))
        }
        button.attributedTitle = result
        button.toolTip = tooltip(for: state)
    }

    private func notify() {
        let content = UNMutableNotificationContent()
        content.title = "Tempo esgotado"
        content.body = state.label
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
    }
}
