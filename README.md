# biliboss/skills

Os skills do biliboss como um plugin do Claude Code, no molde do [mattpocock/skills](https://github.com/mattpocock/skills): um repo, um plugin, uma versão.

| Skill | O que faz |
|---|---|
| `setup-biliboss` | configura o repo uma vez: o `.wiki`, onde se trabalha (`main` direto ou `run/*` com PR) e o ramo principal |
| `wiki-smith` | o `.wiki/` que os agentes leem e mantêm: notas do dia, páginas, mapas, lint e commit |
| `skill-smith` | cria, atualiza e porta skills |
| `sync` | deixa cada repo que a sessão tocou igual ao remoto e sem sujeira, à mão |
| `lp-draft` | o rascunho de uma landing page num HTML só, no `.wiki/resources/` |

## Instalar

```sh
claude plugin marketplace add biliboss/skills
claude plugin install biliboss-skills@biliboss
```

Rode `/setup-biliboss` uma vez em cada repo.

## Mudar um skill

Edite aqui (`skills/<nome>/`), suba a versão no `.claude-plugin/plugin.json` e no `CHANGELOG.md`, commite e faça o push, depois `claude plugin update biliboss-skills@biliboss`. O `wiki-smith` e o `skill-smith` moravam em repos próprios, hoje arquivados.

Os skills da casa (o Bili, o delegate) ficam no plugin privado `biliboss/skills-casa`.
