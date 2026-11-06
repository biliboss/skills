# Changelog

## [0.2.0] - 2026-11-06

### Added
- O design-playground passou a morar na skill, em `playground/`. `scripts/motor.sh` usa essa pasta por padrão (`DP_DIR` só sobrescreve), roda o `bun install` se faltar e passa `DESIGN_PRODUTOS`, `DADOS_DIR` e `PATCHES_DIRS` ao processo do MCP.
- Seção "Mods: herdar, remendar, ligar estados": `herda`/`abstrato`, patches em `<produto>/patches/*.json`, modificadores, `requer` e `componentes_conferir`.

### Changed
- Mudar um wrapper real sem rebuild é um patch, nunca editar o `peca.html`.
- `DADOS_DIR` (conversa, canvas, cache) fica fora do git; padrão `~/.local/state/design-playground`.

## [0.1.0] - 2026-11-04

### Added
- O ciclo: achar o widget no código do produto, escrever o wrapper, `componente_definir({pasta})`, montar as telas com instâncias, o rascunho e o PR só com o sim do dono.
- `scripts/wrapper.sh` (`build`, `conferir`, `pastas`, `foto`) e `scripts/motor.sh` (`claude`, `pi`, `http`).
- `references/produto.md`: o formato da pasta de um produto. O que é de cada produto (a referência, a receita, os wrappers e os rascunhos) mora fora da skill, em `$DESIGN_PRODUTOS/<produto>/`, porque copia o código do produto.
