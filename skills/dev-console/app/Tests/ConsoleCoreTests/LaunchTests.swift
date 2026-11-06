import Foundation
import Testing
@testable import ConsoleCore

@Suite struct LaunchTests {
    @Test func opensTheHomeByDefault() {
        #expect(launchURL(environment: [:]).absoluteString == "http://127.0.0.1:5057/")
    }

    @Test func opensTheGivenPage() {
        #expect(launchURL(environment: ["DEV_CONSOLE_URL": "http://127.0.0.1:5093/"]).absoluteString == "http://127.0.0.1:5093/")
    }

    @Test func aBadOrEmptyPageFallsBackToTheHome() {
        #expect(launchURL(environment: ["DEV_CONSOLE_URL": ""]).absoluteString == "http://127.0.0.1:5057/")
        #expect(launchURL(environment: ["DEV_CONSOLE_URL": "not a url"]).absoluteString == "http://127.0.0.1:5057/")
    }
}
