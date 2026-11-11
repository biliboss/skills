# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-11

### Changed

- Backbrief para um diretor que não é técnico: até cinco frases em prosa, a primeira é como fica para o dono, o que se faz em cinco palavras ou nada, sem motivo, sem ID e com as palavras dele (troca VPS, PR, issue). Pergunta só para o que não tem volta, no texto e nunca em diálogo. Dois exemplos de outros assuntos dentro da skill. Sai o formulário de rótulos (Entendi, Vou fazer, Fica de fora, Pronto quando). Testado no Opus: 884 palavras deram 90-92, a versão de 321 deu 91-93; árvore de decisão em seções deu 84-88 e ficou de fora.

## [0.2.0] - 2026-11-08

### Added

- `Who asks` section: a request from another agent gets the backbrief back by the same channel (`hc send`) before acting; when asking another bot, end with "backbrief primeiro" and read its backbrief before delegating for good. Also states "no journal".

## [0.1.0] - 2026-11-08

### Added

- Light everyday backbrief: at most five lines of text in the reply (understood, will do, left out, done when), then act. Replaces the old heavy `backbrief` skill, now `task-backbrief`.
