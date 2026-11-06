import Foundation

// Fuzzy matching and the model of the native command palette (⌘K domains, ⌘P modules). Pure: no AppKit.

/// One match: a higher `score` is a better match; `positions` are the candidate's Character offsets that matched,
/// for bolding them.
public struct FuzzyMatch: Equatable, Sendable {
    public var score: Int
    public var positions: [Int]
}

/// Lowercased and without accents, one Character at a time so offsets stay aligned with the original text.
private func folded(_ text: String) -> [Character] {
    text.map { ch in
        let f = String(ch).folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil)
        return f.first ?? ch
    }
}

/// Subsequence match, case and accent insensitive: every letter of `query` appears in `candidate`, in order (spaces in the
/// query are ignored). Nil when it does not. Scoring prefers: the match at the start, at word starts, consecutive letters,
/// and fewer gaps. An empty query matches everything with score 0.
public func fuzzyMatch(_ query: String, in candidate: String) -> FuzzyMatch? {
    let q = folded(query).filter { !$0.isWhitespace }
    if q.isEmpty { return FuzzyMatch(score: 0, positions: []) }
    let c = folded(candidate)
    let original = Array(candidate)
    guard q.count <= c.count else { return nil }

    func isBoundary(_ i: Int) -> Bool {
        if i == 0 { return true }
        let prev = original[i - 1]
        return !(prev.isLetter || prev.isNumber) || (prev.isLowercase && original[i].isUppercase)
    }

    // Greedy leftmost match first (existence), then improve: for each start candidate of the first letter, match greedily
    // and keep the best-scoring run. Candidates are short (names), so this is cheap.
    var best: FuzzyMatch?
    var start = 0
    while start < c.count {
        guard let first = c[start...].firstIndex(of: q[0]) else { break }
        start = first + 1
        var positions = [first]
        var cursor = first + 1
        var ok = true
        for ch in q.dropFirst() {
            // prefer a word boundary or the immediate next letter when one is close, otherwise the next occurrence
            guard let next = c[cursor...].firstIndex(of: ch) else { ok = false; break }
            var pick = next
            if next != cursor, let boundary = (cursor..<c.count).first(where: { c[$0] == ch && isBoundary($0) }),
               boundary - cursor <= 3 {
                pick = boundary
            }
            positions.append(pick)
            cursor = pick + 1
        }
        if !ok { break }  // a later start cannot match either
        var score = 0
        for (k, p) in positions.enumerated() {
            score += 10
            if isBoundary(p) { score += 8 }
            if k > 0 {
                let gap = p - positions[k - 1] - 1
                score += gap == 0 ? 6 : -min(gap, 8)
            }
        }
        score -= min(positions[0], 10)  // a late start is worse
        if positions[0] == 0 { score += 10 }
        if q.count == c.count && positions.last == c.count - 1 && positions == Array(0..<c.count) { score += 20 }  // exact
        if best == nil || score > best!.score { best = FuzzyMatch(score: score, positions: positions) }
    }
    return best
}

/// The indexes of `items` that match, best first (ties keep the original order). An empty query keeps every item in order.
public func fuzzyRank(_ query: String, in items: [String]) -> [(index: Int, match: FuzzyMatch)] {
    let hits = items.enumerated().compactMap { i, s in fuzzyMatch(query, in: s).map { (index: i, match: $0) } }
    return hits.sorted { a, b in
        a.match.score != b.match.score ? a.match.score > b.match.score : a.index < b.index
    }
}

// MARK: palette model

/// Which list the palette shows.
public enum PaletteMode: String, Sendable {
    case domains, modules

    public var title: String { self == .domains ? "Domínios" : "Módulos" }
    public var placeholder: String { self == .domains ? "domínio…" : "módulo…" }
}

public struct PaletteItem: Equatable, Sendable {
    public var title: String
    public var subtitle: String
    /// Absolute URL to load in the web view.
    public var url: URL
    public var isCurrent: Bool
}

/// `GET /api/palette?domain=<slug>`: `{domains:[{slug,name}], modules:[{id,title,url}]}`; urls are paths on the console.
public struct PalettePayload: Decodable, Equatable, Sendable {
    public struct Domain: Decodable, Equatable, Sendable { public var slug: String; public var name: String }
    public struct Module: Decodable, Equatable, Sendable { public var id: String; public var title: String; public var url: String }
    public var domains: [Domain]
    public var modules: [Module]

    public static func decode(_ data: Data?) -> PalettePayload? {
        guard let data else { return nil }
        return try? JSONDecoder().decode(PalettePayload.self, from: data)
    }

    /// The items of one mode with absolute URLs against `base` (the console's origin). `current` is the page's URL: the
    /// domain whose slug is in `/domain/<slug>`, or the module whose url equals the page's path (and tab).
    public func items(_ mode: PaletteMode, base: URL, current: URL?) -> [PaletteItem] {
        switch mode {
        case .domains:
            let slug = current.flatMap(Self.domainSlug)
            return domains.compactMap { d in
                URL(string: "/domain/\(d.slug)", relativeTo: base).map {
                    PaletteItem(title: d.name, subtitle: d.slug, url: $0.absoluteURL, isCurrent: d.slug == slug)
                }
            }
        case .modules:
            return modules.compactMap { m in
                URL(string: m.url, relativeTo: base).map {
                    PaletteItem(title: m.title, subtitle: "", url: $0.absoluteURL, isCurrent: Self.sameModule(m.url, current))
                }
            }
        }
    }

    /// `/domain/<slug>…` gives the slug; any other page none.
    public static func domainSlug(_ url: URL) -> String? {
        let parts = url.path.split(separator: "/").map(String.init)
        return parts.count >= 2 && parts[0] == "domain" ? parts[1] : nil
    }

    static func sameModule(_ moduleURL: String, _ current: URL?) -> Bool {
        guard let current, let m = URLComponents(string: moduleURL) else { return false }
        let mTab = m.queryItems?.first { $0.name == "tab" }?.value
        let cTab = URLComponents(url: current, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "tab" }?.value
        if let mTab { return current.path.hasPrefix(m.path) && mTab == (cTab ?? "Domain") }
        // a module without a tab: the page's own path; a domain page without ?tab= is the "Domain" module
        if m.path.hasPrefix("/domain/") { return current.path.hasPrefix(m.path) && (cTab == nil || cTab == "Domain") }
        return current.path == m.path
    }
}

/// The path `GET` for the palette's data, with the page's domain when it is on one.
public func paletteEndpoint(base: URL, current: URL?) -> URL? {
    var parts = URLComponents(url: base, resolvingAgainstBaseURL: false)
    parts?.path = "/api/palette"
    if let slug = current.flatMap(PalettePayload.domainSlug) { parts?.queryItems = [URLQuery.item("domain", slug)] }
    return parts?.url
}

private enum URLQuery {
    static func item(_ name: String, _ value: String) -> URLQueryItem { URLQueryItem(name: name, value: value) }
}
