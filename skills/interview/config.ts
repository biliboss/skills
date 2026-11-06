// Shared by interview.ts (the client) and queue.ts (the long-lived queue server).
import * as path from "node:path";
import * as os from "node:os";
import * as fs from "node:fs";
import { fileURLToPath } from "node:url";
import { loadSettings, assertValidLauncher, type InterviewSettings } from "./vendor/package/settings.ts";

export const SKILL_DIR = path.dirname(fileURLToPath(import.meta.url));
// Our own settings file wins; pi's ~/.pi/agent/settings.json is the fallback, so a pi user keeps theirs.
const OWN_SETTINGS = path.join(SKILL_DIR, "settings.json");

// Fixed port of the queue server. Outside 8377-8396, which the per-form servers scan.
export const DEFAULT_QUEUE_PORT = 8398;
export const DEFAULT_TIMEOUT_SEC = 1800;
export const DEFAULT_IDLE_SEC = 1800;
export const QUEUE_VERSION = "1.1.0";

export function readSettings(): InterviewSettings {
	let parsed: InterviewSettings;
	if (!fs.existsSync(OWN_SETTINGS)) parsed = loadSettings();
	else {
		parsed = JSON.parse(fs.readFileSync(OWN_SETTINGS, "utf-8")) as InterviewSettings;
		assertValidLauncher(parsed.launcher);
	}
	// INTERVIEW_PORT wins over the file (used by the tests to avoid the real queue).
	if (process.env.INTERVIEW_PORT) parsed = { ...parsed, port: Number(process.env.INTERVIEW_PORT) };
	return parsed;
}

export function expandHome(value: string): string {
	if (value === "~") return os.homedir();
	if (value.startsWith("~/")) return path.join(os.homedir(), value.slice(2));
	return value;
}

export const RECOVERY_DIR = path.join(os.homedir(), ".pi", "interview-recovery");
export const QUEUE_LOG = path.join(os.homedir(), ".pi", "interview-queue.log");
