// Decides what the panel shows. Pure: no herdr import, so it loads (and tests) anywhere.

// Reads native view support from the `herdr` module namespace without ever throwing.
// Stock Herdr has no such export: returns null. The Herdr Bili build returns
// { interface, platform, available, kinds: [{ kind, actions }] }.
export function nativeCaps(ns) {
  try {
    if (typeof ns?.nativeViewCapabilities !== "function") return null;
    if (typeof ns?.nativeView?.new !== "function") return null;
    const caps = ns.nativeViewCapabilities();
    return caps && typeof caps === "object" ? caps : null;
  } catch { return null; }
}

export function hasWeb(caps) {
  return Boolean(caps) && caps.available !== false && Array.isArray(caps.kinds) && caps.kinds.some(k => k?.kind === "web");
}

// choice: "page" | "blocks" | null (the owner's toggle).
// mode: "page" (native view), "blocks" (Markdown panel) or "empty".
export function pageMode({ hasHtml, hasMd, caps, choice }) {
  const native = Boolean(hasHtml) && hasWeb(caps);
  if (!native) return { mode: hasMd ? "blocks" : "empty", canToggle: false, hint: null };
  if (!hasMd) return { mode: "page", canToggle: false, hint: null };
  return { mode: choice === "blocks" ? "blocks" : "page", canToggle: true, hint: null };
}

// True when the panel needs the local server: there is a page.html and the build has native web views.
// Decided at data time (reload), not at render time: a window on another Space never renders.
export const wantsServer = ({ hasHtml, caps }) => Boolean(hasHtml) && hasWeb(caps);

// Stable per panel and bot, so a re-render never creates a second view. The instance part is required:
// two live views with the same id erase each other, and a bot can be open in two Canvas panels.
export const viewId = (botId, instance) => `canvas-page-${botId}-${instance}`;

// True when the capabilities list `action` for the `web` kind (check before every call).
export const canDo = (caps, action) => Boolean(caps?.kinds?.some(k => k?.kind === "web" && Array.isArray(k.actions) && k.actions.includes(action)));

// ---- web page through the local server (canvas serve) ----------------------------------------------------------

export const DEFAULT_PORT = 47836;

// True when a "#rgb" / "#rrggbb" color is light (Herdr's theme() has no light/dark flag, only colors).
export function isLight(color) {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})/i.exec(String(color ?? ""));
  if (!m) return true;
  const h = m[1].length === 3 ? [...m[1]].map(c => c + c).join("") : m[1];
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.5;
}

export const webUrl = (port, botId, light) => `http://127.0.0.1:${port}/${encodeURIComponent(botId)}/?theme=${light ? "light" : "dark"}`;

// Is the server answering? Asks /health with curl through herdr.exec (a mod has no fetch).
export async function serverUp(exec, port) {
  try {
    const r = await exec("curl", ["-s", "-m", "2", "-o", "/dev/null", "-w", "%{http_code}", `http://127.0.0.1:${port}/health`], { timeout: 5000 });
    return r.code === 0 && String(r.stdout).trim() === "200";
  } catch { return false; }
}

// Probe; if it does not answer, start it ONCE (`canvas serve --detach`, which returns at once) and probe again.
// Never opens or focuses anything. Returns { ok, started, note }.
export async function ensureServer({ exec, port, bin }) {
  if (await serverUp(exec, port)) return { ok: true, started: false, note: null };
  try { await exec(bin, ["serve", "--detach"], { timeout: 20000 }); }
  catch (e) { return { ok: false, started: false, note: `Servidor local não subiu (${String(e).slice(0, 80)}); página sem comentários.` }; }
  if (await serverUp(exec, port)) return { ok: true, started: true, note: null };
  return { ok: false, started: true, note: "Servidor local não respondeu; página sem comentários." };
}
