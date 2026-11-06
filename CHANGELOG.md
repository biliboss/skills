# Changelog

Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html). Cada skill guarda também o próprio `CHANGELOG.md`.

## 0.102.0

- handoff 0.2.0: the guard, a Hermes plugin (`handoff-guard`) that, in folders with `HANDOFF_AT=<percent>`, injects the handoff order at the threshold and blocks the turn at +15. setup-biliboss 0.2.0: fourth choice, the guard (off by default).

## 0.94.0

- Loose edits from other sessions landed: auth, backbrief, choice, delegate-and-review, dev-console, doctor, domain-plan, envless, handoff, hermes, interview, lp-draft, modifier-here, shape, sync, thread, tmux (patch bumps; auth, domain-plan and lp-draft keep the minor they already carried).

## 0.82.0

- auth 0.1.0: the agent's secure identity. Accounts per provider (Google first, by `gws`), the OAuth client only in envless, one grant per Hermes/Claude profile, a setup the agent guides with the ask tool, the dev-console domain Auth with the Contas widget; `gcal` becomes a thin alias of `auth.sh run`.

## 0.81.0

- thread 0.5.0: closing a thread (`thread.sh close --self --summary`, deferred when the owner is on the tab, one log line in `~/.local/state/threads.log`, never while it waits for him or has subagents running). tmux 0.4.0: `agent-state.sh sub+|sub-`, grey glyph + count of running subagents on the tab, ✓ only at 0.

## 0.80.0

- tmux 0.3.0: `agent-state.sh`, the thread's tab lights up (✓, bordô) when its Hermes agent finishes a turn and clears when the owner enters it, driven by Hermes shell hooks (no polling). thread 0.4.0: `thread.sh touch`, tabs by recency (Bili = 1, threads newest first, non-threads last, focus never moved). kanban 0.7.4 and dev-console 0.30.6 read `@agent`/`@done` first.

## 0.78.0

- hustler 0.1.0: market vision for an idea (customer job, alternatives with sources, positioning map and the upper quadrant, business models incl. open-core, re-check list), with `render-map.sh`; first use on Zelito.

## 0.77.0

- dev-console 0.30.5, kanban 0.7.3: the home module is named `Kanban` in ⌘P and the domain tab (was `Quadro`); `?tab=Quadro` still opens the board (`MODULE_ALIASES`).

## 0.76.0

- Loose notes landed: cost-track 0.5.1, delegate-and-review 0.3.3, dev-console 0.30.4, disky 0.1.1 (organizing `~/src`), domain-plan 0.2.0, kanban 0.7.2 (swimlanes; thread recipe points to `thread`), lp-draft 0.2.2, wiki-smith 0.1.5.

## 0.75.0

- thread 0.2.0: the tab opens in the tmux session where the skill was invoked, right after the invoking agent's window, as a /branch of $HERMES_SESSION_ID (client-latest session outside tmux, `--session` overrides), never a session per card; the card is `@card` on the window. cost-track 0.5.0: the clock reads the active window's `@card` first, new `session-window-changed` hook. kanban 0.7.1: docs.

## 0.74.0

- dev-console 0.30.3: the Kanban's Quadro (`CONSOLE_HOME`) is in ⌘P from every page and in `/api/palette`, first in the list.

## 0.73.0

- thread 0.1.0: a card's topic thread in one call: tmux window + Hermes session (`/branch` of the card's session or new) named `<card> · <topic>`, brief inline by argument, stdin heredoc or gzip+base64 (bracketed paste, no temp file).

## 0.71.0

- backbrief 0.18.0: the "pelo resultado" mode (context first, up to 5 questions, the 5-field request + the week's bet) and the optional `intent` of the teach-back. kanban 0.7.0: `kanban.sh describe` (`card.described`), shown under the card's title on the Quadro.

## 0.70.0

- kanban 0.6.3: the card's tmux tab is named by its title (`pull`) and follows `rename`; the session keeps its slug.

## 0.69.0

- Loose learnings from sessions landed: patch bumps for backbrief, brainstorm, dev-console, hermes (+`references/briefing.md`), kanban, linear, lp-draft, seo-audit, skill-smith (+`resolve_release_conflicts.py`), sync, tmux, wiki-smith.

## 0.68.0

- domain-plan 0.1.0: planning in Upstream; the task's domain drawn in the dev-console as drafts (events, the real screen above each), a hand-editable `.plan/<slug>.jsonl` in the repo and `plan.sh drift` (to build, built, unplanned). kanban 0.6.1: `pull` opens the card's plan.

## 0.67.0

- kanban 0.5.0: `kanban.sh pull`, one gesture to start a task (card, Hermes + tmux session named slug, client switched, cost center bound); hermes 0.3.0: `workspace`; cost-track 0.4.1: `costs.py bind`.

## 0.66.0

- tmux 0.2.0: `run.sh`, processo longo (servidor, watcher, suite de testes) numa sessão tmux presa à worktree do dono, com log, `--low --slot` (tampa global de suites), `reap` e um reaper launchd; seção "Processos longos" no SKILL.md.

## 0.65.0

- cost-track 0.4.0: the cost clock follows the tmux session (`costs.sh tmux-focus`, `tmux-install`); dev-console 0.29.2: the window no longer drives the clock; kanban 0.4.2.

## 0.64.0

- dev-console 0.29.1: `devc delegated` / `devc done` removed (one card per named work). hermes 0.2.4, kanban 0.4.1 (policy), backbrief 0.17.1 (step 9).

## 0.63.0

- dev-console 0.29.0: `devc delegated` / `devc done` / `devc board`, every delegated subagent is a Kanban card
  (Downstream, then Feito). hermes 0.2.3: the spawn step says so.

## 0.62.0

- dev-console 0.28.0: two fingers pan the graph, a pinch or ⌘ + scroll zooms; no graph label under 14 px
  (a zoom floor; nothing folded or hidden).

## 0.61.0

- dev-console 0.27.0: Restores the domain page and the home to 0.24.0 (before the folded lanes of 0.25.0 and the focus home of 0.26.0): the owner lost the side panel and the event texts. devc stays.

## [0.79.0] - 2026-11-06

### Added
- modifier-here 0.1.0: `--here` runs the request in this session, no subagent.

## [0.60.0] - 2026-11-06

### Added

- `dev-console` 0.26.0: a home do foco (`g h`, `/home`, `GET /agent/focus`, `focus.sh`): o card em foco é o topo do Downstream (senão o topo do Upstream, nunca Todo nem Feito, na ordem do Kanban), com o custo que o Kanban dá a ele e o foco embutido; o app abre na home.

## [0.59.0] - 2026-11-06

### Added

- `kanban` 0.4.0: limite de WIP por etapa (`stage_limits`, Upstream 1 por padrão): `create`/`move` recusam com exit 4 e dizem quem ocupa; `--force` registra a exceção (`forced: true`). O cabeçalho da coluna no Quadro e o `list` mostram `Upstream 1/1`.

### Changed

- `kanban create` passa a criar em Todo (era Upstream).

## [0.58.0] - 2026-11-06

### Added

- `dev-console` 0.25.0: um domínio grande (Via, Zap) legível na janela do dono. O layout de ramos abre com uma raia inteira (a do último evento do diário, senão a do `HOME`) e as outras dobradas numa linha com nome e contagem, presos à esquerda; um clique (ou o número da raia) abre e dobra a anterior, `0` abre todas; nenhum rótulo abaixo de 16 px em 1140×1074.

### Fixed

- `dev-console` 0.25.0: `render_screens` mostra só a moldura do próprio produto, escalada ao popup, setas como texto, a lista dos passos e nada de SIMULADO em tela real; o layout de ramos com rótulos de 20 px, saltos desenhados pela ponta e a espinha do Human fora da estação do corretor.

## [0.57.0] - 2026-11-06

### Added

- `kanban` 0.3.0: ordem dos cards numa etapa (`top`, `rank`, `card.prioritized`; o topo é o card em foco), `rename`, a etapa `Todo` (backlog, não conta como dinheiro de Upstream) e o Quadro com o tempo subindo no navegador e atualizando sozinho quando o journal muda.

## [0.56.0] - 2026-11-06

### Added

- `bili` 0.8.0: `watch.py` lê os assuntos de cada vigia de um arquivo JSON (`CASA_BILI_WATCH_SUBJECTS_FILE`); sem o arquivo, o comportamento é o de antes. Com `test_watch.py`. (Reaplica o PR #10.)

## [0.55.0] - 2026-11-06

### Added

- `duplo-local-agents` 1.0.0: junta `herdr-agentes`, `herdr-mesa` e o `mux.sh` da `prime-agent` numa skill só, independente do multiplexador (herdr, tmux ou nenhum). Detalhe em `skills/duplo-local-agents/CHANGELOG.md`.
- `envless` 0.1.0: o segredo entra no comando pelo `envless exec`, nunca na conversa; `list` sem valores, `set` pelo stdin, `get` só com `--confirm`.
- `disky` 0.1.0: o diagnóstico de disco com o disky e a tabela de limpeza que o dono aprova antes de qualquer apagamento.
- `prime-agent` 0.4.0: ids TNN/HNN nos panes, `mux.sh fila` (o padrão para mandar) e a skill Python `mux`; o `mux.sh` passa a viver na `duplo-local-agents`.
- `pi` 0.3.3: `contas-tokens.sh` (os tokens do `setup-token` do envless na extensão `pi-claude-accounts`, principal primeiro).

### Removed

- `herdr-agentes` e `herdr-mesa` (e o `mesa.sh`, o `cartao.py`); o que a `herdr-agentes` ganhou na main desde o #5 foi para a `duplo-local-agents`.

(Reaplica os PRs #2, #3, #4 e #5 sobre a main.)

## [0.54.0] - 2026-11-06

### Added

- `dev-console` 0.24.0: `devc`, a CLI do próprio app, uma porta só para agentes e pessoas (`domains`, `show`, `events --tail`, `focus`, `open`, `shot`, `start`, `stop`; `--json`).

## [0.53.0] - 2026-11-06

### Added

- `backbrief` 0.17.0: `workspace.cleaned` e `tasks.sh clean --task <id>`: o merge só fecha a tarefa (status `done`) quando o worktree, a branch remota e o PR sumiram de verdade; as branches levam o id da tarefa (`task/<id8>-<slug>`, `tasks.sh branch`).
- `kanban` 0.2.0: limite de WIP por repo (`kanban.sh wip`, 3 PRs abertos, sai com 3) e a varredura diária (`kanban.sh sweep --hours 48 [--apply]`) com os eventos `item.aged` e `decision.requested`; o repo que faz deploy (viacorretor) só pede decisão.
- `hermes` 0.2.2: `spawn hacker --repo` recusa (saída 6) no limite de WIP.

## [0.52.0] - 2026-11-06

### Added

- `wiki-smith` 0.1.3: a seção "Absorbing a public skill" (avaliar, ler inteira, trazer só o novo com a origem e o id de instalação) e a linha de roteamento (reaplica o PR #15).

## [0.51.0] - 2026-11-06

### Added

- `design` 0.2.0: o design-playground (MCP e Web) mora na skill, em `playground/`, com herança, patches, modificadores e o log de carga, ao estilo do mod system do RimWorld; a Web leva a guarda de Host/Origin do `/mcp` (reaplica o PR #14).

## [0.50.0] - 2026-11-06

### Added

- `postmortem` 0.1.0: do problema relatado à decisão que o causou, reconstruída dos eventos do NATS (`scripts/timeline.sh`), com modelo de postmortem blameless (reaplica o PR #9).

## [0.49.0] - 2026-11-06

### Added

- `faceless-art` 0.1.0 (a arte sem rosto pelo Codex) e `linkedin-publish` 0.1.1 (publicar, editar e conferir o post pelo Safari, com `li.sh`); reaplica o PR #13.

## [0.48.0] - 2026-11-06

### Added

- `copywriting` 0.2.3: a skill de escrita do Gabriel (post do LinkedIn, Diário e artigo), com `scripts/metricas.sh` e o template do artigo (reaplica o PR #12).

## [0.47.0] - 2026-11-06

### Added

- `fluid-voice-auto-fix` 0.1.0: acha no que o usuário ditou as palavras que o FluidVoice erra e as põe no dicionário e no vocabulário, com backup, diff e guarda da ordem das regras (reaplica o PR #8).

## [0.46.0] - 2026-11-06

### Added

- `linear` 0.3.1: `mesa.agent.decision.made` em toda decisão de criar, dividir ou juntar cartões; cada subcartão vale por si (reaplica o PR #11 sobre os dois níveis que o main já tinha).

## [0.45.0] - 2026-11-06

### Added

- `kanban` 0.1.0: o quadro do dono no dev-console. Cada card é um trabalho ligado a um domínio do console, numa etapa (Upstream, Downstream, Feito); `kanban.sh` é o único escritor do diário (`create`, `move`) e lê o quadro (`list`, `show`, `money`). O dinheiro de cada card é o tempo do domínio dele enquanto esteve em Upstream, lido do diário de custos e pelo preço da hora do centro de custo; a faixa no topo do Quadro soma hoje, a semana (desde segunda) e o mês, e sobe a cada segundo enquanto o relógio roda.
- `dev-console` 0.23.0: `/` abre o Quadro do Kanban (o `CONSOLE_HOME` do projeto), senão o primeiro domínio como antes; um módulo pode ser um widget do projeto (`MODULE_WIDGETS`), e um clique numa entidade dele abre a barra lateral do console com as partes do projeto (`ENTITY_PARTS`); a barra de dinheiro avisa a página ao ligar e desligar o relógio.

## [0.44.1] - 2026-11-06

### Changed

- `dev-console` 0.22.1: o desenho de ramos (branch) é o padrão de todo domínio; raios/metro só pela tecla `L`, sem botão (o nome aparece num aviso rápido).

## [0.44.0] - 2026-11-06

### Added

- `dev-console` 0.22.0: API para agentes e gravador de voo. O DevConsole.app grava uma linha JSON por navegação (os últimos 20, com PNG feito pelo próprio app); rotas `/agent/now`, `/agent/history`, `/agent/shot` e `scripts/agent.sh`.

## [0.43.2] - 2026-11-06

### Changed

- `hermes` 0.2.1 e `backbrief` 0.16.3: o perfil de design se chama `hipster` (hacker, hustler, hipster); UI vai a ele, no Opus com esforço máximo.
- Lições da revisão automática em brainstorm, delegate-and-review, dev-console, diff-review, herdr-agentes e skill-smith.

## [0.43.1] - 2026-11-06

### Changed

- `hermes` 0.2.0: código vai ao perfil `hacker`.
- `backbrief` 0.16.2: a opção de implementar já diz o perfil (`Implementar com hacker (Hermes)`).

## [0.43.0] - 2026-11-06

### Added

- `hermes` 0.1.0: o Claude Code e o pi comandam os perfis locais do Hermes como agentes com memória persistente (`scripts/hermes.sh`: list, spawn, resume, sessions, read, memory, route, dm); trava por perfil, recusa de provedor por token, tabela de roteamento.

### Changed

- `backbrief` 0.16.1: o passo 9 manda a tarefa que tem perfil dono para `hermes.sh spawn`, registrada como `task.executed` com `harness: hermes`.

## [0.42.0] - 2026-11-06

### Added

- `seo-audit` 0.1.0: o SEO de uma página e dos sitemaps, lido do HTML sem JavaScript (`audit.sh`, `sitemap.sh`), com o canonical que volta por redirecionamento.
- `keyword-ideas` 0.1.0: o autocompletar do Google em pt-BR (`suggest.sh`) e as oportunidades do Search Console (`opportunities.sh`, pela skill `search-console`).

## [0.41.0] - 2026-11-06

### Added

- `search-console` 0.1.0: o Google Search Console lido por uma conta de serviço só de leitura (`scripts/gsc.sh`: sites, consultas e páginas por período, sitemaps, inspeção de URL); primeiro uso no perfil `via-ads` do Hermes.

## [0.40.0] - 2026-11-06

### Added

- `brainstorm` 0.1.0: pensar junto quando a ideia ainda está aberta, antes do backbrief. Double Diamond com Cynefin, iceberg, laço causal (desenhado no dev-console, domínio Brainstorm) e pontos de alavanca de Meadows; diário em `~/.local/share/brainstorm/events.jsonl`; README com os créditos de cada fonte.

## [0.39.1] - 2026-11-06

### Fixed

- `dev-console` 0.21.1: ⌘K/⌘P abrem a paleta nativa (o web view engolia as teclas).

## [0.39.0] - 2026-11-06

### Added

- `dev-console` 0.21.0: status line nativa no DevConsole.app (▶/⏸, centro de custo, R$ de hoje, módulo); a página mantém o conteúdo e esconde a própria barra só dentro do app; `GET /api/status`.

## [0.38.0] - 2026-11-06

### Added

- `dev-console` 0.20.0: chrome nativo no DevConsole.app: a paleta de comandos (⌘K domínios, ⌘P módulos) é um painel flutuante do Swift com busca fuzzy; a página guarda o conteúdo e, dentro do app, desliga a própria paleta. `GET /api/palette`.

## [0.37.1] - 2026-11-06

### Changed

- tmux 0.1.1: ler o pane antes de mandar tecla; num agente vivo, nada de `/quit`.

## [0.37.0] - 2026-11-06

### Added

- `dev-console` 0.19.0: `scripts/check.sh`, a checagem headless de uma página do console com o Chrome instalado, para o Claude Code e o pi (retro da sessão).

## [0.36.0] - 2026-11-06

### Changed

- `dev-console` 0.18.0: a barra do módulo Agents no padrão do console, ferramentas com o comando ou o arquivo, sessões pelo nome do `/rename`; o console carrega os próprios módulos pelo caminho (uma instância de teste rodava o `console_agents.py` de outro checkout).

## [0.35.0] - 2026-11-06

### Changed

- `backbrief` 0.16.0: o verify de algo que roda sobe numa porta de teste e chama o que mudou; um merge com conflito resolvido à mão passa pelo `diff-review` e roda antes do merge final.

## [0.34.0] - 2026-11-06

### Changed

- `backbrief` 0.15.0: no Claude Code, a execução confirmada roda num subagente nativo (Agent, Sonnet, numa worktree); o pi fica para fora do Claude Code e para comparar modelos.

## [0.33.0] - 2026-11-06

### Added

- `dev-console` 0.17.0: o módulo Agents (`/agents`, no ⌘P): os prompts digitados no Claude Code e o log das sessões em tempo real (watcher + SSE), inclusive os que entram no meio de um turno; `TrustedHostMiddleware` (400 para outro Host), sem CORS.

## [0.32.0] - 2026-11-06

### Changed

- `task-understand` is now `backbrief` 0.14.0 (US Army backbrief; the Tasks domain keeps its name). Patch bumps: `advisor` 0.1.1, `cost-track` 0.3.2, `dev-console` 0.16.1, `skill-smith` 0.4.1.

## [0.31.0] - 2026-11-06

### Added

- `diff-review` 0.1.0: revisão de código de um diff local (worktree contra a base) com prompt próprio, pelo pi no plano flat (Sonnet na assinatura ou GLM); achados em eventos JSONL; `task-understand` 0.13.4 a chama entre verify e deliver.

## [0.30.0] - 2026-11-06

### Added

- `dev-console` 0.13.0 a 0.16.0: segunda instância sem live reload; `console.sh`, a porta dos agentes (instâncias num journal, domínios, estado em JSON, url, actions, janela por dono); o Playground passa a ser do próprio console (sem iframe e sem chat; o servidor do design-playground portado para Python, dados em `~/.local/state/dev-console/playground/`).

## [0.29.0] - 2026-11-06

### Added

- `tmux` 0.1.0: scripts para ler, listar, mandar texto com segurança (inclusive `/comando` numa TUI), abrir e esperar em panes e janelas; `skill-smith` 0.4.0: toda skill tem `README.md` e `CHANGELOG.md` próprios.

## [0.28.0] - 2026-11-06

### Added

- `advisor` 0.1.0: o agente principal (o Bili no Sonnet) consulta uma segunda opinião (Opus) nos pontos em que o julgamento pesa; contexto compartilhado em `~/.local/share/advisor/` e um diário de decisões que ensina quando vale chamar.

## [0.27.0] - 2026-11-06

### Added

- `retro` 0.1.1, `cost-track` 0.3.1, `task-understand` 0.13.3: `scripts/retro.sh`, `costs.sh` and `tasks.sh` as the entry point of each CLI (the uv Python script stays the implementation).

### Changed

- `skill-smith` 0.3.1: Step 3 says the `.sh` is the interface every harness calls.

## [0.26.0] - 2026-11-06

### Added

- `retro` 0.1.0: the `/retro` skill, an after-action review of the session that turns the owner's corrections into rules for the right skills (he picks, one PR applies); `retro.py` CLI with `emit`, `lessons`, `rejected-rules` and `scan`.

## [0.25.0] - 2026-11-06

### Added

- `dev-console` 0.11.0: ⌘P switches the module (Domain, the project's tabs, Playground) on every page, ⌘K lists domains only; a bottom status line (domain · module · money) replaces the tab bar, on a domain page and on the Playground too; the native app owns ⌘P and ⌘K in a menu so no print panel opens.

### Fixed

- `dev-console`: loading `/playground` no longer ends a running stretch (only the first trusted gesture posts `enter`); `?embed=money` shows the bar.
- `task-understand` 0.13.2 (patch): the Task Results tab no longer 500s on a journal with `method: "pi"`.

## [0.24.0] - 2026-11-06

### Added

- `dev-console` 0.10.0: the Playground mode (`/playground`), the design-playground's canvas composed in an iframe beside
  Domain and tied to no domain, with its own cost center on the money bar and a fixed last row in ⌘K.

## [0.23.0] - 2026-11-06

### Added

- `dev-console` 0.9.0: `LAYOUT = "branch"`, the graph as a git graph read left to right (the Human at the top left, each
  category a lane, a lane born where its transition comes from, a merge as a dashed edge); funnel-stage columns from
  `STAGES` / `STAGE_ORDER` / `STAGE_LABELS`; `L` and a corner button toggle branch and metro on any domain.

## [0.22.0] - 2026-11-05

### Added

- `dev-console` 0.7.0: `LAYOUT = "metro"`, the graph of a big domain drawn as a Tokyo Metro map (octilinear lines from
  the clock, stations in `EVENTS` order, labels that never overlap); a big domain uses it, the order lives only in `EVENTS`.

## [0.21.0] - 2026-11-05

### Added

- `dev-console` 0.6.0: the money bar in the toolbar of every domain with a cost center (spent today ticking, the day
  budget for a client, the rate, ▶ / ⏸, a popover with today per center); the clock writes Costs events.
- `cost-track` 0.3.0: `scripts/costs.py` is the only writer of the Costs journal (`emit` CLI plus the module API the
  console imports); tests in `scripts/test_costs.py`.

### Removed

- `timer` (the menu bar countdown): the clock now lives in the dev-console's money bar and everything lands in the
  Costs journal.

## [0.20.0] - 2026-11-05

### Added

- `cost-track` 0.1.0 (design stage): the Costs domain, everything has a cost; cost centers, worth and time
  entries, drawn in the dev-console.

## [0.19.0] - 2026-11-05

### Added

- `dev-console` 0.5.0: a native macOS window the agent drives. `DevConsole.app` shows the console page in a `WKWebView` (docked at two thirds of the screen, title follows the page); `scripts/window.sh` is the only writer of `command.json`, the app the only writer of `state.json` (url, title, size, last command and result, messages the page posts through the bridge). The headless browser stays how an agent reads the DOM.

## [0.18.0] - 2026-11-05

### Changed

- `task-understand` 0.13.0: `verify` (independent verification, IV&V, in a fresh pi context), `deliver` and the PR
  decision (`merge`, `request-review`) become real commands; a failed verification or a requested review sends the
  task back to execution; the dev-console shows the verification and the delivery under the run.

## [0.16.0] - 2026-11-05

### Added

- `timer` 0.1.0: a countdown in the Mac menu bar driven by the agent through `scripts/timer.sh`; the StatusTimer app only displays the state file.
- `timer` 0.2.0: the menu bar looks like the macOS clock (Nerd Font timer icon, monospaced menu bar font, label only in the tooltip).

## [0.17.0] - 2026-11-05

### Changed

- `task-understand` 0.11.0: pi é o executor, só nos planos flat — a assinatura Claude da mukutu (claude-bridge) e
  o GLM Coding Plan (zai; a chave lida de `~/glm_token` só no env do filho). A mesma tarefa pode rodar em paralelo
  em vários modelos, cada um no seu worktree (`task/<id8>-<model>`), com um `task.executed` por modelo (model,
  provider, plano, exit code, duração, turnos, tokens, custo); OpenRouter e provedores por token são recusados.
  O pedido de confirmação passa a ser: implementar com o modelo recomendado, recomendado + um modelo de teste em
  paralelo, só confirmar, não ficou bom — e o teach-back na pergunta é blocos curtos ou lista numerada, com a
  pergunta ("Bate?") sozinha na última linha.

## [0.15.0] - 2026-11-05

### Changed

- `dev-console`, laid out for two thirds of a MacBook screen (1140 × 1000): right menu at a third of the window,
  the graph header in one line (reading key behind "?"), "N widgets" as the sidebar subtitle, each start's own
  events kept on its side of the Human; Task Results opens on the domain's newest task.

### Added

- `dev-console`: `/domain/<slug>/media?f=<path>` serves the files a domain keeps (`MEDIA`), never outside it.
- `task-understand` 0.10.0: the real ExecutionResult with mermaid and pictures; Task Results filtered by domain.

## [0.14.0] - 2026-11-05

### Changed

- `task-understand` 0.9.0: the confirmation asks Confirm and implement (with the method), Just confirm, or Not good.

## [0.13.0] - 2026-11-05

### Fixed

- `dev-console`: the Task Results tab takes the whole width (no entity rail, no JSON inspector); tab labels keep their
  spaces; report lists have one marker at the body's size; the result names the selected task.

### Changed

- `task-understand` 0.8.0: the teach-back asks for the confirmation with the harness's ask tool.

## [0.12.0] - 2026-11-05

### Added

- `dev-console`: Task Results, the second fixed tab of every domain (when the tasks domain is loaded): the tasks
  executed for that domain, composed from the tasks domain's widget.
- `task-understand` 0.7.0: a task names its domain.

## [0.11.0] - 2026-11-05

### Added

- `task-understand` 0.6.0: typed value objects for the execution and the Task.Executed widgets.
- `dev-console`: the Code part lists the domain's value objects and enums in subsections (the entity and the event's
  value object open, other value objects then types closed; each remembered in localStorage); the widget list is a
  nested tree (`fn.parts`); widgets that come from real sources hide REAL | SIMULADO; mermaid is available to widgets;
  every widget starts with a title; screens are drawn from the code's value objects (contract).

## [0.10.0] - 2026-11-05

### Added

- `task-understand` 0.5.1: the whole process implemented (learnings used, feedback with downscore, three fixed
  versioned styles, options, choice with score, default style = highest score); the default executor follows the
  claude-code skill (max turns, allowed tools, own worktree, JSON output). Implemented by the executor itself, the
  first real run of `tasks.py execute`.

## [0.9.0] - 2026-11-05

### Added

- `task-understand` 0.4.0: configurable executor (default Claude Code on mukutu with Sonnet) and the draft of the
  feedback, learning and style process.
- `dev-console`: the right menu opens with Description (from the code comment of each command); `TRANSITIONS` may
  name the command of each edge; several commands may record one event; domains join through
  `~/.local/state/dev-console/domains.txt` with no restart.

## [0.8.0] - 2026-11-05

### Added

- `task-understand` 0.3.0 (design stage): one command runs the Tasks domain's workflow, Task.Explained then
  Understanding.TaughtBack (teach-back), with a global journal `~/.local/share/tasks/events.jsonl`, the Input
  contract in `scripts/input.py` and the Task Skill widget in the dev-console.

## [0.7.0] - 2026-11-05

### Changed

- `dev-console` 0.4.0: its own domain is Human → Domain.Designed or Domain.Imported → Domain.Updated (the hub, `HUB`), which links Event.Updated, Widget.Updated and Tab.Updated; Action left the domain. The journal is an editable JSONL (`console_domain.jsonl`).
- `dev-console`: the graph uses fCoSE with the Human pinned in the centre; the tab bar shows each domain's `TABS` (Domain fixed), with Nerd Font icons.
- `dev-console`: the right menu is expandable parts (Widgets, Code, JSON, Observability), open at first, closed ones remembered per node in localStorage; Code is a short pseudo-code of the event's context.
- `dev-console`: widgets compose the real components (WidgetList, Toolbar, Code, DomainView, StateGraph, RightMenu); a WidgetList row opens on click, Enter or Space; the Domain's widgets hang on Domain.Updated only.
- `dev-console`: the server runs in a herdr `services` tab.

## [0.6.0] - 2026-11-05

### Added

- `dev-console` 0.3.0: many domains in one console, each in its own context at `/domain/<slug>` (repeat `--project`).
- `dev-console` describes itself: its own domain is the development process (Human → Domain.Designed or Domain.Imported; widgets designed, approved, connected; actions proposed, simulated, ran), journal derived from code with `ast`; DomainView and StateGraph widgets embed the console's own Domain tab (`?embed=1`, `?embed=graph`).
- `INITIAL` (several starting events), `DOMAIN_DRAFT` (a dummy `<SOURCE>_draft.py` written once when missing) and `fn.fake` (design widgets render before their event exists) in the project contract.

### Changed

- `dev-console`: Domain is the first tab and reuses the Model graph (`drawGraph`), sidebar and popup.
- `tensions`: action links use the console's `BASE` (`/domain/<slug>`).

## [0.5.0] - 2026-11-05

### Added

- `dev-console` 0.1.0: one-file FastHTML console for any event-sourced project in development (`--project`): the state machine of commands and events drawn from the code, entities, journal, and widgets per event in a contextual sidebar and a centred popup.

### Changed

- `tensions` 0.2.0: `EVENTS` is `{category: {command: event}}` and smaller; `created_at` in the projection; the project file `dev_console_project.py` hooks it into the dev-console.

## [0.4.0] - 2026-11-04

### Added

- `tensions` 0.1.0: shared append-only JSONL journal for meaningful domain events. One Python stdlib script, one SKILL.md and optional scripts/justfile recipes, without NATS, MCP, or Python packages.
 
## [0.3.0] - 2026-11-04

### Added

- `design` 0.1.0: telas no design-playground com os widgets reais do produto. O wrapper sai do código do produto (`scripts/wrapper.sh build|conferir|pastas|foto`) e o agente vira o motor do MCP (`scripts/motor.sh claude|pi|http`). O que é de cada produto (a referência, a receita, os wrappers e os rascunhos) mora fora do repo, em `DESIGN_PRODUTOS`. Chaves novas no `casa.env.example`: `DP_DIR`, `DP_URL`, `DP_URL_REMOTA`, `DP_TOKEN`, `DESIGN_PRODUTOS` e `PRODUTO_<P>_REPO`/`_REMOTO`.

## [0.1.2] - 2026-11-03

### Changed

- `skill-smith`: as ações de um skill são scripts `.sh`, não um servidor MCP.

## [0.1.1] - 2026-11-03

### Changed

- `sync` 0.1.1: o trabalho de outra sessão também é commitado, em commit separado.

## [0.1.0] - 2026-11-03

### Added

- O plugin `biliboss-skills` e o marketplace `biliboss`, no molde do mattpocock/skills.
- `wiki-smith` (de biliboss/wiki-smith, 0.1.2), `skill-smith` (de biliboss/skill-smith), `lp-draft`, `sync` (do biliboss) e o novo `setup-biliboss`.
