import AppKit
import ConsoleCore

/// Borderless panels do not become key by default; the search field needs it.
private final class PalettePanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

/// The native chrome's command palette: ⌘K lists the domains, ⌘P the modules (Spotlight-like panel over the window).
/// Items come from the console's `GET /api/palette`; Enter hands the chosen URL to `open`, which loads it in the web
/// view, the same navigation the web palette does with `location.href` (the new page's first trusted gesture then posts
/// `/domain/<slug>/time/enter` itself, so the cost clock claim is unchanged).
@MainActor
final class PaletteController: NSObject, NSTextFieldDelegate, NSTableViewDataSource, NSTableViewDelegate {
    private let panel: PalettePanel
    private let field = NSTextField()
    private let table = NSTableView()
    private let hint = NSTextField(labelWithString: "↑↓ escolher · Enter abrir · Esc fechar")
    private let scroll = NSScrollView()

    private let parent: () -> NSWindow?
    private let currentURL: () -> URL?
    private let open: (URL) -> Void

    private var mode: PaletteMode = .domains
    private var items: [PaletteItem] = []
    private var hits: [(item: PaletteItem, positions: [Int])] = []
    private var loading: Task<Void, Never>?

    private static let width: CGFloat = 560
    private static let rowHeight: CGFloat = 30
    private static let maxRows = 9

    init(parent: @escaping () -> NSWindow?, currentURL: @escaping () -> URL?, open: @escaping (URL) -> Void) {
        self.parent = parent
        self.currentURL = currentURL
        self.open = open
        panel = PalettePanel(contentRect: NSRect(x: 0, y: 0, width: Self.width, height: 120),
                             styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: true)
        super.init()
        build()
    }

    // MARK: view

    private func build() {
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.level = .floating
        panel.hidesOnDeactivate = true
        panel.isReleasedWhenClosed = false
        panel.isMovable = false

        let blur = NSVisualEffectView()
        blur.material = .hudWindow
        blur.blendingMode = .behindWindow
        blur.state = .active
        blur.wantsLayer = true
        blur.layer?.cornerRadius = 12
        blur.layer?.masksToBounds = true
        panel.contentView = blur

        field.font = .systemFont(ofSize: 20, weight: .regular)
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = .none
        field.delegate = self
        field.translatesAutoresizingMaskIntoConstraints = false

        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("item"))
        column.resizingMask = .autoresizingMask
        table.addTableColumn(column)
        table.headerView = nil
        table.backgroundColor = .clear
        table.rowHeight = Self.rowHeight
        table.intercellSpacing = NSSize(width: 0, height: 0)
        table.selectionHighlightStyle = .regular
        table.dataSource = self
        table.delegate = self
        table.target = self
        table.action = #selector(rowClicked)

        scroll.documentView = table
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.translatesAutoresizingMaskIntoConstraints = false

        hint.font = .systemFont(ofSize: 11)
        hint.textColor = .tertiaryLabelColor
        hint.translatesAutoresizingMaskIntoConstraints = false

        let rule = NSBox()
        rule.boxType = .separator
        rule.translatesAutoresizingMaskIntoConstraints = false

        for v in [field, rule, scroll, hint] { blur.addSubview(v) }
        NSLayoutConstraint.activate([
            field.topAnchor.constraint(equalTo: blur.topAnchor, constant: 12),
            field.leadingAnchor.constraint(equalTo: blur.leadingAnchor, constant: 18),
            field.trailingAnchor.constraint(equalTo: blur.trailingAnchor, constant: -18),
            field.heightAnchor.constraint(equalToConstant: 28),
            rule.topAnchor.constraint(equalTo: field.bottomAnchor, constant: 10),
            rule.leadingAnchor.constraint(equalTo: blur.leadingAnchor),
            rule.trailingAnchor.constraint(equalTo: blur.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: rule.bottomAnchor, constant: 4),
            scroll.leadingAnchor.constraint(equalTo: blur.leadingAnchor, constant: 6),
            scroll.trailingAnchor.constraint(equalTo: blur.trailingAnchor, constant: -6),
            scroll.bottomAnchor.constraint(equalTo: hint.topAnchor, constant: -4),
            hint.leadingAnchor.constraint(equalTo: blur.leadingAnchor, constant: 18),
            hint.bottomAnchor.constraint(equalTo: blur.bottomAnchor, constant: -8),
        ])
    }

    // MARK: open / close

    var isVisible: Bool { panel.isVisible }

    /// Opens the palette in `mode`; the same shortcut again closes it.
    func toggle(_ mode: PaletteMode) {
        if panel.isVisible && self.mode == mode { close(); return }
        show(mode)
    }

    func show(_ mode: PaletteMode) {
        self.mode = mode
        items = []
        hits = []
        field.stringValue = ""
        field.placeholderString = mode.placeholder
        table.reloadData()
        resize()
        position()
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(field)
        load()
    }

    func close() {
        loading?.cancel()
        panel.orderOut(nil)
        parent()?.makeKeyAndOrderFront(nil)
    }

    private func position() {
        guard let w = parent() else { panel.center(); return }
        let f = w.frame
        let size = panel.frame.size
        panel.setFrameOrigin(NSPoint(x: f.midX - size.width / 2, y: f.maxY - f.height * 0.22 - size.height))
    }

    private func resize() {
        let rows = min(max(hits.count, 1), Self.maxRows)
        let height = 12 + 28 + 10 + 1 + 4 + CGFloat(rows) * Self.rowHeight + 12 + 22
        let top = panel.frame.maxY
        panel.setContentSize(NSSize(width: Self.width, height: height))
        if panel.frame.maxY != top, panel.isVisible { panel.setFrameOrigin(NSPoint(x: panel.frame.minX, y: top - panel.frame.height)) }
    }

    // MARK: data

    private func load() {
        loading?.cancel()
        let current = currentURL()
        guard let current, let base = URL(string: "/", relativeTo: current)?.absoluteURL,
              let endpoint = paletteEndpoint(base: base, current: current) else { return }
        let mode = self.mode
        loading = Task { [weak self] in
            let data = try? await URLSession.shared.data(from: endpoint).0
            guard !Task.isCancelled, let payload = PalettePayload.decode(data) else { return }
            let items = payload.items(mode, base: base, current: current)
            await MainActor.run {
                guard let self, self.mode == mode else { return }
                self.items = items
                self.refilter()
            }
        }
    }

    private func refilter() {
        let ranked = fuzzyRank(field.stringValue, in: items.map(\.title))
        hits = ranked.map { (items[$0.index], $0.match.positions) }
        table.reloadData()
        if !hits.isEmpty {
            // the current one is not preselected: Enter on an empty query opens the first, like the web palette
            table.selectRowIndexes(IndexSet(integer: 0), byExtendingSelection: false)
        }
        resize()
    }

    // MARK: field + keys

    func controlTextDidChange(_ obj: Notification) { refilter() }

    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        switch selector {
        case #selector(NSResponder.moveDown(_:)): move(1)
        case #selector(NSResponder.moveUp(_:)): move(-1)
        case #selector(NSResponder.insertNewline(_:)): choose(table.selectedRow)
        case #selector(NSResponder.cancelOperation(_:)): close()
        default: return false
        }
        return true
    }

    private func move(_ delta: Int) {
        guard !hits.isEmpty else { return }
        let row = min(max(table.selectedRow + delta, 0), hits.count - 1)
        table.selectRowIndexes(IndexSet(integer: row), byExtendingSelection: false)
        table.scrollRowToVisible(row)
    }

    @objc private func rowClicked() { choose(table.clickedRow) }

    private func choose(_ row: Int) {
        guard hits.indices.contains(row) else { return }
        let url = hits[row].item.url
        close()
        open(url)
    }

    // MARK: table

    func numberOfRows(in tableView: NSTableView) -> Int { hits.count }

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let hit = hits[row]
        let cell = NSTableCellView()
        let title = NSTextField(labelWithString: "")
        title.attributedStringValue = Self.highlighted(hit.item.title + (hit.item.isCurrent ? "  · atual" : ""),
                                                       positions: hit.positions, currentFrom: hit.item.title.count)
        let tag = NSTextField(labelWithString: hit.item.subtitle)
        tag.font = .systemFont(ofSize: 12)
        tag.textColor = .tertiaryLabelColor
        tag.alignment = .right
        for v in [title, tag] { v.translatesAutoresizingMaskIntoConstraints = false; cell.addSubview(v) }
        title.lineBreakMode = .byTruncatingTail
        NSLayoutConstraint.activate([
            title.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 12),
            title.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            tag.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -12),
            tag.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            title.trailingAnchor.constraint(lessThanOrEqualTo: tag.leadingAnchor, constant: -12),
        ])
        return cell
    }

    /// Matched letters in bold; the "· atual" tail dimmed.
    private static func highlighted(_ text: String, positions: [Int], currentFrom: Int) -> NSAttributedString {
        let out = NSMutableAttributedString()
        let set = Set(positions)
        for (i, ch) in text.enumerated() {
            var attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 15, weight: set.contains(i) ? .bold : .regular),
                                                        .foregroundColor: NSColor.labelColor]
            if i >= currentFrom { attrs[.foregroundColor] = NSColor.tertiaryLabelColor; attrs[.font] = NSFont.systemFont(ofSize: 12) }
            out.append(NSAttributedString(string: String(ch), attributes: attrs))
        }
        return out
    }
}
