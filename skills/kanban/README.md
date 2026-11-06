# kanban

O quadro do Gabriel no dev-console: cada card é um trabalho ligado a um domínio do console, numa etapa (Upstream,
Downstream ou Feito). O Quadro é a página inicial do console (`/`), com a faixa de dinheiro no topo: o que o tempo em
Upstream custou hoje, na semana (desde segunda) e no mês, subindo a cada segundo enquanto o relógio roda num domínio
de um card em Upstream. As regras para agentes estão no [SKILL.md](SKILL.md).

| Comando | Exemplo |
|---|---|
| criar um card | `scripts/kanban.sh create "Kanban" --domain kanban` |
| mudar de etapa | `scripts/kanban.sh move Kanban Downstream` |
| ver os cards | `scripts/kanban.sh list` |
| um card | `scripts/kanban.sh show Kanban` |
| o dinheiro | `scripts/kanban.sh money` |

O diário é `~/.local/share/kanban/events.jsonl` (ou `KANBAN_DIR`), escrito só pelo `kanban.sh`. O dinheiro vem do diário
de custos (skill `cost-track`), só lido: o tempo do domínio do card enquanto ele esteve em Upstream, pelo preço da hora
do centro de custo. Testes: `uv run --script scripts/test_kanban.py`. Histórico: [CHANGELOG.md](CHANGELOG.md).

Os nomes vêm do Kanban Method (David J. Anderson, *Kanban: Successful Evolutionary Change for Your Technology Business*,
2010) e do Upstream Kanban (Patrick Steyaert, *Essential Upstream Kanban*, 2018).
