# Pesquisa: skill `retro` — estado da arte

Data: 2026-11-06. Só leitura. Nada instalado.
Caminho base Hermes: `/Users/billiboss/.hermes/hermes-agent` (abrev. `HA/`).

## 1. Loop de auto-melhoria do Hermes

Fonte principal: `HA/agent/background_review.py` (1390 linhas).

**Quando roda**
- Fim de turno, por contagem. Skills: `_iters_since_skill >= _skill_nudge_interval` e `skill_manage` disponível (`HA/agent/turn_finalizer.py:863-867`). Memória: `memory.nudge_interval` (padrão 10, `HA/hermes_cli/config_defaults.py:1307`).
- Manual: `/refine [foco]`. O foco é anexado ao prompt (`background_review.py:1351-1375`).
- Roda numa thread em um fork do agente. Máx. 16 iterações (`:173`). Orçamento de tokens de entrada: 75% do contexto, teto de 600k (`:180-182`).

**O que lê**
- O snapshot da conversa inteira (cache aquecido). Se usa modelo auxiliar diferente, recebe um digest: últimas 24 mensagens literais e as antigas viram "USER: ..." truncado em 300 caracteres (`_digest_history`, `:332-362`).
- Ferramentas permitidas: só `skills` (+ `memory` se o gatilho for de memória) e `read_file`/`search_files`. Escrita livre é negada; tudo passa pela validação do `skill_manage` (`_review_tool_whitelist`, `:1114-1156`).
- Revisão de skill nunca recebe a ferramenta de memória, para não apagar entradas sem supervisão (`:1118-1121`).

**Critério skill vs memória** (`:516-520`, `:567-573`)
- "Memory captures 'who the user is and what the current situation ... is'; skills capture 'how to do this class of task for this user'."
- "A user-preference lesson lives in exactly ONE place: the skill that governs the task when one exists, USER.md only for cross-cutting preferences no skill owns — never both."
- Memória tem dois alvos: USER.md (quem é o usuário) e MEMORY.md (fatos do ambiente). "One fact goes to ONE store, never both" (`:377`).

**Sinais que valem ação** (`:464-475`)
- Correção de estilo, tom, formato ou verbosidade. "Frustration signals ... are FIRST-CLASS skill signals".
- Correção de workflow ou sequência de passos → vira pitfall ou passo explícito.
- Técnica não trivial, workaround ou caminho de debug.
- Skill carregada que estava errada, incompleta ou velha → "Patch it NOW".

**Ordem de preferência** (`:476-507`)
1. Atualizar skill carregada na sessão.
2. Atualizar skill guarda-chuva existente.
3. Adicionar arquivo de suporte (`references/`, `templates/`, `scripts/`) com ponteiro de uma linha no SKILL.md.
4. Criar skill nova, só em nível de classe. Nome nunca é PR, erro ou codinome.

**Anti-ruído e anti-duplicata**
- Grounding obrigatório: "Save only facts GROUNDED in this conversation — a user message or tool result you can point to. Never infer the user's traits ... never turn a one-off request into a standing preference unless the user marked it general ('always', 'from now on', 'remember')" (`:383-388`).
- Formato do aprendizado: "A pitfall is a generalizable rule + one clause of WHY (the mechanism), imperative." Sem número de PR, data ou citação do usuário como conteúdo; citação só se for a melhor declaração da regra (`:409-414`).
- "The same lesson learned twice is ONE rule. Before adding, search the skill (and its references/) ... strengthen or clarify it rather than appending a second copy" (`:415-417`).
- Não duplicar o que AGENTS.md e schemas de ferramenta já ensinam (`:418-420`).
- "Fix the skill in place ... do not append 'UPDATE: actually...'" (`:426-427`).
- `references/` por tema, nunca `<data>-<incidente>.md`. "A skill with dozens of one-off references is the failure shape" (`:421-425`).
- Bloco "não capturar" (`:431-454`): falhas de ambiente (binário ausente, credencial), afirmações negativas sobre ferramentas ("X is broken", viram recusas por meses), erro transitório já resolvido (a lição é o retry), narrativa de tarefa única, falhas sem solução (não vender tentativas como "workflow confiável"). Se falhou por setup, capture o FIX numa skill de setup.
- Read-before-write forçado: o `skill_manage` recusa patch sem `skill_view` fresco na mesma revisão (`:508-515`).
- Sobreposição entre skills só é anotada; o curator consolida. "Never delete a skill here" (`:521-522`).
- Viés contra inação: "Be ACTIVE — most sessions produce at least one skill update... A pass that does nothing is a missed learning opportunity" (`:457-459`). Mas "Nothing to save." continua sendo saída válida (`:524-526`).
- Escrita de memória pode exigir aprovação humana: `write_approval` (escritas de fundo ficam em fila, `/memory pending|approve|reject`) (`config_defaults.py:1300-1301`).

**Lição de engenharia:** negar `read_file` ao fork causou "~142 denials + ~204 read-before-write refusals" e quase nenhum patch aterrissou (`background_review.py:1126-1132`). O agente de revisão precisa poder ler a skill antes de editar.

## 2. Fontes abertas e da web

| Fonte | O que faz | Ideia para roubar |
|---|---|---|
| claude-reflect (BayramAnnakov) — https://github.com/BayramAnnakov/claude-reflect | Hook detecta correções ("no, use X", "actually...") e enfileira em `~/.claude/learnings-queue.json`. `/reflect` revisa com humano e grava. `/reflect-skills` acha padrões repetidos no histórico. | Roteamento por destino com escolha do usuário: "skill file \| CLAUDE.md \| both" quando a correção veio logo após invocar uma skill (https://clauderules.net/rules/claude-reflect-claude-md). Também `--scan-history --days N` e aviso de que o Claude Code apaga sessões após 30 dias (`cleanupPeriodDays`). |
| Mesmo repo, dedupe | Antes de gravar, confere conteúdo existente: merge / replace / skip. `/reflect --dedupe` consolida entradas semanticamente parecidas. | Três ações de dedupe explícitas por lição + passe periódico de consolidação. |
| claude-reflect-skill (rodrigo-kiko) — https://github.com/rodrigo-kiko/claude-reflect-skill | Extrai correções, padrões que funcionaram e preferências; grava seção "Session Learnings" no CLAUDE.md. | Capturar também o que funcionou (✅), não só o que deu errado. |
| Claudeception (blader) — https://github.com/blader/claudeception | Skill que, após descoberta não óbvia, cria skill nova. Hook `UserPromptSubmit` força avaliar toda sessão. Modo retrospectiva: extrai "top candidates (typically 1-3 per session)". | Teto de 1-3 lições por sessão. Filtro: só extrai o que exigiu descoberta real, tem gatilho claro e foi verificado (fork https://github.com/abhattacherjee/claudeception). Descrição escrita para recuperação futura. |
| Anthropic, Agent Skills — https://www.anthropic.com/research/equipping-agents-for-the-real-world-with-agent-skills | Divulgação progressiva em 3 níveis. Diretrizes de avaliação. | "Iterate with Claude: ... ask Claude to capture its successful approaches and common mistakes ... If it goes off track ... ask it to self-reflect on what went wrong." E "Start with evaluation": ache a lacuna em tarefas reais antes de escrever. |
| anthropics/skills skill-creator — https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | Guia de escrita. | SKILL.md abaixo de ~500 linhas; passou disso, mover para arquivos referenciados com "quando ler". Todo "quando usar" vai na `description`, não no corpo. Orçamento para evitar inchaço. |
| Reflexion (Shinn et al. 2023) — https://arxiv.org/abs/2303.11366 | Agente converte feedback (escalar ou texto) em reflexão verbal, guardada em buffer de memória episódica para a próxima tentativa. "Semantic gradient signal". | Reflexão ligada a um sinal concreto de feedback, não introspecção solta. A reflexão é texto no contexto, sem mexer em pesos, o que combina com editar SKILL.md. |
| Voyager (Wang et al. 2023) — https://arxiv.org/abs/2305.16291 | Biblioteca de skills; só entra skill verificada ("Each time GPT-4 generates and verifies a new skill, we add it"). Indexada por descrição; composição de skills simples. Ciclo com feedback de execução, erros e auto-verificação. | Gate de verificação antes de admitir (aqui: o dono aceita + diff aplicado). Skills compõem em vez de duplicar. Contadores de uso/falha por skill (https://github.com/Abhishek200416/IVA, implementação de terceiros) como base para medir. |
| After-Action Review (Exército dos EUA) — https://www.teamretro.com/retrospective-templates/after-action-review/ e https://patrickneilbradley.com/how-i-run-an-aar.html | 4 perguntas: o que era esperado, o que aconteceu, por que a diferença, o que manter/mudar. Saída escrita com dono e prazo. | Formato interno da lição: esperado → ocorrido → causa → ação. Distinguir "skill gap" de "alignment gap" (instrução ambígua ou sistema quebrado) (https://teambuildingbot.com/how-to-run-an-after-action-review/). Olhar também para o que foi melhor que o planejado. Parar em causa que dá para mudar, não em culpado. |
| Retro ágil (Start/Stop/Continue) | Formato de agrupamento de itens. Não pesquisei fonte primária; usar só como ideia secundária. | Três baldes por lição: sustain (regra a manter), improve, change. Já coberto pelo AAR. |

## 3. Síntese: 10 ideias para a `retro`

1. **Sinais de detecção em ordem de força** [Hermes `:464-475`; claude-reflect]. (a) marcador explícito do dono ("sempre", "a partir de agora", "lembra", "remember:"); (b) correção direta ("não, use X", "para de..."); (c) retrabalho: o dono pediu de novo a mesma coisa ou desfez o resultado; (d) erro de ferramenta seguido de contorno que funcionou; (e) skill carregada que se provou errada. Frustração conta como sinal de skill, não só de memória.

2. **Ancorar na skill em jogo** [Hermes `:478-485`; claude-reflect]. Para cada lição, achar a skill que estava carregada (leitura de `SKILL.md` ou `/skill`) quando a correção ocorreu. Ela é o destino padrão. Sem skill em jogo, procurar guarda-chuva existente; só então propor skill nova, em nível de classe.

3. **Grounding obrigatório, citação do dono como evidência** [Hermes `:383-388`]. Toda lição aponta para uma mensagem real (arquivo JSONL + índice). Nunca inferir traço do dono. Pedido pontual não vira regra, a menos que ele marque como geral. **Diferença deliberada:** o Hermes proíbe citação como conteúdo da skill; na `retro` a citação vive no evento `lesson.proposed` (evidência para o dono), não no texto gravado na skill.

4. **Formato da lição = regra + porquê, imperativa** [Hermes `:409-411`; AAR]. Campos: `skill`, `regra` (1 frase), `porquê` (mecanismo), `evidência` (citação), `tipo` (skill gap vs alignment gap, do AAR), `escopo` (sempre / só neste projeto). Sem data, PR ou narrativa no texto final.

5. **Dedupe contra o texto existente antes de propor** [Hermes `:415-417`; claude-reflect]. Ler a skill alvo e `references/`. Resultado por lição: `novo`, `reforçar` (editar a frase existente), `já coberto` (descartar e registrar `lesson.rejected` com motivo `duplicate`). Corrigir no lugar, nunca anexar "ATUALIZAÇÃO: na verdade...". Se o dono repetiu a correção, a regra existia e não foi seguida: isso aponta para a descrição ou a posição da regra na skill, não para uma segunda cópia.

6. **Decisão skill vs wiki vs nada** [Hermes `:516-520`, `:431-454`]. Regra proposta:
   - Skill: "como fazer esta classe de tarefa para este dono" (procedimento, preferência de formato, pitfall).
   - Wiki/memória: fato sobre ambiente ou projeto (caminho, convenção, quirk de config). Um destino só, nunca os dois.
   - Nada: falha de ambiente (binário ausente, credencial), afirmação negativa sobre ferramenta, erro transitório resolvido, narrativa de tarefa única, tentativa sem solução. Para falha de setup, propor o FIX numa skill de setup.

7. **Teto e anti-inchaço** [Claudeception "1-3 por sessão"; skill-creator <500 linhas; Hermes `:421-425`]. No máximo 3 a 5 lições por rodada. Se a skill alvo passa de ~500 linhas, propor mover conteúdo para `references/<tema>.md` com ponteiro. Regras sempre ativas ficam no `SKILL.md`; profundidade ocasional vai em `references/` por tema, nunca um arquivo por incidente. Anotar skills sobrepostas, sem consolidar na hora.

8. **Pontuar antes de mostrar ao dono**. Sugestão minha, inspirada nos filtros do Claudeception (descoberta real, gatilho claro, verificada). Dar a cada lição uma confiança (explícita > correção repetida > inferida). Esconder as inferidas abaixo de um corte, ou listá-las em "talvez", para o multi-select não virar ruído.

9. **Leitura retroativa sob demanda** [claude-reflect `--scan-history`]. Se a conversa foi compactada ou o dono pede sessões antigas, ler o JSONL de `~/.claude/projects/<dir>/<sessão>.jsonl`. Avisar que o Claude Code apaga sessões antigas (padrão 30 dias, `cleanupPeriodDays`), então vale rodar `/retro` cedo. No pi, ler o formato próprio de sessão dele (não pesquisado aqui).

10. **Medir se a lição funcionou** [Voyager contadores; Anthropic "start with evaluation"; AAR "sustain"]. Eventos além dos três previstos: `lesson.applied` (PR mergeado, com hash do trecho da skill) e `lesson.recurred` (o mesmo tipo de correção apareceu depois em sessão posterior que carregou a skill). Métrica: taxa de reincidência por skill e por lição, lida do JSONL. Reincidência alta → a regra está mal escrita ou mal posicionada, não falta outra regra. Também registrar `lesson.rejected` com motivo (duplicada, errada, específica demais) para calibrar a detecção. Esta parte é proposta nossa; nenhuma fonte pesquisada implementa essa medição.

11. **Registrar o que funcionou** [claude-reflect-skill; AAR]. Incluir lições positivas: abordagem que o dono elogiou ou aceitou de primeira. Entram como "manter" só se há aprovação explícita; não inferir de silêncio.

12. **Escrita segura**. Leitura obrigatória da skill antes de editar (read-before-write) [Hermes `:508-515`]. Edição em worktree e PR, com o dono escolhendo no multi-select (equivale ao `write_approval` do Hermes). A `retro` nunca apaga skill. Se a skill for travada pelo dono, devolver a mudança sugerida no texto em vez de recriá-la com outro nome [Hermes `:483-485`].

## Lacunas
- Não li o código do pi nem o formato de sessão dele.
- Não li o corpo completo da skill do Claudeception nem os hooks do claude-reflect (só README e trechos de busca).
- Start/Stop/Continue ficou sem fonte primária.
- O Hermes não mede se uma lição funcionou. Só há contagem de uso de tokens da revisão (`_snapshot_review_usage`, `background_review.py:778`).
