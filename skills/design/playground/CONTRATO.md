# Contrato interno

O plano mora no wiki de quem usa o playground. Este arquivo fixa as interfaces entre as partes: quem muda uma delas atualiza este arquivo no mesmo commit.

## Decisões

- Um motor por vez (ver "Os motores e os transportes").
- A tela é HTML livre com CSS. Tamanhos: `celular` = iPhone 393×852, `tablet` = 768×1024, `desktop` = web 1280×800.
- O canvas sobrevive a reiniciar (`$DADOS_DIR/canvas.json`), e a conversa também (`$DADOS_DIR/conversa.jsonl`).
- A porta é 5317 (`PORT`). `DADOS_DIR` troca a pasta dos dados (padrão `~/.local/state/design-playground`, fora do git). `ABRIR_WEB=0` não abre o navegador (testes).

## Arquivos

| Arquivo | O quê |
|---|---|
| `src/main.ts` | liga o app ao stdio e encerra limpo |
| `src/app.ts` | `criarApp({porta, dadosDir, webDir, abrirWeb, pingMs, progressoMs, operacaoMs})` |
| `src/chat.ts` | mensagens, entregues, digitando e atividade, motor, assinantes do SSE, a espera longa, `conversa.jsonl` |
| `src/canvas.ts` | o espelho do canvas em `canvas.json` |
| `src/operacoes.ts` | as operações do canvas: manda à página e espera a resposta |
| `src/http.ts` | as rotas e o SSE |
| `src/componentes.ts` | as definições: valida, lê a pasta do wrapper, guarda com versão |
| `src/mcp-http.ts` | o Streamable HTTP em `/mcp`, a guarda do Host e o motor único |
| `src/ferramentas.ts` | as instruções do `initialize` e as ferramentas |
| `web/index.html`, `web/app.css` | o layout e a forma `tela` |
| `web/canvas.js` | o tldraw, as formas `tela` e `widget`, a pilha, a migração e as operações |
| `web/widgets.js` | as definições de `/api/componentes` e o desenho de uma instância num shadow DOM |
| `web/paleta.js` | a paleta de componentes |
| `web/chat.js`, `web/chat.css` | o chat; repassa os eventos `canvas` (`playground:canvas`) e `componente` (`playground:componente`) ao `canvas.js` |
| `test/**` | `bun test` |

O processo: `bun run src/main.ts`, o MCP por stdio e o HTTP (`Bun.serve`, `127.0.0.1:$PORT`). Nada vai para o stdout além do MCP; log no stderr.

## Mensagem e motor

```ts
type Mensagem = { id: string; autor: "pessoa" | "agente"; texto: string; em: string /* ISO */;
  selecao?: string[] /* ids das formas selecionadas no envio */; tipo?: "atividade" };
type Motor = "ouvindo" | "ocupado" | "sem-agente";
```

`Motor`: `ouvindo` com um `chat_aguardar` pendente; `ocupado` depois do `initialize` sem espera; `sem-agente` antes do `initialize` ou com o transporte fechado. Uma mensagem com `tipo: "atividade"` é uma linha de atividade do agente, não uma resposta.

`conversa.jsonl`: uma `Mensagem` por linha, `{"entregue": [ids]}` para o que já foi ao agente e `{"apagada": id}` para o que o agente apagou.

## HTTP

| Rota | O quê |
|---|---|
| `GET /`, `GET /web/<arquivo>` | a página e os estáticos de `web/` (sem `..`) |
| `GET /api/estado` | `{ motor, digitando, atividade?, mensagens }` |
| `POST /api/mensagens` | `{ texto, selecao? }` → `201 { mensagem }`; texto vazio → `400` |
| `GET /api/eventos` | o SSE (abaixo) |
| `GET /api/canvas` | `{ registros }` (o espelho) |
| `POST /api/canvas/diff` | `{ put?, remove? }` (registros do tldraw, escopo `document`) → `204` |
| `POST /api/canvas/resposta` | `{ pedido, ok, resultado?, erro? }` → `204`; pedido desconhecido ou vencido → `404` |

## SSE `/api/eventos`

- `ola`: `{ motor, digitando, atividade?, mensagens }`, ao conectar.
- `mensagem`: `Mensagem`.
- `apagada`: `{ id }`.
- `digitando`: `{ ativo, texto? }` (`texto` é a atividade atual).
- `motor`: `{ estado }`.
- `canvas`: `{ pedido, op }`, só para a aba aberta mais recente.
- `: ping` a cada 15 s.

## Operações do canvas

O servidor manda `{pedido, op}`; o `canvas.js` aplica com o `editor` e responde em `POST /api/canvas/resposta`. Sem aba aberta, a ferramenta recusa na hora; sem resposta em 15 s (a aba dorme em segundo plano), a ferramenta diz que a operação ficou na fila e que não deve ser reenviada.

| `op.tipo` | Campos | Resultado |
|---|---|---|
| `tela_criar` | `nome, html, w, h, x?, y?` (sem x/y: à direita do que existe) | `{ id }` |
| `tela_mudar` | `id, html?, nome?, w?, h?` | `{ id }` |
| `tela_ler` | `id` | `{ id, nome, w, h, html }` |
| `ler` | `ids?` | `{ formas: [{id, tipo, x, y, w, h, nome?, texto?, cor?, geo?, pai?, pilha?, lateral?, coluna?}], selecao }` (`lateral` no frame com coluna lateral; `coluna`, `"lateral"` ou `"principal"`, em cada filho dele) |
| `criar` | `formas: [{tipo: geo/text/note/frame, x, y, w?, h?, texto?, cor?, geo?}]` | `{ ids }` |
| `mudar` | `mudancas: [{id, x?, y?, w?, h?, texto?, cor?}]` | `{ ids }` |
| `apagar` | `ids` | `{ apagadas }` |
| `focar` | `ids?` | `{ ok }` |

A forma `tela` (tldraw, `type: "tela"`): `props { w, h, nome, html }`, uma cabeça de 28 px com o nome e o HTML num iframe `sandbox="allow-scripts"`. Ela só recebe clique em modo de edição (duplo clique).

## Página

- `index.html`: `<header id="motor">`, `<main id="canvas">` e `<aside id="chat">` (~380 px). Carrega `/web/app.css`, `/web/chat.css`, `/web/canvas.js` e `/web/chat.js`.
- `canvas.js` expõe `window.playground = { selecao(), editor }` e ouve `window` `playground:canvas` (o `chat.js` repassa cada evento `canvas` do SSE, para cada aba ter uma conexão só).
- Sem build: React 18.3.1 e tldraw 3.15.4 pelo esm.sh; marked 18.1.3 e DOMPurify 3.4.17 no chat.

## Componentes e instâncias (o MCP genérico)

O MCP não conhece nenhum produto: não há kit dentro dele. Os componentes chegam de fora, de um **wrapper** escrito pela skill `design` a partir do código do produto.

```ts
type Variante = { html?: string; css: string; w: number; h: number };
type Componente = {
  id: string;              // "<produto>/<peça>", kebab-case: "loja/cartao-produto"
  nome: string; descricao: string;
  estado: "rascunho" | "real";
  versao: number;          // o MCP sobe a cada componente_definir; o wrapper não manda
  html: string;            // o markup, com os ancestrais de que o CSS precisa
  css: string;             // já resolvido para o celular (393); :root vira :host ao entrar no shadow DOM
  w: number; h: number;    // o tamanho natural no celular
  variantes?: { desktop?: Variante };   // a web (1280): css (e html, se mudar) resolvidos para a largura
  slots: Slot[];           // texto, html, attr:x, estilo:p, lista ([data-texto], " | "), como antes
  dados: Record<string, string | string[]>;   // o padrão
  fonte?: { repo: string; arquivo: string; simbolo?: string; commit: string; receita: "executar" | "copiar" };
  fontes?: string[];       // URLs de <link rel=stylesheet> para o <head> da página
  sprite?: string;         // SVG com <symbol>, injetado em cada instância
  herda?: string;          // "<produto>/<peça>" do pai (Abstract + ParentName do RimWorld)
  abstrato?: boolean;      // base para herdar: fora do componente_listar padrão, não se instancia
  requer?: string[];       // ids de componentes que precisam estar definidos (o About.xml)
};
```

- **Todos os erros de uma vez:** `problemasDoComponente(v)` devolve todas as mensagens (`problemaDoComponente` devolve a primeira ou `null`). `componente_definir` erra com a mensagem, se for uma, ou com `N problemas:` e uma linha `- …` por problema.
- **Herança:** a cópia guarda a definição como veio (com `herda`); a leitura (`ler`, `todos`, `/api/componentes`) a resolve. O filho ganha nos campos escalares; `dados` e `variantes` mesclam por chave; `slots` mesclam por `chave` (o do filho troca o de mesma chave, os novos entram no fim); `css` = o do pai + `\n` + o do filho; `html`, `sprite` e `fonte` do filho ganham se vierem, senão valem os do pai. O filho pode omitir o que o pai tem: a validação olha o resultado resolvido. Pai inexistente e ciclo são problemas ao definir. Redefinir um pai manda o SSE `componente` também para cada descendente.
- **Abstrato:** `abstrato: true` some do `listar` (use `listar(produto, true)` para incluir; o resumo traz `abstrato` e `herda`) e a instância recusa ("é abstrato, use um filho"). O abstrato precisa estar completo depois de resolvido.
- **`requer`:** id que não está definido ao definir = problema ("requer X, que não está definido").
- **Sprite:** se o `html` (ou o `html` da variante desktop) usa `<use href="#id">` (ou `xlink:href`) e o `sprite` resolvido não tem `<symbol id="id">`, é problema.

- `estado: "real"` exige `fonte`; um rascunho com `fonte` é recusado. Campos fora do tipo são descartados, e uma `versao` mandada é ignorada.
- Um `desktop.css` na pasta sem `variantes.desktop` no JSON vira a variante `{css, w: 1280, h: <o h do celular>}`. A pasta recusa `..` e link que aponta para fora dela; cada arquivo vai até 4 MB.
- **O wrapper** é uma pasta com `componente.json` (o tipo acima, sem `versao`) e, se quiser, `peca.html`, `peca.css`, `desktop.css`, `sprite.svg`: quando o campo `html`, `css`, `variantes.desktop.css` ou `sprite` falta no JSON, o MCP lê o arquivo de mesmo papel na pasta.
- **Guarda:** o MCP copia a definição para `<dadosDir>/componentes/<produto>/<peça>.json` (com a `versao`). A cópia é cache; a verdade é a pasta da skill.
- **A variante:** a instância usa `variantes.desktop` quando o frame dela tem largura ≥ 1024, e o padrão no resto. Vale a largura do frame, não a da coluna: uma instância na coluna lateral de um frame de 1280 usa a desktop.

**Ferramentas** (substituem `widget_catalogo`, `widget_inserir`, `widget_mudar`, `widget_tmp_criar`):

| Ferramenta | O quê |
|---|---|
| `componente_definir({pasta})` ou `({componente})` | Lê a pasta de um wrapper (caminho absoluto) ou recebe o JSON; valida; grava com `versao` +1; manda o SSE `componente`. Devolve `{id, versao, estado}`. |
| `componente_listar({produto?})` | `{componentes: [{id, nome, descricao, estado, versao, w, h, chaves, dados}]}`, com uma `dica` quando vazio |
| `componente_ler({id})` | A definição inteira. |
| `tela_montar({nome, largura, altura?, x?, y?, pecas: [{componente, dados?}], lateral?: {largura, pecas}})` | O frame com pilha e as instâncias. Com `lateral`, as peças dela ficam numa coluna à esquerda (x = 0, w = `largura`) e as `pecas` à direita (x = `largura`, w = a largura do frame − `largura`), cada coluna empilhada a partir de y = 0. Recusa componente ou chave de dados que não existe (também na lateral) e `lateral.largura` fora de 80 até a largura do frame − 200. |
| `instancia_inserir({tela, componente, dados?, indice?, coluna?})` | Uma instância dentro de uma tela; `coluna` é `"lateral"` ou `"principal"` (o padrão), e uma tela sem lateral recusa `"lateral"`. |
| `instancia_mudar({id, dados})` | Junta os dados de uma instância com os atuais. |
| `canvas_agrupar({ids})` | Continua igual (op `agrupar`). |

**HTTP:** `GET /api/componentes` → `{ componentes: Componente[] }` (as definições atuais). Sai `GET /api/kits` e `/kits/tmp/`.

**SSE:** `componente`: `{ id, versao }`, para todas as abas: a página busca a definição nova e redesenha as instâncias daquele id.

**Modificadores** (os Comps do RimWorld, o *modifier* do BEM): estados que o componente declara e a instância liga.

```ts
modificadores?: Record<string, { descricao?: string; classe?: string; attr?: Record<string, string>; css?: string; dados?: Record<string, string | string[]> }>;
```

- Na instância: `modificadores: string[]` (em `tela_montar`, `instancia_inserir` e `instancia_mudar`). Nome que o componente não declara é erro.
- Efeito: `classe` e `attr` vão na raiz da peça (`attr: {disabled: ""}`); o `css` entra depois do da peça; os `dados` ficam por baixo dos da instância (a instância ganha).
- Resolve o estado que não é slot: `disabled`, vazio, erro.

**Patches** (os PatchOperations do RimWorld): remendos nos componentes, aplicados na leitura e nunca gravados; por isso sobrevivem ao `wrapper.sh build`. Cada arquivo é `$DESIGN_PRODUTOS/<produto>/patches/*.json` (ou uma pasta de `PATCHES_DIRS`):

```json
{ "alvo": "loja/botao" | ["loja/botao", "loja/cartao"] | "loja/*",
  "seExiste": "loja/selo" | ["loja/selo", "loja/icone"],
  "porque": "texto livre",
  "ops": [
    { "op": "replace", "path": "/dados/texto", "value": "Comprar" },
    { "op": "html", "seletor": ".selo", "acao": "remover" },
    { "op": "css", "anexar": ".botao { border-radius: 8px }" }
  ] }
```

- **`ops`:** JSON Patch (RFC 6902) `add`, `replace`, `remove` e `test` sobre a definição. `test` que falha pula o patch inteiro (o PatchOperationConditional). `html`: `seletor` + `acao` (`remover`, `texto`, `attr`, `classe`, `antes`, `depois`) + `valor` e, no `attr`, `nome`. `css`: `anexar`.
- **`seExiste`** (o `MayRequire`): o patch só vale se todos os ids estão definidos; senão é pulado, sem erro.
- **Atômico:** uma op que erra descarta o patch. Seletor que não acha nada é erro. Patch que deixa o componente inválido é descartado.
- **Ordem:** produto em ordem alfabética, e dentro dele o arquivo por nome.
- **O log:** `componentes_conferir({produto?})` e `GET /api/componentes/log` listam os patches aplicados, pulados e com erro, os `requer` faltando e os filhos inválidos.

**A forma `widget`:** `props { w, h, componente, dados }` (dados em JSON). A instância guarda só os próprios dados; os padrões vêm da definição atual, como no Figma. A variante vem do frame mais próximo, mesmo passando por um `group`. Desenha a definição atual num shadow DOM; uma instância de `rascunho` leva uma faixa âmbar "rascunho" no canto de cima. A pilha e o `group` continuam como antes.

**A coluna lateral:** um frame com pilha e `meta.lateral = L` empilha duas colunas: a lateral (x = 0, w = L) e a principal (x = L, w = largura − L), cada filho com `meta.coluna` (`"lateral"` ou `"principal"`). Um filho fora do x da coluna dele (arrastado, ou que acabou de entrar no frame) vai para a lateral se o meio dele cair em x < L, e para a principal no resto. A paleta solta na coluna do ponto; o clique na paleta com um filho da lateral selecionado entra no fim da lateral. Frame sem `meta.lateral` empilha como antes.

**Operações** (o caminho de sempre, SSE `canvas` → `POST /api/canvas/resposta`): `tela_montar { nome, w, h, x?, y?, pecas: [{componente, dados?}], lateral?: {largura, pecas} }` → `{ id, pecas, lateral? }` (`lateral`: os ids das instâncias da coluna lateral); `instancia_inserir { tela, componente, dados?, indice?, coluna? }` → `{ id }`; `instancia_mudar { id, dados }` → `{ id }`; `agrupar { ids }` → `{ id }`. O `ler` traz `componente` e `dados` nas instâncias, `lateral` no frame com coluna lateral e `coluna` nos filhos dele.

**Migração do canvas:** ao abrir, a página troca `props.kit` + `props.peca` por `props.componente`: `via-v12/<p>` → `via/<p>` e `tmp/<p>` → `via/<p>`. Uma instância cujo componente ainda não foi definido mostra "componente loja/x não definido" no lugar, sem quebrar a tela.

**A paleta** lista os componentes de `/api/componentes`, por produto, com o estado.

## De onde vêm os nomes

Do mod system do RimWorld: Def (a definição), `ParentName`/`Abstract` (`herda`/`abstrato`), PatchOperations (patches), `MayRequire` (`seExiste`), Comps (modificadores) e `About.xml` (`requer`). Do JSON Patch (RFC 6902): as ops `add`, `replace`, `remove` e `test`. Do BEM: o *modifier*.

## Os motores e os transportes

Nenhum agente é o dono do motor. Quem quer ser o motor entra por opção, ao iniciar. Um motor por vez.

- **stdio** (como antes): o cliente sobe `bun run src/main.ts`. Se a porta já estiver em uso, o MCP sobe e toda ferramenta recusa, com a URL do motor atual.
- **Servidor**: `bun run src/main.ts --servidor` sobe só o HTTP (a Web e o MCP), sem stdio, e fica de pé até ser parado.
- **Streamable HTTP** em `/mcp`, no mesmo `Bun.serve` da Web, servido nos dois modos (`WebStandardStreamableHTTPServerTransport` do SDK, com sessão).
- **Onde escuta:** sempre `127.0.0.1:$PORT`; e, se houver tailnet, também no IP da tailnet (`tailscale ip -4`, ou `DP_TAILNET_IP`), na mesma porta. Nunca `0.0.0.0`. `DP_TAILNET=0` desliga a tailnet.
- **Guarda do `/mcp`:** só aceita `Host` que seja `127.0.0.1`, `localhost`, o IP da tailnet ou um nome `*.ts.net`; e `Origin`, quando vem, do mesmo conjunto. O resto leva 403 (contra DNS rebinding). Se `DP_TOKEN` existir, exige `Authorization: Bearer <DP_TOKEN>` (sem ele, 401). A guarda vale só para `/mcp`.
- **`--servidor` com a porta em uso sai com código 1.** SIGTERM, SIGINT e SIGHUP encerram.
- **Um motor por vez:** o primeiro cliente MCP (de qualquer transporte) que chama uma ferramenta vira o motor. Enquanto ele estiver conectado, as ferramentas de outro cliente recusam com "outra sessão já é o motor". O motor de HTTP solta a vez quando a sessão fecha (`DELETE /mcp` ou o transporte fecha) ou fica 120 s sem chamar nada e sem `chat_aguardar` pendente. A sessão stdio só solta ao fechar: um Claude Code parado no stdio segura o motor.
