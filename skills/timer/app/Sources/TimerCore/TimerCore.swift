import Foundation

/// The state file written by `scripts/timer.sh` (the only writer). The app only reads it.
public struct TimerState: Codable, Equatable, Sendable {
    public enum Status: String, Codable, Sendable {
        case idle, running, paused
    }

    public var status: Status
    /// Epoch seconds when a running timer ends.
    public var endsAt: Double?
    /// Seconds left when paused.
    public var remaining: Double?
    public var label: String
    public var updatedAt: Double?

    enum CodingKeys: String, CodingKey {
        case status, remaining, label
        case endsAt = "ends_at"
        case updatedAt = "updated_at"
    }

    public init(status: Status = .idle, endsAt: Double? = nil, remaining: Double? = nil,
                label: String = "", updatedAt: Double? = nil) {
        self.status = status
        self.endsAt = endsAt
        self.remaining = remaining
        self.label = label
        self.updatedAt = updatedAt
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = try c.decodeIfPresent(Status.self, forKey: .status) ?? .idle
        endsAt = try c.decodeIfPresent(Double.self, forKey: .endsAt)
        remaining = try c.decodeIfPresent(Double.self, forKey: .remaining)
        label = try c.decodeIfPresent(String.self, forKey: .label) ?? ""
        updatedAt = try c.decodeIfPresent(Double.self, forKey: .updatedAt)
    }

    /// Decodes the file contents. Missing, empty or broken data reads as idle.
    public static func decode(_ data: Data?) -> TimerState {
        guard let data, let s = try? JSONDecoder().decode(TimerState.self, from: data) else { return TimerState() }
        return s
    }

    /// Remaining seconds (never negative). Zero when idle.
    public func remaining(now: Date) -> TimeInterval {
        switch status {
        case .idle: return 0
        case .paused: return max(0, remaining ?? 0)
        case .running: return max(0, (endsAt ?? 0) - now.timeIntervalSince1970)
        }
    }

    /// True when a running timer has reached zero.
    public func isExpired(now: Date) -> Bool {
        status == .running && remaining(now: now) <= 0
    }
}

/// What the menu bar shows.
public enum Display: Equatable, Sendable {
    case idle
    case text(String)
}

/// Pure mapping from state and time to the status item text.
public func display(for state: TimerState, now: Date) -> Display {
    switch state.status {
    case .idle:
        return .idle
    case .paused:
        return .text("⏸ " + format(seconds: state.remaining(now: now)))
    case .running:
        var text = format(seconds: state.remaining(now: now))
        let label = truncate(state.label, to: 16)
        if !label.isEmpty { text += " " + label }
        return .text(text)
    }
}

public func truncate(_ text: String, to limit: Int) -> String {
    let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard t.count > limit else { return t }
    return String(t.prefix(limit - 1)) + "…"
}

/// Formats seconds as `MM:SS`, or `H:MM:SS` from one hour up. Rounds up so 00:00 only shows at the end.
public func format(seconds: TimeInterval) -> String {
    let total = max(0, Int(seconds.rounded(.up)))
    let h = total / 3600
    let m = (total % 3600) / 60
    let s = total % 60
    if h > 0 { return String(format: "%d:%02d:%02d", h, m, s) }
    return String(format: "%02d:%02d", m, s)
}

/// Parses `25` (minutes), `25m`, `90s`, `1h` or `mm:ss` into seconds. Invalid or zero gives nil.
/// Same semantics as `scripts/timer.sh`.
public func parseDuration(_ text: String) -> TimeInterval? {
    let t = text.trimmingCharacters(in: .whitespaces)
    guard !t.isEmpty else { return nil }
    func number(_ p: Substring) -> Int? {
        guard !p.isEmpty, p.count <= 6, p.allSatisfy({ $0 >= "0" && $0 <= "9" }) else { return nil }
        return Int(p)
    }
    let seconds: Int
    if t.contains(":") {
        let parts = t.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 2, let m = number(parts[0]), let s = number(parts[1]), s < 60 else { return nil }
        seconds = m * 60 + s
    } else if let last = t.last, "smh".contains(last) {
        guard let n = number(t.dropLast()) else { return nil }
        seconds = n * (last == "s" ? 1 : last == "m" ? 60 : 3600)
    } else {
        guard let m = number(Substring(t)) else { return nil }
        seconds = m * 60
    }
    return seconds > 0 ? TimeInterval(seconds) : nil
}
