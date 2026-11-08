---
name: lp-draft
description: >-
  Draft a product or version landing page as a single HTML prototype in the repo's
  `$WIKI_HOME/<projeto>/resources/` (not the final LP, and no Markdown copy): grill the user about the product
  with AskUserQuestion, absorb the product's design system (DESIGN.md or tokens, a UI package,
  the live site, a Design System artifact) or create one next to the page, write the page,
  serve it with Vite hot reload, check it with screenshots, and link it in the wiki. Use when
  the user says "lp", "landing page", "cria a LP da versão X", "transforma em LP", "LP em
  $WIKI_HOME/<projeto>/resources", "draft a landing page", "protótipo da landing". Not impeccable: that one
  designs and critiques any interface; lp-draft runs the whole LP draft and loads impeccable
  for the design part. Not wiki: lp-draft calls it only to link the page.
metadata:
  version: 0.3.0
  license: MIT
---

# lp-draft — a landing page prototype in `$WIKI_HOME/<projeto>/resources/`

The draft LP is **one HTML file**, `$WIKI_HOME/<projeto>/resources/<produto>-<versão>-lp.html`, for seeing and discussing the product's pitch. It is a prototype, not the final landing page: no Markdown version, no deploy, no real form.

## Where the LP sits in planning, and showcase first

In the owner's planning, the LP comes right after the brief: once a version's brief is written in `$WIKI_HOME/<projeto>/`, the next step is the version's LP, so partners and clients see the same picture before anything is built (it aligns expectations). **When the version has widgets or UI, the showcase comes first:** build the new and changed pieces as real components in the product's UI package and its showcase page (for the Sygnal, `libs/ui` and `sygnal.html`, both themes, with fictional data that matches the brief), then take the LP's images from that showcase (as `scripts/sygnal-shots.mjs` does). The prototype is the start of the final product, not throwaway art; the LP only tells the story around it. A version with no UI goes straight to Step 0.

The brief the LP reads from has a fixed shape: a hub page `<produto>-<versão>.md` (the goal in one line, each front in a paragraph with its link, what stays out, how we will know it worked, "Decidi X porque Y" lines, what waits on the owner, at most 8 questions to the partners), one page per front, and the outside input (a partner's chat, tracker docs) kept in `fontes/`. The LP's facts come only from these pages.

## Step 0 — Read the repo's rules

1. `AGENTS.md` / `CLAUDE.md` of the repo, and the wiki's HTML rule: `rg -n -i 'resources/' "$WIKI_HOME/<projeto>/manter-wiki.md"` (or the repo's maintenance page).
2. The copy ruler: `rg -l -i 'copywriting|escrever-bem|writing' "$WIKI_HOME/<projeto>"`, then read only the matching section (in biliboss: `moc-copywriting` and `escrever-bem`, with *O Alquimista* as the bar for the opening paragraph). No ruler in the repo: short sentences, concrete words, the reader's problem before the product.
3. What the conversation and the wiki already say about the product: `rg -n -i '<produto>' "$WIKI_HOME/<projeto>"`. Read the product's page, if any.

## Step 1 — Grill the product (AskUserQuestion)

Ask only what the conversation has not answered, up to 4 questions per call, recommended option first with "(Recommended)", each question self-contained. Cover:

- **Who reads it** (the buyer, in their words) and **the promise in one sentence**.
- **The call to action** and where it goes (WhatsApp, form, email). No destination yet → a placeholder, said so in the page footer.
- **What is fact and what is open**: price, niche, numbers, names of people, clients, years of experience, testimonials. Open items stay out of the page.
- **Brand and tone**, unless a design system answers it (Step 2).

When the page's content already comes from this conversation (a study, a comparison, the user's own thesis), skip the grill: decide audience, promise and CTA yourself and state them in the report as "Decidi X porque Y" — the desk owner wants autonomy, and a question about a draft costs more than a wrong guess he can revert.

Pitfall: never fill a gap with an invented fact (initials for the founders, "90+ years", a client logo, a testimonial) — a draft that looks finished gets shown to clients as is. An illustrative example (a sample chat, sample numbers) is fine when it reads as an example.

## Step 2 — Absorb or create the design system

Look for one, in this order, and use the first that exists:

1. **Tokens in the product repo**: `DESIGN.md`, `tokens.css`, `tailwind.config.*`, CSS custom properties.
2. **A UI package** (e.g. `@mukutu/ui`): its colors, fonts and components' look.
3. **The live site or a URL**: read colors, fonts and logo with the browser.
4. **A Design System artifact**: `Artifact` with `action: "list"`, `scope: "types"`, then list that type's artifacts and read the product's one.

**A designer's brand export beats the theme already in the UI package.** When the product has a newer design system from its designer (a manual plus `tokens.json` and logos), the LP and the showcase use it, never the older theme the package still ships: an LP in the superseded look misaligns exactly the people it is meant to align. A claude.ai artifact shared by link opens only for an account with access: ask the owner once to export it to a local folder, then copy that folder into the repo (next to the product's UI layer, as untouched reference material) right away, because a scratch export is cleaned up; re-list it before copying, since files can still be downloading.

None → **create** it: `$WIKI_HOME/<projeto>/resources/<produto>/tokens.css` (colors, fonts, radius, spacing, light and dark) and `$WIKI_HOME/<projeto>/resources/<produto>/design.md` (a few lines: the palette and why, the fonts, the tone). Pick it from the audience and brand, and load the `impeccable` skill for the design choices. The next version of the LP reuses these files.

Details and the token contract: [references/design-system.md](references/design-system.md).

## Step 3 — Write the page

- **File**: `$WIKI_HOME/<projeto>/resources/<produto>-<versão>-lp.html` (slug in lowercase, version like `0.1.0`).
- **Fragment**: start with `<meta charset="utf-8">`, the viewport meta and `<title>` (the product name, 1–3 words); no `<!doctype>`, `<html>` or `<body>`, so the same file can be published as an Artifact.
- **Tokens**: `<link rel="stylesheet" href="<produto>/tokens.css">` (or the absorbed source), and every color from a token. Dark mode under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`.
- **Libraries** only from a CDN with an exact version; fonts only from Google Fonts in the draft (a published copy self-hosts them: [references/publish.md](references/publish.md)).
- **The showcase inside the LP**: a section with a tab list (one tab per screen, its question as the label) and one `<iframe>` that loads the real screen file, with a line under it saying what to try. The theme toggle also sets `data-theme` on each iframe's `documentElement` (same origin) and on its `load`, or the screens stay light in a dark page. Keep fixed controls (the theme toggle) in the bottom-right corner, clear of section titles.
- **In a plan**, the LP lives in `$WIKI_HOME/<projeto>/resources/` on the plan branch and points at the screens in `.plan/<slug>/telas/` by relative path; serve the repo root (`python -m http.server` from the root) so both resolve.
- **Layout**: works at 390px with a 16px gutter and no horizontal scroll; `prefers-reduced-motion` respected.
- **Section spacing**: when a section also carries a layout class (`<section class="wrap">`), the class's `padding` shorthand overrides `section { padding }` and the sections glue together; write `section.wrap { padding-top: … }` (higher specificity), and in a grid of cards make an odd last item span the row (`li:last-child:nth-child(odd) { grid-column: 1 / -1 }`) or a gray empty cell shows.
- **A family of pages** (a second LP on the same study) reuses the first one's `tokens.css` and copies its CSS patterns; no new design system.
- **Structure is free, per product.** The only fixed parts: the promise at the top with the CTA, an opening paragraph that passes the copy ruler, and the CTA again at the end. Footer: product, version and "rascunho".

## Step 4 — Serve with hot reload

```sh
npx -y vite@6.4.5 "$WIKI_HOME/<projeto>/resources" --port 5180 --strictPort --open /<produto>-<versão>-lp.html
```

Run it in the background, then show it to the owner inside the dev-console: `devc browse localhost:5180/<file>` opens the console's Browser module, where he validates the page (same for any screen on a local server). If 5180 is taken, a server is probably already up: open `http://localhost:5180/<file>` instead of starting another. A sandboxed agent (T3 Code) cannot reach a server it starts; the user runs the command.

## Step 5 — Look at it

With the browser tools (Claude in Chrome, or Hermes `browser_exec` with `local=true` so it reaches localhost), on `http://localhost:5180/<file>`: screenshot at 390px and at desktop width, in light and in dark (set `document.documentElement.dataset.theme = 'dark'` with the JavaScript tool). Recipe for `browser_exec`: viewport via `cdp('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=True)` (1280×900 for desktop); set `document.documentElement.style.scrollBehavior='auto'` first, because the page's `scroll-behavior: smooth` makes a capture right after `scrollTo` land mid-scroll; jump per `section[id]` and copy each `capture_screenshot()` to its own file (the helper overwrites one path). Check `document.documentElement.scrollWidth == 390` for horizontal overflow. Fix what breaks (overflow, contrast, a section that collapses badly) and look again. Say in the report what you looked at; if the browser was unavailable, say the page was not seen.

## Step 6 — Link it in the wiki

Load `wiki` and let it do the wiki part: one line in `index.md` and in the product's `moc-*` pointing to `resources/<produto>-<versão>-lp.html` (with "`npm run wiki:resources` para abrir" or the Vite command), a diary note, dates, lint, and a commit of only these paths (the page, the product's `tokens.css` / `design.md`, the index and moc lines, the note). No push.

## Delegating the page

The page is long work: hand Step 3 to a subagent with a facts file as its ONLY source ("do not invent"), the design-system path, the section list, and "no git, no server". The parent keeps Steps 4–6: serve, screenshot, fix, commit. A subagent that never opened a browser says "not rendered" — treat the layout as unchecked until Step 5. For an LP that compares several things (frameworks, vendors, tools), the research-to-page pipeline is in [references/comparison-lp.md](references/comparison-lp.md).

## Publishing

The draft never deploys by itself. When the owner says the product's domain should show it, follow [references/publish.md](references/publish.md): serve it from the app already on that domain, never migrate the live service without his GO, and self-host the fonts first.

## Report

The URL being served, the file path, where the design system came from (absorbed from X, or created), what is a placeholder (CTA destination, sample numbers), what was seen in the screenshots, and the commit.
