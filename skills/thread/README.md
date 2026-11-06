# thread

Abre o tópico de um card numa chamada só: uma janela tmux na sessão do card, rodando uma sessão do Hermes (um `/branch` da sessão do card, ou uma nova) chamada `<card> · <tópico>`, com o brief entregue na hora, sem arquivo em temp. Regras e uso: [SKILL.md](SKILL.md).

| Comando | O que faz | Exemplo |
|---|---|---|
| `thread.sh open` | abre janela + sessão + brief | `thread.sh open unicred acesso-bubble --brief - <<'EOF' … EOF` |
| `thread.sh list` | lista as threads | `thread.sh list unicred` |
| `thread.sh close` | fecha só a janela | `thread.sh close unicred acesso-bubble` |

O brief vai por `tmux load-buffer` (stdin) + `paste-buffer -p` (colagem entre colchetes): uma mensagem só, sem limite prático de tamanho. `--brief-gz` aceita base64 de gzip para quem tem parâmetro limitado.

## Testes

`skills/thread/scripts/test.sh`: `hermes` falso e servidor tmux privado (`-L thread-test-<pid>`); cobre new, branch, brief de 200 KB intacto, `--brief-gz`, list e close.

## Créditos e referências

| Base | Autor | O que usamos | Link |
|---|---|---|---|
| tmux (`load-buffer`, `paste-buffer -p`, opções `@`) | Nicholas Marriott e colaboradores | entrega do brief e marcas nas janelas | https://github.com/tmux/tmux (não conferido com curl) |
| Hermes Agent (`/branch`, `sessions rename`) | Nous Research | ramo da sessão do card e título | https://github.com/NousResearch/hermes-agent (não conferido com curl) |

Histórico: [CHANGELOG.md](CHANGELOG.md).
