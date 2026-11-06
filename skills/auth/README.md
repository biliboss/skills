# auth

A identidade segura do agente: quem ele é quando age em nome do dono, em vários provedores e contas, com vários perfis
(Hermes/Claude), cada um só com as contas que recebeu. É o "Nango em uma CLI" da casa: leve, sem servidor.

- **Segredos só no envless** (o cliente OAuth) e **no Keychain** (a chave que cifra o token); nada em código, log, diário ou repo.
- **O provedor renova o token**: Google pelo `gws`, a CLI oficial dele.
- **O setup é o produto**: `auth.sh setup` roda o que pode e o agente guia o resto com a ferramenta de perguntas.
- **Perfis**: `auth.sh grant <conta> --profile hacker`; `run` recusa a conta que o perfil não recebeu.

Regras do agente: [SKILL.md](SKILL.md). Histórico: [CHANGELOG.md](CHANGELOG.md).

## Como funciona

1. `auth.sh setup google` confere `envless` e `gws`, guarda o cliente OAuth no envless e grava o provedor.
2. `auth.sh add google pessoal voce@gmail.com --services calendar` registra a conta (pasta 0700 própria).
3. O dono roda `auth.sh login pessoal` (abre o navegador). `auth.sh check` confirma.
4. O agente roda `auth.sh run pessoal -- gws calendar +agenda --today`.

| Comando | Exemplo |
|---|---|
| `setup` | `auth.sh setup google --client-secret-json ~/Downloads/client_secret.json` |
| `add` | `auth.sh add google mukutu gabriel@mukutu.com.br --services calendar,gmail` |
| `grant` / `revoke` | `auth.sh grant mukutu --profile hacker` |
| `login` | `auth.sh login mukutu` |
| `list` / `aliases` | `auth.sh list --json` |
| `check` | `auth.sh check mukutu` |
| `run` | `auth.sh run mukutu -- gws gmail users getProfile --params '{"userId":"me"}'` |
| `remove` | `auth.sh remove mukutu --yes` (só o token local) |

Testes: `uv run --script scripts/test_auth.py` (gws e envless de mentira no PATH, HOME temporário).

## O domínio (dev-console, `/domain/auth`)

Entidade **Account** (provedor, apelido, e-mail, serviços, perfis, estado) e **Provider**. Cinco eventos, no estilo
*Updated* (um por elemento), diário `~/.local/share/auth/events.jsonl`:

| Evento | Quando |
|---|---|
| `provider.updated` | o cliente OAuth do provedor está no envless (só os nomes das chaves) |
| `account.updated` | a conta entrou ou mudou (serviços, só leitura, perfis com acesso) |
| `account.connected` | o login foi feito e a conta respondeu |
| `account.checked` | uma sonda: `ok` / `needs_login` / `broken`, e `expires_at` se o provedor diz |
| `account.disconnected` | o token local saiu; nada foi revogado |

Widget **Contas**: uma linha por conta, `provedor · apelido · e-mail · ● ok / ◆ precisa de login / ✗ quebrada`; bordô só
no que pede o dono.

## Por que é diferente

Dois eixos: **leveza** (sem servidor para operar) e **identidade segura para agentes** (várias contas, segredo fora da
conversa, perfil com permissão). O alvo é o quadrante de cima à direita. Posições são leitura nossa dos READMEs e docs
abaixo, não medição.

```
 identidade segura para agentes (várias contas, perfis, segredo fora da conversa)
   ^
   |  Composio (plataforma hospedada)      |            auth  <- alvo
   |  Nango (servidor para operar)         |
   |---------------------------------------+------------------------------->
   |                                       |  oama (só e-mail)   leve, sem servidor
   |                                       |  oauth2c (só busca o token)
   |
```

| Ferramenta | O que é (segundo a própria fonte) | Onde fica |
|---|---|---|
| [Nango](https://github.com/NangoHQ/nango) | plataforma de integrações com OAuth gerenciado, para produtos; é um servidor (próprio ou na nuvem) | rica em contas, pesada |
| [Composio](https://composio.dev) | plataforma de ferramentas e autenticação para agentes, hospedada | rica em agentes, serviço de terceiros |
| [oama](https://github.com/pdobsan/oama) | gerente de credenciais OAuth para e-mail | leve, só e-mail |
| [oauth2c](https://github.com/cloudentity/oauth2c) | cliente de linha de comando que obtém tokens OAuth 2.0 | leve, só busca o token |

O que leva `auth` ao quadrante de cima, e que dá para conferir no código e nos testes:

- **O segredo nunca sai do envless e do Keychain**: o cliente entra no comando por `envless exec`, o JSON baixado vai por
  stdin, e o teste usa um segredo-isca que não pode aparecer em saída, config nem diário.
- **Um escritor só**: o diário e a config são escritos apenas por `auth.py`; o console só lê.
- **Setup guiado pela ferramenta de perguntas**: quatro perguntas, o agente executa o resto e para só no login.
- **Concessão por perfil**: `run` recusa a conta que o perfil não recebeu. Honestidade: é trava contra engano, não
  sandbox; quem controla o ambiente do processo escolhe o perfil.

Decidi não adotar Nango nem Composio porque o dono quer zero servidor e zero terceiro no caminho do token (LGPD); Nango
fica como o desenho de referência (conexões por usuário, o provedor renova).

## Créditos e referências

| Base | Autor | O que usamos | Link conferido |
|---|---|---|---|
| googleworkspace/cli (`gws`), Apache-2.0, "não é um produto oficial do Google" | Google Workspace (comunidade) | login OAuth, renovação, token cifrado com chave no Keychain | sim |
| Nango | NangoHQ | desenho de referência: conexão por conta, o provedor renova | sim |
| oama | pdobsan | ideia de gerente de credenciais OAuth por linha de comando (só e-mail; no macOS usa GPG) | sim |
| oauth2c | Cloudentity | alternativa para provedores sem CLI própria (não implementada ainda) | sim |
| OAuth 2.0, RFC 6749 · PKCE, RFC 7636 | IETF, 2012 · 2015 | o fluxo que o `gws login` executa | sim |
| envless | biliboss | cofre dos segredos | skill `envless` |
| Event modeling / `Updated` | skill `design-taste` | cinco eventos | n/a |
