# Espelho do Linear num GitHub Project (mão única)

Use quando um time acompanha o projeto pelo GitHub Project da organização dele. O Linear é a fonte; o GitHub Project repete a definição, o status e os project updates. Nome da literatura: "one-way sync" / "mirror".

## Passos

1. **Achar o Project:** `GH_TOKEN=$(gh-app token <org>) gh project list --owner <org>`. Toda escrita vai como o app (gh-app), nunca como o dono. Se o token não lê Projects, falta a permissão `organization_projects` do app: isso é conta, espera o dono, com o clique exato.
2. **Definição para o time:** README e descrição curta do Project em português simples: o que é, o marco ativo, e que o Linear é a fonte.
3. **Script do espelho** (uv, PEP 723, no `scripts/` do perfil): lê os `projectUpdates(first:5)` do projeto no Linear e cria, para cada um novo, um status update no Project com `createProjectV2StatusUpdate` (`projectId`, `status`, `body`). Saúde → status: `onTrack`→`ON_TRACK`, `atRisk`→`AT_RISK`, `offTrack`→`OFF_TRACK`.
   - **Idempotente:** guarde o id do último update espelhado num arquivo de estado (ou chave de KV) e poste só os mais novos; rode duas vezes e confira que a segunda não repete.
   - Silencioso quando não há novidade: um cron `no_agent` entrega o stdout tal como sai, e stdout vazio não manda nada.
4. **Disparo:** um cronjob do Hermes sem modelo, a cada 15 min (`no_agent`, `script` = um `.sh` que faz `exec uv run -q --script <script>.py`). Escolha o cron enquanto os project updates do Linear não chegam ao NATS; quando chegarem, troque por gatilho no evento.
5. **Wiki:** a página do projeto diz a direção, o gatilho, a frequência e a origem do nome.
