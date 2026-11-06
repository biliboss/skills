import AppKit
import ConsoleCore
import WebKit

/// The flight recorder: on every navigation of the window (a load, a module, an event, a widget) one JSON line goes to
/// `<recorder dir>/events.jsonl` with a PNG the app took itself (`WKWebView.takeSnapshot`: no focus, no domain switch,
/// no cost-clock claim). Only the last 20 lines and their PNGs stay. Nothing leaves the machine.
@MainActor
final class RecorderController {
    private let webView: WKWebView
    private var pending: PageReport?
    private var lastReport = PageReport()
    private var pendingErrors: [String] = []
    private var debounce: DispatchWorkItem?
    private var last: RecorderLine?

    let dir: URL = {
        if let o = ProcessInfo.processInfo.environment["DEV_CONSOLE_RECORDER_DIR"], !o.isEmpty {
            return URL(fileURLWithPath: o, isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/state/dev-console/recorder", isDirectory: true)
    }()
    private var eventsFile: URL { dir.appendingPathComponent("events.jsonl") }

    init(webView: WKWebView) {
        self.webView = webView
        webView.configuration.userContentController.addUserScript(
            WKUserScript(source: Self.script, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        last = Self.readLines(eventsFile).last.flatMap(RecorderLine.decode)
    }

    /// True when the message was the page's recorder report (it is not an agent message, so `last_message` stays clear).
    func handle(message body: Any) -> Bool {
        guard let report = PageReport.decode(message: body) else { return false }
        pendingErrors += report.errors
        pending = report
        debounce?.cancel()
        let item = DispatchWorkItem { [weak self] in
            MainActor.assumeIsolated { self?.record(force: false, completion: nil) }
        }
        debounce = item
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: item)  // a burst of changes is one line
        return true
    }

    /// Writes one line now. `force` (the `shot` command) records even when nothing changed since the last line.
    /// The completion gets the line's JSON text, or an `error: ...` text.
    func record(force: Bool, completion: ((String) -> Void)?) {
        let report = pending ?? lastReport  // a forced shot keeps the page's last reported state
        lastReport = report
        pending = nil
        debounce?.cancel()
        let errors = clipErrors(pendingErrors)
        let now = Date()
        let at = RecorderRing.at(now)
        let size = webView.bounds.size
        var line = RecorderLine(at: at, url: webView.url?.absoluteString, domain: report.domain, module: report.module,
                                event: report.event, widget: report.widget, width: Double(size.width),
                                height: Double(size.height), errors: errors,
                                shot: RecorderRing.shotPath(dir: dir.path, at: at))
        if !force, errors.isEmpty, let last, last.sameState(as: line) {
            completion?(last.encoded() ?? "")
            return
        }
        pendingErrors = []
        let config = WKSnapshotConfiguration()
        webView.takeSnapshot(with: config) { [weak self] image, error in
            let png = image.flatMap(Self.pngData)
            let failure = error?.localizedDescription
            MainActor.assumeIsolated {
                guard let self else { return }
                guard let png else {
                    line.shot = ""
                    self.write(line)
                    completion?("error: snapshot failed: \(failure ?? "no image")")
                    return
                }
                let shot = URL(fileURLWithPath: line.shot)
                try? FileManager.default.createDirectory(at: shot.deletingLastPathComponent(), withIntermediateDirectories: true)
                try? png.write(to: shot, options: .atomic)
                self.write(line)
                completion?(line.encoded() ?? "")
            }
        }
    }

    private func write(_ line: RecorderLine) {
        guard let text = line.encoded() else { return }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let (kept, dropped) = RecorderRing.trim(lines: Self.readLines(eventsFile) + [text])
        try? (kept.joined(separator: "\n") + "\n").write(to: eventsFile, atomically: true, encoding: .utf8)
        for path in RecorderRing.shotsToDelete(dropped: dropped, dir: dir.path) {
            try? FileManager.default.removeItem(atPath: path)
        }
        last = line
    }

    private static func readLines(_ file: URL) -> [String] {
        ((try? String(contentsOf: file, encoding: .utf8)) ?? "").split(separator: "\n").map(String.init)
    }

    private static func pngData(_ image: NSImage) -> Data? {
        guard let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff) else { return nil }
        return rep.representation(using: .png, properties: [:])
    }

    /// Runs in every page at document start. State comes from the URL query the console already keeps (`tab`, `ev`, `w`)
    /// and from `#mod-name`; errors are `window.onerror`, unhandled rejections and `console.error`.
    static let script = #"""
    (() => {
      const h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.devconsole;
      if (!h || window.__devconsoleRecorder) return;
      window.__devconsoleRecorder = true;
      const errs = []; let timer = null;
      const str = v => { try { return v instanceof Error ? (v.stack || String(v)).split('\n')[0] : typeof v === 'string' ? v : JSON.stringify(v); } catch (e) { return String(v); } };
      const state = () => {
        const p = location.pathname, q = new URLSearchParams(location.search), m = p.match(/^\/domain\/([^\/]+)/);
        const mod = (document.getElementById('mod-name') || {}).textContent;
        return {type: 'recorder', domain: m ? m[1] : null,
          module: mod || (p.startsWith('/playground') ? 'Playground' : p.startsWith('/agents') ? 'Agents' : null),
          event: q.get('ev'), widget: q.get('w'), errors: errs.splice(0)};
      };
      const send = () => { clearTimeout(timer); timer = setTimeout(() => h.postMessage(state()), 250); };
      for (const k of ['pushState', 'replaceState']) { const o = history[k]; history[k] = function () { const r = o.apply(this, arguments); send(); return r; }; }
      window.addEventListener('popstate', send); window.addEventListener('hashchange', send);
      window.addEventListener('DOMContentLoaded', send); window.addEventListener('load', send);
      window.addEventListener('error', e => { errs.push('pageerror: ' + (e.message || str(e.error))); send(); });
      window.addEventListener('unhandledrejection', e => { errs.push('unhandledrejection: ' + str(e.reason)); send(); });
      const ce = console.error; console.error = function () { errs.push('console: ' + [...arguments].map(str).join(' ')); send(); return ce.apply(this, arguments); };
    })();
    """#
}
