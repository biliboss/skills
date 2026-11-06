# Changelog

Todas as mudanças do skill `bili`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-11-04

### Added
- `CASA_BILI_GRILL=ask|interview|plain` (padrão `ask`): o modo do grill do passo 0 (AskUserQuestion, a skill `interview` ou texto no chat). Documentado no `casa.env.example`.
- Regras iguais nos três modos: escrever para si as decisões que faltam e a ordem antes de perguntar; uma pergunta binária por vez; cada resposta escolhe o próximo ramo; parar quando o pedido bastar; pedido já claro faz zero perguntas e diz isso.

### Changed
- O método do grill vem da skill `grilling` (grill-me): a skill manda carregá-la, sem copiar o texto; sem ela instalada, cai no modo `plain` com as mesmas regras.

## [0.6.0] - 2026-11-04

### Added
- Três rotas escolhidas por configuração (`CASA_BILI_ROTA=local|remoto|linear`, padrão `local`) e uma porta só, `scripts/bili.sh` (`pedir`, `esperar`, `ler`, `rota [local|remoto|linear]`). `rota` mostra a rota e, com argumento, grava no `casa.env`.
- `scripts/nats-bili.sh`: as rotas local e remoto publicam `mesa.agent.request.received` (gramática do libs/local-events) com a CLI `nats` e leem a resposta `mesa.agent.request.answered` pelo `trace_id`.
- `BILI_SECO=1` no `linear-bili.sh pedir`: imprime a menção exata, sem comentar.
- `casa.env.example`: `CASA_BILI_ROTA` e as URLs, streams, usuário e arquivo de senha do NATS.

### Changed
- O `linear-bili.sh` passa a ser a rota `linear`, chamada pelo `bili.sh`. O grill binário continua. O passo 3 do passo 0 manda pela rota, não mais por digitar na fila do pane.

## [0.5.0] - 2026-11-04

### Added
- Passo 0, "No Mac: grill primeiro, depois o Bili local": todo pedido do dono no Mac vai ao Bili local, depois do grill com a ferramenta AskUserQuestion, uma pergunta binária por vez (a recomendada primeiro), num arquivo e pela fila do `mux.sh`.
- O monitor do NATS: `scripts/watch.py` (uv), uma linha por evento que pede atenção humana (asks, errors, panes, cycle, llm, routes), armado pela ferramenta Monitor e rearmado quando expira.

### Changed
- O Bili da VPS passa a ser pedido pelo Bili local; a descrição diz isso.

## [0.4.4] - 2026-11-04

### Fixed
- Uma sessão por cartão: delegar já abre a sessão do Bili, e uma menção depois abre uma segunda no mesmo cartão. Cartão novo vai sem delegado, com o pedido numa menção só; cartão já delegado leva o contexto no corpo, sem nova menção.

## [0.4.3] - 2026-11-04

### Changed
- Os valores da casa (hosts, usuários, caminhos, contas, ids do Linear) vêm do `casa.env` (`~/.config/biliboss/casa.env`, modelo em `casa.env.example`); a skill veio para o repo público `biliboss/skills`, sem eles no texto.
- O `linear-bili.sh` usa o `dono.sh` da skill `linear`.

## [0.4.2] - 2026-11-03

### Added
- Conferir no stream ENTRADA que o pedido entrou; se a entrega se perdeu, marcar de novo.

## [0.4.1] - 2026-11-03

### Fixed
- A descrição sem `: ` solto, que o pi lia como YAML inválido.

## [0.4.0] - 2026-11-03

### Changed

- O canal com o Bili é o Linear: o pedido é uma menção a ele num cartão (a sessão de agente: duplo-server, NATS, Bili), e a resposta volta no mesmo cartão. O Mattermost foi desligado.

### Added

- `scripts/linear-bili.sh` (`pedir`, `esperar`, `ler`), sobre o `dono.sh` da skill `linear`.

### Removed

- O privado do Mattermost; o `scripts/mm.sh` só avisa que ele está desligado.

## [0.3.1] - 2026-11-03

### Changed

- O `mm.sh esperar` acha a resposta em qualquer canal: o Bili responde no canal do assunto marcando o dono.

## [0.3.0] - 2026-11-03

### Changed

- O privado do Mattermost é o único canal: nunca falar com o Bili direto (duplo MCP, API do Hermes, SSH). A memória e o andamento viram perguntas no privado.

### Removed

- A leitura da memória pelos recursos `duplo://` do duplo-mcp.

## [0.2.1] - 2026-11-03

### Added

- O `mm.sh esperar` mostra o tempo de ciclo (`— ciclo: N s`), do `create_at` da mensagem à primeira resposta do Bili.

## [0.2.0] - 2026-11-03

### Changed

- O canal é o privado dono↔Bili no Mattermost, como manda a regra "pedido novo entra pelo privado do Bili". O `duplo_ask` sai dos pedidos; o duplo MCP fica para ler os recursos (`duplo://perfil`, `duplo://memoria/inbox`).

### Added

- `scripts/mm.sh`: `enviar`, `esperar` (a primeira resposta do Bili desde um `create_at`) e `ler`, pela API do Mattermost, como o usuário do dono, com o token copiado pelo Ansible.

## [0.1.0] - 2026-11-03

### Added

- Falar com o Bili pelo `duplo_ask` no `mcpc` (`@duplo-bili`): conferir a sessão, perguntar (na linha ou por arquivo com `jq`), continuar pela `conversa`, pedir trabalho em segundo plano, acompanhar e ler os recursos `duplo://`.
- As armadilhas: `--timeout 600`, o turno longo que estoura o prazo do servidor, os clones do Bili atrás do `origin` (push e hash antes de pedir), a VPS sem sudo nem Docker para ele (o Ansible roda do Mac) e os hooks do Bash.
