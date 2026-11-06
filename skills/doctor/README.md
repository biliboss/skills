# doctor

O protocolo da casa para dizer se um projeto ou ferramenta está saudável e pronto para trabalhar: cinco dimensões
(ambiente, arquitetura, comportamento, observabilidade, agente), achados só de leitura, cada um com o comando que
conserta. `doctor()` pergunta "o sistema está saudável?"; `test()` pergunta "o comportamento está certo?". Regras e
formato: [SKILL.md](SKILL.md).

| Comando | O que faz |
|---|---|
| `scripts/doctor.py [repo]` | doctor genérico de qualquer repo; descobre e junta o doctor do projeto |
| `scripts/doctor.py [repo] --run-tests --timeout 60` | também roda o comando de teste detectado |
| `scripts/doctor.py [repo] --json --verbose` | um objeto JSON por achado, inclusive os `ok` |
| `scripts/test.sh` | 14 checks em dois repos temporários (um saudável, um quebrado) |

Exemplo de linha: `drift environment python-lock: pyproject.toml is newer than uv.lock -> uv lock`.
Saída: `0` saudável, `1` drift ou falha, `2` o doctor não rodou. Histórico: [CHANGELOG.md](CHANGELOG.md).

## Créditos e referências

| Base | Autor | Ideia tomada | Link | Verificado |
|---|---|---|---|---|
| `brew doctor` | Homebrew | um comando que lista problemas prováveis e sai com código ≠ 0 | https://docs.brew.sh/Manpage#doctor-dr-options-diagnostic_check- | `brew doctor --help` local |
| `flutter doctor` | Flutter | diagnóstico do ambiente com a correção sugerida ao lado | https://docs.flutter.dev/reference/flutter-cli | sim (tabela de comandos) |
| Probes de liveness/readiness | Kubernetes | "vivo" e "pronto para trabalhar" são perguntas diferentes | https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/ | não aberto nesta sessão |
| Health Check API | Chris Richardson, microservices.io | o serviço expõe o próprio estado de saúde | https://microservices.io/patterns/observability/health-check-api.html | não aberto nesta sessão |
| Detecção de drift | Terraform (HashiCorp) | o real deixou de bater com o declarado vira um status próprio | https://developer.hashicorp.com/terraform/tutorials/state/resource-drift | não aberto nesta sessão |
| Doctor driven development | Gabriel Fonseca | o doctor vem antes do teste, e diagnostica também o agente | (ideia do dono, 06/11/2026) | não se aplica |
