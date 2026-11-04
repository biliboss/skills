// The queue server: one long-lived process on a fixed port that owns the one interview window.
// Clients (interview.ts) POST a form to /enqueue and long-poll /wait/<id> for the answer.
// The page at / shows the form of the moment (the vendored pi-interview form, in an iframe)
// and how many wait; when one is submitted it moves on to the next by itself.
// Drafts are saved on every change to a recovery file, so a timeout or a closed window never loses answers.

import http, { type IncomingMessage, type ServerResponse } from "node:http";
import * as fs from "node:fs";
import * as path from "node:path";
import { randomUUID } from "node:crypto";
import { startInterviewServer, type ResponseItem, type InterviewServerHandle } from "./vendor/package/server.ts";
import type { QuestionsFile } from "./vendor/package/schema.ts";
import { openWindow, closeOrca, type OpenRequest } from "./launch.ts";
import { readSettings, expandHome, DEFAULT_QUEUE_PORT, DEFAULT_IDLE_SEC, QUEUE_VERSION, RECOVERY_DIR } from "./config.ts";

type Status = "queued" | "active" | "done" | "expired" | "cancelled";

interface Item {
	id: string;
	title: string;
	questions: QuestionsFile;
	cwd: string;
	timeoutSec: number;
	status: Status;
	// Late: the waiting process gave up (timeout) or vanished; the form stays answerable, answers go to the file.
	late: boolean;
	draft: ResponseItem[];
	result?: ResponseItem[];
	reason?: string;
	recoveryFile: string;
	createdAt: number;
	activeSince: number;
	lastActivity: number;
	lastPoll: number;
	vendor: { handle: InterviewServerHandle; url: string } | null;
	starting: boolean;
	waiters: Array<() => void>;
	finishedAt?: number;
}

const WINDOW_ALIVE_MS = 12_000;
const REOPEN_GRACE_MS = 20_000;
const ORPHAN_MS = 120_000;
const SUBMIT_LINGER_MS = 12_000;
const KEEP_FINISHED_MS = 10 * 60_000;

function sanitize(value: string): string {
	return value.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 40);
}

function json(res: ServerResponse, status: number, body: unknown): void {
	const data = JSON.stringify(body);
	res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
	res.end(data);
}

function readBody(req: IncomingMessage): Promise<unknown> {
	return new Promise((resolve, reject) => {
		let size = 0;
		const chunks: Buffer[] = [];
		req.on("data", (c: Buffer) => {
			size += c.length;
			if (size > 20 * 1024 * 1024) { req.destroy(); reject(new Error("Body too large")); return; }
			chunks.push(c);
		});
		req.on("end", () => {
			try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf-8")) : {}); }
			catch (e) { reject(e); }
		});
		req.on("error", reject);
	});
}

const SHELL_HTML = `<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Interview</title>
<style>
:root{color-scheme:light dark;--bg:#fafafa;--fg:#1a1a1a;--muted:#6b6b6b;--bar:#ececec;--line:#d6d6d6;--accent:#0b6bcb;--warn:#a05a00}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eaeaea;--muted:#9a9a9a;--bar:#202020;--line:#333;--accent:#5aa9ff;--warn:#f0b050}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
body{display:flex;flex-direction:column}
#bar{display:flex;gap:12px;align-items:center;padding:8px 16px;background:var(--bar);border-bottom:1px solid var(--line);min-height:24px;flex-wrap:wrap}
#title{font-weight:600}
#count{color:var(--accent)}
#late,#note{color:var(--warn)}
#next{color:var(--muted);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#frame{flex:1;border:0;width:100%;background:var(--bg)}
#empty{flex:1;display:flex;align-items:center;justify-content:center;color:var(--muted);padding:16px;text-align:center}
.hidden{display:none!important}
</style></head><body>
<div id="bar"><span id="title">Interview</span><span id="count"></span><span id="next"></span><span id="late"></span></div>
<div id="note" class="hidden" style="padding:6px 16px"></div>
<div id="empty">Nenhum formulário na fila. Esta janela passa ao próximo sozinha quando chegar um.</div>
<iframe id="frame" class="hidden" title="Formulário"></iframe>
<script>
(function(){
  var frame=document.getElementById("frame"),empty=document.getElementById("empty"),title=document.getElementById("title"),
      count=document.getElementById("count"),next=document.getElementById("next"),late=document.getElementById("late"),note=document.getElementById("note");
  var shownUrl="";
  function render(s){
    var cur=s.current;
    if(!cur){
      title.textContent="Interview";count.textContent="";next.textContent="";late.textContent="";note.classList.add("hidden");
      frame.classList.add("hidden");empty.classList.remove("hidden");
      if(shownUrl){frame.removeAttribute("src");shownUrl="";}
      document.title="Interview";return;
    }
    title.textContent=cur.title;
    document.title=(s.queue.length?"("+s.queue.length+") ":"")+cur.title;
    count.textContent=s.queue.length?(s.queue.length+(s.queue.length===1?" formulário espera na fila":" formulários esperam na fila")):"Último da fila";
    next.textContent=s.queue.length?"Próximos: "+s.queue.map(function(q){return q.title}).join(" · "):"";
    late.textContent=s.lateCount?(s.lateCount+" expirado(s) ainda respondível(is)"):"";
    if(cur.late){note.textContent="O tempo deste formulário acabou. Você ainda pode responder; as respostas vão para o arquivo de recuperação: "+cur.recoveryFile;note.classList.remove("hidden");}
    else note.classList.add("hidden");
    empty.classList.add("hidden");frame.classList.remove("hidden");
    if(cur.url&&cur.url!==shownUrl){shownUrl=cur.url;frame.src=cur.url;}
  }
  function poll(){
    fetch("/state?shell=1",{cache:"no-store"}).then(function(r){return r.json()}).then(render).catch(function(){title.textContent="Servidor da fila parou";}).finally(function(){setTimeout(poll,1500)});
  }
  poll();
})();
</script></body></html>`;

export async function serveQueue(opts: { port?: number; idleSec?: number }): Promise<void> {
	const settings = readSettings();
	const port = opts.port ?? settings.port ?? DEFAULT_QUEUE_PORT;
	const idleMs = (opts.idleSec ?? Number(process.env.INTERVIEW_IDLE_SEC ?? DEFAULT_IDLE_SEC)) * 1000;
	const remote = Boolean(process.env.SSH_CONNECTION || process.env.SSH_TTY);

	const items = new Map<string, Item>();
	let order: Item[] = []; // pending items, first = current
	let current: Item | null = null;
	let lastShell = 0;
	let openedAt = 0;
	let opens = 0;
	let lastActivity = Date.now();
	let lastLauncher: OpenRequest = {};
	let baseUrl = `http://127.0.0.1:${port}/`;

	const touch = () => { lastActivity = Date.now(); };
	const wake = (item: Item) => { const w = item.waiters.splice(0); for (const f of w) f(); };

	function writeRecovery(item: Item): void {
		try {
			fs.mkdirSync(RECOVERY_DIR, { recursive: true });
			const body = {
				id: item.id,
				title: item.title,
				status: item.late && item.status === "done" ? "answered-late" : item.status,
				savedAt: new Date().toISOString(),
				cwd: item.cwd,
				questions: item.questions.questions,
				description: item.questions.description,
				responses: item.result ?? item.draft,
			};
			const tmp = `${item.recoveryFile}.tmp`;
			fs.writeFileSync(tmp, JSON.stringify(body, null, 2), { mode: 0o600 });
			fs.renameSync(tmp, item.recoveryFile);
		} catch (err) {
			process.stderr.write(`recovery write failed: ${err instanceof Error ? err.message : String(err)}\n`);
		}
	}

	function closeVendor(item: Item): void {
		const v = item.vendor;
		item.vendor = null;
		try { v?.handle.close(); } catch {}
	}

	async function ensureVendor(item: Item): Promise<void> {
		if (item.vendor || item.starting) return;
		if (item.status !== "active" && !(item.late && item.status === "expired")) return;
		item.starting = true;
		try {
			const handle = await startInterviewServer(
				{
					questions: item.questions,
					sessionToken: randomUUID(),
					sessionId: item.id,
					cwd: item.cwd,
					timeout: 0, // the timeout is the queue's, not the page's: the form never closes itself
					theme: { toggleHotkey: "mod+shift+l", ...(settings.theme ?? {}) },
					...(settings.snapshotDir ? { snapshotDir: expandHome(settings.snapshotDir) } : {}),
					autoSaveOnSubmit: settings.autoSaveOnSubmit ?? true,
					...(item.draft.length ? { savedAnswers: item.draft } : {}),
					canGenerate: false,
					askModels: [],
					defaultAskModel: null,
				},
				{
					onDraft: (responses) => {
						if (current !== item) return;
						item.draft = responses;
						item.lastActivity = Date.now();
						touch();
						writeRecovery(item);
					},
					onSubmit: (responses) => {
						touch();
						item.result = responses;
						item.draft = responses;
						finish(item, "done");
						// Keep the page until it saved its snapshot (onFinish) so the owner sees the confirmation.
						const t = setTimeout(() => leave(item), SUBMIT_LINGER_MS);
						t.unref();
					},
					onFinish: async () => { setTimeout(() => leave(item), 1500).unref(); },
					onCancel: (reason, partial) => {
						touch();
						if (partial?.length) item.draft = partial;
						if (reason === "stale") {
							// The window went away without a word: keep the form pending, start a fresh page when it returns.
							closeVendor(item);
							writeRecovery(item);
							return;
						}
						item.result = item.draft;
						item.reason = "user";
						finish(item, "cancelled");
						leave(item);
					},
				},
			);
			if (item.status === "done" || item.status === "cancelled" || current !== item) {
				try { handle.close(); } catch {}
				return;
			}
			item.vendor = { handle, url: handle.url };
		} catch (err) {
			process.stderr.write(`vendor start failed: ${err instanceof Error ? err.message : String(err)}\n`);
		} finally {
			item.starting = false;
		}
	}

	function finish(item: Item, status: Status): void {
		item.status = status;
		item.finishedAt = Date.now();
		writeRecovery(item);
		wake(item);
	}

	// The item is over: drop its page and move on.
	function leave(item: Item): void {
		closeVendor(item);
		order = order.filter((i) => i !== item);
		if (current === item) advance();
	}

	function advance(): void {
		const next = order.find((i) => i.status === "queued") ?? order.find((i) => i.status === "expired");
		current = next ?? null;
		if (!next) return;
		if (next.status === "queued") {
			next.status = "active";
			next.activeSince = Date.now();
			next.lastActivity = Date.now();
		}
		void ensureVendor(next);
	}

	function expire(item: Item, reason: string): void {
		item.late = true;
		item.reason = reason;
		item.status = "expired";
		item.finishedAt = undefined;
		writeRecovery(item);
		wake(item);
		const waiting = order.some((i) => i.status === "queued");
		if (waiting && current === item) {
			// Do not let a slow form block the line: it goes to the back, still answerable.
			closeVendor(item);
			order = [...order.filter((i) => i !== item), item];
			advance();
		}
	}

	function enqueue(body: Record<string, unknown>): Item {
		const questions = body.questions as QuestionsFile;
		if (!questions || !Array.isArray(questions.questions)) throw new Error("Missing questions");
		const id = randomUUID();
		const now = new Date();
		const stamp = `${now.toISOString().slice(0, 10)}_${now.toTimeString().slice(0, 8).replace(/:/g, "")}`;
		const title = questions.title || "Interview";
		const item: Item = {
			id,
			title,
			questions,
			cwd: typeof body.cwd === "string" ? body.cwd : process.cwd(),
			timeoutSec: typeof body.timeout === "number" && body.timeout > 0 ? body.timeout : 0,
			status: "queued",
			late: false,
			draft: Array.isArray(body.savedAnswers) ? (body.savedAnswers as ResponseItem[]) : [],
			recoveryFile: path.join(RECOVERY_DIR, `${stamp}_${sanitize(title)}_${id.slice(0, 8)}.draft.json`),
			createdAt: Date.now(),
			activeSince: 0,
			lastActivity: Date.now(),
			lastPoll: Date.now(),
			vendor: null,
			starting: false,
			waiters: [],
		};
		items.set(id, item);
		order.push(item);
		writeRecovery(item);
		touch();
		if (!current) advance();
		return item;
	}

	async function maybeOpen(req: OpenRequest): Promise<void> {
		lastLauncher = req;
		const now = Date.now();
		if (now - lastShell < WINDOW_ALIVE_MS) return;
		if (now - openedAt < REOPEN_GRACE_MS) return;
		openedAt = now;
		opens++;
		try {
			await openWindow(baseUrl, { ...req, title: "Interview" }, remote);
		} catch (err) {
			process.stderr.write(`open window failed: ${err instanceof Error ? err.message : String(err)}\n`);
		}
	}

	function snapshotState() {
		const pending = order.filter((i) => !i.late || i === current);
		const queue = order.filter((i) => i !== current && i.status === "queued").map((i) => ({ id: i.id, title: i.title }));
		return {
			ok: true,
			version: QUEUE_VERSION,
			windowAlive: Date.now() - lastShell < WINDOW_ALIVE_MS,
			opens,
			current: current
				? {
					id: current.id,
					title: current.title,
					url: current.vendor?.url ?? null,
					late: current.late,
					status: current.status,
					recoveryFile: current.recoveryFile,
					deadline: !current.late && current.timeoutSec > 0 ? Math.max(current.activeSince, current.lastActivity) + current.timeoutSec * 1000 : null,
				}
				: null,
			queue,
			lateCount: order.filter((i) => i.late).length,
			pending: pending.length,
		};
	}

	function waitStatus(item: Item) {
		const position = item.status === "queued" ? order.filter((i) => i.status === "queued").indexOf(item) + 1 : 0;
		const final = item.status === "done" || item.status === "cancelled" || item.status === "expired";
		return {
			ok: true,
			status: item.status,
			position,
			recoveryFile: item.recoveryFile,
			...(item.reason ? { reason: item.reason } : {}),
			...(final ? { responses: item.status === "done" ? item.result ?? [] : item.result ?? item.draft } : {}),
		};
	}

	const server = http.createServer(async (req, res) => {
		try {
			const method = req.method || "GET";
			const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
			// Closes DNS rebinding: a rebound request carries the attacker's Host.
			if (req.headers.host !== undefined && !["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname)) {
				res.writeHead(403); res.end("Invalid host"); return;
			}
			if (method === "POST" && !req.headers["x-interview-client"]) {
				// A custom header forces a CORS preflight, which this server never grants: no cross-site POSTs.
				json(res, 403, { ok: false, error: "Missing X-Interview-Client header" }); return;
			}

			if (method === "GET" && url.pathname === "/") {
				res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
				res.end(SHELL_HTML); return;
			}
			if (method === "GET" && url.pathname === "/health") {
				json(res, 200, { ok: true, service: "interview-queue", version: QUEUE_VERSION, pid: process.pid }); return;
			}
			if (method === "GET" && url.pathname === "/state") {
				if (url.searchParams.has("shell")) {
					lastShell = Date.now();
					if (current && !current.vendor) void ensureVendor(current);
				}
				json(res, 200, snapshotState()); return;
			}
			if (method === "POST" && url.pathname === "/enqueue") {
				const body = (await readBody(req)) as Record<string, unknown>;
				const item = enqueue(body);
				if (body.open !== false) {
					await maybeOpen({
						launcher: body.launcher as OpenRequest["launcher"],
						browser: typeof body.browser === "string" ? body.browser : settings.browser,
						glimpseFloating: settings.glimpseFloating,
					});
				}
				json(res, 200, { ok: true, id: item.id, recoveryFile: item.recoveryFile, position: waitStatus(item).position, url: baseUrl });
				return;
			}
			const waitMatch = url.pathname.match(/^\/wait\/([0-9a-f-]{36})$/);
			if (method === "GET" && waitMatch) {
				const item = items.get(waitMatch[1]);
				if (!item) { json(res, 404, { ok: false, error: "Unknown id" }); return; }
				item.lastPoll = Date.now();
				const hold = Math.min(Math.max(Number(url.searchParams.get("hold") ?? 20), 0), 55) * 1000;
				const isFinal = () => item.status === "done" || item.status === "cancelled" || item.status === "expired";
				if (!isFinal() && hold > 0) {
					await new Promise<void>((resolve) => {
						const t = setTimeout(done, hold);
						function done() { clearTimeout(t); resolve(); }
						item.waiters.push(done);
						res.on("close", done);
					});
				}
				if (res.writableEnded || res.destroyed) return;
				item.lastPoll = Date.now();
				json(res, 200, waitStatus(item)); return;
			}
			const cancelMatch = url.pathname.match(/^\/cancel\/([0-9a-f-]{36})$/);
			if (method === "POST" && cancelMatch) {
				const item = items.get(cancelMatch[1]);
				if (item && (item.status === "queued" || item.status === "active")) {
					item.result = item.draft;
					item.reason = "client-aborted";
					finish(item, "cancelled");
					leave(item);
				}
				json(res, 200, { ok: true }); return;
			}
			res.writeHead(404); res.end("Not found");
		} catch (err) {
			if (!res.headersSent) json(res, 500, { ok: false, error: err instanceof Error ? err.message : String(err) });
		}
	});

	await new Promise<void>((resolve) => {
		server.once("error", (err: NodeJS.ErrnoException) => {
			// Two processes raced to start the server: the loser sees EADDRINUSE and leaves it to the winner.
			if (err.code === "EADDRINUSE") { process.stderr.write(`port ${port} already in use: another queue server won the race\n`); process.exit(0); }
			process.stderr.write(`queue server failed: ${err.message}\n`);
			process.exit(1);
		});
		server.listen(port, "127.0.0.1", () => resolve());
	});
	process.stderr.write(`interview queue server on ${baseUrl} (pid ${process.pid}, idle exit ${idleMs / 1000}s)\n`);

	const shutdown = (code: number) => {
		for (const item of items.values()) closeVendor(item);
		void (async () => {
			if (lastLauncher.launcher === "orca" && !process.env.INTERVIEW_OPEN_CMD) await closeOrca(baseUrl).catch(() => {});
			process.exit(code);
		})();
	};
	for (const sig of ["SIGINT", "SIGTERM"] as const) process.on(sig, () => shutdown(0));

	setInterval(() => {
		const now = Date.now();
		for (const item of [...order]) {
			// The one waiting on the current form timed out: keep the form answerable, hand back the draft.
			if (item === current && item.status === "active" && !item.late && item.timeoutSec > 0
				&& now - Math.max(item.activeSince, item.lastActivity) > item.timeoutSec * 1000) {
				expire(item, "timeout");
				continue;
			}
			// The waiting process died without cancelling: do not let the form hold the line forever.
			if (!item.late && (item.status === "queued" || item.status === "active") && now - item.lastPoll > ORPHAN_MS) {
				expire(item, "client-gone");
			}
		}
		for (const [id, item] of items) {
			if (item.finishedAt && now - item.finishedAt > KEEP_FINISHED_MS && !order.includes(item)) items.delete(id);
		}
		const hasLive = order.some((i) => !i.late);
		if (hasLive) touch();
		if (!hasLive && now - lastActivity > idleMs) {
			process.stderr.write("idle: no forms for a while, exiting\n");
			shutdown(0);
		}
	}, 1000).unref();
	// Keep the process alive on the HTTP server (the interval is unref'd on purpose).
}
