# Publishing the LP on the product's own domain

The draft stays in `$WIKI_HOME/<projeto>/resources/`. When the owner says the product's domain should show it, he has made the
"publish outward" decision; this is how to do it without touching the service already on that domain.

## When the domain already serves a running app

Serve the LP from that app instead of moving the domain to another host. Moving a live service (to Coolify or
anywhere) means stopping it, which needs the owner's explicit GO; the LP does not need it. Record the migration as an
open question in the plan with "Decidi servir a LP do app que já está no domínio porque mover o serviço no ar exige GO".

1. **Copy the site into the app**: `site/index.html` (the LP), `site/telas/` (the showcase screens it embeds, plus
   their shared CSS), `site/logos/`. Rewrite the relative paths the draft used (`../../.plan/<slug>/telas/`,
   `../../libs/<brand>/...`) with one script, then grep the copy for the old prefixes: zero hits.
2. **Pack it like the app's other assets**: if the app already packs HTML into a generated module (a `*.gen.ts`
   ignored by git, so the Node server and a Worker serve it without disk), add a `build-site` script that walks
   `site/` into `{path: {type, binary, body}}` (binary as base64) and chain it in every script that runs the build
   (`build`, `start`, `test`, `dev`, `deploy`) and in the Dockerfile's copy of generated files. Refuse unknown
   extensions in the packer so a file never ships without a content-type.
3. **Route**: `/` serves `index.html`, other packed paths serve themselves (GET/HEAD only, short cache). Move the
   page that used to live at `/` to a named path (e.g. `/conectar`) and point the LP's secondary CTA at it.
4. **Tests**: repoint every test that fetched `/` for the old page; add one that loads `/`, extracts every
   `src`/`href` into the site and asserts 200 for each, checks an image's magic byte, and checks an unknown path is 404.
5. **Verify locally** on a free port, `devc browse` it, then PR, merge, and watch the app's deploy workflow to the end
   (`gh run watch <id> --exit-status`).
6. **Verify production**: 200 on `/`, a screen, a logo and the moved page; the `<title>`; and the service's main
   endpoint (e.g. a `tools/list` POST to `/mcp`) still answers, since the root change rode the same deploy.

## Before sending it outside

- **Self-host the fonts.** The draft may load Google Fonts; a published page must not, because every visitor's IP goes
  to Google (LGPD rule of the house: nothing to vendors). Ship the woff2 files in `site/` and use `@font-face`.
- Screens that subagents wrote and nobody looked at stay out of the showcase until seen at 390 px and desktop.
