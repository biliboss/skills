# Changelog

Todas as mudanças do skill `pi`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-11-04

### Changed
- O `pi-claude.sh` usa o `git-agente.gitconfig` (e o `gh-agente`) da pasta da conta, se existirem: o pi commita e dá push como o bot do app, como as sessões do Claude Code (skill `git-agente`).

## [0.2.2] - 2026-11-04

### Changed
- Os valores da casa (hosts, usuários, caminhos, contas, ids do Linear) vêm do `casa.env` (`~/.config/biliboss/casa.env`, modelo em `casa.env.example`); a skill veio para o repo público `biliboss/skills`, sem eles no texto.
- O `ligar-skills.sh` lê só o `plugin.json` do repo `biliboss/skills`.

## [0.2.1] - 2026-11-03

### Added

- O `/goal` fica com o `@narumitw/pi-goal` (o auditor do `pi-goal-x` não fecha pelo bridge) e como testar uma extensão isolada com `-ne -e`.

## [0.2.0] - 2026-11-03

### Added

- `ligar-skills.sh`: as skills dos dois plugins no pi, como links lidos do `plugin.json`; a que sai do plugin vai para `~/.pi/agent/skills-desligadas/`.

## [0.1.0] - 2026-11-03

### Added

- O skill `pi`: rodar o pi.dev no Mac com as duas contas do Claude pela assinatura (`pi-claude-bridge`, a conta pelo `CLAUDE_CONFIG_DIR`).
- `atualizar.sh [mac|vps|tudo]`: todo pi na versão mais nova (Mac, o root da VPS pelo pnpm, os usuários extras da VPS), com as extensões e os catálogos, e a conferência dos logins OAuth do root.
- Os scripts: `pi-claude.sh` (roda o pi com a conta principal ou a secundária), `contas.sh` (que conta tem cada pasta, e `--teste`), `instalar.sh` (o pi e o bridge prontos, os modelos) e `vps.sh` (como o pi da VPS chega aos provedores, sem credencial).
