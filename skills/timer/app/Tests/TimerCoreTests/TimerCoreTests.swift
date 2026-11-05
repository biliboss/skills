import Foundation
import Testing
@testable import TimerCore

private let t0 = Date(timeIntervalSince1970: 1_000_000)

@Suite struct StateTests {
    @Test func decodesRunning() {
        let json = #"{"status":"running","ends_at":1000060,"remaining":null,"label":"foco","updated_at":1000000}"#
        let s = TimerState.decode(Data(json.utf8))
        #expect(s.status == .running)
        #expect(s.label == "foco")
        #expect(s.remaining(now: t0.addingTimeInterval(15)) == 45)
    }

    @Test func decodesPaused() {
        let s = TimerState.decode(Data(#"{"status":"paused","remaining":30,"label":""}"#.utf8))
        #expect(s.status == .paused)
        #expect(s.remaining(now: t0) == 30)
        #expect(s.remaining(now: t0.addingTimeInterval(999)) == 30)
    }

    @Test func brokenOrMissingIsIdle() {
        #expect(TimerState.decode(nil).status == .idle)
        #expect(TimerState.decode(Data()).status == .idle)
        #expect(TimerState.decode(Data("nope".utf8)).status == .idle)
        #expect(TimerState.decode(Data(#"{"status":"weird"}"#.utf8)).status == .idle)
    }

    @Test func remainingNeverNegativeAndExpires() {
        let s = TimerState(status: .running, endsAt: 1_000_010)
        #expect(!s.isExpired(now: t0))
        #expect(s.isExpired(now: t0.addingTimeInterval(10)))
        #expect(s.remaining(now: t0.addingTimeInterval(500)) == 0)
        #expect(!TimerState(status: .paused, remaining: 0).isExpired(now: t0))
    }
}

@Suite struct DisplayTests {
    @Test func idle() {
        #expect(display(for: TimerState(), now: t0) == .idle)
    }

    @Test func runningIgnoresLabel() {
        var s = TimerState(status: .running, endsAt: 1_000_125)
        #expect(display(for: s, now: t0) == .running("02:05"))
        s.label = "foco"
        #expect(display(for: s, now: t0) == .running("02:05"))
    }

    @Test func runningOverOneHour() {
        let s = TimerState(status: .running, endsAt: 1_003_725)
        #expect(display(for: s, now: t0) == .running("1:02:05"))
    }

    @Test func pausedIsDistinctFromRunning() {
        let s = TimerState(status: .paused, remaining: 90, label: "x")
        #expect(display(for: s, now: t0) == .paused("01:30"))
        #expect(display(for: s, now: t0) != .running("01:30"))
    }

    @Test func expiredShowsZero() {
        let s = TimerState(status: .running, endsAt: 1_000_000)
        #expect(display(for: s, now: t0.addingTimeInterval(3)) == .running("00:00"))
    }

    @Test func tooltipIsTheLabel() {
        #expect(tooltip(for: TimerState(label: "foco")) == "foco")
        #expect(tooltip(for: TimerState(label: "  ")) == nil)
        #expect(tooltip(for: TimerState()) == nil)
    }
}

@Suite struct FormatTests {
    @Test func formats() {
        #expect(format(seconds: 0) == "00:00")
        #expect(format(seconds: 0.2) == "00:01")
        #expect(format(seconds: 65) == "01:05")
        #expect(format(seconds: 3600) == "1:00:00")
        #expect(format(seconds: 3725) == "1:02:05")
        #expect(format(seconds: -5) == "00:00")
    }
}

@Suite struct ParseTests {
    @Test func accepted() {
        #expect(parseDuration("25") == 1500)
        #expect(parseDuration("25m") == 1500)
        #expect(parseDuration("90s") == 90)
        #expect(parseDuration("1h") == 3600)
        #expect(parseDuration("1:30") == 90)
        #expect(parseDuration(" 5 ") == 300)
    }

    @Test func rejected() {
        for bad in ["", "0", "0s", "abc", "-5", "1:75", "1:2:3", "m", "1.5", "5x", ":30", "1:"] {
            #expect(parseDuration(bad) == nil, "\(bad)")
        }
    }
}
