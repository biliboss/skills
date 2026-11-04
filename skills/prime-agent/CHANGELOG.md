# Changelog

Todas as mudanças do skill `prime-agent`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-04

### Changed
- A skill não depende mais do herdr: `scripts/mux.sh` (qual, abrir, ler, tecla, manda) fala com o herdr ou com o tmux, detectados por `$HERDR_PANE_ID` e `$TMUX` (ou `$MUX`); sem multiplexador, `abrir.sh` imprime o comando. Os passos usam só o `mux.sh`, e o envio da mensagem deixou de passar pela skill `herdr-agentes`. Os panes do tmux saem como `TNN` (`%4` vira `T04`), e o `mux.sh` escolhe o multiplexador pelo id.

## [0.2.0] - 2026-11-04

### Added
- A receita `references/receita-hyperdx.md` (o briefing, o padrão de funções que funciona com o `mcpc`, a conferência e o fecho) e um exemplo de uso de ponta a ponta na SKILL.md.

## [0.1.0] - 2026-11-04

### Added
- O Prime Agent como caderno de análise no GLM do coding plan: `configurar.sh` (binário, traces e telemetria off, padrão zai), `rodar.sh` (a chave lida só na chamada), `abrir.sh` (pane à direita, uma pasta por tema), `sessao.sh` (o resumo da sessão de uma pasta) e o modelo `templates/BRIEF.md`.
- Os passos do briefing ao fecho: conferir os números, fechar toda análise no `.wiki` (wiki-smith), promover a consulta para script, macro ou tile, e passar o trabalho da VPS ao Bili num cartão.
