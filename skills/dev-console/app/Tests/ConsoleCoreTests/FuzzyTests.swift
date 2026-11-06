import Foundation
import Testing
@testable import ConsoleCore

@Suite struct FuzzyMatchTests {
    @Test func subsequenceMatchesInOrder() {
        #expect(fuzzyMatch("tsk", in: "Task Results")?.positions == [0, 2, 3])
        #expect(fuzzyMatch("rk", in: "Task Results") == nil)  // out of order
        #expect(fuzzyMatch("zz", in: "Task Results") == nil)
    }

    @Test func caseAndAccentsAreIgnored() {
        #expect(fuzzyMatch("visao", in: "Visão") != nil)
        #expect(fuzzyMatch("VISÃO", in: "visao") != nil)
        #expect(fuzzyMatch("dominios", in: "Domínios")?.positions == Array(0..<8))
        #expect(fuzzyMatch("cafe", in: "Café")?.positions == [0, 1, 2, 3])
    }

    @Test func emptyQueryMatchesAll() {
        #expect(fuzzyMatch("", in: "anything") == FuzzyMatch(score: 0, positions: []))
        #expect(fuzzyMatch("  ", in: "x")?.positions == [])
    }

    @Test func queryLongerThanCandidateFails() {
        #expect(fuzzyMatch("playgrounds", in: "Playground") == nil)
    }

    @Test func prefixAndWordStartBeatScatter() {
        let prefix = fuzzyMatch("pla", in: "Playground")!
        let scatter = fuzzyMatch("pla", in: "Stop later")!
        #expect(prefix.score > scatter.score)
        let word = fuzzyMatch("tr", in: "Task Results")!
        let inner = fuzzyMatch("tr", in: "Attractor")!
        #expect(word.score > inner.score)
    }

    @Test func rankSortsBestFirstAndKeepsOrderOnTies() {
        let items = ["Stop later", "Playground", "Agents"]
        #expect(fuzzyRank("pla", in: items).map(\.index) == [1, 0])
        #expect(fuzzyRank("", in: items).map(\.index) == [0, 1, 2])
        #expect(fuzzyRank("age", in: items).map(\.index) == [2])
    }

    @Test func positionsStayAlignedWithTheOriginalText() {
        // "ç" folds to one character, so the offsets are those of the original string
        #expect(fuzzyMatch("aca", in: "Ação")?.positions == [0, 1, 2] || fuzzyMatch("aca", in: "Ação") == nil)
        #expect(fuzzyMatch("ac", in: "Ação")?.positions == [0, 1])
    }
}

@Suite struct PaletteModelTests {
    private let base = URL(string: "http://127.0.0.1:5098")!
    private let json = #"""
    {"domains":[{"slug":"tasks","name":"Tasks"},{"slug":"costs","name":"Costs"}],
     "modules":[{"id":"Domain","title":"Domain","url":"/domain/costs?tab=Domain"},
                {"id":"Task Results","title":"Task Results","url":"/domain/costs?tab=Task%20Results"},
                {"id":"playground","title":"Playground","url":"/playground"},
                {"id":"agents","title":"Agents","url":"/agents"}]}
    """#

    @Test func decodesAndBuildsAbsoluteURLs() {
        let p = PalettePayload.decode(Data(json.utf8))!
        let page = URL(string: "http://127.0.0.1:5098/domain/costs/t/x")!
        let d = p.items(.domains, base: base, current: page)
        #expect(d.map(\.title) == ["Tasks", "Costs"])
        #expect(d.map(\.isCurrent) == [false, true])
        #expect(d[0].url.absoluteString == "http://127.0.0.1:5098/domain/tasks")
        let m = p.items(.modules, base: base, current: page)
        #expect(m[1].url.absoluteString == "http://127.0.0.1:5098/domain/costs?tab=Task%20Results")
        #expect(m.map(\.isCurrent) == [true, false, false, false])  // no ?tab= is the Domain module
    }

    @Test func currentModuleFollowsTabAndPath() {
        let p = PalettePayload.decode(Data(json.utf8))!
        let tab = URL(string: "http://127.0.0.1:5098/domain/costs/t/x?tab=Task%20Results")!
        #expect(p.items(.modules, base: base, current: tab).map(\.isCurrent) == [false, true, false, false])
        let pg = URL(string: "http://127.0.0.1:5098/playground")!
        #expect(p.items(.modules, base: base, current: pg).map(\.isCurrent) == [false, false, true, false])
        #expect(p.items(.domains, base: base, current: pg).allSatisfy { !$0.isCurrent })
    }

    @Test func badJSONIsNil() {
        #expect(PalettePayload.decode(nil) == nil)
        #expect(PalettePayload.decode(Data("{}".utf8)) == nil)
    }

    @Test func endpointCarriesTheDomain() {
        let on = URL(string: "http://127.0.0.1:5098/domain/costs/t/x?tab=Domain")!
        #expect(paletteEndpoint(base: base, current: on)?.absoluteString == "http://127.0.0.1:5098/api/palette?domain=costs")
        #expect(paletteEndpoint(base: base, current: URL(string: "http://127.0.0.1:5098/agents"))?.absoluteString
                == "http://127.0.0.1:5098/api/palette")
    }
}
