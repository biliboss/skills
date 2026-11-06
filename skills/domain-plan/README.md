# domain-plan

Planejar uma tarefa enquanto o card está em Upstream: desenhar o domínio dela no dev-console (os eventos e, acima de
cada evento que alguém vê, a tela de verdade), marcar cada elemento como rascunho ou real, e detectar o **drift** entre o
desenho e o código. O drift é o plano que o Downstream executa. As regras para agentes estão no [SKILL.md](SKILL.md).

| Comando | O que faz |
|---|---|
| `scripts/plan.sh start <slug> --repo R --events-file F` | abre `<repo>/.plan/<slug>.jsonl` |
| `scripts/plan.sh add <slug> --kind event\|screen\|document --name N` | desenha um elemento (rascunho ou real) |
| `scripts/plan.sh drift <slug> [--mark]` | a construir, construído, fora do plano |
| `scripts/plan.sh confirm <slug>` | o dono aprovou: o card vai para Downstream |

O plano é um JSONL que se edita à mão. Testes: `uv run --script scripts/test_plan.py`. Histórico: [CHANGELOG.md](CHANGELOG.md).

## Créditos

- **Event Modeling** (Adam Dymitruk, 2019): os eventos e as telas acima deles, na mesma linha do tempo.
- **Plan e drift** vêm da infraestrutura como código (`terraform plan`, HashiCorp): estado desejado contra estado real,
  e a diferença são as mudanças a aplicar.
- **Upstream Kanban** (Patrick Steyaert, 2018): Upstream é descobrir e decidir; o ponto de compromisso abre o Downstream.
