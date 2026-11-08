---
name: choice
description: >-
  Use when the owner has to choose between options (a logo, an icon, a screen, a name, a text, a palette): run it as a tournament of 4. Each round shows 4 options with the agent's confidence summing 100, ranked 01-04 (01 is the champion the agent picks, so there is always one), in a full-screen showcase in the dev-console; the owner answers with three fixed keys (⏎ another round: the champion against 3 new challengers, a accept, f feedback that becomes a criterion) until he accepts. scripts/tournament.py is the only writer of its journal and draws each round on the thread screen (skill thread). Use when he says "me dá opções", "4 opções", "outra rodada", "torneio", "desafiantes", "escolher o logo". Not brainstorm (an idea still open) nor task-backbrief (a task to confirm).
metadata:
  version: 0.1.2
  license: MIT
---

# choice: a tournament of 4

Born from the DevConsole logo (round 1: prompt, grafo, janela, eventos; round 2: janela against squircle, janela de
eventos, moeda). The thread is where it lives: the thread screen is the ask tool (skill `thread`, `threadview.py`).

## The process (few edges)

```
tournament.opened → round.shown ⇄ round.answered → tournament.won
```

- **Every round has 4 options and a champion.** Your confidence in each sums 100; they are ranked, and 01 is the
  champion you pick. No discard branch: if he likes none, he gives feedback and your champion still stands.
- **Three edges, each on a fixed key, the same in every round** (muscle memory): ⏎ another round (the champion
  against 3 new challengers), `a` accept the champion, `f` feedback (his words become a criterion of the next round).
  `o` opens the showcase. He ends it; never a fixed number of rounds.
- **Talk about options by name**, never by letter or number: the number is the rank and changes each round.
- **Drawing challengers takes longer than a thread turn (10 s)**: do it as a worker (`view.py worker add/done`).

## Use

```bash
T=<this skill>/scripts/tournament.py
python3 $T open <slug> "<tema>" --thread <hermes-session-id> [--kind logo|screen|name|text|palette]
python3 $T round <slug> --option "<nome>" <path> <pct>   # four times; round 2+ includes the champion
python3 $T answer <slug> another|accept|feedback ["<as palavras dele>"]   # when "torneio <slug>: …" arrives
python3 $T show <slug>      # round, champion, criteria (every feedback so far), last options
python3 $T list
```

- With `--thread`, each round is drawn on the thread screen through the thread skill's `scripts/view.py`
  (`THREADVIEW_PY` overrides): artifacts 01-04 with their %, the input turned into the three edges, and the
  showcase opened in the dev-console by itself (`devc open`).
- **Screens (`--kind screen`) go in as PNGs, not HTML:** build each option as an HTML file in the product's look with
  the same demo data, then screenshot it at the widget's width with 2x scale (`browser_exec` local, `cdp
  Emulation.setDeviceMetricsOverride width=720 deviceScaleFactor=2`) and pass the PNG. Make the 4 options different
  ideas of the screen (one decision at a time, a list, a data panel, a two-column split), not 4 colorings of one layout,
  and rank the one that best fits the product's design premise as champion.
- The showcase is a full-screen grid in the dev-console's look (dark, monospace): each option large and at 16/32 px,
  the champion marked green with its %. No extra "all side by side" artifact: the grid compares.
- Refusals (exit 2, nothing written): a round before the previous was answered, a round without the champion,
  confidence not summing 100, a missing file, feedback without words.
- Journal: `~/.local/share/tournament/events.jsonl` (`TOURNAMENT_DIR`). In the dev-console it is the domain
  `choice` (`scripts/dev_console_project.py`): `console.sh domains add <this skill>/scripts/dev_console_project.py`.
