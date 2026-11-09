# agentsmd

Cria, migra ou audita o `AGENTS.md` e a memória de agentes de um projeto. As regras estáveis ficam num arquivo curto, carregado em toda sessão; o que envelhece vai para um `STATE.md`, com fonte e data em cada afirmação.

## Como funciona

1. Escolha o modo: criar, migrar memórias espalhadas ou auditar um arquivo existente.
2. Classifique cada linha: regra, estado, decisão, histórico ou algo que o agente descobre sozinho.
3. Preencha os templates e apague as seções vazias.
4. Confira o resultado com a lista de auditoria.

As regras ficam em [SKILL.md](SKILL.md).

| Arquivo | Para quê |
|---|---|
| [templates/AGENTS.md](templates/AGENTS.md) | modelo das regras estáveis |
| [templates/STATE.md](templates/STATE.md) | modelo do estado datado |
| [references/prior-art.md](references/prior-art.md) | fontes e o que foi aproveitado |

Exemplo: `/agentsmd migra as memórias deste projeto para AGENTS.md e STATE.md`.

Não há script nem teste automatizado nesta versão. Histórico: [CHANGELOG.md](CHANGELOG.md).

## Créditos e referências

| Autor | Trabalho | Ano | Link | Link conferido |
|---|---|---|---|---|
| Comunidade AGENTS.md | agents.md | 2025 | https://agents.md | sim |
| Gloaguen et al. | Evaluating AGENTS.md | 2026 | https://arxiv.org/abs/2602.11988 | sim |
| Lulla et al. | On the Impact of AGENTS.md Files | 2026 | https://arxiv.org/abs/2601.20404 | sim |
| Anthropic | Claude Code memory | 2026 | https://code.claude.com/docs/en/memory | sim |
| OpenAI | Codex AGENTS.md | 2026 | https://learn.chatgpt.com/docs/agent-configuration/agents-md | sim |
