# Routing evals: does task-understand load on its own?

Manual evals for the description, run each prompt in a **fresh session** with no `/task-understand` and no hint.
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

Haiku is enough for a routing check; Sonnet when Haiku's answer is unclear. Link the skills first (`pi` skill,
`ligar-skills.sh`), then per prompt:

```sh
bash <pi skill>/scripts/pi-claude.sh mukutu -p --no-session --mode json \
  --model claude-bridge/claude-haiku-5-5 "<prompt>" > run.jsonl
grep -c 'task-understand/SKILL.md' run.jsonl   # > 0: the skill was read
```

In Hermes: `hermes -p <profile> chat -Q --oneshot --max-turns 6 -q "<prompt>"`, then look for a `skill_view` of
`task-understand` in that session.

## Results

- 2026-11-05, Hermes (Opus 5.5), description 0.12.1: #1 failed (wrote the script without a teach-back), #2 passed,
  #5 passed (read the README, the line was already there). The description alone did not route #1 in Hermes,
  whose skill index shows only the first ~60 characters.
