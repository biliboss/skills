# Changelog

## [0.1.0] - 2026-11-06

### Added
- `auth.sh` (setup, add, grant, revoke, login, list, aliases, check, run, remove) com a lógica em `auth.py` (uv).
- Provedor Google pelo `gws`: uma pasta 0700 por conta, o cliente OAuth só no envless.
- Perfis: `grant`/`revoke`, e `run`/`check`/`login` recusam conta não liberada ao perfil.
- Domínio Auth no dev-console (cinco eventos, widget Contas) e diário em `~/.local/share/auth/events.jsonl`.
- `gcal` como apelido fino de `auth.sh run`.
