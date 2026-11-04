---
name: mux
description: Drive terminal panes in tmux and herdr from the Python REPL with stable two-digit ids (TNN for tmux, HNN for herdr) - list every pane, read a screen, send a key or a message, open a pane and name it. Use to manage agent sessions in panes deterministically ("lista os panes", "manda para o H05", "lê o T01", "renomeia os panes do herdr").
---

# mux

Funções síncronas, já importadas no REPL como `mux`. Cada uma chama o `mux.sh` da skill prime-agent,
que é a fonte da lógica (o mesmo comportamento do shell).

```python
mux.panes()                       # lista de dicts: id, mux, pane, nome, estado
mux.ler("T01", 40)                # a tela do pane, como texto
mux.tecla("H05", "Enter")
mux.manda("H05", "texto da mensagem")   # cola e aperta Enter
mux.nomear("w5Y:p9", "duplo-eval-tasks")  # dá o próximo HNN livre; devolve o id
mux.abrir("/pasta", "nome", "comando")    # pane à direita deste; devolve o id
```

- `TNN` é do tmux (nas opções `@tnn`/`@nome` do pane), `HNN` é do herdr (no rótulo, `HNN - nome`).
- `pane` aceita o id (`T01`, `H05`) ou o id nativo (`%4`, `w5R:p39`).
- Um erro do `mux.sh` vira `RuntimeError` com a mensagem dele.
