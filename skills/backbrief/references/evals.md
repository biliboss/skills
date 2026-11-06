# Routing evals: does backbrief load on its own?

Manual evals for the description, run each prompt in a **fresh session** with no `/backbrief` and no hint.
Pass = the agent behaves as the "expected" column says on its first reply. The point is the description alone, so
run them after any change to it.

| # | Prompt | Expected |
|---|---|---|
| 1 | `Escreve um script em <scratch>/renomear-fotos.sh que renomeia as fotos de uma pasta pela data EXIF.` | Loads the skill: repeats the work back and asks "Bate?" before writing a line |
| 2 | `Que horas são em Lisboa agora?` | Does not load it: answers at once |
| 3 | `Inicia um timer de 25 min.` | Does not load it: a one-line command (the `timer` skill), done directly |
| 4 | `Cria uma issue no mukutu-mono lembrando de completar o ponto e põe em Ready to Start.` | Loads it: a team's board; the teach-back says who moves which card |
| 5 | `Adiciona uma linha no README dizendo que a skill timer existe.` | Borderline: either is fine, but if it acts it must read the file first and not duplicate a line that is already there |

## Running on pi (cheap)

Ladder: at least 10 description variants on Haiku, 2 work prompts each; only if none passes, the same on Sonnet;
only if Sonnet fails too, give up on the description and put the rule in the harness/profile. Rerun the winners
2 more rounds before adopting one (models are not deterministic; 2/2 once is luck-prone).

`scripts/route_eval.py <haiku|sonnet> [variants...]` does it: each variant is a copy of the skill with only the
description changed, loaded with `pi --no-skills --skill <each real skill> --skill <variant>` so it competes as in
real use, each run in its own temp dir. Edit its `V` dict to try new wordings.

- **Score by the requested file, not by "wrote any file"**: PASS = the file the prompt asked for does not exist and
  the answer asks for the confirmation. The skill's own flow writes a helper `.sh` for the emits, so counting any
  write fails every correct teach-back; and grepping the log for the SKILL.md path is not proof of a read.
- Wrap a generated description on word boundaries (`textwrap.fill`): a YAML folded scalar turns a mid-word line
  break into a space and splits the word.

In Hermes: `hermes -p <profile> chat -Q --oneshot --max-turns 6 -q "<prompt>"`, then look for a `skill_view` of
`backbrief` in that session (`state.db`, `messages.tool_calls`). Hermes shows only the first ~60 characters of
each description in its index (the real line is in `system_prompts.prompt`), and a profile that says "act on your
recommendation" outweighs any description, so test Hermes separately from pi.

## Results

- 2026-11-05, Hermes (Opus 5.5), description 0.12.1: #1 failed (wrote the script without a teach-back), #2 passed,
  #5 passed (read the README, the line was already there). The description alone did not route #1 in Hermes,
  whose skill index shows only the first ~60 characters.
- 2026-11-05, pi on Haiku 5.5, 10 descriptions x 2 work requests, the other skills loaded beside it (pass = the
  requested file not created and the answer asks for the confirmation): the 0.12.1 description 0/2; "gate" 6/6 in
  three rounds, "first step" 6/6, "do not write before this skill" 5/6; the rest 0 to 1 of 2. The gate went in
  (0.12.2).
- 2026-11-05, Hermes (Opus 5.5, profile bili) with the gate description: 0/2, both scripts written at once. The
  profile's own rules (act on your recommendation, ask only the four cases) win over a skill description, so in
  Hermes the gate needs a line in the profile; pi and Claude Code route by the description.
