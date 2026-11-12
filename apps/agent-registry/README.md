# Agent Registry — Home prototype

Design draft for #204. Open `prototypes/home.html` directly in a browser; no build, installation, network, or server is required.

The Home brings agents, reusable skills, and MCP connections into one light grayscale workspace. The self-contained CSS defines prototype UI primitives (buttons, cards, badges, tabs, fields, and dialogs); no production UI Kit dependency has been selected or integrated yet.

## Review

- Browse Home, Agents, Skills, and MCP tools in the sidebar.
- Filter cards by type and search by name, description, or tag.
- Open a card to inspect resource details.
- Register a demo agent; verify the count and recent activity update.
- Press `/` to focus search; use Escape to close a dialog.
- Resize the page for desktop, tablet, and mobile layouts.

All resources and activity are illustrative. New agents live in memory and disappear on reload. There are no live agent executions, MCP connections, credentials, or persistence. Browser visual QA is pending; this remains a draft for design review.
