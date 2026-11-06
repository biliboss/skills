# Changelog

Todas as mudanças do skill `disky`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

### Added
- O diagnóstico de disco com o disky 0.11: medir o livre pelo `df`, a foto (`scan`), onde mora o espaço com `--physical` (`dirs`, `top`, `ext`, `stats`, `query` em DuckDB), os candidatos em dry-run (`cleanup` sem `--apply`) conferidos um a um (existe hoje, repo limpo, ignorado pelo git, sem processo usando).
- A tabela (caminho, tamanho físico, o que é, se se regenera) em três grupos, regenerável, pergunte e do dono, aprovada pelo dono antes de qualquer apagamento; depois, `cleanup --apply --reversible` ou `rm` caminho a caminho, e o `df`, o `scan` e o `diff` de novo.
- As lições da limpeza do Mac: no APFS o tamanho apagado não é o liberado (clones e hardlinks), as cópias do Chrome em `code_sign_clone`, o peso das fotos do disky, a foto travada durante um `scan`, as worktrees de agente limpas e já no origin (`git worktree remove`), e o que é do dono quando o seguro não basta (VM de app, reinício, apps e fórmulas grandes).
