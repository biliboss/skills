# rebrief

Muda o nome ou a identidade de um bot companheiro e guarda a identidade anterior. As regras estão no
[SKILL.md](SKILL.md); o histórico, no [CHANGELOG](CHANGELOG.md).

| Comando | Exemplo |
|---|---|
| Renomear | `scripts/rebrief revisor --name "Revisora"` |
| Nova identidade | `scripts/rebrief revisor --brief /caminho/brief.md` |

Testes: `python3 scripts/test_rebrief.py`. Usam registro temporário e um `hc` falso.
