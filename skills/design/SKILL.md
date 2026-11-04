---
name: design
description: Desenhar telas de um produto no canvas do design-playground com os widgets reais do código dele. Acha o widget no repo do produto (só leitura, pelo origin/main), escreve o wrapper fino (componente.json, HTML, CSS por largura, sprite) com scripts/wrapper.sh, define o componente no MCP (componente_definir com a pasta), monta as telas com instâncias (tela_montar) e guarda o componente novo como rascunho até virar PR no produto. Também sobe o agente como motor do MCP (scripts/motor.sh). Use quando pedirem "desenha a tela X do produto", "monta a jornada no canvas", "seja o motor do design-playground", "cria o wrapper do cartão", "esse componente não existe, faz um rascunho", "os wrappers estão em dia?", "atualiza os componentes do produto". Não é a lp-draft (uma landing page num HTML só) nem a estudo-html (estudo em página).
metadata:
  version: 0.2.0
  license: MIT
---

# design: telas com os widgets reais do produto

O design-playground mora nesta skill, em `playground/` ([README](playground/README.md), [CONTRATO](playground/CONTRATO.md)). Ele é um canvas (tldraw) com um MCP sem LLM: o agente conectado é o motor. **O MCP não conhece produto nenhum.** Ele desenha componentes num shadow DOM, compõe telas e guarda instâncias. Quem sabe onde mora cada widget é esta skill: um wrapper por componente, escrito a partir do **código** do produto. **O que é de cada produto mora fora da skill**, numa pasta privada (`$DESIGN_PRODUTOS/<produto>/`), porque copia o código do produto: o formato está em [references/produto.md](references/produto.md).

Mudanças: [CHANGELOG.md](CHANGELOG.md).

## As regras

1. **O átomo é o widget com o HTML e o CSS reais do produto.** Acima dele é tldraw nativo: `frame` para a tela, `group` para a peça composta.
2. **O wrapper sai do código do produto, não do site no ar:** fiel à fonte, funciona antes do deploy e acompanha o repo. Leia o repo do produto **só pelo git do `origin/main`**; nunca mude o checkout, nunca crie ramo, worktree ou PR sem o sim do dono.
3. **Executar antes de copiar.** A receita roda o código do produto (as funções de template numa VM, o JSX renderizado para HTML). Copiar o template com ponteiro (`fonte.receita: "copiar"`) só quando o código não roda sozinho, e diga por quê no `porque` do componente.
4. **Instâncias, como no Figma:** a definição é uma; cada uso no canvas é uma instância com os próprios dados. Mudou a definição, todas se redesenham. Uma instância muda só os dados (os slots).
5. **Componente novo nasce rascunho** (`estado: "rascunho"`, sem `fonte`), guardado em `$DESIGN_PRODUTOS/<produto>/rascunhos/`. Vira `"real"` só depois do PR no produto existir, com a `fonte` apontando para ele.
6. **`estado: "real"` exige `fonte`** `{repo, arquivo, simbolo, commit, receita}`. O `repo` é o nome no GitHub (`dono/repo`), nunca um caminho local.
7. **Dados de exemplo sem gente de verdade:** nada de nome ou telefone de cliente; use "Cliente" e "(11) 9 0000-0000".

## A casa

Os scripts leem `~/.config/biliboss/casa.env` (ou `$BILIBOSS_CASA`); o modelo é o `casa.env.example` na raiz do repo:

| Chave | O quê |
|---|---|
| `DP_DIR` | opcional: outra pasta do design-playground. O padrão é o `playground/` desta skill |
| `DADOS_DIR` | opcional: a conversa, o canvas e o cache dos componentes (fora do git). Padrão: `~/.local/state/design-playground` |
| `DP_URL`, `DP_URL_REMOTA` | o endereço local e o da tailnet (porta 5317) |
| `DP_TOKEN` | opcional: o Bearer que o `/mcp` exige |
| `DESIGN_PRODUTOS` | a pasta privada dos produtos: `<produto>/referencia.md`, `render.ts`, `componentes/`, `rascunhos/` |
| `PRODUTO_<P>_REPO`, `PRODUTO_<P>_REMOTO` | o checkout local do produto e o nome dele no GitHub (`<P>` é o produto em maiúsculas) |

## 0. Ser o motor

`scripts/motor.sh claude` ou `scripts/motor.sh pi` sobe o agente com o MCP por stdio (uma config temporária com `bun run playground/src/main.ts`, `DESIGN_PRODUTOS` e `DADOS_DIR` no env; o `bun install` roda sozinho se faltar). Para um agente remoto ou um segundo cliente: `scripts/motor.sh http [--remota] [--servidor]` imprime o `/mcp` (Streamable HTTP) e a config de cliente HTTP; `--servidor` sobe o servidor só HTTP se ninguém estiver na porta. **Um motor por vez:** se outra sessão já é o motor, as ferramentas recusam; feche a outra.

No motor: abra a Web (`web_abrir`), fique em `chat_aguardar`, conte cada passo com `chat_atividade` e volte ao `chat_aguardar` depois de cada resposta.

## 1. Os componentes no MCP

1. `scripts/wrapper.sh conferir <produto>`: quais wrappers ficaram atrás do `origin/main` e se o arquivo da fonte mudou. Mudou: `scripts/wrapper.sh build <produto> <id…>`.
2. `componente_listar({produto})` mostra o que o MCP já tem. Falta algum: para cada linha de `scripts/wrapper.sh pastas <produto>`, `componente_definir({pasta})` (o caminho absoluto; o MCP lê os arquivos, o CSS de 70 KB não passa pelo agente).

## 2. O widget que a tela pede e ainda não tem wrapper

1. **Ache o widget no código:** `$DESIGN_PRODUTOS/<produto>/referencia.md` diz onde moram e como renderizar. Sem referência, procure no `origin/main` (`git -C "$PRODUTO_<P>_REPO" grep -n '<classe ou texto>' origin/main -- <pasta>`) e escreva a `referencia.md` com o que achou.
2. **Escreva a receita:** em `$DESIGN_PRODUTOS/<produto>/render.ts`, a entrada da peça (o estado da tela, o seletor, o símbolo, os slots). Os slots: `texto`, `html`, `attr:<atributo>`, `estilo:<propriedade>` e `lista` (o elemento repetido; com ícone, marque o texto com `[data-texto]`, e `" | "` separa as partes de um item).
3. **Gere e olhe:** `scripts/wrapper.sh build <produto> <id>` grava `$DESIGN_PRODUTOS/<produto>/componentes/<id>/` (`componente.json`, `peca.html`, `peca.css`, `desktop.css`, `sprite.svg`); `scripts/wrapper.sh foto <produto> <id>` desenha a peça num shadow DOM a 393 e a 1280. Compare com a tela do produto antes de definir.
4. `componente_definir({pasta})`.

**O CSS sai resolvido por largura:** media query num shadow DOM olha a janela do canvas, não a peça. O `peca.css` é o celular (sem os `@media (min-width)` acima de 393), o `desktop.css` é a web (com os de até 1280 abertos). O frame com largura ≥ 1024 usa a variante desktop.

**A casca:** o `peca.html` traz os ancestrais de que o CSS precisa (rasos, só a tag e os atributos), e os estilos do `body` vão inline no ancestral de cima, porque o `body` não existe no shadow DOM.

## 3. Montar a tela

`tela_montar({nome, largura, pecas: [{componente, dados}]})`, de cima para baixo, em `393` (iPhone) e `1280` (web). Os dados são os do caso (textos, preços, bairros), só as chaves que o componente tem. Ajuste com `instancia_mudar({id, dados})`, `instancia_inserir` e `canvas_agrupar`.

## 4. O componente que o produto não tem

1. Escreva `$DESIGN_PRODUTOS/<produto>/rascunhos/<peça>/`: `componente.json` (`id: "<produto>/<peça>"`, `estado: "rascunho"`, sem `fonte`, `w: 393`, `h`, `slots`, `dados`), `peca.html` e `peca.css`. Use os tokens e as classes do produto quando der, para o rascunho parecer da casa.
2. `componente_definir({pasta})`: a instância aparece com a faixa âmbar "rascunho". Para um teste rápido, `componente_definir({componente})` com o JSON; guarde na pasta assim que servir.
3. **Aprovado pelo dono:** o PR no produto com o componente de verdade, **só com o sim dele**. Com o PR aberto, o rascunho vira wrapper real (`componentes/<peça>/`, `estado: "real"`, `fonte` no arquivo e no commit do PR) e sai de `rascunhos/`.

## Mods: herdar, remendar, ligar estados

Ideias do mod system do RimWorld, para mudar um componente sem copiar nem editar o wrapper.

- **Herdar:** `herda: "<produto>/<peça>"` no `componente.json`. O filho muda só o que é dele: escalares ganham, `dados`/`variantes`/`slots` mesclam por chave, `css` = pai + filho. `abstrato: true` é uma base: não se instancia nem aparece no `componente_listar`.
- **Patch:** um JSON em `$DESIGN_PRODUTOS/<produto>/patches/*.json`, aplicado na leitura e nunca gravado, por isso sobrevive ao `wrapper.sh build`:

```json
{
  "alvo": "loja/botao",
  "seExiste": "loja/selo",
  "porque": "o botão do mês leva o selo",
  "ops": [
    {"op": "replace", "path": "/dados/texto", "value": "Comprar"},
    {"op": "html", "seletor": ".selo", "acao": "remover"},
    {"op": "css", "anexar": ".botao { border-radius: 8px }"}
  ]
}
```

  `alvo` é um id, uma lista ou `loja/*`. `ops` são as do JSON Patch (`add`, `replace`, `remove`, `test`; `test` que falha pula o patch) mais `html` (`remover|texto|attr|classe|antes|depois`) e `css`. É atômico; seletor que não acha nada é erro; patch que deixa o componente inválido é descartado.
- **Modificadores:** estados prontos no componente (`modificadores: {"carregando": {classe, attr, css, dados}}`), ligados na instância com `modificadores: ["carregando"]` (`tela_montar`, `instancia_inserir`, `instancia_mudar`). É o jeito de ter `disabled`, vazio e erro sem slot novo.
- **Requer:** `requer: ["loja/icone"]` faz o componente falhar cedo se falta um id. `<use href="#x">` sem `<symbol id="x">` no sprite também é erro.
- **Conferir:** `componentes_conferir({produto?})` mostra o log de carga: patches aplicados, pulados ou com erro, `requer` faltando, filhos inválidos.

**De onde vêm os nomes:** RimWorld (Def, `ParentName`/`Abstract`, PatchOperations, `MayRequire` = `seExiste`, Comps = modificadores, `About.xml` = `requer`), JSON Patch (RFC 6902) e o *modifier* do BEM.

## O que pega

- **Rode o build depois de mudar a receita.** Mudar um wrapper real sem rebuild = patch (próxima seção), nunca editar o `peca.html` ou o `peca.css`: o próximo build apaga.
- **Imagem com `loading="lazy"` não decodifica fora da tela:** tire o `loading` antes do `decode()`, ou a espera não volta.
- **Dado do exemplo não é slot:** o que vem do dado (um mapa desenhado, a quantidade de pontinhos de uma galeria, um `disabled`) fica como no exemplo; se a tela precisa mudar isso, é um slot novo na receita.

## Os produtos

Cada produto é uma pasta em `$DESIGN_PRODUTOS` (fora deste repo, porque copia o código do produto): `ls "$DESIGN_PRODUTOS"`. Produto novo: [references/produto.md](references/produto.md).
