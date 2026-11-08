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
  if (!hasMd) return { mode: "page", canToggle: false, hint: "Comentar exige page.md; esta página é só leitura." };
  return { mode: choice === "blocks" ? "blocks" : "page", canToggle: true, hint: null };
}

// Stable per panel and bot, so a re-render never creates a second view. The instance part is required:
// two live views with the same id erase each other, and a bot can be open in two Canvas panels.
export const viewId = (botId, instance) => `canvas-page-${botId}-${instance}`;

// True when the capabilities list `action` for the `web` kind (check before every call).
export const canDo = (caps, action) => Boolean(caps?.kinds?.some(k => k?.kind === "web" && Array.isArray(k.actions) && k.actions.includes(action)));
