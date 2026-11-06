import Testing
@testable import ConsoleCore

@Suite struct ShortcutTests {
    @Test func commandKOpensDomains() {
        #expect(PaletteMode.forShortcut("k", command: true, otherModifiers: false) == .domains)
        #expect(PaletteMode.forShortcut("K", command: true, otherModifiers: false) == .domains)
    }

    @Test func commandPOpensModules() {
        #expect(PaletteMode.forShortcut("p", command: true, otherModifiers: false) == .modules)
    }

    @Test func othersPassThrough() {
        #expect(PaletteMode.forShortcut("k", command: false, otherModifiers: false) == nil)
        #expect(PaletteMode.forShortcut("p", command: true, otherModifiers: true) == nil)  // ⇧⌘P stays the page's
        #expect(PaletteMode.forShortcut("c", command: true, otherModifiers: false) == nil)  // copy keeps working
        #expect(PaletteMode.forShortcut(nil, command: true, otherModifiers: false) == nil)
    }
}
