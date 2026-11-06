import Foundation

/// The page the window opens at launch: the console's home (`/`, the focus: the Kanban card in Doing, or the board),
/// never the last URL it saved in state.json. A window launched for one page (`DEV_CONSOLE_URL`, as
/// `window.sh --owner <name> launch <url>` does) opens that page.
public func launchURL(environment: [String: String]) -> URL {
    let home = URL(string: "http://127.0.0.1:5057/")!
    guard let text = environment["DEV_CONSOLE_URL"]?.trimmingCharacters(in: .whitespaces), !text.isEmpty,
          let url = URL(string: text), url.scheme != nil else { return home }
    return url
}
