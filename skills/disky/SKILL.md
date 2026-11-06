---
name: disky
description: "Diagnostique o disco cheio do Mac com o disky (o nosso analisador de disco, open source) e proponha a limpeza sem apagar nada por conta própria. `scan` tira uma foto do disco; `dirs`, `top`, `ext` e `query` (SQL) com `--physical` mostram onde mora o espaço; `cleanup` sem `--apply` lista node_modules, target, .venv e builds; `diff`, `growth` e `predict` dizem o que cresceu e quando enche. Apagar, só com a tabela (caminho, tamanho, o que é, se se regenera) aprovada pelo dono. Use quando disserem \"o disco está cheio\", \"libera espaço\", \"o que está ocupando o disco\", \"roda o disky\", \"limpa os node_modules\", \"quanto livre tem\", \"o que cresceu no disco\", \"quando o disco enche\". Não é a `sync` (git) nem o `docker system prune` (nunca)."
metadata:
  version: 0.1.1
---

# disky — onde mora o espaço, e o que se pode apagar

O [disky](https://github.com/biliboss/disky) varre uma pasta, guarda a foto (snapshot, um banco DuckDB) e responde perguntas sobre ela. O agente diagnostica e propõe; **quem decide o que se apaga é o dono, pela tabela.** Instalação: `cargo install disky`; `disky schema` descreve todo comando e todo formato de saída em JSON.

## Passos

1. **Meça o livre de verdade, antes de tudo.** É o número que o dono quer ver mudar:
   ```sh
   df -k / | tail -1 | awk '{print $4/1048576" GiB livres"}'
   diskutil info / | grep -i 'free space'
   ```
2. **Tire a foto.** `disky scan ~` (o home leva poucos minutos; `disky scan /` para o volume todo). Toda consulta depois lê a foto, não o disco: **depois de apagar algo, escaneie de novo** antes de propor mais, ou a lista traz caminhos que já não existem.
   - **Uma foto em escrita fica travada** (`snapshot locked`) enquanto um `scan` roda, seu ou de outra sessão: espere e tente de novo, ou leia a anterior (`--snapshot @latest~1`), sabendo que ela é mais velha.
   - Se o home soma bem menos que o usado do volume, o resto está fora dele (`/private/var/folders`, `/Applications`, `/opt`, `/Library`): meça com `du -sh -x <pasta>` ou escaneie `/`.
3. **Ache onde mora o espaço, sempre com `--physical`.** No APFS o tamanho lógico mente: um arquivo esparso (a imagem do OrbStack, de uma VM) diz terabytes e ocupa poucos gigas.
   ```sh
   disky dirs --physical --limit 60
   disky top --physical --limit 50
   disky ext --physical
   disky stats --physical
   ```
   Para agrupar como quiser, `disky query` (DuckDB, tabela `files`: `path`, `name`, `ext`, `size`, `physical_size`, `mtime`, `is_dir`, `depth`):
   ```sh
   disky query "select array_to_string(list_slice(string_split(path,'/'),1,5),'/') p,
     round(sum(coalesce(physical_size,size))/1e9,2) gb from files where not is_dir
     group by 1 order by 2 desc limit 40" --format json
   ```
4. **Liste os candidatos regeneráveis, em dry-run.** `disky cleanup --physical --limit 5000 --format json` lista `node_modules`, `target`, `__pycache__`, `.next`, `dist`, `build`, `.venv`, `.gradle` e `.pytest_cache` (filtre com `-t node_modules,target`). Antes de pôr um deles na tabela:
   - **Confira que ele existe hoje e quanto ocupa:** `test -e <caminho> && du -sh <caminho>`. A foto pode ser de dias atrás, e outra sessão pode já ter limpado.
   - **Fique com o caminho mais de fora:** o cleanup lista também o `node_modules` dentro de outro `node_modules`; somar os dois conta duas vezes.
   - **O repo tem de estar limpo e parado:** `git -C <repo> status --porcelain` vazio, `git check-ignore -q <caminho>` (só o que é ignorado pelo git, nunca um arquivo versionado), e nenhum processo usando a pasta (`lsof -d cwd` e `lsof | grep <caminho>`): um servidor ou um agente rodando ali quebra.
   - **Worktrees de agente paradas** (`git worktree list` de cada repo; as dos agentes costumam ficar em `.claude/worktrees/`): se estão limpas, o `HEAD` já está no origin (`git branch -r --contains HEAD`) e nenhum processo roda nelas, `git worktree remove <caminho>` libera o espaço e o ramo fica. Com commit fora do origin, é do dono.
   - Fora do cleanup, os caches que se regeneram: `~/Library/Caches/*`, os caches de app Electron e de perfil de navegador de teste (`Cache`, `Code Cache`, `cache2`), `brew cleanup -n -s` (mostra sem apagar), as caches de uv, npm, bun, pnpm e cargo, `xcrun simctl list devices unavailable`, o `pnpm store prune`, e imagens e containers Docker parados, um a um pelo nome.
5. **Monte a tabela e entregue ao dono.** Uma linha por caminho:

   | caminho | tamanho físico | o que é | se regenera? |
   |---|---|---|---|

   Separe em três grupos: **regenerável** (build, dependência, cache: some e volta sozinho ou com um `install`), **pergunte** (o que não se regenera, ou que você não sabe o que é) e **do dono** (só o tamanho: Lixeira, snapshots locais do Time Machine (`tmutil listlocalsnapshots /`), backups, arquivos pessoais grandes, apps grandes para desinstalar, fórmulas grandes do Homebrew, o disco da VM de um app como o Claude Desktop, worktrees com commit fora do origin, e o reinício do Mac, que devolve o volume de swap e VM). Apague só o que ele aprovar.
   - **Quando o seguro não basta para a meta, pare e pergunte** com a tabela, somando quanto falta e sugerindo a combinação que chega lá. Pela skill `askuser` se a tela dela estiver aberta; senão, na conversa.
6. **Apague o aprovado e meça de novo.** `rm -rf` caminho a caminho do que foi aprovado, ou `disky cleanup -t <categoria> --apply` quando o dono aprovou a lista inteira do cleanup. O `--reversible` manda para a Lixeira, que só libera espaço quando o dono a esvazia: use-o quando ele quiser poder desfazer, e diga que o ganho fica para depois. Depois, o `df` do passo 1 de novo, `disky scan ~` e `disky diff @latest~1 @latest` (o que sumiu). Relate o livre antes e depois e o que se apagou.

## Organizar o `~/src` (código parado)

A regra do dono: **projeto sem mexer há 7 dias ou mais e 100% no remoto sai do Mac; o resto parado vai para o SSD.**

1. **Levantamento num script só** (somente leitura, uma linha por pasta numa TSV): tipo (dir, link, arquivo), dias
   desde o arquivo mais novo (pulando `node_modules`, `.venv`, `target`, `dist`), tamanho, e no git: remote, arquivos
   sem commit, commits sem push (`git log --branches --not --remotes`), stash, se é worktree. Veredito por linha:
   `remove` (parado e sincronizado), `keep-local-work` (parado com trabalho só aqui), `no-git`, `keep-recent`.
2. **Pergunte uma vez, pelo ask tool,** com a lista do `remove` e o tamanho, e o destino do resto. Arquivos sensíveis
   soltos na raiz (extrato, dump `.sql.gz`, bundle, chave) entram na mesma pergunta.
3. **Apague reconferindo cada repo na hora** (`status --porcelain`, unpushed e stash zerados); o que mudou desde o
   levantamento fica.
4. **Arquive o parado com trabalho local no SSD** (`/Volumes/<ssd>/src-archive/<nome>`), pulando a pasta que um
   processo usa (`lsof -d cwd`), depois `git worktree repair` nos repos e worktrees movidos, e deixe **um link só**,
   `~/src/archive`, nunca um link por projeto.
5. **Sensíveis:** chave vai para um cofre do envless (base64, conferindo o tamanho devolvido) e a cópia em texto para
   `~/Private/` (700) até o dono confirmar; o resto sensível também para `~/Private/`.

- **Cheque a seleção antes do passo destrutivo seguinte:** se a lista a mover saiu vazia, pare. Um filtro na coluna
  errada selecionou zero e a remoção dos links por projeto rodou mesmo assim.
- **Antes de mover para o SSD, meça o livre dele** (`df -h /Volumes/<ssd>`): cheio, o que cabe é decisão do dono
  (backups velhos, modelos baixados, cópias de jogos), com a tabela do passo 5 acima.
- **Na tabela do SSD, recomende apagar o que é de dev e volta sozinho:** backup de VM de dev (colima), cache de
  modelos (`hf-cache`, `ollama-models`), cópia de jogo ou app (`Steam` dentro de um offload). O dono trata isso como
  descartável e aprova de uma vez. Pergunte de verdade só por backup de dado (de cliente, de banco, `*-backup` de
  produto) e por sessões de agente. Abra antes o que é um balaio (`offloaded-*`, `downloads`): liste um nível abaixo
  com `du -sh` e a data, e decida por subpasta.
- **Caches no SSD: esvazie o conteúdo e mantenha a pasta** (`find <pasta> -mindepth 1 -maxdepth 1 -exec rm -rf {} +`),
  porque links do Mac apontam para ela. O cache de módulos do Go é só leitura: `chmod -R u+w` antes de apagar.

## O que pega

- **O tamanho apagado não é o espaço liberado.** No APFS, clones e hardlinks dividem blocos: as dependências do pnpm, uma cópia de app clonada. Apagar 6,8 GB lógicos de builds liberou 1,8 GB; doze cópias do Chrome de 18 GB liberaram 0,7 GB. Meça o ganho só pelo `df` antes e depois, e diga isso ao propor.
- **O Chrome empilha cópias de si** em `$TMPDIR/../X/com.google.Chrome.code_sign_clone/` (uma por atualização). Só a que o processo usa importa (`lsof | grep code_sign_clone`); as outras se apagam, mas liberam pouco pelo motivo acima.
- **As fotos do disky pesam** (meio giga cada) e moram em `~/Library/Application Support/disky`. `disky forget --keep-last 3` mostra o que sairia; só com `--apply` apaga.
- **O que você escreve durante a limpeza vai para `/tmp`,** nunca para a pasta de estado do agente ou do repo.

## O que nunca

- **Não apague sem a tabela aprovada,** nem `cleanup --apply` sem o dono ter visto a lista.
- **Nada pessoal ou insubstituível:** Documentos, Desktop, Downloads, Fotos, iCloud (`~/Library/Mobile Documents`), Mail, Mensagens.
- **Nada de sessão nem estado de agente:** `~/.claude*`, `~/.pi/agent/sessions`, `~/.local/state`, e nada em repo com mudança não commitada.
- **Não esvazie a Lixeira nem apague snapshots ou backups:** só o tamanho, para o dono.
- **Nunca `docker system prune`;** imagem e container, um a um pelo nome. Não feche apps nem mate processos de outras sessões.
