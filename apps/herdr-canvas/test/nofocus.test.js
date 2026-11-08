import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const FORBIDDEN = /mod\.open|layout\.(show|select|switch|clone|hide)|mod\.clone|agent\.focus|pane\.(focus|split|go)|space\.select|terminal\.keep|tab\.select|open\s+-g|\bopen\s+-n\b/;
// The only allowed mention: the keys.json binding string, which the owner presses; install.py never runs it.
const BINDING = "mod.open:herdr-canvas";
const strip = s => s.replace(/\/\*[\s\S]*?\*\//g, "").split("\n").filter(l => !/^\s*(\/\/|#)/.test(l)).join("\n");

test("mod code, install.py and install.sh call no focus or layout command", () => {
  const files = readdirSync(join(here, "../mod")).filter(f => f.endsWith(".js")).map(f => join(here, "../mod", f));
  files.push(join(here, "../install.py"), join(here, "../install.sh"));
  assert.ok(files.length === 6);
  for (const f of files) {
    const hit = FORBIDDEN.exec(strip(readFileSync(f, "utf8")).split(BINDING).join(""));
    assert.equal(hit, null, `${f}: ${hit && hit[0]}`);
  }
});

test("install.py runs only `herdr-app check` as a subprocess", () => {
  const text = readFileSync(join(here, "../install.py"), "utf8");
  const calls = text.match(/subprocess\.\w+\(\[[^\]]*\]/g) ?? [];
  assert.deepEqual(calls, ["subprocess.run(['herdr-app', 'check', str(mod)]"]);
  assert.ok(!/herdr-app['"],\s*['"]do/.test(text));
});
