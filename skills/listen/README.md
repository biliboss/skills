# listen

Quem quer ouvir registra o hook no bot ouvido: `listen` escreve, no `.claude/settings.json` do bot alvo, uma entrada
em `hooks.Stop` e outra em `hooks.Notification` que chamam `bili-agents/scripts/ag-notify <ouvinte> <evento>`. O
`ag-notify` acha o terminal vivo do ouvinte no Herdr (pelo nome registrado, senão pela pasta), espera a linha de
entrada ficar vazia (só `❯` e espaços, NBSP incluído) e faz `hc send` de uma linha
`<hook from="<alvo>">Nome: terminou o turno (sessão xxxxxxxx). <mensagem> Leia com hc read tN.</hook>`.
Sem terminal vivo, não faz nada. Espera até 10 minutos; o hook em si volta na hora (a espera roda desacoplada).
As regras estão no [SKILL.md](SKILL.md); o histórico, no [CHANGELOG](CHANGELOG.md).

| Comando | Exemplo |
|---|---|
| Escutar (da pasta do ouvinte) | `scripts/listen viacorretor` |
| Escutar de outra pasta | `scripts/listen viacorretor --as bili` |
| Só um evento | `scripts/listen viacorretor --events stop` |
| Parar de escutar | `scripts/listen viacorretor --off` |

Um Claude Code já aberto só carrega hooks novos depois de `/hooks` ou de reiniciar: a saída traz `needs_reload: true`
quando o alvo está vivo. `roster` mostra `listeners` por bot.

Testes: `python3 scripts/test_listen.py` (registro temporário, `hc` falso) e
`python3 ../bili-agents/scripts/test_notify.py` (detecção da linha vazia, resolução do terminal, a mensagem).
