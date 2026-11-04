# Um produto na skill design

O que é de cada produto mora fora da skill, numa pasta privada: `$DESIGN_PRODUTOS/<produto>/` (o caminho vem do casa.env). A skill é pública; os wrappers copiam o HTML, o CSS e os dados de exemplo do produto, que costumam ser privados.

```
$DESIGN_PRODUTOS/<produto>/
  referencia.md          onde moram os widgets no repo do produto, como renderizar, o que pega
  render.ts              a receita: tira o HTML e o CSS do código do produto
  componentes/<peça>/    os wrappers reais (gerados pelo build; não edite à mão)
  rascunhos/<peça>/      os componentes novos, escritos pelo agente
```

No casa.env, por produto: `PRODUTO_<P>_REPO` (o checkout local, só leitura), `PRODUTO_<P>_REMOTO` (o nome no GitHub, `dono/repo`) e, se o ramo não for `main`, `PRODUTO_<P>_RAMO`.

## A receita (`render.ts`)

Um módulo ES que o `scripts/wrapper.ts build` importa. Ele recebe a lib da skill por `process.env.DESIGN_LIB` (`const { resolverCss, CELULAR, DESKTOP } = await import(process.env.DESIGN_LIB)`), porque mora fora da skill.

- `export const ARQUIVOS: Record<string, string>`: os arquivos do produto que a receita lê; o `conferir` olha se mudaram desde o `fonte.commit`.
- `export async function construir(ler, browser, ids)`: `ler(caminho)` devolve o conteúdo do arquivo no `origin/main`; `browser` é um Chrome (playwright-core); `ids` filtra as peças (vazio = todas). Devolve a lista de peças: `{id, nome, descricao, html, css, desktopCss, sprite?, fontes?, slots, dados, fonte: {arquivo, simbolo, receita}}`.

Executar antes de copiar: carregue o código do produto (as funções de template numa VM com os dados de exemplo das stories, ou o JSX renderizado para HTML), desenhe a tela num Chrome e tire a peça dela. O CSS sai resolvido por largura com `resolverCss`.

## O componente (`componente.json`)

O formato é o do `CONTRATO.md` do design-playground: `id` (`<produto>/<peça>`), `nome`, `descricao`, `estado` (`real` exige `fonte`; `rascunho` não tem), `html` ou `peca.html`, `css` ou `peca.css`, `variantes.desktop` ou `desktop.css`, `w`, `h`, `slots`, `dados`, `fontes`, `sprite` ou `sprite.svg`.
