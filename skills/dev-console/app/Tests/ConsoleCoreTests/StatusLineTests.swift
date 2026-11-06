import Foundation
import Testing
@testable import ConsoleCore

@Suite struct StatusLineTests {
    @Test func formatsBRL() {
        #expect(formatBRL(1190.48) == "R$ 1.190,48")
        #expect(formatBRL(0) == "R$ 0,00")
        #expect(formatBRL(7.5) == "R$ 7,50")
        #expect(formatBRL(1234567.891) == "R$ 1.234.567,89")
        #expect(formatBRL(999.999) == "R$ 1.000,00")
        #expect(formatBRL(-12.3) == "R$ -12,30")
        #expect(formatBRL(.nan) == "R$ 0,00")
    }

    @Test func decodesStatusJSON() {
        let json = #"{"domain":"dev-console","cost_center":"Biliboss","running":true,"today_brl":1190.48,"budget_brl":1500,"module":"Agents"}"#
        let s = StatusInfo.decode(Data(json.utf8))
        #expect(s?.costCenter == "Biliboss" && s?.running == true && s?.module == "Agents")
        #expect(s?.moneyText == "R$ 1.190,48 de R$ 1.500,00")
        #expect(s?.overBudget == false)
    }

    @Test func nullsAndGarbage() {
        let s = StatusInfo.decode(Data(#"{"domain":"x","cost_center":null,"running":false,"today_brl":null,"budget_brl":null,"module":null}"#.utf8))
        #expect(s?.costCenter == nil && s?.moneyText == "")
        let noBudget = StatusInfo.decode(Data(#"{"running":false,"today_brl":3}"#.utf8))
        #expect(noBudget?.moneyText == "R$ 3,00")
        #expect(StatusInfo.decode(nil) == nil)
        #expect(StatusInfo.decode(Data()) == nil)
        #expect(StatusInfo.decode(Data("nope".utf8)) == nil)
        #expect(StatusInfo.decode(Data("[1]".utf8)) == nil)
    }

    @Test func overBudget() {
        #expect(StatusInfo(todayBRL: 11, budgetBRL: 10).overBudget)
        #expect(!StatusInfo(todayBRL: 10, budgetBRL: 10).overBudget)
        #expect(!StatusInfo(todayBRL: 10).overBudget)
    }

    @Test func messageFromThePage() {
        let ok: [String: Any] = ["type": "status", "domain": "d", "base": "/domain/d", "running": true, "today_brl": 2.5, "budget_brl": NSNull()]
        let s = StatusInfo.decode(message: ok)
        #expect(s?.running == true && s?.todayBRL == 2.5 && s?.budgetBRL == nil && s?.domainSlug == "d")
        #expect(StatusInfo.decode(message: ["type": "other"]) == nil)
        #expect(StatusInfo.decode(message: "text") == nil)
        #expect(StatusInfo.decode(message: ["running": true]) == nil)
    }

    @Test func pollKeepsPagesModuleAndBase() {
        let old = StatusInfo(module: "Agents", base: "/domain/d")
        let polled = StatusInfo(costCenter: "C", running: true, todayBRL: 5).filling(from: old)
        #expect(polled.module == "Agents" && polled.base == "/domain/d" && polled.running)
    }

    @Test func clockRoutes() {
        #expect(clockRoute(base: "/domain/d", running: false) == "/domain/d/time/start")
        #expect(clockRoute(base: "/domain/d", running: true) == "/domain/d/time/stop")
    }
}
