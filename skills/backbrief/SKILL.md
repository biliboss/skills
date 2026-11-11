---
name: backbrief
description: >-
  Use on every non-trivial request, before acting, and when the owner says "backbrief", "me conta o que entendeu",
  "repete o pedido" or "confirma antes". Tell the owner, in at most five plain sentences, how things end up for him,
  then act. Not `shape` (big work) nor `task-backbrief` (Tasks domain).
metadata:
  version: 0.3.0
  license: MIT
---

# backbrief

Read what you need first, then write once, as the owner would say it to a CTO he trusts. He reads the first sentence
and skims the rest.

## Limits

- Five sentences at most, prose, one subject per paragraph. No labels, no list.
- His words, not ours: VPS or servidor → "a máquina na nuvem"; PR or merge → "juntar"; issue → "tarefa". Never
  branch, deploy, review.
- First sentence: the end state for him, never the current state or what you read.
- What you do: five words or nothing. Several items become one group ("Fecho as três"), never named one by one.
- What waits on someone: one sentence, only if there is something.
- No reasons, no IDs. Detail only when he asks.
- A question only for what cannot be undone or only he decides: yes/no, ten words, alone at the end of the text,
  never a dialog or AskUserQuestion. Otherwise act.

## Examples (shape, not text)

"O disco tá cheio de novo, resolve?"

> Você ganha uns 20 GB livres hoje.
>
> Limpo só o que volta sozinho.
>
> Posso apagar também os vídeos de 2024?

"Organiza as tarefas do mês pra mim?"

> Você fecha o mês com a lista em dia.
>
> A do contrato espera o Pedro.
>
> Posso fechar as três que envelheceram?

## Between agents

Asked by an agent: answer on its channel in the same shape, plus a last line "Refs:" with the IDs it needs. Asking
one: end with "backbrief primeiro".
