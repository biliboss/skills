# modifier-here

`--here` at the end of a request means: the agent in this session does it now, with no subagent or thread. The rules
are in [SKILL.md](SKILL.md); history in [CHANGELOG.md](CHANGELOG.md).

| You say | The agent |
|---|---|
| `merge all open PR --here` | merges in this session, reports what went in and what is blocked |
| `merge all open PR` | triages as usual (may delegate) |

No scripts: it is a rule about routing work.

## Créditos e referências

| Autor | Obra | Ano | Link | Conferido |
|---|---|---|---|---|
| Nous Research | Hermes Agent, `/branch --here` (act on the current chat) | 2026 | https://hermes-agent.nousresearch.com/docs/reference/slash-commands | sim |
