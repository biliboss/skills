# The design system of a draft LP

The page never hard-codes a color or a font. It reads tokens, so the next version of the LP, and later the real site, start from the same values.

## The token contract

`$WIKI_HOME/<projeto>/resources/<produto>/tokens.css` defines at least these custom properties, for light and for dark:

| Token | What it is |
|---|---|
| `--bg`, `--surface` | page background and card background |
| `--ink`, `--mute` | main text and secondary text |
| `--line` | borders and dividers |
| `--acc`, `--acc-soft` | the brand accent and its tint for backgrounds |
| `--ok` | positive numbers and checks |
| `--cta` | the call-to-action button (e.g. WhatsApp green when the CTA is WhatsApp) |
| `--font-display`, `--font-body` | headline and body font stacks |
| `--radius` | the base corner radius |

Dark values go twice: under `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){…}}` and under `:root[data-theme="dark"]{…}`, so the screenshot step can force a theme. The page body sets `background: var(--bg)` explicitly.

## Absorbing an existing system

Map what you find onto the contract above; do not invent names the source does not have.

- **DESIGN.md / tokens / Tailwind**: copy the values, keep the source's names in a comment next to each token.
- **UI package**: read its theme or CSS variables from `node_modules` or the source repo; take its fonts too.
- **Live site**: read `getComputedStyle` of the body, headings and the main button with the browser JavaScript tool; note the URL and date in `design.md`.
- **Design System artifact**: read it with `Artifact` (`action: "read"`) and take its tokens; link it in `design.md`.

Absorbed values still go into `$WIKI_HOME/<projeto>/resources/<produto>/tokens.css`, with `design.md` saying where they came from, so the draft works offline and the source can be re-read later.

## Creating one

Choose from the audience and the promise, not from habit. Write `design.md` in a few lines: the palette and why (e.g. warm cream and terracotta with a serif for a service sold on trust to small-business owners), the two fonts, the tone, and the larger base size (17–18px) when the readers are older. Load `impeccable` for the choices.
