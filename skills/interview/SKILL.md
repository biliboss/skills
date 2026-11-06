---
name: interview
description: Ask the user structured questions in a rich interactive form (pi-interview) in one browser, Orca or native macOS window shared by every call. Single and multi choice with recommendations, free text, image upload, and context panels with code, diffs, Markdown, tables, Mermaid and charts. Forms queue up in that window and the answers come back to each caller. Marked answers are never lost when time runs out. Use for grilling rounds, requirements gathering, design tradeoffs, or any batch of decisions that needs more context than AskUserQuestion can show. Use whenever the user asks to be grilled or interviewed, or says "interview", "pi-interview", "form".
metadata:
  version: 1.1.0
  license: MIT
---

# Interview (pi-interview for Claude Code)

`interview.ts` runs the form from the `pi-interview` package (vendored in `vendor/package`, v0.14.0, MIT, by Nico Bailon; see `ATTRIBUTION.md`) without pi. You write a questions JSON, start the form in the background, and the answers come back on stdout when the user submits.

## One window, a queue

The first call starts a long-lived queue server on a fixed port (8398, or `port` in `settings.json`) and opens **one** window. Every later call, from any session, sees the server up, puts its form in the queue (no new window) and waits for its own answer. The window shows the form of the moment and how many wait; after each submit it moves to the next by itself. If the window was closed, the next call reopens it (one window). The server exits by itself after 30 minutes with no forms; logs go to `~/.pi/interview-queue.log`.

**In the dev-console.** When the dev-console answers on `http://127.0.0.1:5057/` (setting `console`), it is the window:
if its window already shows the queue (`devc now --json` is `/browser?url=http://127.0.0.1:8398…`) nothing opens and the
queue's page moves on to the next form by itself; else `devc browse http://127.0.0.1:8398/` opens the queue in its Browser
module. With the console down, or no `devc`, the window opens as always: the skill works on its own.

## Run it

1. Write the questions to a JSON file in your scratchpad directory (format below).
2. Start the form with the Bash tool and **`run_in_background: true`**, always:

   ```bash
   node <skill-dir>/interview.ts /abs/path/questions.json
   ```

   `<skill-dir>` is this skill's folder. Never run it in the foreground: the owner may take longer than the Bash timeout, and other forms may be ahead of yours in the queue.
3. Tell the user in one line that the form is open (stderr has the address and your queue position), then **end your turn**. Do not poll. When the process exits you are notified; read its output.
4. Exit codes: `0` completed, `2` cancelled or skipped (partial answers, if any, are printed), `3` timed out, `1` error (message on stderr), `130` aborted.

Flags: `--timeout <seconds>` (default 1800, counted from when your form is on screen and reset by every change), `--launcher browser|orca|glimpse`, `--no-open` (queue the form without opening a window, e.g. over SSH).

Defaults live in `settings.json` next to this file (falls back to pi's `~/.pi/agent/settings.json` under `interview`): `launcher`, `browser`, `timeout`, `port`, `theme` (`{ "name": "default"|"tufte", "mode": "dark"|"light"|"auto" }`), `snapshotDir`, `autoSaveOnSubmit`, `glimpseFloating`, `console` (the dev-console's URL, default `http://127.0.0.1:5057/`; `false` never uses it; `INTERVIEW_CONSOLE_URL` wins). Without a launcher it opens a native window if `glimpseui` is installed globally, else the default browser.

## Never lose answers

- Every change is saved to the server as a draft, in a recovery file: `~/.pi/interview-recovery/<date>_<title>_<id>.draft.json`. Closing the window does not cancel the form; reopen the window and it picks up where it was.
- When the timeout runs out, the form is **not** closed. It stays answerable in the window (it moves behind the other forms if some wait). Your process exits with code `3` and prints what was marked so far plus the recovery file path. If the owner answers later, the file is updated with the final answers and `"status": "answered-late"`.
- On code `3`, use the printed answers, say that the form is still open, and read the recovery file again later if the answers matter.
- To reopen a form pre-filled, pass a recovery file, or a saved snapshot's `index.html` (from `~/.pi/interview-snapshots/`), instead of the JSON.

## Questions JSON

```json
{
  "title": "Plano do worker de backups",
  "description": "Revise minhas recomendações e ajuste o que precisar.",
  "questions": [
    {
      "id": "storage",
      "type": "single",
      "question": "Onde guardar os backups?",
      "options": ["R2", "S3", "Disco da VPS"],
      "recommended": "R2",
      "context": "R2 não cobra saída de dados.",
      "weight": "critical"
    },
    {
      "id": "targets",
      "type": "multi",
      "question": "O que entra no backup?",
      "options": ["Banco de dados", "Documentos", "Configurações"],
      "recommended": ["Banco de dados", "Documentos"]
    },
    {
      "id": "api",
      "type": "single",
      "question": "Qual forma de API?",
      "options": [
        { "label": "Callback", "content": { "source": "run(job, (err) => …)", "lang": "ts" } },
        { "label": "Promise", "content": { "source": "await run(job)", "lang": "ts" } }
      ],
      "recommended": "Promise",
      "conviction": "slight"
    },
    { "id": "notes", "type": "text", "question": "Alguma restrição que eu não vi?", "weight": "minor" },
    {
      "id": "arch",
      "type": "info",
      "question": "Como fica",
      "media": { "type": "mermaid", "mermaid": "graph LR\nCron-->Worker-->R2" }
    }
  ]
}
```

- **Types:** `single` (radio), `multi` (checkbox), `text` (textarea), `image` (upload, paste, camera; answers are file paths you can Read), `info` (context only, no answer).
- **Options:** strings, or `{ "label", "content"?: { "source", "lang"?, "file"?, "lines"?, "highlights"?, "title"?, "showSource"? } }`. The user can always type "Other" and add a note to a choice.
- **`recommended`:** always set it, with `context` saying why. It shows a Recommended badge and pre-selects. `"conviction": "slight"` when unsure (no pre-select), `"strong"` when very sure.
- **`weight`:** `"critical"` for key decisions, `"minor"` for low-stakes ones.
- **`content`** on a question: code or Markdown shown above the options (`"lang": "md"` renders Markdown; `"lang": "diff"` for diffs).
- **`media`** (one or a list): `{ "type": "image", "src", "alt", "caption" }`, `{ "type": "table", "table": { "headers", "rows", "highlights" } }`, `{ "type": "chart", "chart": { "type", "data", "options" } }` (Chart.js), `{ "type": "mermaid", "mermaid": "…" }`, `{ "type": "html", "html": "…" }`; `"position": "above"|"below"|"side"`.
- With recommendations set, make `description` say "review my suggestions and adjust".

## The answer

Stdout has a readable summary plus a JSON block: `[{ "id", "question", "type", "value", "attachments"? }]`. Choice values are `{ "option", "note"? }` (a list for `multi`); text is a string; images are file paths. Unanswered questions are left out. If the user cancels or skips, proceed with your recommendations and say so.

## Not wired (vs. pi)

The Generate more / Review options / Ask buttons call models through pi's registry, so they are off here. Async delivery is the background Bash notification.

## Tests

`bash <skill-dir>/test/run.sh` starts a throwaway queue (own port, own HOME, a fake window opener) and checks: two forms at once open one window and each caller gets its own answer; a form with `--timeout 5` exits 3 with the draft and the recovery file; the server exits when idle; and the launcher's three cases, with a fake console and a fake `devc` first on PATH (console down: the window; console showing the queue: nothing; console elsewhere: `devc browse`). Credits and the standalone use: [README.md](README.md).
