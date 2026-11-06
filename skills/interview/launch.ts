// Opens the one interview window. Runs inside the queue server, so the window outlives any single form.
import * as path from "node:path";
import * as fs from "node:fs";
import { execFile, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import type { InterviewSettings } from "./vendor/package/settings.ts";
import { readSettings } from "./config.ts";

function run(command: string, args: string[]): Promise<string> {
	return new Promise((resolve, reject) => {
		execFile(command, args, { timeout: 60_000 }, (error, stdout, stderr) => {
			if (error) reject(new Error(`${command} ${args[0] ?? ""}: ${stderr || error.message}`));
			else resolve(stdout);
		});
	});
}

// Orca may reload a tab's initial URL during creation, which cancels an interview, so open blank first.
async function openOrca(url: string): Promise<void> {
	const created = JSON.parse(await run("orca", ["tab", "create", "--url", "about:blank", "--json"])) as { result?: { browserPageId?: string } };
	const page = created.result?.browserPageId;
	if (typeof page !== "string") throw new Error("orca tab create returned no browserPageId");
	await run("orca", ["tab", "switch", "--page", page, "--focus"]);
	await run("orca", ["goto", "--page", page, "--url", url]);
}

export async function closeOrca(url: string): Promise<void> {
	const listed = JSON.parse(await run("orca", ["tab", "list", "--worktree", "all", "--json"])) as {
		result: { tabs: { url: string; browserPageId: string; worktreeId: string }[] };
	};
	for (const tab of listed.result.tabs) {
		if (tab.url === url) await run("orca", ["tab", "close", "--page", tab.browserPageId, "--worktree", `id:${tab.worktreeId}`]);
	}
}

type GlimpseOpen = (html: string, opts: Record<string, unknown>) => { on(event: "closed", handler: () => void): void; close(): void };

async function loadGlimpse(): Promise<GlimpseOpen | null> {
	let entry: string | null = null;
	try {
		entry = createRequire(import.meta.url).resolve("glimpseui");
	} catch {
		try {
			const candidate = path.join(execFileSync("npm", ["root", "-g"], { encoding: "utf-8" }).trim(), "glimpseui", "src", "glimpse.mjs");
			if (fs.existsSync(candidate)) entry = candidate;
		} catch {}
	}
	if (!entry) return null;
	return ((await import(entry)) as { open: GlimpseOpen }).open;
}

export interface OpenRequest {
	launcher?: InterviewSettings["launcher"];
	browser?: string;
	glimpseFloating?: boolean;
	title?: string;
}

// The dev-console (skills/dev-console), when it answers, is the window: (1) console down -> false, the caller opens
// today's window; (2) its window already shows this queue (devc now: /browser?url=<the queue>) -> nothing opens, the
// queue's page moves to the next form by itself; (3) else `devc browse <url>` opens the queue in its Browser module.
// The console's URL: INTERVIEW_CONSOLE_URL (tests; "" turns it off), else `console` in settings (false = off), else
// 5057. A devc that fails (not installed) falls back to the window, so a form is never left unseen.
async function openInConsole(url: string): Promise<boolean> {
	const setting = (readSettings() as { console?: string | false | null }).console;
	const at = process.env.INTERVIEW_CONSOLE_URL ?? (setting === undefined ? "http://127.0.0.1:5057/" : setting || "");
	if (!at) return false;
	try {
		const res = await fetch(at, { redirect: "manual", signal: AbortSignal.timeout(800) });
		await res.body?.cancel().catch(() => {});
		if (res.status < 200 || res.status >= 400) return false;
	} catch {
		return false;
	}
	const port = new URL(at).port || "80";
	const queue = new URL(url);
	try {
		const now = new URL((JSON.parse(await run("devc", ["--port", port, "now", "--json"])) as { url?: string }).url ?? "", at);
		const shown = now.pathname === "/browser" ? new URL(now.searchParams.get("url") ?? "", "http://invalid") : null;
		if (shown && shown.port === queue.port && ["127.0.0.1", "localhost"].includes(shown.hostname)) return true;
	} catch {} // no navigation recorded yet: open it
	try {
		await run("devc", ["--port", port, "browse", url]);
		return true;
	} catch (err) {
		process.stderr.write(`devc browse failed, opening a window instead: ${err instanceof Error ? err.message : String(err)}\n`);
		return false;
	}
}

// INTERVIEW_OPEN_CMD stands in for the window (tests): it is run with the URL as its only argument.
export async function openWindow(url: string, req: OpenRequest, remote: boolean): Promise<void> {
	if (!remote && (await openInConsole(url))) return;
	const custom = process.env.INTERVIEW_OPEN_CMD;
	if (custom) {
		await run(custom, [url]);
		return;
	}
	if (req.launcher === "orca") return openOrca(url);
	if (req.launcher !== "browser" && process.platform === "darwin" && !remote) {
		const open = await loadGlimpse();
		if (open) {
			const win = open(`<!DOCTYPE html><html><body style="margin:0;background:#1a1a2e"><script>window.location.replace(${JSON.stringify(url)});</script></body></html>`, {
				width: 900, height: 780, title: req.title || "Interview", floating: req.glimpseFloating ?? false,
			});
			win.on("closed", () => {});
			return;
		}
		if (req.launcher === "glimpse") throw new Error("Glimpse launcher unavailable: npm i -g glimpseui");
	}
	if (remote) {
		const port = new URL(url).port;
		process.stderr.write(`Remote session: forward the port first, e.g. ssh -L ${port}:127.0.0.1:${port} <host>\n`);
	}
	const opener = process.platform === "darwin" ? "open" : "xdg-open";
	await run(opener, req.browser && process.platform === "darwin" ? ["-a", req.browser, url] : [url]);
}
