# trace

O trace de uma resposta, no estilo OpenTelemetry: só os recursos que o dono criou (CLAUDE.md, AGENTS.md, páginas
da wiki do projeto (skill `wiki`), as skills dele, hooks, memória, settings) e que estavam em jogo naquele turno. As regras estão no
[SKILL.md](SKILL.md); o histórico, no [CHANGELOG](CHANGELOG.md).

## Como funciona

1. O script lê o transcript da sessão (`~/.claude/projects/<pasta>/<sessão>.jsonl`), só leitura.
2. Acha o turno-alvo (o anterior ao que chamou o `trace`) e lista os recursos seus: arquivos de instrução
   carregados, skills chamadas, arquivos seus lidos e hooks que injetaram contexto.
3. O agente completa `efeito` e `peso` (interpretação, marcada `inferred`) e imprime a árvore.

## Comandos

| Comando | Exemplo |
|---|---|
| Última resposta | `scripts/trace.sh` |
| A resposta anterior | `scripts/trace.sh --back 2` |
| Outra sessão | `scripts/trace.sh ~/.claude/projects/<pasta>/<id>.jsonl` |
| JSON | `scripts/trace.sh --json` |
| Exporta OTLP | `scripts/trace.sh --otlp "$SCRATCH/trace.json"` |

## Créditos e referências

| Autor | Obra | Ano | Link | Link checado |
|---|---|---|---|---|
| OpenTelemetry | GenAI semantic conventions | 2024– | https://opentelemetry.io/docs/specs/semconv/gen-ai/ | sim (200) |
| OpenTelemetry | OTLP specification | 2023– | https://opentelemetry.io/docs/specs/otlp/ | sim (200) |
| Arize AI | OpenInference | 2024– | https://github.com/Arize-ai/openinference | sim (200) |
| Langfuse | Data model | 2024– | https://langfuse.com/docs/observability/data-model | sim (200) |
