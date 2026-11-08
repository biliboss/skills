# Doctor

Diagnose project readiness with the existing five-dimension generic doctor, or execute `.doctor.yaml` capability
contracts with explicit failure evidence. [Instructions](SKILL.md) · [Changelog](CHANGELOG.md).

| Command | Purpose |
| --- | --- |
| `scripts/doctor.py [repo]` | Generic read-only readiness diagnosis |
| `scripts/doctor --root [repo]` | Fast capability checks |
| `scripts/doctor runtime` | Runtime checks |
| `scripts/doctor journey` | User journeys |
| `scripts/doctor --all --json` | Full capability report |
| `scripts/doctor --changed --base origin/main` | Changed paths, fast and runtime |
| `uv run --script scripts/test_contracts.py` | Isolated acceptance tests |
| `scripts/test.sh` | Generic doctor regression fixtures |

See [contract syntax and examples](references/contracts.md) for evidence recording and adapters.

## Créditos e referências

| Base | Autor | Ideia tomada | Link | Verificado |
|---|---|---|---|---|
| `brew doctor` | Homebrew | um comando que lista problemas prováveis e sai com código ≠ 0 | https://docs.brew.sh/Manpage#doctor-dr-options-diagnostic_check- | `brew doctor --help` local |
| `flutter doctor` | Flutter | diagnóstico do ambiente com a correção sugerida ao lado | https://docs.flutter.dev/reference/flutter-cli | sim (tabela de comandos) |
| Probes de liveness/readiness | Kubernetes | "vivo" e "pronto para trabalhar" são perguntas diferentes | https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/ | não aberto nesta sessão |
| Health Check API | Chris Richardson, microservices.io | o serviço expõe o próprio estado de saúde | https://microservices.io/patterns/observability/health-check-api.html | não aberto nesta sessão |
| Detecção de drift | Terraform (HashiCorp) | o real deixou de bater com o declarado vira um status próprio | https://developer.hashicorp.com/terraform/tutorials/state/resource-drift | não aberto nesta sessão |
| Doctor driven development | Gabriel Fonseca | o doctor vem antes do teste, e diagnostica também o agente | (ideia do dono, 06/11/2026) | não se aplica |
