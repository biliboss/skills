# Gates copiáveis

Modelo de gates para o `gate.sh` e o `merge.sh`: um `.pre-commit-config.yaml` lido pelo [prek](https://prek.j178.dev), com hooks locais (`language: system`, nada é baixado) que nunca modificam arquivo.

| Estágio | Python | TypeScript |
|---|---|---|
| pre-commit | `ruff format --check`, `ruff check` (C901 max 10, TID251), pyright, gitleaks | biome (cognitiva 15, noRestrictedImports), tsc incremental, gitleaks |
| pre-push | import-linter, vulture, jscpd | dependency-cruiser, knip, jscpd |

## Como copiar

1. Na raiz do projeto: `mkdir .gates && cp ratchet.py .gates/`, e copie o conteúdo de `python/` ou de `typescript/` (inclusive os arquivos que começam com ponto).
2. Python: cole `pyproject.gates.toml` no `pyproject.toml` e troque `meuprojeto` em `.importlinter` pelo pacote raiz.
3. Ajuste `banned-api` (Python) ou `noRestrictedImports` (biome) e os caminhos de `.dependency-cruiser.cjs` e `knip.json` ao projeto.
4. Ferramentas no PATH: `prek`, `ruff`, `pyright`, `gitleaks`, `jscpd` (Python); `biome`, `tsc`, `gitleaks`, `knip`, `jscpd` (TypeScript). `vulture` e `import-linter` rodam por `uvx`, e o `dependency-cruiser` por `npx`, sem instalar global.
5. Legado: `python3 .gates/ratchet.py --name <nome> --baseline .gates-baseline.json --update -- <o mesmo comando do hook>` para cada gate com catraca (`ruff`, `pyright`, `import-linter`, `vulture`, `jscpd`; `biome`, `tsc`, `depcruise`, `knip`). Commite `.gates-baseline.json`. Para formatação legada, rode `ruff format` uma vez, porque o `ruff format --check` não tem catraca.
6. Rodar: `prek run --stage pre-commit --files <arquivos>` e `prek run --stage pre-push --files <arquivos>` (os arquivos podem estar sem commit).

## A catraca

`ratchet.py --name X --baseline .gates-baseline.json [--update] [--ignore REGEX] -- <comando>` normaliza cada linha de saída tirando números de linha e coluna, conta por linha normalizada e reprova só o que aumentou contra a linha de base de X, mostrando o que piorou. Comando com saída 0 passa. Detalhes no `--help`.

- Saída por ferramenta: `ruff check --quiet --output-format=concise` (uma linha por achado), `biome ci --reporter=github`, `tsc --pretty false`, `knip --reporter compact`; pyright, vulture e import-linter já saem em linhas.
- Limite: a mensagem entra na linha normalizada. Se ela traz um número que muda (a complexidade de `11 > 10` para `12 > 10`), o achado conta como novo; é intencional, porque uma função legada que piorou deve reprovar.
- O gitleaks nunca passa pela catraca. Ele roda como `gitleaks dir`, que lê a pasta e por isso vê arquivo não commitado (confirmado na prática); `gitleaks git` só veria commits.

## O que não foi exercitado de verdade

Ver o CHANGELOG da skill: o TypeScript foi exercitado com biome e tsc (e knip, jscpd e depcruise sem violação real); a combinação inteira com um projeto TypeScript de verdade, não.
