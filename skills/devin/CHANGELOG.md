# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-08

### Added

- Lote: `batch.sh` (manifesto JSON validado antes de disparar, base resolvida uma vez, teto `DEVIN_MAX_PARALLEL` contado em todas as rodadas), `gate.sh` (escopo contra `allowed` e gates do prek por fora do Devin), `retry.sh` (mesmo worktree, tentativas arquivadas, 2 no máximo) e `merge.sh` (fila na ordem do grafo, só integra, nunca faz push, para no conflito ou no gate reprovado). `_gates.sh` interno.
- `references/lote.md` e `templates/gates/` (Python e TypeScript para o prek, mais a catraca `ratchet.py` para o legado).

### Changed

- Modelo padrão `swe-2-medium` (antes `swe-2-max`, agora só na segunda retentativa).

### Verified

- Devin falso, repositórios temporários: 9 cartões nunca passam de 8 running; arquivo fora de `allowed` reprova; função com complexidade acima de 10 reprova (e passa com o legado na linha de base); segredo falso reprova no gitleaks; dois cartões no mesmo arquivo param o `merge.sh` no conflito. Python exercitado inteiro; TypeScript só com biome, tsc, knip, jscpd e dependency-cruiser em projeto mínimo.
- Não exercitado: o Devin real; pre-push do TypeScript com violação real de knip e dependency-cruiser; o `merge.sh` com gate reprovado depois do merge.

## [0.1.0] - 2026-11-08

### Added

- Delegação ao Devin CLI em background com `run.sh`, `check.sh`, `wait.sh`, `review.sh` e `clean.sh`: um worktree e um branch por tarefa, `swe-2-max` e `accept-edits` por padrão.
