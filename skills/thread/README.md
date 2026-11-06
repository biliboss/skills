# thread

Abre um tópico numa chamada só: uma janela tmux **na sessão onde a skill foi chamada** (nunca uma sessão por card), rodando uma sessão do Hermes que é sempre um `/branch` da sessão que chamou (`$HERMES_SESSION_ID`; `--new` só se pedido), logo depois da janela do agente que chamou (a thread mais nova é sempre a aba 2) chamada `<card> · <tópico>` (ou só `<tópico>`), com o brief entregue na hora, sem arquivo em temp. O card fica na janela (`@card`), e o relógio de custo lê o card da janela ativa. Regras e uso: [SKILL.md](SKILL.md).

| Comando | O que faz | Exemplo |
|---|---|---|
| `thread.sh open <tópico>` | abre janela + sessão Hermes + brief | `thread.sh open acesso-bubble --card unicred --brief - <<'EOF' … EOF` |
| `thread.sh list` | lista as janelas com `@thread`, em todas as sessões | `thread.sh list` |
| `thread.sh close <tópico>` | fecha só a janela | `thread.sh close acesso-bubble` |

Opções do `open`: `--card C`, `--session S`, `--from ID_DA_SESSÃO | --new`, `--brief TEXTO | - | --brief-gz B64`. Fora do tmux (o agente do desktop), abre na sessão do cliente com atividade mais recente.

O brief vai por `tmux load-buffer` (stdin) + `paste-buffer -p` (colagem entre colchetes): uma mensagem só, sem limite prático de tamanho. `--brief-gz` aceita base64 de gzip para quem tem parâmetro limitado.

## Testes

`skills/thread/scripts/test.sh`: `hermes` falso e servidor tmux privado (`-L thread-test-<pid>`); cobre o `/branch` de `$HERMES_SESSION_ID` (recusa sem ele), a posição da aba, a sessão do chamador, a do cliente mais ativo (shim de `list-clients`), `--session`, `@card` por slug e por id, new, branch, brief de 200 KB intacto, `--brief-gz`, list entre sessões e close.

## Créditos e referências

| Base | Autor | O que usamos | Link |
|---|---|---|---|
| tmux (`load-buffer`, `paste-buffer -p`, opções `@`) | Nicholas Marriott e colaboradores | entrega do brief e marcas nas janelas | https://github.com/tmux/tmux (não conferido com curl) |
| Hermes Agent (`/branch`, `sessions rename`) | Nous Research | ramo da sessão do card e título | https://github.com/NousResearch/hermes-agent (não conferido com curl) |

Histórico: [CHANGELOG.md](CHANGELOG.md).
