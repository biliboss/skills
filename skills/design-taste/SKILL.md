---
name: design-taste
description: Judge the taste and quality of something before it is made and after, in one of five facets (interface, business, product, software, writing); a verdict with reasons, not a process for producing it. The interface facet is the strongest, for landing pages on Tailwind and DaisyUI. It spots the generic AI-looking page, makes the author pick a point of view, and ends in a before-shipping check. Use when the user says "design-taste", "o gosto", "está genérico?", "cara de IA", "dá uma opinião de design", "isso está bom?", "qual o ponto de vista", "antes de entregar", "julga a LP". Not impeccable (it executes and critiques UI craft with commands and detectors; load it to fix what this finds), not design (canvas with the product's real widgets), not lp-draft (runs the whole LP draft; it calls this to judge).
metadata:
  version: 0.1.0
  license: MIT
---

# design-taste: a judgement before and after

`shape` routes "taste and quality" here. This skill **judges**; it does not produce. It answers two questions: *before* building, "what is the point of view and what will be refused?"; *after*, "does this have taste, and what is the one thing to fix first?". To fix UI, hand the verdict to `impeccable`; to draft an LP, `lp-draft` calls this for the verdict.

Changes: [CHANGELOG.md](CHANGELOG.md). Credits and sources: [README.md](README.md).

## How to read the tags

- **[casa]** comes from the owner's wiki (`~/biliboss/.wiki`); the page is cited. It is his preference.
- **[geral]** is general design judgement, not something he said. Say so when you use it as a reason; never present it as his taste.
- Nothing is invented as his. Where the wiki is silent on a facet, only [geral] appears or the facet is thin on purpose.

## Steps

1. **Pick the facet** (one, sometimes two): interface, business, product, software, writing. Say which.
2. **Mode.** Nothing exists yet: *before* (write the point of view and the refusals, 5 lines). Something exists: *after* (open it running, look, then verdict). Never judge a screen from its code alone [casa: `pedidos-licoes-entrega`: a screen leaves only after it was opened running and captured on desktop and mobile].
3. **Verdict in this shape:** the point of view as you read it (one sentence; if you cannot write it, that is the finding), what is generic, what has taste, the one fix that moves it most, and a ship / do not ship. Short; the owner reads fast [casa: `escrever-bem`].
4. **Hand off.** Fixing goes to `impeccable` (or the builder); a missing system goes to `lp-draft`'s design-system step. Do not rewrite the page yourself.

## Interface (landing pages, Tailwind + DaisyUI)

### What the owner's wiki shows

All of it was written for terminal screens (`~/biliboss/.wiki/design-taste.md`); carrying it to the web is my inference, flagged here once.

- **[casa] Weight, colour and space organise the information, not frames or ornament.** Hierarchy comes from normal vs. dim vs. bold and from white space.
- **[casa] One accent colour, for what matters.** Colour that is everywhere says nothing; red only for error. (His terminal accent is bordô `#800020` per the Hermes `design-taste` skill; a product picks its own.)
- **[casa] Nothing repeated and nothing the system does not know.** A fact appears once; no placeholder claim.
- **[casa] Start minimal; add a block only when asked.**
- **[casa] Test at the size it will be used,** and a landing page with a mis-scaled phone was refused live in a meeting (`pedidos-licoes-entrega`).
- **[casa] The checklist of "design humilde"** (`recurso-design-humilde`): see, hear, touch, feel, create, validate, not-know, conform, fail. The two that bite a page: *Ver* (what is seen first, desktop and phone, with prints) and *Errar* (what shows when it fails, empty, or offline).
- **[casa] Copy** (`moc-copywriting`, `marketing-pessoal-voz`, `escrever-bem`): the opening is the point of view said by one concrete image, not an abstract claim; short sentences, everyday words, active verbs; no invented number, case or client.

### How to spot the generic AI-looking page [geral]

Count the signs; three or more and the page has no point of view yet.

- **Untouched DaisyUI theme.** Default `light`/`dark` or a stock theme name, `btn-primary` in the stock indigo or violet, nothing set for radius, font or palette.
- **The stock skeleton.** Navbar, `hero` with headline + two buttons + image on the right, a row of three equal icon cards, a `stats` strip, testimonials, pricing in three cards, a CTA band, a footer. The order could belong to any product.
- **Same-size feature cards** with an icon in a circle, a heading and two lines. Cards used as the page structure; nested cards.
- **Gradient text, purple-to-blue gradients, blurred blobs, glassmorphism,** `rounded-2xl shadow-xl` on everything.
- **Emoji or random icons as decoration;** a kicker/eyebrow above every heading; numbered sections without a sequence that matters.
- **Copy that fits any product:** "Supercharge your workflow", "all-in-one", "seamless", "unlock", "next-generation", a headline with no noun the reader would say aloud.
- **One font, default weights,** every heading the same size jump, centered text everywhere.
- **Stock or generated imagery** that shows nothing of the product; a real screenshot is stronger than any illustration.
- **Every section animates in the same way.**

Execution-level bans and detectors live in `impeccable` (`reference/craft-floor.md`); do not duplicate them, point to them.

### Choose a point of view (before)

Write these five lines before anything is built; if one stays blank, ask or decide, do not start.

1. **The reader and the moment:** who opens this, where, in what mood (a broker on the phone between visits is not a CTO at a desk).
2. **The one promise,** in the words that person would say, with a concrete image. Not a category.
3. **The one accent and the one personality** (quiet, blunt, warm, technical, playful), with a reason from the product. A point of view is a choice that excludes something.
4. **What it is not:** name two things it will refuse (e.g. no stock hero image, no card grid, no gradient). Refusals are what make taste visible.
5. **The proof:** the real thing it can show (screenshot, number from a source, a real quote). Without proof, shorter beats grander.

### Judge the build (after)

- **Hierarchy:** blur your eyes or shrink the screenshot to thumbnail. One thing wins, a second is clear, the rest recedes. If five things shout, nothing does. Check by size, weight and space before colour.
- **Restraint:** one accent, at most two type sizes of jump per section, one authored motion. Remove one element per section and see if it still works; if yes, leave it out.
- **DaisyUI with intent:** a custom theme (palette, radius and font variables set from the brand), component classes used where they fit (`btn`, `navbar`, `badge`) but layout, spacing and type scale decided by the page, not inherited. Utility sprawl is not taste either; repeated patterns belong in one place.
- **Copy first:** read the headline and sub aloud. If it could be the headline of a competitor, it fails.
- **Proof and honesty:** every number has a source; no invented testimonials or logos.
- **Mobile is the page,** not a shrunk desktop: the first screen on a phone still holds the promise and the one action.

### Reject (without more discussion) [geral]

The stock skeleton with no choice behind it; gradient text; an eyebrow on every heading; icon-in-circle card grids; invented stats or testimonials; a CTA that says "Get started" when the action has a name; any element that exists only because the template had a slot.

### Before shipping (checklist)

- [ ] The point-of-view sentence exists and the page obeys it.
- [ ] Opened running, captured on phone and desktop, light and dark if both ship; looked at, not assumed [casa].
- [ ] Thumbnail test: one clear focal point and one primary action.
- [ ] Not three or more of the generic signs above.
- [ ] Theme is custom; accent used for the action and nothing else.
- [ ] Empty, error and loading states of any form or live part exist [casa: *Errar*].
- [ ] Copy has no invented claim and passes the competitor test.
- [ ] Contrast, focus and tap targets pass (run `impeccable audit` for the mechanical part).

## Other facets (brief; only what the wiki grounds)

- **Business.** [casa] Ask by the outcome, not the named thing: "daqui a 90 dias deu certo: o que mudou?" (`shape`, *Pelo resultado*; `fit-for-purpose`). [casa] The Hustler asks first whether the thing should exist (`pedidos-licoes-entrega`). [casa] Leave no decision open: pick, record why, list the dropped options with reasons. Taste here is the cheapest move that moves the number.
- **Product.** [casa] See before making, keep the evidence (print, quote, number), and let the person served say whether it is good (`recurso-design-humilde`). Say what is still not known. [geral] A product has taste when it can say what it refuses to do.
- **Software.** [casa] The rules of `software-design-taste`: KISS; wiki and scripts first, skill when relevant, app last; one file per purpose; one source per datum and one writer per field; code in English, docs in Portuguese; a rule that can be measured becomes a test, otherwise it stays "só revisão". Judge a change against that table instead of restating it.
- **Writing.** [casa] `escrever-bem` (clarity, brevity, strong verb, the reader is in a hurry, cut the clutter), `moc-copywriting` (the opening should be good to read; short sentence, everyday word, concrete image, warmth), `marketing-pessoal-voz` (open with a concrete image; offer two alternative openings outside the text; separate fact, hypothesis and experiment; never invent a number or a client).

## Pitfalls

- Do not pass off general judgement as the owner's taste; tag it. His interface wiki is about terminals and gives principles, not a landing-page style.
- A verdict is not a redesign: name the one fix that matters most, then stop. A list of twenty is a failure to judge.
- A pinned brief (a client's brand, a fixed palette) beats these defaults; judge whether the page serves the brief well, not whether it matches your taste.
- The house's Hermes skill `design-taste` (Bili profile, 0.3.0) holds the dev-console, domain, graph and code rules; this one is the portable judgement. When a dev-console screen is the subject, read that one as well.
