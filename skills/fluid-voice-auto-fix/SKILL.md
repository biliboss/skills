---
name: fluid-voice-auto-fix
description: >-
  Fix words the FluidVoice dictation gets wrong over and over (tool, agent and person names, "para" heard as "mara"): mine what the user dictated in Claude Code and Hermes transcripts and FluidVoice's own history, suggest candidates, and add them to the FluidVoice custom dictionary and vocabulary boost, with a backup and a before/after diff. Guards rule order so a short rule never breaks a longer one. Use when the user says "o ditado errou", "o FluidVoice escreve errado", "ensina o FluidVoice", "adiciona no dicionário do FluidVoice", "boost de vocabulário", "fluid voice auto fix", or complains a name is transcribed wrong. Not for other dictation apps.
metadata:
  version: 0.1.0
  license: MIT
---

# fluid-voice-auto-fix — ensinar o FluidVoice a escrever certo

`S` = `scripts/` desta skill. Tudo passa por `S/fix.sh` (precisa de `uv`; macOS). Todo comando que muda algo faz **backup, mostra o diff antes/depois e reinicia o FluidVoice** (só reabre se ele estava aberto).

## Passos

1. **Achar candidatos:** `S/fix.sh scan [--top N]`. Lê, só leitura, `~/.claude/projects/*/*.jsonl`, o `state.db` de cada perfil do Hermes e o `TranscriptionHistory.sqlite3` do FluidVoice (o melhor: tem texto cru e corrigido). Sugere: padrões conhecidos (`mara o` → `para o`), correções do usuário ("não é X, é Y"), pares cru→corrigido do próprio FluidVoice e palavras ditadas várias vezes que o texto digitado escreve de outro jeito. **É heurístico e ruidoso: nunca aplique em lote; leia cada linha, e pergunte se houver dúvida.** `scan` nunca aplica nada.
2. **Regra de troca:** `S/fix.sh add "<gatilho>" ["<gatilho2>" ...] -- <substituição>`. Cada argumento antes do `--` é um gatilho inteiro (frase com espaço entre aspas). Ex.: `add billy bily -- Bili`; `add "mara o" -- para o`.
   - **Não crie regra para uma palavra solta que pode ser nome** (`Mara`); use o contexto (`mara o`, `mara ser`).
   - A ordem das regras no FluidVoice é desconhecida: um gatilho curto (`billy`) pode quebrar um longo (`billy boss` → `biliboss`). O script soma sozinho a forma já reescrita (`bili boss`) como gatilho da regra longa, nas duas ordens de criação, e recusa um gatilho que já existe com outra substituição.
3. **Nome próprio ou termo técnico:** além da regra, `S/fix.sh boost <termo> [alias...]` põe o termo no vocabulário (`parakeet_custom_vocabulary.json`, peso 10), que o reconhecedor usa antes do texto sair. Só vale com `VocabularyBoostingEnabled=1` (o script avisa se não estiver).
4. **Conferir:** `S/fix.sh list` mostra regras e termos.
5. **Desfazer:** `S/fix.sh backup` guarda o estado; `S/fix.sh restore <arquivo>` volta (e faz um backup do estado atual antes).

## Como funciona, e armadilhas

- O dicionário é a chave `CustomDictionaryEntries` do domínio de preferências, um `Data` com JSON `[{"triggers":[...],"replacement":"...","id":"UUID"}]`. Lê com `defaults export`; escreve com `defaults write ... -data <hex>`. **Escreva com o app fechado**: uma escrita com ele aberto pode ser sobrescrita; o script fecha (`osascript quit`) e reabre (`open -b`).
- Backups: `$FLUID_BACKUP_DIR` (padrão `~/.local/share/fluid-voice-auto-fix/backups`), um JSON com o dicionário e o vocabulário.
- Config por ambiente (todas opcionais): `FLUID_DOMAIN` (`com.FluidApp.app`), `FLUID_APP_ID`, `FLUID_VOCAB`, `FLUID_BACKUP_DIR`, `FLUID_HISTORY`, `FLUID_CLAUDE_GLOB`, `FLUID_HERMES_DBS` (`:`), `FLUID_RESTART=0` (não mexe no app).
- Testes: `sh tests/test.sh` (domínio falso e arquivos temporários; nunca toca o FluidVoice real).

Mudanças: [CHANGELOG.md](CHANGELOG.md).
