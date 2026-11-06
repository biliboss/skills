# Changelog

Todas as mudanças do skill `linear`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-11-06

### Added
- `mesa.agent.decision.made` em toda decisão de criar, dividir ou juntar cartões, e a regra de que cada subcartão vale por si e abre uma sessão (do PR #11, sobre os dois níveis que o main já tinha).

## [0.2.2] - 2026-11-04

### Fixed
- Uma sessão do Bili por cartão: delegar já abre a sessão dele; para pedir com contexto, cartão sem delegado e uma menção só (skill `bili`).

## [0.2.1] - 2026-11-04

### Changed
- Os valores da casa (hosts, usuários, caminhos, contas, ids do Linear) vêm do `casa.env` (`~/.config/biliboss/casa.env`, modelo em `casa.env.example`); a skill veio para o repo público `biliboss/skills`, sem eles no texto.
- O script da chave pessoal virou `dono.sh`; o `ids.sh` lê os ids do `casa.env`.

## [0.2.0] - 2026-11-03

### Added

- A seção "Onde a conversa mora": o marco não tem comentário, então leva um cartão de conversa (onde o Bili ouve) e um Doc com o resultado; o projeto conversa pelos updates.

## [0.1.0] - 2026-11-03

### Added

- O skill `linear`: ler um projeto antes de mexer, escrever o projeto, criar cartões de resultado, manter o marco honesto e postar updates na régua do Alquimista, com imagens.
- Os scripts:
  - `linear.sh`: o MCP oficial do Linear pelo `mcpc @linear`, o caminho principal, que avisa quando o login venceu;
  - `projeto.sh`: o retrato do projeto, com os marcos, o progresso, os cartões e o último update;
  - `upload.sh`: um arquivo para o Linear, devolvendo a URL para usar no Markdown;
  - `dono.sh`: a chave pessoal do dono, para ler a inbox e as preferências dele;
  - `lin.sh`: o GraphQL com a voz do app, o caminho reserva;
  - `ids.sh`: os ids fixos.
