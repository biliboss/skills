import Foundation
import Testing
@testable import ConsoleCore

@Suite struct RecorderTests {
    func line(_ at: String, dir: String = "/r") -> RecorderLine {
        RecorderLine(at: at, url: "http://127.0.0.1:5057/", domain: "demo", module: "Domain", width: 960, height: 800,
                     shot: RecorderRing.shotPath(dir: dir, at: at))
    }

    @Test func encodesOneLineWithEveryKey() throws {
        let text = try #require(line("20261106T120000.123Z").encoded())
        #expect(!text.contains("\n"))
        for key in ["at", "url", "domain", "module", "event", "widget", "width", "height", "errors", "shot"] {
            #expect(text.contains("\"\(key)\":"))
        }
        #expect(text.contains("\"event\":null") && text.contains("\"errors\":[]"))
        #expect(RecorderLine.decode(text) == line("20261106T120000.123Z"))
        #expect(RecorderLine.decode("not json") == nil)
    }

    @Test func atIsUTCAndFileSafe() {
        let at = RecorderRing.at(Date(timeIntervalSince1970: 1_793_966_400.123))
        #expect(at == "20261106T120000.123Z")
        #expect(RecorderRing.shotPath(dir: "/r", at: at) == "/r/shots/20261106T120000.123Z.png")
    }

    @Test func trimKeepsTheLastTwenty() {
        let lines = (1...25).map { "{\"at\":\"\($0)\"}" } + ["", "  "]
        let (kept, dropped) = RecorderRing.trim(lines: lines)
        #expect(kept.count == 20 && kept.first == "{\"at\":\"6\"}" && kept.last == "{\"at\":\"25\"}")
        #expect(dropped.count == 5 && dropped.first == "{\"at\":\"1\"}")
        let short = RecorderRing.trim(lines: ["{}", "{}"])
        #expect(short.kept.count == 2 && short.dropped.isEmpty)
    }

    @Test func onlyShotsUnderTheRecorderDirAreDeleted() throws {
        let inside = try #require(line("a", dir: "/r").encoded())
        let outside = try #require(line("b", dir: "/elsewhere").encoded())
        let sneaky = try #require(RecorderLine(at: "c", shot: "/r/shots/../../etc/x.png").encoded())
        let del = RecorderRing.shotsToDelete(dropped: [inside, outside, sneaky, "junk"], dir: "/r")
        #expect(del == ["/r/shots/a.png"])
    }

    @Test func sameStateIgnoresTimeAndErrors() {
        var a = line("1"), b = line("2")
        b.errors = ["boom"]
        #expect(a.sameState(as: b))
        a.widget = "Timeline"
        #expect(!a.sameState(as: b))
    }

    @Test func decodesThePageReport() {
        let body: [String: Any] = ["type": "recorder", "domain": "demo", "module": "Events", "event": NSNull(),
                                   "widget": "Timeline", "errors": ["pageerror: x"]]
        let r = PageReport.decode(message: body)
        #expect(r == PageReport(domain: "demo", module: "Events", event: nil, widget: "Timeline", errors: ["pageerror: x"]))
        #expect(PageReport.decode(message: ["type": "status"]) == nil)
        #expect(PageReport.decode(message: "x") == nil)
    }

    @Test func clipsErrors() {
        let many = (0..<30).map { "e\($0)" } + ["  "]
        #expect(clipErrors(many).count == 20)
        #expect(clipErrors([String(repeating: "x", count: 400)])[0].count == 301)
        #expect(clipErrors(["", " "]).isEmpty)
    }

    @Test func windowCommandKnowsShot() {
        let c = WindowCommand(id: 1, action: "shot")
        #expect(c.action == .shot && c.validationError() == nil)
    }
}
