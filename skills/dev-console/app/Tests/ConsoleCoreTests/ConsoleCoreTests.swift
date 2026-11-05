import CoreGraphics
import Foundation
import Testing
@testable import ConsoleCore

private func cmd(_ json: String) -> WindowCommand? { WindowCommand.decode(Data(json.utf8)) }

@Suite struct CommandDecodeTests {
    @Test func decodesOpen() {
        let c = cmd(#"{"id":3,"action":"open","url":"http://127.0.0.1:5057/","updated_at":1000}"#)
        #expect(c?.id == 3)
        #expect(c?.action == .open)
        #expect(c?.url == "http://127.0.0.1:5057/")
        #expect(c?.validationError() == nil)
    }

    @Test func decodesDockAndResize() {
        let d = cmd(#"{"id":4,"action":"dock","side":"left"}"#)
        #expect(d?.dockSide == .left)
        #expect(d?.validationError() == nil)
        let r = cmd(#"{"id":5,"action":"resize","width":900,"height":700}"#)
        #expect(r?.width == 900 && r?.height == 700)
        #expect(r?.validationError() == nil)
    }

    @Test func brokenOrMissingIsNil() {
        #expect(WindowCommand.decode(nil) == nil)
        #expect(WindowCommand.decode(Data()) == nil)
        #expect(cmd("nope") == nil)
        #expect(cmd(#"{"action":"reload"}"#) == nil)
    }

    @Test func validationCatchesBadFields() {
        #expect(cmd(#"{"id":1,"action":"dance"}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"open"}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"open","url":"not a url"}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"resize","width":0,"height":5}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"dock","side":"top"}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"eval","js":""}"#)?.validationError() != nil)
        #expect(cmd(#"{"id":1,"action":"reload"}"#)?.validationError() == nil)
    }
}

@Suite struct GateTests {
    @Test func appliesEachIdOnce() throws {
        var gate = CommandGate()
        let a = try #require(cmd(#"{"id":1,"action":"reload"}"#))
        let first = gate.accept(a)
        let second = gate.accept(a)
        let third = gate.accept(a)
        #expect(first)
        #expect(!second)
        #expect(!third)
        let b = try #require(cmd(#"{"id":2,"action":"show"}"#))
        let next = gate.accept(b)
        #expect(next)
        #expect(gate.lastApplied == 2)
    }

    @Test func ignoresOlderIds() throws {
        var gate = CommandGate(lastApplied: 7)
        let five = gate.accept(try #require(cmd(#"{"id":5,"action":"hide"}"#)))
        let seven = gate.accept(try #require(cmd(#"{"id":7,"action":"hide"}"#)))
        let eight = gate.accept(try #require(cmd(#"{"id":8,"action":"hide"}"#)))
        #expect(!five)
        #expect(!seven)
        #expect(eight)
    }

    @Test func restartDoesNotReplayTheLastCommand() throws {
        // The app starts with the last_command_id it wrote before quitting.
        let state = WindowState.decode(Data(#"{"last_command_id":9}"#.utf8))
        var gate = CommandGate(lastApplied: state.lastCommandId)
        let replay = gate.accept(try #require(cmd(#"{"id":9,"action":"open","url":"http://x/"}"#)))
        #expect(!replay)
    }
}

@Suite struct StateTests {
    @Test func roundTrips() throws {
        let s = WindowState(url: "http://127.0.0.1:5057/domain/x", title: "Console", visible: true, width: 960,
                            height: 800, lastCommandId: 2, lastResult: "42",
                            lastMessage: .object(["kind": .string("ping"), "n": .number(1)]), updatedAt: 5)
        let back = WindowState.decode(s.encoded())
        #expect(back == s)
    }

    @Test func encodesEveryKey() throws {
        let data = try #require(WindowState().encoded())
        let obj = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        for key in ["url", "title", "visible", "width", "height", "last_command_id", "last_result", "last_message", "updated_at"] {
            #expect(obj[key] != nil, "missing \(key)")
        }
    }

    @Test func brokenIsFresh() {
        #expect(WindowState.decode(nil) == WindowState())
        #expect(WindowState.decode(Data("x".utf8)) == WindowState())
    }
}

@Suite struct ResultTests {
    @Test func rendersJSResults() {
        #expect(renderEvalResult("hello") == "hello")
        #expect(renderEvalResult(NSNumber(value: 42)) == "42")
        #expect(renderEvalResult(NSNumber(value: true)) == "true")
        #expect(renderEvalResult(NSNull()) == "null")
        #expect(renderEvalResult(nil) == "undefined")
        #expect(renderEvalResult(["b": 1, "a": "x"] as [String: Any]) == #"{"a":"x","b":1}"#)
        #expect(renderEvalResult([1, 2] as [Any]) == "[1,2]")
    }

    @Test func convertsBridgeMessages() {
        let v = JSONValue(any: ["ok": true, "items": [1, "a"], "none": NSNull()] as [String: Any])
        #expect(v == .object(["ok": .bool(true), "items": .array([.number(1), .string("a")]), "none": .null]))
    }
}

@Suite struct FrameTests {
    private let visible = CGRect(x: 0, y: 25, width: 1800, height: 1000)

    @Test func dockRightTakesTwoThirdsAgainstTheRightEdge() {
        let f = dockFrame(in: visible, side: .right)
        #expect(f.width == 1200)
        #expect(f.height == 1000)
        #expect(f.maxX == visible.maxX)
        #expect(f.minY == visible.minY)
    }

    @Test func dockLeftTakesTwoThirdsAgainstTheLeftEdge() {
        let f = dockFrame(in: visible, side: .left)
        #expect(f.minX == 0)
        #expect(f.width == 1200)
    }

    @Test func dockRoundsOddWidths() {
        #expect(dockFrame(in: CGRect(x: 0, y: 0, width: 1512, height: 900), side: .right).width == 1008)
        #expect(dockFrame(in: CGRect(x: 0, y: 0, width: 1000, height: 900), side: .right).width == 667)
    }

    @Test func resizeKeepsTopLeft() {
        let f = resizedFrame(CGRect(x: 100, y: 200, width: 500, height: 400), width: 300, height: 250)
        #expect(f.minX == 100)
        #expect(f.maxY == 600)
        #expect(f.size == CGSize(width: 300, height: 250))
    }
}
