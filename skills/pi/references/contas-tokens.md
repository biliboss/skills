# Os tokens do `claude setup-token` para a troca de conta no pi

A extensão `pi-claude-accounts` troca de conta pelo `CLAUDE_CODE_OAUTH_TOKEN`, e cada conta extra é um token de `claude setup-token`: vale 1 ano, não se renova e não aparece de novo. O login OAuth da pasta (`claude auth login`) é outra coisa: renova o acesso a cada uso, mas o token de renovação tem prazo fixo de semanas, e o Claude Code avisa 3 dias antes.

## Gerar o token na conta certa

1. **Num pane à parte, sem abrir navegador:** `tmux new-window -d -n pi-token "BROWSER=/usr/bin/true CLAUDE_CONFIG_DIR=<pasta> claude setup-token; sleep 3600"`. Sem o `BROWSER`, ele abre o navegador padrão (no Mac, o Safari) e autoriza sozinho na conta que estiver logada lá: o token sai da conta errada sem nenhum aviso.
2. **O link:** tire do pane com `tmux capture-pane -p | awk '/^https:\/\/claude.com\/cai\/oauth\/authorize/{on=1} on{print} /state=/{if(on)exit}' | tr -d ' \n'` e abra no perfil do Chrome da conta certa: `open -a "Google Chrome" --args --profile-directory=<perfil> "<url>"`. O nome de cada perfil e o e-mail estão em `~/Library/Application Support/Google/Chrome/Local State` (`.profile.info_cache`). Use uma aba só e reaproveite-a; feche no fim as que abriu.
3. **Authorize:** confira o "Logged in as" antes. O clique é do dono quando a automação da tela não alcança.
4. **O código:** a página "Authentication code" mostra `código#state`; o "Copy Code" copia os dois. Cole no pane sem ecoar (`tmux send-keys -t <pane> -l "$(pbpaste)"`, uma pausa, `Enter`) e esvazie a área de transferência depois (`printf '' | pbcopy`). Só o código, sem o `#state`, dá "Invalid code".
5. **Guardar sem ver:** `tmux capture-pane -p -J -S -300 -t <pane> | awk '/sk-ant-oat/{on=1} /Store this token/{on=0} on' | tr -d ' \n\r\t' | envless set CLAUDE_TOKEN_<NOME> --env=claude` (de dentro do cofre `~/.cofre-claude`). Feche a janela logo depois: o token fica no histórico do pane.
6. **Conferir que é outra conta:** rode o `claude -p` mínimo com cada token (`--model haiku --output-format stream-json --verbose --setting-sources= --strict-mcp-config --tools= --no-session-persistence`) e compare o `rate_limit_event`. Duas contas diferentes têm uso e reset diferentes. Uma conta Max com pouco uso só manda a janela de 7 dias.

## Levar ao pi

`CASA_CLAUDE_PRIORIDADE="<principal> <reserva>" S/contas-tokens.sh --sem-login` grava as chaves `CLAUDE_TOKEN_*` do cofre no `~/.pi/agent/claude-accounts.json` (0600) e a ordem no `claude-accounts-priority.json` ao lado. O valor passa só pelo ambiente do filho. Teste numa cópia antes (`PI_CLAUDE_ACCOUNTS_FILE=<cópia>`). Num pi aberto: `/reload` e depois `/claude-accounts refresh`.

## Antes de vencer

Anote a data de cada token e de cada login de pasta num cartão do Linear para o dono. Gerar um token novo não revoga o antigo: revogue em claude.ai › Settings › Claude Code.
