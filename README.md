# biliboss/skills

Os skills do biliboss como um plugin do Claude Code, no molde do [mattpocock/skills](https://github.com/mattpocock/skills): um repo, um plugin, uma versão.

| Skill | O que faz |
|---|---|
| `setup-biliboss` | configura o repo uma vez: o `.wiki`, onde se trabalha (`main` direto ou `run/*` com PR) e o ramo principal |
| `wiki-smith` | o `.wiki/` que os agentes leem e mantêm: notas do dia, páginas, mapas, lint e commit |
| `skill-smith` | cria, atualiza e porta skills |
| `sync` | deixa cada repo que a sessão tocou igual ao remoto e sem sujeira, à mão |
| `lp-draft` | o rascunho de uma landing page num HTML só, no `.wiki/resources/` |
| `bili` | falar com o Bili (o agente de vida longa) por um cartão do Linear: pedir, esperar, ler |
| `linear` | o Linear do dono: ler um projeto, criar cartões, marcos e updates, subir imagens |
| `herdr-agentes` | abrir, conduzir, fechar e retomar sessões de agente (Claude Code ou pi) nas abas do herdr |
| `herdr-mesa` | a mesa do herdr em fases (um workspace por fase), com o cartão de cada item no focus |
| `delegate-and-review` | passar uma tarefa de código a um subagente que abre um PR, e revisar e corrigir depois |
| `pi` | o pi.dev com as contas do Claude pela assinatura, as skills ligadas no pi e o pi da VPS |
| `estudo-html` | um estudo entregue como página HTML local no `.wiki/resources/`, com veredito e matriz |
| `design` | telas no canvas do design-playground com os widgets reais do produto: o wrapper a partir do código, as instâncias, o rascunho e o motor do MCP |
| `interview` | formulários de perguntas ricos (pi-interview) numa janela única com fila; rascunho salvo a cada mudança, e o tempo limite não perde respostas |
| `envless` | usar um segredo do cofre (envless) num comando sem que o valor passe pela conversa |
| `disky` | achar onde mora o espaço do disco com o disky e propor a limpeza numa tabela que o dono aprova |

## Instalar

```sh
claude plugin marketplace add biliboss/skills
claude plugin install biliboss-skills@biliboss
```

Rode `/setup-biliboss` uma vez em cada repo.

## A configuração da casa

As skills da casa (`bili`, `linear`, `herdr-agentes`, `pi`, `estudo-html`, `design`) precisam de valores que são de cada um: o workspace e os ids do Linear, o host da VPS, as contas do Claude, o repo principal, o design-playground e os checkouts dos produtos. Nada disso mora aqui. Cada máquina tem um `casa.env` fora do git:

```sh
mkdir -p ~/.config/biliboss
cp casa.env.example ~/.config/biliboss/casa.env
$EDITOR ~/.config/biliboss/casa.env   # troque cada placeholder pelo valor real
```

Os scripts carregam o arquivo com `. "${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"`; para usar outro arquivo, aponte `BILIBOSS_CASA`. Se o arquivo ou uma chave faltar, o script para dizendo qual chave falta. O `casa.env.example` lista todas as chaves, com um comentário em cada. Nunca commite o `casa.env`.

## Mudar um skill

Edite aqui (`skills/<nome>/`), suba a versão no `.claude-plugin/plugin.json` e no `CHANGELOG.md`, commite e faça o push, depois `claude plugin update biliboss-skills@biliboss`. O `wiki-smith` e o `skill-smith` moravam em repos próprios, hoje arquivados.

