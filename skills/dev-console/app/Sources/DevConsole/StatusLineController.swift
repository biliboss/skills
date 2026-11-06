import AppKit
import ConsoleCore
import WebKit

/// The window's bottom status line, drawn natively (the chrome); the page keeps the content. It is a view of the
/// page's own numbers (pushed by `postMessage({type: "status"})` on every tick) with a slow `GET /api/status`
/// refresh as the fallback, and it never writes the cost journal: ▶/⏸ asks the page to do what its own button does
/// (`devconsoleToggle`), or posts to the same `/time/start|stop` route when the page cannot.
@MainActor
final class StatusLineController {
    private weak var webView: WKWebView?
    private let bar = NSStackView()
    private let button = NSButton()
    private let center = NSTextField(labelWithString: "")
    private let money = NSTextField(labelWithString: "")
    private let module = NSTextField(labelWithString: "")
    private var info: StatusInfo?
    private var refreshTimer: Timer?
    /// The hour, first on the line, like iOS's status-bar clock: the system font (SF), semibold, digits that do not
    /// jump, 24 h, the colon blinking on the half second.
    private let clock = NSTextField(labelWithString: "")
    private var clockTimer: Timer?
    private var colonOn = true
    /// The weekly limit of the owner's Claude accounts, from the console's /api/claude-usage.
    private let usage = NSTextField(labelWithString: "")
    private var usageTimer: Timer?
    /// A click on the domain (left) or on the module (right) asks for the native palette in that mode.
    var onPalette: ((PaletteMode) -> Void)?

    static let height: CGFloat = 22

    /// The window's content view: the web view above, the status line under it.
    func install(webView: WKWebView) -> NSView {
        self.webView = webView
        let container = NSView()
        webView.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(webView)

        let font = NSFont.systemFont(ofSize: 11)
        let mono = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .semibold)
        button.isBordered = false
        button.font = font
        button.target = self
        button.action = #selector(toggle)
        button.setContentHuggingPriority(.required, for: .horizontal)
        center.font = font; center.textColor = .secondaryLabelColor
        money.font = mono
        module.font = font; module.textColor = .tertiaryLabelColor
        for label in [center, money, module] { label.lineBreakMode = .byTruncatingTail }
        center.addGestureRecognizer(NSClickGestureRecognizer(target: self, action: #selector(askDomains)))
        module.addGestureRecognizer(NSClickGestureRecognizer(target: self, action: #selector(askModules)))
        let spacer = NSView()
        spacer.setContentHuggingPriority(.init(1), for: .horizontal)

        bar.orientation = .horizontal
        bar.spacing = 8
        bar.edgeInsets = NSEdgeInsets(top: 0, left: 8, bottom: 0, right: 10)
        clock.font = NSFont.monospacedDigitSystemFont(ofSize: NSFont.systemFontSize, weight: .semibold)
        clock.textColor = .labelColor
        clock.setContentHuggingPriority(.required, for: .horizontal)
        clock.setContentCompressionResistancePriority(.required, for: .horizontal)
        usage.font = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .regular)
        usage.textColor = .tertiaryLabelColor
        usage.setContentHuggingPriority(.required, for: .horizontal)
        bar.setViews([clock, button, center, money, spacer, usage, module], in: .leading)
        bar.translatesAutoresizingMaskIntoConstraints = false
        bar.wantsLayer = true
        let line = NSBox(); line.boxType = .separator; line.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(bar); container.addSubview(line)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: container.topAnchor),
            webView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: bar.topAnchor),
            bar.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            bar.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            bar.bottomAnchor.constraint(equalTo: container.bottomAnchor),
            bar.heightAnchor.constraint(equalToConstant: Self.height),
            line.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            line.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            line.bottomAnchor.constraint(equalTo: bar.topAnchor),
        ])
        render()
        tickClock()
        clockTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tickClock() }
        }
        clockTimer?.tolerance = 0.05
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in MainActor.assumeIsolated { self?.fetchUsage() } }
        usageTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.fetchUsage() }
        }
        // Fallback: a page that is loading, throttled or gone does not push; a slow refresh keeps the numbers honest.
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 8, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
        return container
    }

    /// True when the message was a status push (then AppDelegate does not log it as `last_message`).
    func handle(message body: Any) -> Bool {
        guard let next = StatusInfo.decode(message: body) else { return false }
        info = next
        render()
        return true
    }

    private func render() {
        let i = info
        button.title = i?.running == true ? "⏸" : "▶"
        button.isEnabled = i?.costCenter != nil
        button.toolTip = i?.running == true ? "pausar" : "iniciar"
        center.stringValue = i?.costCenter ?? i?.domain ?? "—"
        money.stringValue = i?.moneyText ?? ""
        money.textColor = i?.overBudget == true ? .systemRed : .labelColor
        module.stringValue = [i?.domain, i?.module].compactMap { $0 }.joined(separator: " · ")
    }

    @objc private func askDomains() { onPalette?(.domains) }
    @objc private func askModules() { onPalette?(.modules) }

    // MARK: ▶/⏸

    @objc private func toggle() {
        guard let webView, let info else { return }
        let script = "typeof window.devconsoleToggle === 'function' ? (window.devconsoleToggle(), true) : false"
        webView.evaluateJavaScript(script) { [weak self] value, _ in
            let handled = (value as? Bool) == true
            MainActor.assumeIsolated { if !handled { self?.postClock(info) } }
        }
    }

    /// Same route the web button posts to; the cost-track writer behind it is the only one that touches the journal.
    private func postClock(_ i: StatusInfo) {
        guard let base = i.base, let origin = webView?.url,
              let url = URL(string: clockRoute(base: base, running: i.running), relativeTo: origin) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request) { [weak self] _, _, _ in
            DispatchQueue.main.async { MainActor.assumeIsolated { self?.refresh() } }
        }.resume()
    }

    // MARK: fallback refresh

    private func refresh() {
        guard let origin = webView?.url, let slug = info?.domainSlug,
              var parts = URLComponents(url: origin, resolvingAgainstBaseURL: false) else { return }
        parts.path = "/api/status"
        parts.queryItems = [URLQueryItem(name: "domain", value: slug)]
        parts.fragment = nil
        guard let url = parts.url else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let next = StatusInfo.decode(data) else { return }
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard let self else { return }
                    self.info = next.filling(from: self.info)
                    self.render()
                }
            }
        }.resume()
    }

    /// Redraws the hour; the colon shows on the first half of each second and hides on the second (blinks).
    private func tickClock() {
        let now = Date()
        let c = Calendar.current.dateComponents([.hour, .minute, .nanosecond], from: now)
        colonOn = (c.nanosecond ?? 0) < 500_000_000
        let hh = String(format: "%02d", c.hour ?? 0), mm = String(format: "%02d", c.minute ?? 0)
        let font = clock.font ?? NSFont.monospacedDigitSystemFont(ofSize: NSFont.systemFontSize, weight: .semibold)
        let text = NSMutableAttributedString(string: hh, attributes: [.font: font, .foregroundColor: NSColor.labelColor])
        text.append(NSAttributedString(string: ":", attributes: [
            .font: font, .foregroundColor: colonOn ? NSColor.labelColor : NSColor.clear]))
        text.append(NSAttributedString(string: mm, attributes: [.font: font, .foregroundColor: NSColor.labelColor]))
        clock.attributedStringValue = text
    }

    /// "mukutu 100% · pessoal 82%": the spent account (100%) in red, the others tertiary; the tooltip says when each resets.
    private func fetchUsage() {
        guard let origin = webView?.url, var parts = URLComponents(url: origin, resolvingAgainstBaseURL: false) else { return }
        parts.path = "/api/claude-usage"; parts.query = nil; parts.fragment = nil
        guard let url = parts.url else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let data, let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let accounts = obj["accounts"] as? [[String: Any]] else { return }
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard let self else { return }
                    let font = self.usage.font ?? NSFont.systemFont(ofSize: 11)
                    let text = NSMutableAttributedString()
                    var tips: [String] = []
                    for (i, a) in accounts.enumerated() {
                        let name = a["name"] as? String ?? "?"
                        let week = a["week"] as? Int
                        if i > 0 { text.append(NSAttributedString(string: " · ", attributes: [.font: font, .foregroundColor: NSColor.tertiaryLabelColor])) }
                        let spent = (week ?? 0) >= 100
                        text.append(NSAttributedString(string: week.map { "\(name) \($0)%" } ?? "\(name) —", attributes: [
                            .font: spent ? NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .semibold) : font,
                            .foregroundColor: spent ? NSColor.systemRed : NSColor.tertiaryLabelColor]))
                        if let r = a["resets"] as? String { tips.append("\(name) volta \(r.prefix(16).replacingOccurrences(of: "T", with: " "))") }
                    }
                    self.usage.attributedStringValue = text
                    self.usage.toolTip = "limite semanal do Claude · " + tips.joined(separator: " · ")
                }
            }
        }.resume()
    }
}
