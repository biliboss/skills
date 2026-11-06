# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.3] - 2026-11-06

### Changed

- Code changes go to a subagent sized to the step (the owner's "edit here" is the exception); a mid-task simplification is a full replacing steer; the merge script stops on a red test.

## [0.3.2] - 2026-11-04

### Changed
- O vizinho nomeado na descrição é a `duplo-local-agents` (ex-`herdr-agentes`).

## [0.2.3] - 2026-11-04

### Changed
- Os valores da casa (hosts, usuários, caminhos, contas, ids do Linear) vêm do `casa.env` (`~/.config/biliboss/casa.env`, modelo em `casa.env.example`); a skill veio para o repo público `biliboss/skills`, sem eles no texto.

## [0.2.2] - 2026-11-03

### Fixed
- A descrição sem `: ` solto (o pi lia como YAML inválido) e o vizinho certo, a `herdr-agentes`, no lugar do `delegate`.

## [0.2.1] - 2026-11-03

### Fixed
- A worktree do subagente sai do `command wt -C <repo> switch --create run/<tema> --base main` (o worktrunk), como manda a página `worktrunk` do wiki, e não do `git worktree add`, que o Claude Code nega fora da pasta da sessão.

## [0.2.0] - 2026-11-03

### Changed
- O passo 1 tira a tarefa e o repo da conversa (a última oferta ou recomendação, o "PRÓXIMO" de um repasse, a página de desenho, os achados abertos) e leva ao briefing o que a conversa já estabeleceu; sem 100% de clareza (o quê, o repo, o que entra e o que fica fora do PR), pergunta antes de lançar, uma vez, pela `AskUserQuestion` (a ferramenta padrão), com a recomendada primeiro.

## [0.1.0] - 2026-11-03

### Added
- Primeira versão (nasceu como `subagente-pr` e foi renomeada no mesmo dia): confirmar a tarefa e o repo, olhar o repo, o briefing em seis partes, lançar um Sonnet em segundo plano numa worktree nova, revisar o PR (testes rodados por você, `code-review`, as correções do briefing item por item) e corrigir os achados no mesmo ramo, sem merge nem deploy.
