import CoreGraphics
import Foundation

// Pure logic of the native window: no AppKit, so it is testable. The app is the only writer of
// state.json; `scripts/window.sh` is the only writer of command.json.

/// One command from `command.json`, written by `scripts/window.sh`.
public struct WindowCommand: Decodable, Equatable, Sendable {
    public enum Action: String, Sendable {
        case open, reload, show, hide, resize, dock, eval
    }

    public enum Side: String, Sendable {
        case left, right
    }

    public var id: Int
    /// The raw action text, so an unknown action can still be acknowledged (and its id consumed).
    public var actionName: String
    public var side: String?
    public var url: String?
    public var width: Double?
    public var height: Double?
    public var js: String?
    public var updatedAt: Double?

    enum CodingKeys: String, CodingKey {
        case id, side, url, width, height, js
        case actionName = "action"
        case updatedAt = "updated_at"
    }

    public init(id: Int, action: String, side: String? = nil, url: String? = nil, width: Double? = nil,
                height: Double? = nil, js: String? = nil, updatedAt: Double? = nil) {
        self.id = id
        self.actionName = action
        self.side = side
        self.url = url
        self.width = width
        self.height = height
        self.js = js
        self.updatedAt = updatedAt
    }

    public var action: Action? { Action(rawValue: actionName) }
    public var dockSide: Side? { side.flatMap(Side.init(rawValue:)) }

    /// Decodes the file contents. Missing, empty or broken data, or no `id`, gives nil.
    public static func decode(_ data: Data?) -> WindowCommand? {
        guard let data else { return nil }
        return try? JSONDecoder().decode(WindowCommand.self, from: data)
    }

    /// Why the command cannot be applied, or nil when it is well formed.
    public func validationError() -> String? {
        guard let action else { return "unknown action '\(actionName)'" }
        switch action {
        case .open:
            guard let url, !url.isEmpty, URL(string: url)?.scheme != nil else { return "open needs a url with a scheme" }
        case .resize:
            guard let width, let height, width > 0, height > 0 else { return "resize needs a positive width and height" }
        case .dock:
            guard dockSide != nil else { return "dock needs side left or right" }
        case .eval:
            guard let js, !js.isEmpty else { return "eval needs js" }
        case .reload, .show, .hide:
            break
        }
        return nil
    }
}

/// "Apply once per id": a command runs only when its id is above the last one applied.
/// The kqueue fires on every write to the directory (the app's own state.json included), and the app can
/// restart with an old command.json on disk, so the gate starts from the state's `last_command_id`.
public struct CommandGate: Equatable, Sendable {
    public private(set) var lastApplied: Int

    public init(lastApplied: Int = 0) {
        self.lastApplied = lastApplied
    }

    /// True the first time an id is seen; false for a repeat or an older id.
    public mutating func accept(_ command: WindowCommand) -> Bool {
        guard command.id > lastApplied else { return false }
        lastApplied = command.id
        return true
    }
}

/// A JSON value, for `last_message` (whatever the page posts through the bridge).
public enum JSONValue: Codable, Equatable, Sendable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .null: try c.encodeNil()
        case .bool(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .string(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        }
    }

    /// Converts what WebKit hands over (NSDictionary, NSArray, NSString, NSNumber, NSNull).
    public init(any value: Any?) {
        switch value {
        case nil, is NSNull: self = .null
        case let v as String: self = .string(v)
        case let v as NSNumber:
            self = CFGetTypeID(v) == CFBooleanGetTypeID() ? .bool(v.boolValue) : .number(v.doubleValue)
        case let v as [Any]: self = .array(v.map { JSONValue(any: $0) })
        case let v as [String: Any]: self = .object(v.mapValues { JSONValue(any: $0) })
        default: self = .string(String(describing: value))
        }
    }

    /// A string stays as is; everything else is compact JSON with sorted keys.
    public var rendered: String {
        if case .string(let s) = self { return s }
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        // A bare number or bool is valid JSON text for JSONEncoder on macOS 13+.
        guard let data = try? enc.encode(self), let text = String(data: data, encoding: .utf8) else { return "" }
        return text
    }
}

/// The result of an `eval` as one string. JS `undefined` reaches Swift as nil.
public func renderEvalResult(_ value: Any?) -> String {
    if value == nil { return "undefined" }
    return JSONValue(any: value).rendered
}

/// `state.json`, written only by the app.
public struct WindowState: Codable, Equatable, Sendable {
    public var url: String?
    public var title: String?
    public var visible: Bool
    public var width: Double
    public var height: Double
    public var lastCommandId: Int
    public var lastResult: String?
    public var lastMessage: JSONValue?
    public var updatedAt: Double?

    enum CodingKeys: String, CodingKey {
        case url, title, visible, width, height
        case lastCommandId = "last_command_id"
        case lastResult = "last_result"
        case lastMessage = "last_message"
        case updatedAt = "updated_at"
    }

    public init(url: String? = nil, title: String? = nil, visible: Bool = false, width: Double = 0,
                height: Double = 0, lastCommandId: Int = 0, lastResult: String? = nil,
                lastMessage: JSONValue? = nil, updatedAt: Double? = nil) {
        self.url = url
        self.title = title
        self.visible = visible
        self.width = width
        self.height = height
        self.lastCommandId = lastCommandId
        self.lastResult = lastResult
        self.lastMessage = lastMessage
        self.updatedAt = updatedAt
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        url = try c.decodeIfPresent(String.self, forKey: .url)
        title = try c.decodeIfPresent(String.self, forKey: .title)
        visible = try c.decodeIfPresent(Bool.self, forKey: .visible) ?? false
        width = try c.decodeIfPresent(Double.self, forKey: .width) ?? 0
        height = try c.decodeIfPresent(Double.self, forKey: .height) ?? 0
        lastCommandId = try c.decodeIfPresent(Int.self, forKey: .lastCommandId) ?? 0
        lastResult = try c.decodeIfPresent(String.self, forKey: .lastResult)
        lastMessage = try c.decodeIfPresent(JSONValue.self, forKey: .lastMessage)
        updatedAt = try c.decodeIfPresent(Double.self, forKey: .updatedAt)
    }

    /// Every key is always present (null when unset), so the agent reads a stable shape.
    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(url, forKey: .url)
        try c.encode(title, forKey: .title)
        try c.encode(visible, forKey: .visible)
        try c.encode(width, forKey: .width)
        try c.encode(height, forKey: .height)
        try c.encode(lastCommandId, forKey: .lastCommandId)
        try c.encode(lastResult, forKey: .lastResult)
        try c.encode(lastMessage, forKey: .lastMessage)
        try c.encode(updatedAt, forKey: .updatedAt)
    }

    /// Missing, empty or broken data reads as a fresh state.
    public static func decode(_ data: Data?) -> WindowState {
        guard let data, let s = try? JSONDecoder().decode(WindowState.self, from: data) else { return WindowState() }
        return s
    }

    public func encoded() -> Data? {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try? enc.encode(self)
    }
}

/// Two thirds of the visible frame's width and its full height, against the left or right edge.
/// The console's UI is made for 2 of 3 columns; the free third is for a terminal or chat.
public func dockFrame(in visible: CGRect, side: WindowCommand.Side) -> CGRect {
    let width = (visible.width * 2 / 3).rounded()
    let x = side == .right ? visible.maxX - width : visible.minX
    return CGRect(x: x, y: visible.minY, width: width, height: visible.height)
}

/// A new size with the top-left corner kept in place (AppKit's origin is bottom-left).
public func resizedFrame(_ frame: CGRect, width: Double, height: Double) -> CGRect {
    CGRect(x: frame.minX, y: frame.maxY - height, width: width, height: height)
}

/// Seconds since the Mac's last input of any kind (keyboard, mouse, trackpad). The page stops the money bar's clock
/// after 5 minutes of this. It must be the any-input event type (`~0`, kCGAnyInputEventType): `.null` (0) answers with
/// the time since boot and would stop the clock at once.
public func systemIdleSeconds() -> Double {
    guard let any = CGEventType(rawValue: ~0) else { return 0 }
    return CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: any)
}

/// The script that hands the idle time to the page; a page without the money bar has no `devconsoleIdle`, so nothing happens.
public func idleScript(seconds: Double) -> String {
    let s = seconds.isFinite ? max(0, seconds) : 0
    return "typeof window.devconsoleIdle === 'function' && window.devconsoleIdle(\(Int(s.rounded())))"
}
