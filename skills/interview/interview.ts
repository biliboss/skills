#!/usr/bin/env node
// Claude Code wrapper for pi-interview (https://github.com/nicobailon/pi-interview-tool).
// Reuses the package's form server (vendor/package/server.ts), which has no pi dependency.
// Every call enqueues its form on one long-lived queue server (queue.ts, fixed port) that owns the
// single window; this process waits for the answer. The first call starts the server.
//
// Usage: node interview.ts <questions.json | snapshot.html | inline JSON> [--timeout <s>] [--launcher browser|orca|glimpse] [--no-open]
// Prints the answers to stdout and exits 0 (completed), 2 (cancelled), 3 (timeout), 1 (error).

import * as path from "node:path";
import * as fs from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import type { ResponseItem, ChoiceResponseValue } from "./vendor/package/server.ts";
import { validateQuestions, sanitizeLLMJSON, type Question, type QuestionsFile } from "./vendor/package/schema.ts";
import { assertValidLauncher, type InterviewSettings } from "./vendor/package/settings.ts";
import { readSettings, expandHome, DEFAULT_QUEUE_PORT, DEFAULT_TIMEOUT_SEC, QUEUE_LOG } from "./config.ts";

const SELF = fileURLToPath(import.meta.url);

interface Args {
	questions: string;
	timeout?: number;
	launcher?: InterviewSettings["launcher"];
	noOpen?: boolean;
	serve?: boolean;
	idleSec?: number;
}

function parseArgs(argv: string[]): Args {
	if (argv[0] === "--serve") {
		const i = argv.indexOf("--idle-sec");
		return { questions: "", serve: true, ...(i >= 0 ? { idleSec: Number(argv[i + 1]) } : {}) };
	}
	let questions: string | undefined;
	let timeout: number | undefined;
	let launcher: InterviewSettings["launcher"];
	let noOpen = false;
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (arg === "--timeout") timeout = Number(argv[++i]);
		else if (arg === "--no-open") noOpen = true;
		else if (arg === "--launcher") {
			const value = argv[++i];
			assertValidLauncher(value);
			launcher = value as InterviewSettings["launcher"];
		} else if (questions === undefined) questions = arg;
		else throw new Error(`Unexpected argument: ${arg}`);
	}
	if (!questions) throw new Error("Usage: node interview.ts <questions.json | recovery.json | snapshot.html | inline JSON> [--timeout s] [--launcher browser|orca|glimpse] [--no-open]");
	return { questions, noOpen, ...(timeout !== undefined ? { timeout } : {}), ...(launcher !== undefined ? { launcher } : {}) };
}

type LoadedQuestions = QuestionsFile & { savedAnswers?: ResponseItem[] };

function loadQuestions(input: string, cwd: string): LoadedQuestions {
	const trimmed = input.trimStart();
	if (trimmed.startsWith("{")) {
		try {
			return validateQuestions(JSON.parse(trimmed));
		} catch {
			return validateQuestions(JSON.parse(sanitizeLLMJSON(trimmed)));
		}
	}
	const expanded = expandHome(input);
	const file = path.isAbsolute(expanded) ? expanded : path.join(cwd, expanded);
	if (!fs.existsSync(file)) throw new Error(`Questions file not found: ${file}`);
	const content = fs.readFileSync(file, "utf-8");
	if (file.endsWith(".html") || file.endsWith(".htm")) {
		// A saved snapshot embeds its questions and answers; reopen it pre-filled.
		const match = content.match(/<script[^>]+id=["']pi-interview-data["'][^>]*>([\s\S]*?)<\/script>/i);
		if (!match) throw new Error("Invalid saved interview: missing embedded data");
		const raw = JSON.parse(match[1]) as Record<string, unknown>;
		const validated = validateQuestions(raw);
		return Array.isArray(raw.savedAnswers) ? { ...validated, savedAnswers: raw.savedAnswers as ResponseItem[] } : validated;
	}
	const raw = JSON.parse(content) as Record<string, unknown>;
	const validated = validateQuestions(raw);
	// A recovery file (draft) carries the answers given so far: reopen it pre-filled.
	return Array.isArray(raw.responses) && raw.responses.length ? { ...validated, savedAnswers: raw.responses as ResponseItem[] } : validated;
}

function isChoice(value: unknown): value is ChoiceResponseValue {
	return !!value && typeof value === "object" && !Array.isArray(value) && typeof (value as ChoiceResponseValue).option === "string";
}

function formatValue(value: ResponseItem["value"]): string {
	if (Array.isArray(value)) {
		return value.map((item) => (isChoice(item) ? (item.note ? `${item.option} (${item.note})` : item.option) : String(item))).join(", ");
	}
	if (isChoice(value)) return value.note ? `${value.option} (${value.note})` : value.option;
	return value;
}

function hasContent(response: ResponseItem | undefined): response is ResponseItem {
	if (!response) return false;
	if (response.attachments?.length) return true;
	return formatValue(response.value).trim() !== "";
}

function formatAnswers(responses: ResponseItem[], questions: Question[]): string {
	const byId = new Map(responses.map((r) => [r.id, r]));
	const answered = questions.flatMap((q) => {
		const r = byId.get(q.id);
		if (!hasContent(r)) return [];
		return [{ id: q.id, question: q.question, type: q.type, value: r.value, ...(r.attachments?.length ? { attachments: r.attachments } : {}) }];
	});
	if (answered.length === 0) return "(none)";
	const summary = answered
		.map((a) => `- ${a.question}: ${formatValue(a.value)}${a.attachments ? ` [attachments: ${a.attachments.join(", ")}]` : ""}`)
		.join("\n");
	return `${summary}\n\nStructured response data:\n\n\`\`\`json\n${JSON.stringify(answered, null, 2)}\n\`\`\``;
}

function pause(ms: number): Promise<void> {
	return new Promise((r) => setTimeout(r, ms));
}

async function call<T>(base: string, method: string, route: string, body?: unknown, timeoutMs = 5000): Promise<T> {
	const res = await fetch(`${base}${route}`, {
		method,
		headers: { "Content-Type": "application/json", "X-Interview-Client": "1" },
		...(body !== undefined ? { body: JSON.stringify(body) } : {}),
		signal: AbortSignal.timeout(timeoutMs),
	});
	return (await res.json()) as T;
}

async function isQueueServer(base: string): Promise<boolean> {
	try {
		const h = await call<{ ok?: boolean; service?: string }>(base, "GET", "/health", undefined, 1500);
		return h.ok === true && h.service === "interview-queue";
	} catch {
		return false;
	}
}

// First try the server that is already up; start one only if it does not answer.
// Two processes may start one at once: the loser gets EADDRINUSE, exits quietly, and both use the winner.
async function ensureServer(base: string, port: number): Promise<void> {
	if (await isQueueServer(base)) return;
	fs.mkdirSync(path.dirname(QUEUE_LOG), { recursive: true });
	const log = fs.openSync(QUEUE_LOG, "a");
	const child = spawn(process.execPath, [...process.execArgv, SELF, "--serve"], {
		detached: true,
		stdio: ["ignore", log, log],
		env: process.env,
	});
	child.unref();
	for (let i = 0; i < 60; i++) {
		await pause(250);
		if (await isQueueServer(base)) return;
	}
	throw new Error(`The queue server did not come up on port ${port} (see ${QUEUE_LOG}); is another program using that port?`);
}

interface WaitReply {
	ok: boolean;
	status: "queued" | "active" | "done" | "expired" | "cancelled";
	position: number;
	recoveryFile: string;
	reason?: string;
	responses?: ResponseItem[];
	error?: string;
}

async function main(): Promise<number> {
	const args = parseArgs(process.argv.slice(2));
	if (args.serve) {
		const { serveQueue } = await import("./queue.ts");
		await serveQueue({ ...(args.idleSec ? { idleSec: args.idleSec } : {}) });
		return await new Promise<number>(() => {}); // the server runs until it idles out
	}
	const settings = readSettings();
	const cwd = process.cwd();
	const questions = loadQuestions(args.questions, cwd);
	const timeout = args.timeout ?? settings.timeout ?? DEFAULT_TIMEOUT_SEC;
	const launcher = args.launcher ?? settings.launcher;
	const port = settings.port ?? DEFAULT_QUEUE_PORT;
	const base = `http://127.0.0.1:${port}`;

	await ensureServer(base, port);
	const { savedAnswers, ...questionsOnly } = questions;
	const queued = await call<{ ok: boolean; id: string; recoveryFile: string; position: number; error?: string }>(base, "POST", "/enqueue", {
		questions: questionsOnly,
		cwd,
		timeout,
		open: !args.noOpen,
		launcher,
		browser: settings.browser,
		...(savedAnswers ? { savedAnswers } : {}),
	});
	if (!queued.ok) throw new Error(queued.error || "enqueue failed");
	process.stderr.write(`Interview form: ${base}/ (one window for every form)\n`);
	process.stderr.write(queued.position > 0 ? `Queued at position ${queued.position}.\n` : "Your form is the one on screen.\n");
	process.stderr.write(`Draft and recovery file: ${queued.recoveryFile}\n`);

	let aborted = false;
	for (const signal of ["SIGINT", "SIGTERM"] as const) {
		process.on(signal, () => {
			if (aborted) return;
			aborted = true;
			process.stdout.write("Interview was aborted.\n");
			call(base, "POST", `/cancel/${queued.id}`, {}, 2000).catch(() => {}).finally(() => process.exit(130));
		});
	}

	let failures = 0;
	let lastPosition = queued.position;
	for (;;) {
		let reply: WaitReply;
		try {
			reply = await call<WaitReply>(base, "GET", `/wait/${queued.id}?hold=20`, undefined, 30_000);
			failures = 0;
		} catch {
			if (++failures >= 5) {
				process.stdout.write(`Interview queue server stopped answering.\n\nWhatever was answered is saved in: ${queued.recoveryFile}\n`);
				return 1;
			}
			await pause(2000);
			continue;
		}
		if (!reply.ok) throw new Error(reply.error || "wait failed");
		if (reply.status === "queued" || reply.status === "active") {
			if (reply.position !== lastPosition) {
				lastPosition = reply.position;
				process.stderr.write(reply.position > 0 ? `Queue position ${reply.position}.\n` : "Your form is now on screen.\n");
			}
			continue;
		}
		const responses = reply.responses ?? [];
		if (reply.status === "done") {
			process.stdout.write(`User completed the interview form.\n\nAnswered responses:\n${formatAnswers(responses, questions.questions)}\n`);
			return 0;
		}
		if (reply.status === "cancelled") {
			process.stdout.write(
				responses.some(hasContent)
					? `Interview cancelled by the user with partial responses.\n\nAnswered responses:\n${formatAnswers(responses, questions.questions)}\n\nProceed with these inputs and use your best judgment for unanswered questions.\n`
					: "User skipped the interview without providing answers. Proceed with your best judgment - use recommended options where specified.\n",
			);
			return 2;
		}
		// expired: the form is still open in the window and still answerable.
		const why = reply.reason === "client-gone" ? "lost contact" : `timed out after ${timeout} seconds`;
		process.stdout.write(
			`Interview ${why}. The form stays open in the window; the owner can still answer it, and anything marked is saved.\n\n` +
				(responses.some(hasContent)
					? `Answers so far:\n${formatAnswers(responses, questions.questions)}\n\n`
					: "No answers so far.\n\n") +
				`Recovery file (draft, updated on every change and when the form is answered late): ${reply.recoveryFile}\n` +
				"Reopen it with: node interview.ts <that file>\n",
		);
		return 3;
	}
}

main().then(
	(code) => process.exit(code),
	(err) => {
		process.stderr.write(`interview: ${err instanceof Error ? err.message : String(err)}\n`);
		process.exit(1);
	},
);
