# Systems thinking tools

Depth for the four tools in SKILL.md. Credits: the README.

## Cynefin (Snowden, Boone 2007)

| Domain | The relation of cause and effect | Move | In a brainstorm |
|---|---|---|---|
| clear | obvious to everyone | sense, categorise, respond | apply the known rule; probably not a brainstorm: route to task-backbrief |
| complicated | knowable by analysis or expertise | sense, analyse, respond | compare options, ask who knows; a design with a recommendation |
| complex | visible only in hindsight | probe, sense, respond | the approach is a small, safe-to-fail experiment, with what it should teach |
| chaotic | no useful link | act, sense, respond | stabilise first, think after |
| disorder | unknown which domain | break it into parts and classify each | the usual start of a vague idea |

Classify by asking: "dá para saber a resposta com análise, ou só dá para descobrir tentando?".

## Iceberg (event, pattern, structure, mental model)

Four levels, from what is seen to what drives it: **event** (what happened), **pattern** (what keeps happening),
**structure** (what produces the pattern: rules, incentives, flows, delays), **mental model** (beliefs that keep the
structure in place). Ask one level at a time; stop when the answer names a structure or belief the owner can change.
Attribution of the model: see the README (uncertain).

## Causal loop diagram

Variables are nouns that vary (quantities, not actions). A link `A -> B` is `+` when A up makes B up (and A down, B
down), `-` when A up makes B down. A loop is a closed path: count its `-` links; even (including zero) is **R**
(reinforcing, growth or collapse), odd is **B** (balancing, goal-seeking). Name delays when they matter (`||`) in
the variable's text. Write them down with `variable.added`, `link.added`, `loop.identified`; read them back with
`brainstorm.sh graph <session>`, or see them in the console's Brainstorm domain.

Example: `pressa -> bugs (+)` and `bugs -> pressa (-)`: more rush, more bugs; more bugs, less rush (the team slows
down). One `-` in the cycle, so it is B.

## Leverage points (Meadows, 1999)

From weakest to strongest: 12 numbers (constants, parameters); 11 buffer sizes; 10 stock-and-flow structure;
9 delays; 8 balancing loops; 7 reinforcing loops; 6 information flows; 5 rules; 4 self-organisation; 3 goals;
2 the paradigm out of which the system arises; 1 the power to transcend paradigms. (Meadows numbers them from 12
down to 1, 12 being the weakest; the SKILL's `level` field uses her numbers: `level 12` = numbers, `level 1` =
transcending paradigms.) Rank the candidate interventions by level and prefer the deeper one that is still
reachable; people push the weak levers (numbers) because they are easy.
