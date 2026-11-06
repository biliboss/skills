import Foundation

// The flight recorder's pure half: one JSON line per navigation, a ring of the last 20 lines (and their PNGs).
// No AppKit, no disk: `RecorderController` (the app) does the I/O, this file is what the tests cover.

/// One line of `events.jsonl`. Every key is always present (null when unset), so an agent reads a stable shape.
public struct RecorderLine: Codable, Equatable, Sendable {
    public var at: String
    public var url: String?
    public var domain: String?
    public var module: String?
    public var event: String?
    public var widget: String?
    public var width: Double
    public var height: Double
    public var errors: [String]
    public var shot: String

    public init(at: String, url: String? = nil, domain: String? = nil, module: String? = nil, event: String? = nil,
                widget: String? = nil, width: Double = 0, height: Double = 0, errors: [String] = [], shot: String) {
        self.at = at; self.url = url; self.domain = domain; self.module = module; self.event = event
        self.widget = widget; self.width = width; self.height = height; self.errors = errors; self.shot = shot
    }

    enum CodingKeys: String, CodingKey { case at, url, domain, module, event, widget, width, height, errors, shot }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        at = try c.decode(String.self, forKey: .at)
        url = try c.decodeIfPresent(String.self, forKey: .url)
        domain = try c.decodeIfPresent(String.self, forKey: .domain)
        module = try c.decodeIfPresent(String.self, forKey: .module)
        event = try c.decodeIfPresent(String.self, forKey: .event)
        widget = try c.decodeIfPresent(String.self, forKey: .widget)
        width = try c.decodeIfPresent(Double.self, forKey: .width) ?? 0
        height = try c.decodeIfPresent(Double.self, forKey: .height) ?? 0
        errors = try c.decodeIfPresent([String].self, forKey: .errors) ?? []
        shot = try c.decodeIfPresent(String.self, forKey: .shot) ?? ""
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(at, forKey: .at)
        try c.encode(url, forKey: .url)
        try c.encode(domain, forKey: .domain)
        try c.encode(module, forKey: .module)
        try c.encode(event, forKey: .event)
        try c.encode(widget, forKey: .widget)
        try c.encode(width, forKey: .width)
        try c.encode(height, forKey: .height)
        try c.encode(errors, forKey: .errors)
        try c.encode(shot, forKey: .shot)
    }

    /// The line as one compact JSON text with sorted keys and no newline (the caller adds it).
    public func encoded() -> String? {
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        guard let data = try? enc.encode(self) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    /// Broken or empty text is nil.
    public static func decode(_ text: String) -> RecorderLine? {
        try? JSONDecoder().decode(RecorderLine.self, from: Data(text.utf8))
    }

    /// Same place as another line: a burst of reports that changed nothing is not a new navigation.
    public func sameState(as other: RecorderLine) -> Bool {
        url == other.url && domain == other.domain && module == other.module && event == other.event
            && widget == other.widget
    }
}

public enum RecorderRing {
    public static let keep = 20

    /// UTC, sortable, safe in a file name: `20261106T120000.123Z`.
    public static func at(_ date: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyyMMdd'T'HHmmss.SSS'Z'"
        return f.string(from: date)
    }

    /// `<dir>/shots/<at>.png`
    public static func shotPath(dir: String, at: String) -> String {
        (dir as NSString).appendingPathComponent("shots/\(at).png")
    }

    /// The last `keep` non-empty lines, and the older ones that were dropped (their PNGs go with them).
    public static func trim(lines: [String], keep: Int = RecorderRing.keep) -> (kept: [String], dropped: [String]) {
        let live = lines.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        let n = max(keep, 0)
        guard live.count > n else { return (live, []) }
        return (Array(live.suffix(n)), Array(live.prefix(live.count - n)))
    }

    /// PNG paths of the dropped lines that really live under `<dir>/shots/` (never delete anything else).
    public static func shotsToDelete(dropped: [String], dir: String) -> [String] {
        let root = ((dir as NSString).appendingPathComponent("shots") as NSString).standardizingPath + "/"
        return dropped.compactMap { RecorderLine.decode($0)?.shot }
            .map { ($0 as NSString).standardizingPath }
            .filter { $0.hasPrefix(root) && $0.hasSuffix(".png") }
    }
}

/// What the page's recorder script reports through `messageHandlers.devconsole` (`type: "recorder"`).
public struct PageReport: Equatable, Sendable, Decodable {
    public var domain: String?
    public var module: String?
    public var event: String?
    public var widget: String?
    public var errors: [String]

    enum CodingKeys: String, CodingKey { case type, domain, module, event, widget, errors }

    public init(domain: String? = nil, module: String? = nil, event: String? = nil, widget: String? = nil, errors: [String] = []) {
        self.domain = domain; self.module = module; self.event = event; self.widget = widget; self.errors = errors
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        domain = (try? c.decodeIfPresent(String.self, forKey: .domain)).flatMap { $0 }
        module = (try? c.decodeIfPresent(String.self, forKey: .module)).flatMap { $0 }
        event = (try? c.decodeIfPresent(String.self, forKey: .event)).flatMap { $0 }
        widget = (try? c.decodeIfPresent(String.self, forKey: .widget)).flatMap { $0 }
        errors = (try? c.decodeIfPresent([String].self, forKey: .errors)) ?? []
    }

    /// nil unless the body is an object with `type: "recorder"`.
    public static func decode(message body: Any) -> PageReport? {
        guard let dict = body as? [String: Any], dict["type"] as? String == "recorder" else { return nil }
        guard let data = JSONValue(any: body).rendered.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(PageReport.self, from: data)
    }
}

/// At most `maxCount` errors, each cut to `maxLength` characters, blanks dropped: a page in a loop cannot fill the disk.
public func clipErrors(_ errors: [String], maxCount: Int = 20, maxLength: Int = 300) -> [String] {
    errors.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        .prefix(maxCount).map { $0.count > maxLength ? String($0.prefix(maxLength)) + "…" : $0 }
}
