---
name: auth
description: >-
  Use when an agent needs to act as the owner on a provider account (Google first), or when connecting, checking,
  granting or removing accounts. The agent's secure identity: several accounts per provider, the OAuth client only in
  envless, tokens kept by the provider's official CLI (gws), a grant per Hermes/Claude profile, and a guided setup.
  Triggers "auth", "conecta minha conta Google", "adiciona a conta X", "qual conta está logada", "a conta precisa de
  login", "libera a conta pro perfil hacker", "gcal", "setup do Google", "contas". Not envless (that stores one secret;
  this uses it for logins) and not the harness's own /login (that signs in to the model provider).
metadata:
  version: 0.2.0
  license: MIT
---

# auth — a identidade segura do agente

Quem o agente é quando age em nome do dono, em vários provedores e contas, com vários perfis (Hermes/Claude), cada um só
com as contas que recebeu. Segredos só no envless e no Keychain; o provedor renova o token (gws). O produto é o **setup**:
ele roda o que pode e para só no que é do dono. Domínio, tabela de eventos e créditos: [README.md](README.md).

Entrada única: `scripts/auth.sh` (lógica em `auth.py`, uv). Nunca imprima, grave em log, diário, issue ou repo um valor
de segredo; `auth.sh` só fala de nomes, e-mails e estados.

## Setup (o fluxo principal)

1. **Pergunte uma vez**, com a ferramenta de perguntas do harness (AskUserQuestion / clarify), as quatro de uma chamada, a
   recomendação sempre a primeira opção:

   | # | Pergunta (texto exato) | Opções |
   |---|---|---|
   | 1 | Qual provedor conectar? | Google (recomendado) · Outro (diga qual) |
   | 2 | Quais contas, com apelido? | as já conhecidas: `auth.sh list` + o que o dono já usa (recomendado) · Só uma conta · Outras (escreva `apelido=e-mail`) |
   | 3 | O que o agente pode fazer nelas? | Agenda, só leitura (recomendado) · Agenda, Gmail e Drive, só leitura · Agenda, Gmail e Drive, leitura e escrita |
   | 4 | Quais perfis usam cada conta? | Só o dono (recomendado) · O perfil que está perguntando · Todos os perfis |

   Sem ferramenta de perguntas, faça as mesmas quatro em texto, curtas. Escrita e "todos os perfis" só com o OK explícito.
2. **Rode você mesmo**, sem pedir licença, nesta ordem:
   - `auth.sh setup google` — confere `envless` e `gws`, o cofre e as chaves do cliente OAuth no envless e grava o
     provedor. Exit 3 = falta o cliente: ele imprime os passos do Cloud Console com os links exatos; passe-os ao dono
     tal como saíram. Com o `client_secret.json` baixado: `auth.sh setup google --client-secret-json <arquivo>` (o valor
     vai ao envless por stdin; avise o dono de apagar o JSON).
   - `auth.sh add google <apelido> <e-mail> --services calendar[,gmail,drive] [--write] [--grant perfil1,perfil2]` por conta.
   - `auth.sh setup google` de novo: cria as pastas 0700, checa cada conta e imprime o comando de login de quem precisa.
3. **Pare só no que é do dono**: o login no navegador (um comando por conta, `auth.sh login <apelido>`, dê o comando
   exato e o e-mail a escolher) e qualquer coisa que custe dinheiro. Não abra o navegador por ele.
4. **Depois do login**, rode `auth.sh check` e responda por conta: `● ok`, `◆ precisa de login` (repita o comando),
   `✗ quebrada` (leia o motivo; API desligada no projeto é o comum).
5. Mostre o widget **Contas** do dev-console (`devc open auth`, `devc shot`).

## Comandos

| Comando | Faz |
|---|---|
| `setup [provedor] [--client-secret-json F] [--cofre D] [--env E]` | o onboarding acima |
| `add <provedor> <apelido> <e-mail> [--services a,b] [--write] [--grant p1,p2]` | registra a conta (só leitura por padrão) |
| `grant <apelido> --profile P` / `revoke …` | libera/retira uma conta de um perfil |
| `login <apelido>` | login no navegador, passo do dono |
| `list [--provider P] [--json]` · `aliases [P]` | contas e estado · os apelidos que este perfil pode rodar |
| `check [apelido] [--json]` | sonda cada conta com uma chamada barata; exit 1 se alguma não está ok |
| `run <apelido> -- <cmd…>` | roda o comando com o ambiente da conta (cliente do envless + pasta da conta) |
| `remove <apelido> [--yes]` | apaga o token local; sem `--yes` só explica; nunca revoga no provedor |

`gcal <apelido|todas> <args do gws>` é um apelido fino de `auth.sh run <apelido> -- gws …`.

## Cofre de logins (Bitwarden)

Os logins de sites do dono (o que não é chave de API: isso fica no envless) moram no Bitwarden, lido pela CLI oficial
`bw` através de `scripts/bw.sh`. O dev-console mostra a seção **Cofre** no widget Contas.

| Comando | Faz |
|---|---|
| `bw.sh status` | `locked`/`unlocked`, e-mail, última sincronização; nenhum segredo |
| `bw.sh unlock` | **do dono, no terminal dele** (senha mestra = login): a chave de sessão vai ao Keychain (`bw-session`), nunca a arquivo, log ou chat; já sincroniza |
| `bw.sh sync` | grava `~/.local/state/auth/bitwarden.json` só com metadados (site, nome, usuário, tem 2FA, senha repetida sim/não) |
| `bw.sh login <site>` | as contas daquele site (nome, usuário), para o preenchimento |
| `bw.sh lock` | bloqueia e apaga a sessão do Keychain |

- **Senha nunca sai do `bw`**: o `jq` recebe o cofre por pipe, transforma a senha em hash só para contar repetição e a
  descarta. O widget lê o JSON de metadados; nunca chame `bw` ao desenhar a página.
- **Cofre bloqueado = uma linha bordô com o comando exato** (`bw.sh unlock`), e o relato diz que o desbloqueio é dele.
- O Browser do app (WKWebView) não roda a extensão do Bitwarden: o preenchimento, quando vier, é do app/console, com
  o valor indo do `bw` direto à página.

## Regras

- **Perfil**: `AUTH_PROFILE`, senão o perfil do `HERMES_HOME`, senão `owner` (shell do dono, vê tudo). `run`, `check` e
  `login` recusam (exit 4) conta que o perfil não recebeu; quem libera é o dono (`grant`). É trava contra uso por engano,
  não sandbox: quem controla o ambiente do processo escolhe o perfil.
- **Só leitura por padrão**; escrita é escolha do dono na pergunta 3.
- **Remover não revoga**: revogar no provedor (https://myaccount.google.com/permissions) é do dono.
- **Um escritor**: o diário `~/.local/share/auth/events.jsonl` (`AUTH_DIR`) só é escrito por `auth.py`; a config
  (`~/.config/auth/config.json`, `AUTH_HOME`, 0600) também. O dev-console só lê.
- **Keychain**: o gws guarda uma chave AES no Keychain (item `gws-cli`, único por usuário do Mac) e o token cifrado em
  `credentials.enc` dentro da pasta de cada conta (0700). A chave é compartilhada, o texto cifrado não: as contas não se
  misturam. Backend `file` só se o Keychain não existir (servidor).
- Depois de mexer, rode os testes: `uv run --script scripts/test_auth.py`.
