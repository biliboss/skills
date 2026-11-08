---
name: backbrief
description: >-
  Use on every non-trivial request, before acting, and when the owner says "backbrief", "me conta o que entendeu",
  "o que você entendeu", "repete o pedido" or "confirma antes". The everyday default: say back, in at most five lines
  of plain text in the reply, what you understood, what you will do, what stays out and how the owner will see it
  is done, then act. Not `shape` (the planning door for big work) and not `task-backbrief` (the Tasks-domain gate
  that waits for a confirmation and runs the journal).
metadata:
  version: 0.1.0
  license: MIT
---

# backbrief

A short teach-back before acting, as plain text in the reply. No Skill tool, no AskUserQuestion, no form: the owner
reads it as he reads anything else.

## Steps

1. Read the request. Trivial (a question, a one-line command): just answer, no backbrief.
2. Write the backbrief, at most five lines, always in this order:
   1. **Entendi:** what you understood the request to be.
   2. **Vou fazer:** what you will do, in steps.
   3. **Fica de fora:** what you will not touch.
   4. **Pronto quando:** how the owner will see that it is done.
3. Act right after, in the same turn, without waiting for an ok.
4. Stop and wait only for an irreversible decision (delete, pay, publish, force push) or a choice only the owner can
   make. Then ask that one thing in the same text.

## Which one

- Everyday work: `backbrief` (this skill).
- Big work that needs context, a planning piece and a delegation: `shape`.
- A Tasks-domain task that must wait for the confirmation and keep the journal: `task-backbrief`.
