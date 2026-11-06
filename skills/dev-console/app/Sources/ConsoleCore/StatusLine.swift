import Foundation

/// What the native status line shows: the same numbers as the page's bottom bar, from the page's own message
/// (`postMessage({type: "status", ...})`) or from `GET /api/status?domain=<slug>`. Pure: no AppKit, no network.
public struct StatusInfo: Equatable, Sendable, Decodable {
    public var domain: String?
    public var costCenter: String?
    public var running: Bool
    public var todayBRL: Double?
    public var budgetBRL: Double?
    public var module: String?
    /// The page's route prefix (`/domain/<slug>`), so the app knows which routes the clock answers on.
    public var base: String?

    public init(domain: String? = nil, costCenter: String? = nil, running: Bool = false, todayBRL: Double? = nil,
                budgetBRL: Double? = nil, module: String? = nil, base: String? = nil) {
        self.domain = domain; self.costCenter = costCenter; self.running = running
        self.todayBRL = todayBRL; self.budgetBRL = budgetBRL; self.module = module; self.base = base
    }

    enum CodingKeys: String, CodingKey {
        case domain, running, module, base
        case costCenter = "cost_center", todayBRL = "today_brl", budgetBRL = "budget_brl"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        domain = try? c.decodeIfPresent(String.self, forKey: .domain)
        costCenter = try? c.decodeIfPresent(String.self, forKey: .costCenter)
        running = (try? c.decodeIfPresent(Bool.self, forKey: .running)) ?? false
        todayBRL = try? c.decodeIfPresent(Double.self, forKey: .todayBRL)
        budgetBRL = try? c.decodeIfPresent(Double.self, forKey: .budgetBRL)
        module = try? c.decodeIfPresent(String.self, forKey: .module)
        base = try? c.decodeIfPresent(String.self, forKey: .base)
    }

    /// Broken, empty or non-object JSON is nil.
    public static func decode(_ data: Data?) -> StatusInfo? {
        guard let data, !data.isEmpty else { return nil }
        return try? JSONDecoder().decode(StatusInfo.self, from: data)
    }

    /// A `WKScriptMessage.body`: only an object with `type == "status"`.
    public static func decode(message body: Any) -> StatusInfo? {
        guard let object = body as? [String: Any], object["type"] as? String == "status",
              JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object) else { return nil }
        return decode(data)
    }

    /// A poll answer has no module (the server does not know the page's tab) and no base: keep the page's.
    public func filling(from old: StatusInfo?) -> StatusInfo {
        var next = self
        if next.module == nil { next.module = old?.module }
        if next.base == nil { next.base = old?.base }
        return next
    }

    /// `/domain/<slug>` -> `<slug>`.
    public var domainSlug: String? {
        guard let base, base.hasPrefix("/domain/") else { return nil }
        let slug = base.dropFirst("/domain/".count)
        return slug.isEmpty ? nil : String(slug)
    }

    /// The line's money text: "R$ 12,00 de R$ 100,00", "R$ 12,00" with no budget, "" with no cost center.
    public var moneyText: String {
        guard let todayBRL else { return "" }
        guard let budgetBRL else { return formatBRL(todayBRL) }
        return "\(formatBRL(todayBRL)) de \(formatBRL(budgetBRL))"
    }

    public var overBudget: Bool {
        guard let todayBRL, let budgetBRL else { return false }
        return todayBRL > budgetBRL
    }
}

/// "R$ 1.190,48": pt-BR grouping and decimal comma, two decimals, independent of the Mac's locale.
public func formatBRL(_ value: Double) -> String {
    guard value.isFinite else { return "R$ 0,00" }
    let cents = Int((abs(value) * 100).rounded())
    let whole = String(cents / 100), frac = String(format: "%02d", cents % 100)
    var grouped = "", count = 0
    for ch in whole.reversed() {
        if count > 0, count % 3 == 0 { grouped.append(".") }
        grouped.append(ch); count += 1
    }
    let sign = value < 0 && cents > 0 ? "-" : ""
    return "R$ \(sign)\(String(grouped.reversed())),\(frac)"
}

/// The route the ▶/⏸ falls back to when the page cannot toggle itself: the same ones the web button posts to.
public func clockRoute(base: String, running: Bool) -> String {
    "\(base)/time/\(running ? "stop" : "start")"
}
