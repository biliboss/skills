---
name: linkedin-publish
description: Use when publicar, editar ou conferir um post do Gabriel no LinkedIn pelo Mac ("publica no LinkedIn", "posta o diário", "edita o último post", "confere como ficou o post", "o post saiu grudado"). Dirige o Safari já logado com AppleScript + JavaScript pelo script `scripts/li.py` (compose, publish, edit-last, check). Só publica ou salva com pedido explícito do Gabriel naquele turno. Para a imagem do post é a `faceless-art`; para ler o LinkedIn de outras pessoas não é esta.
metadata:
  version: 0.1.0
---

# linkedin-publish — o post sai pelo Safari do Mac

O Gabriel já está logado no Safari do Mac. Nada de senha, nada de browser novo. `scripts/li.py` (uv, PEP 723) gera o JavaScript e chama `osascript`; o Safari precisa estar aberto numa janela do LinkedIn (a aba da frente).

```bash
li.py compose <texto.md> [--image arte.png]   # abre o compositor, põe imagem e texto; NÃO publica
li.py publish                                 # clica 'Publicar'
li.py edit-last <texto.md> [--save]           # troca o texto do último post; --save clica 'Salvar'
li.py check                                   # só leitura: lê o último post e confere o formato
```

## Regra de ouro

**Publicar para fora é decisão do Gabriel.** `publish` e `edit-last --save` só rodam com o pedido explícito dele **neste turno** ("pode publicar"). Sem isso, pare em `compose`/`edit-last` (o texto fica no compositor) e mostre o que ficaria. `check` é leitura e vale sempre.

## Fluxo de um post novo

1. Texto em `texto.md`: parágrafos separados por linha em branco, `**negrito**` no gancho e no fecho, `_itálico_` onde couber. Imagem pela `faceless-art`.
2. `li.py compose texto.md --image arte.png`. Confira na tela (screenshot do Safari) e mostre ao Gabriel.
3. Com o pedido explícito: `li.py publish`.
4. `li.py check`: deve dar `br` alto (linhas em branco), `strong` 3 e uma imagem.

Editar um post no ar: `li.py edit-last novo.md` → conferir → com pedido, `--save` → `check`.

## O que pega (e o script já resolve)

- **O `computer_use` não enxerga o Safari** (fica em outro Space: "no on-screen window") e o System Events não tem a janela; o seletor de arquivo nativo não dá para dirigir. Por isso AppleScript `do JavaScript`, com o JS lido de arquivo UTF-8 (`read POSIX file ... as «class utf8»`): sem problema de aspas nem de acento. Se o Safari recusar JavaScript, ligue Desenvolvedor > "Permitir JavaScript de Eventos da Apple".
- **Abrir o compositor:** o 'Começar publicação' é um DIV; ache a folha com esse texto e clique em `closest('[tabindex],button')`. O editor é tiptap/ProseMirror: `.ProseMirror[contenteditable=true]`.
- **Linha em branco:** cole `text/html` com `<p><br></p>` **entre** os parágrafos (senão o LinkedIn publica tudo grudado), com `<strong>`; `text/plain` vai de reserva. É um `ClipboardEvent('paste')` com `DataTransfer`.
- **Trocar o texto:** limpe (`selectAll` + `delete`) numa chamada e cole em **outra**; na mesma, o paste soma ao texto antigo e duplica.
- **Imagem apaga o texto:** colar imagem no editor limpa o texto. Ponha a imagem **primeiro** e o texto depois. O que funciona é interceptar o input de arquivo: JPG (`sips -s format jpeg`) como data URL → `File`, sobrescreve `HTMLInputElement.prototype.click` para setar `this.files` e disparar `input`/`change` quando `type==='file'`, e então clica 'Mídia'. Abre o editor de imagem: clique 'Avançar'.
- **Classes CSS são ofuscadas e mudam:** ache elementos por texto e `aria-label` (ex.: 'Abrir menu de controle da publicação de Gabriel Fonseca' → 'Editar'), nunca por classe.
- **Esperar a página:** não há evento; o script sonda a cada 0,5 s com limite. Se esgotar, olhe a tela antes de repetir.

## Conferência no ar

`li.py check` abre `https://www.linkedin.com/in/me/recent-activity/all/` e imprime: começo do texto, nº de `<br>` diretos (a linha em branco vira `<br><br>`), `<strong>`, imagens do card (~616x616 numa janela larga) e o veredito do formato. Se o formato vier suspeito, `edit-last` com o mesmo texto.
