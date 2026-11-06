# interview

Rich question forms for coding agents (Claude Code, pi, Hermes): single and multi choice with recommendations, free
text, images, and context panels (code, diffs, Markdown, tables, Mermaid, charts). Every form goes into one queue served
on `http://127.0.0.1:8398/`; one window shows the form of the moment, and each caller gets its own answers back on
stdout. Drafts are saved on every change, so a timeout or a closed window never loses an answer.

## Standalone

Only Node is needed (22.18 or newer runs the `.ts` files directly):

```sh
node interview.ts questions.json   # run it in the background: the answers come back on stdout when the form is sent
```

The first call starts the queue server and opens one window (Glimpse when installed, else the default browser;
`--launcher browser|orca|glimpse`); later calls queue up in that window. `--no-open` queues a form without any window.
The questions format, the exit codes and the settings are in [SKILL.md](SKILL.md).

## In the dev-console

When the [dev-console](../dev-console/) answers on `http://127.0.0.1:5057/`, it is the window:

- its window already shows the queue (`devc now --json` is `/browser?url=http://127.0.0.1:8398…`): nothing opens, the
  queue's page moves on to the next form by itself;
- else `devc browse http://127.0.0.1:8398/` opens the queue in the console's Browser module.

With the console down, or no `devc`, the skill opens its own window as above. `"console": false` in `settings.json`
turns this off; `"console": "<url>"` points at another console.

## Tests

`bash test/run.sh` runs a throwaway queue (its own port and HOME, a fake window and a fake `devc` first on PATH) and
checks the queue, the timeout, the idle exit and the launcher's three cases (console down, console showing the queue,
console elsewhere).

## Credits

The form is [pi-interview](https://github.com/nicobailon/pi-interview-tool) (npm:
[`pi-interview`](https://www.npmjs.com/package/pi-interview)) by Nico Bailon, MIT licensed, vendored at v0.14.0 in
`vendor/package` and used without pi. The queue, the single window, the drafts and the dev-console launcher are this
skill's. See [ATTRIBUTION.md](ATTRIBUTION.md).
