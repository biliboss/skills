# biliboss/skills

Os skills do biliboss como um plugin do Claude Code, no molde do [mattpocock/skills](https://github.com/mattpocock/skills): um repo, um plugin, uma versão.

| Skill | O que faz |
|---|---|
| `tensions` | registra eventos de domínio significativos no JSONL global, com Python stdlib e recipes `just` opcionais |
| `backbrief` | em desenho, domínio Tasks: um comando para a tarefa explicada a alguém e repetida de volta do jeito que foi entendida (teach-back) |
| `cost-track` | domínio Costs: tudo tem custo; cada domínio pertence a um centro de custo e o tempo ligado vira dinheiro; único escritor do diário de custos |
| `kanban` | o quadro do dono (Todo, Upstream, Downstream, Feito; o topo da coluna é o card em foco), cada card ligado a um domínio do dev-console; o Quadro é a página inicial do console, com o que o tempo em Upstream custou hoje, na semana e no mês; limite de WIP por repo (3 PRs abertos) e a varredura diária do que passou de 48 h |
| `domain-plan` | planejar a tarefa em Upstream: desenhar o domínio no dev-console (eventos e a tela de cada um), marcar rascunho ou real e detectar o drift entre o desenho e o código, que vira a lista do Downstream |
| `brainstorm` | pensar junto quando a ideia ainda está aberta, antes do backbrief: Double Diamond com pensamento sistêmico (Cynefin, iceberg, laço causal desenhado no dev-console, pontos de alavanca); termina numa nota "Decidi X porque Y" |
| `hustler` | a visão de mercado de uma ideia: o trabalho do cliente, as alternativas reais com fonte, o mapa de posicionamento (quadrante superior) e os modelos de negócio, open-core incluído; refeito a cada rodada, sempre indo além |
| `auth` | a identidade segura do agente: contas por provedor (Google primeiro), segredos só no envless e no Keychain, uma concessão por perfil, setup guiado |
| `retro` | a revisão da sessão (after-action review): as correções do dono viram regras nos skills certos, escolhidas por ele e aplicadas num PR |
| `diff-review` | a revisão de código de um diff local, com prompt próprio no plano flat: só problemas que o diff introduziu, cada um com cenário de falha; bloqueio aberto volta para a execução |
| `dev-console` | console de um arquivo só (FastHTML) para ver qualquer projeto event-sourced em desenvolvimento: máquina de estados, entidades, diário e widgets por evento; também numa janela nativa do Mac que o agente move por um script; a barra de dinheiro (▶ liga o relógio do centro de custo do domínio) |
| `setup-biliboss` | configura o repo uma vez: o `.wiki`, onde se trabalha (`main` direto ou `run/*` com PR) e o ramo principal |
| `wiki-smith` | o `.wiki/` que os agentes leem e mantêm: notas do dia, páginas, mapas, lint e commit |
| `thread` | o tópico de um card numa chamada só: janela tmux + sessão Hermes (branch ou nova) `<card> · <tópico>`, brief inline sem arquivo; as abas por recência (a mais recente é a 2) e a aba acende (✓) quando o agente termina um turno (skill tmux) |
| `handoff` | a passagem de turno de um agente Hermes no tmux: registra a sessão em `bili-sessions.jsonl`, abre o branch numa aba à direita e só então limpa a original (`/new` + resumo) |
| `skill-smith` | cria, atualiza e porta skills |
| `sync` | deixa cada repo que a sessão tocou igual ao remoto e sem sujeira, à mão |
| `postmortem` | do problema relatado até a decisão que o causou, reconstruída dos eventos do NATS, e a mudança aplicada |
| `lp-draft` | o rascunho de uma landing page num HTML só, no `.wiki/resources/` |
| `bili` | falar com o Bili (o agente de vida longa) por um cartão do Linear: pedir, esperar, ler |
| `linear` | o Linear do dono: ler um projeto, criar cartões, marcos e updates, subir imagens |
| `duplo-local-agents` | sessões de agente locais (Claude Code, pi) no herdr, no tmux ou sem multiplexador, pelo `mux.sh`; a mesa em fases e o focus no herdr |
| `delegate-and-review` | passar uma tarefa de código a um subagente que abre um PR, e revisar e corrigir depois |
| `pi` | o pi.dev com as contas do Claude pela assinatura, as skills ligadas no pi e o pi da VPS |
| `estudo-html` | um estudo entregue como página HTML local no `.wiki/resources/`, com veredito e matriz |
| `design` | telas no canvas do design-playground com os widgets reais do produto: o wrapper a partir do código, as instâncias, o rascunho e o motor do MCP; leva o design-playground (`playground/`) dentro e mods ao estilo RimWorld (herdar, patch, modificadores) |
| `hermes` | o Claude Code e o pi comandam os perfis locais do Hermes (researcher, designer, sre, via-ads, mantainer) como agentes com memória própria |
| `shape` | a porta padrão de planejamento: contexto, a peça certa (brainstorm, pelo resultado, interview, domain-plan, design-taste), backbrief e só então a delegação |
| `modifier-here` | `--here` no fim do pedido: o agente faz na própria sessão, sem subagente |
| `interview` | formulários de perguntas ricos (pi-interview) numa janela única com fila; com o dev-console no ar, a fila abre no módulo Browser dele em vez de uma janela própria (`devc browse`); rascunho salvo a cada mudança, e o tempo limite não perde respostas |
| `copywriting` | a escrita do Gabriel que vende uma ideia: post do LinkedIn, o Diário e o artigo, com a voz e as métricas de prosa da wiki |
| `faceless-art` | a arte sem rosto do Gabriel gerada pelo Codex, com os prompts de referência |
| `linkedin-publish` | publicar, editar e conferir um post do LinkedIn pelo Safari do Mac já logado |
| `envless` | usar um segredo do cofre (envless) num comando sem que o valor passe pela conversa |
| `disky` | achar onde mora o espaço do disco com o disky e propor a limpeza numa tabela que o dono aprova |

## Instalar

```sh
claude plugin marketplace add biliboss/skills
claude plugin install biliboss-skills@biliboss
```

Rode `/setup-biliboss` uma vez em cada repo.

## A configuração da casa

As skills da casa (`bili`, `linear`, `duplo-local-agents`, `pi`, `estudo-html`, `design`) precisam de valores que são de cada um: o workspace e os ids do Linear, o host da VPS, as contas do Claude, o repo principal, o design-playground e os checkouts dos produtos. Nada disso mora aqui. Cada máquina tem um `casa.env` fora do git:

```sh
mkdir -p ~/.config/biliboss
cp casa.env.example ~/.config/biliboss/casa.env
$EDITOR ~/.config/biliboss/casa.env   # troque cada placeholder pelo valor real
```

Os scripts carregam o arquivo com `. "${BILIBOSS_CASA:-$HOME/.config/biliboss/casa.env}"`; para usar outro arquivo, aponte `BILIBOSS_CASA`. Se o arquivo ou uma chave faltar, o script para dizendo qual chave falta. O `casa.env.example` lista todas as chaves, com um comentário em cada. Nunca commite o `casa.env`.

## Mudar um skill

Edite aqui (`skills/<nome>/`), suba a versão no `.claude-plugin/plugin.json` e no `CHANGELOG.md`, commite e faça o push, depois `claude plugin update biliboss-skills@biliboss`. O `wiki-smith` e o `skill-smith` moravam em repos próprios, hoje arquivados.

