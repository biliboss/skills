# tmux

Skill de agente para tudo o que se faz em panes e janelas do tmux: ler, listar, mandar texto com segurança, abrir e renomear janelas, esperar um texto. Cada ação é um script em `scripts/`, que chama o binário do tmux pelo caminho (o alias `tmux` do shell do dono atrapalha) e resolve o alvo por igualdade exata. Nenhum script mata sessão ou servidor.

| Script | O que faz | Exemplo |
|---|---|---|
| `scripts/win.sh list` | lista panes: id, sessão:janela.pane, janela, comando, pasta | `win.sh list --json` |
| `scripts/win.sh new` | abre janela com nome e comando, sem roubar o foco | `win.sh new build "make test" --cwd ~/app` |
| `scripts/win.sh rename` | renomeia a janela de um alvo | `win.sh rename bili-sonnet bili-opus` |
| `scripts/pane.sh read` | últimas N linhas sem brancos | `pane.sh read bili-sonnet 30` |
| `scripts/pane.sh send` | manda texto, confere o fim, aperta Enter | `pane.sh send %12 "/reload-plugins"` |
| `scripts/pane.sh key` | manda teclas nomeadas | `pane.sh key %12 Escape C-c` |
| `scripts/pane.sh wait` | espera um texto (ou a tela parar), com prazo | `pane.sh wait %12 --text 'done' --timeout 60` |

Alvos: `%12`, `nome-da-janela`, `sessao:janela`, `sessao:janela.pane`. `TMUX_SOCKET=nome` usa outro servidor; `TMUX_BIN` aponta o binário.

## Testes

```
skills/tmux/scripts/test.sh
```

Sobe um servidor tmux privado (socket `skilltest-<pid>`), roda os casos, imprime `ok`/`FAIL` e derruba só esse servidor. Sai 0 só se tudo passa. Não usa um Claude Code de verdade.

## Histórico

Veja o [CHANGELOG.md](CHANGELOG.md). O uso por agentes está no [SKILL.md](SKILL.md).
