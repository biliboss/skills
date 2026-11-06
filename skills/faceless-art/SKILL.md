---
name: faceless-art
description: Use when gerar ou refazer a arte faceless de um post ("faz a arte do post", "gera a imagem", "refaz a arte com sócias gordinhas", "ilustração faceless", "arte quadrada para o LinkedIn"). Gera a imagem 1:1 pelo Codex CLI (gerador de imagem da OpenAI) com a direção de arte da casa, edita por referência e confere antes de entregar. Não publica; para postar é a `linkedin-publish`.
metadata:
  version: 0.1.0
---

# faceless-art — a arte do post, gerada pelo Codex CLI

A arte é linguagem visual do post, nunca evidência falsa (nada de "foto" de cliente, número ou tela inventados).

## 1. Escreva o prompt num arquivo

Um `prompt.txt` em inglês (o gerador entende melhor), com: o caminho final do PNG, a direção de arte (abaixo), o conceito da cena e os textos exatos que a arte leva. Modelos reais: [references/prompt-velumma-v1.txt](references/prompt-velumma-v1.txt) (geração) e [references/prompt-velumma-v2-edicao.txt](references/prompt-velumma-v2-edicao.txt) (edição por referência).

Direção de arte da casa (repita no prompt, o gerador não lembra):
- personagens **faceless**: cabeça lisa de manequim, sem olhos, nariz nem boca; a emoção vem da postura;
- humor editorial brasileiro, traço limpo e forte, fundo claro, **1:1**;
- sem logos e sem personagem de marca (nada da Marvel, por exemplo);
- todo texto da arte em português do Brasil correto, com acento, "spelled exactly"; liste os textos permitidos e diga "no other text";
- gente real, não padrão: corpos, cores de pele e idades como as pessoas reais (gordinhas, negra, nordestina, velhas), com carinho e dignidade, sem caricatura. Descreva o corpo e a roupa de cada pessoa, senão o gerador devolve o padrão magro e branco.

## 2. Gere

```bash
CODEX=/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex   # fora do PATH
$CODEX exec --skip-git-repo-check -s workspace-write -C <dir-do-png> - < prompt.txt
```

- `--full-auto` não existe nesta versão; não pede login. Leva cerca de 2 min: rode em background e siga em frente.
- O PNG nasce em `~/.codex/generated_images/...` e o prompt manda copiar para o caminho final; confirme que o arquivo está lá.
- Saída: 1254x1254.

## 3. Refazer = editar, não gerar de novo

Passe a imagem anterior como referência no prompt e diga **o que muda** e **o que fica** ("CHANGE ONLY the three women...; keep the composition, labels, colors exactly"). Gerar do zero muda tudo e perde o que já estava aprovado.

## 4. Confira antes de entregar (sempre)

1. Abra a imagem (vision) e verifique: rosto liso em **todos** os personagens, grafia de cada texto, nenhum logo ou marca, a cena do conceito.
2. `sips -g pixelWidth -g pixelHeight arte.png` (quadrada).
3. Para o LinkedIn, o `li.py compose --image` converte PNG em JPG sozinho.
4. Se falhou algo, é uma edição por referência (passo 3), não um prompt novo.

## Pitfalls

- Pedir "a palavra X não deve aparecer" explicitamente quando o nome do produto não pode estar na arte; o gerador gosta de escrever o nome.
- Texto longo na arte sai com erro de grafia: poucas palavras, em maiúsculas, rótulos curtos.
- Não commite o PNG gerado no repo público; ele fica no post e na pasta de trabalho.
