# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-06

### Added

- O protocolo do advisor (`~/.local/share/advisor/README.md`) virado skill, os dois lados na mesma skill. O agente
  principal é o Bili no Sonnet (não um "executor"); o advisor (Opus) é a segunda opinião quando o julgamento pesa.
- Cinco pontos de consulta, que são decisões e não só código: o plano (inclui fazer à mão, subagente ou o Bili da VPS),
  travou, antes de entregar (obrigatório mesmo com os testes verdes), algo difícil de desfazer ou que sai para fora, e o
  pedido ambíguo. Fora deles, o agente segue sozinho.
- A description dispara em todo pedido: antes de começar, decidir se consulta e registrar a decisão.
- `decisions.jsonl` e os scripts `decide.sh` (`advisor.decided`, chamando ou não), `rate.sh` (`advice.rated` e
  `advisor.missed`) e `decisions.sh recent <task_kind>` (resume as últimas decisões do tipo e diz CHAME ou PULE): o
  histórico ensina em quais tipos de decisão vale chamar (`codigo`, `delegacao`, `operacao-externa`, `ambiguidade`...).
- `scripts/ask.sh`: `ask` (a pergunta, com os recursos copiados para `resources/<thread>/`), `reply` (o veredito
  `segue|corrige|para`), `note` (um fato) e `thread` (lê a thread). Escreve com `jq`, recusa linhas acima de 3500 bytes
  e recusa copiar `.env`, chaves, token e `.sesskey`. `ADVISOR_DIR`, `ADVISOR_ACTOR` e `ADVISOR_TO` configuram.
