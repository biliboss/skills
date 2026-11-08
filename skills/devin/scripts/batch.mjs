#!/usr/bin/env node
// batch.mjs: runner de scripts de orquestração (subconjunto da sintaxe de workflows do Claude) que dispara Devins.
// Uso interno do batch.sh. Node puro, sem dependências. Veja references/batch.md.
import { spawn } from 'node:child_process'
import { appendFileSync, copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const RUNS_DIR = process.env.DEVIN_RUNS_DIR
const ALLOWED_OPTS = ['label', 'phase', 'schema', 'model', 'mode', 'base', 'out']
const UNSUPPORTED_GLOBALS = ['log', 'workflow', 'budget']
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

// Erro de configuração do script: não vira null dentro de parallel/pipeline, derruba o batch.
class Fatal extends Error {
  constructor(msg) { super(msg); this.fatal = true }
}
function usage(msg) {
  console.error(`batch: ${msg}`)
  process.exit(2)
}

// ---- argumentos ----
let repo = '', max = Number(process.env.DEVIN_BATCH_MAX || 3), argsJson, scriptPath = ''
{
  const a = process.argv.slice(2)
  for (let i = 0; i < a.length; i++) {
    const k = a[i]
    if (k === '--repo') repo = a[++i] ?? usage('--repo pede um caminho')
    else if (k === '--max') max = Number(a[++i] ?? usage('--max pede um número'))
    else if (k === '--args') argsJson = a[++i] ?? usage('--args pede um JSON')
    else if (k.startsWith('-')) usage(`opção desconhecida: ${k}`)
    else if (!scriptPath) scriptPath = k
    else usage(`argumento extra: ${k}`)
  }
}
if (!repo) usage('falta --repo')
if (!scriptPath) usage('falta o script .mjs')
if (!Number.isInteger(max) || max < 1) usage('--max pede um inteiro maior que 0')
if (!RUNS_DIR) usage('DEVIN_RUNS_DIR ausente: rode pelo batch.sh')
let scriptArgs
if (argsJson !== undefined) {
  try { scriptArgs = JSON.parse(argsJson) } catch (e) { usage(`--args não é JSON válido: ${e.message}`) }
}
let source
try { source = readFileSync(scriptPath, 'utf8') } catch (e) { usage(`não li o script: ${e.message}`) }
repo = resolve(repo)

// ---- ler e separar o script ----
// Troca comentários e textos de string por espaços, mantendo o que está dentro de ${...}.
function blank(code) {
  let out = '', i = 0
  const n = code.length
  const tpl = (depth) => {
    // dentro de um template; devolve ao achar a crase de fechamento
    while (i < n) {
      const c = code[i]
      if (c === '\\') { out += '  '; i += 2; continue }
      if (c === '`') { out += ' '; i++; return }
      if (c === '$' && code[i + 1] === '{') {
        out += '  '; i += 2
        let d = 1
        while (i < n && d > 0) {
          const e = code[i]
          if (e === '{') d++
          else if (e === '}') { d--; if (d === 0) { out += ' '; i++; break } }
          else if (e === '`') { out += ' '; i++; tpl(depth + 1); continue }
          else if (e === '"' || e === "'") { str(e); continue }
          out += e; i++
        }
        continue
      }
      out += c === '\n' ? '\n' : ' '; i++
    }
  }
  const str = (q) => {
    out += ' '; i++
    while (i < n && code[i] !== q) { if (code[i] === '\\') { out += ' '; i++ } out += ' '; i++ }
    out += ' '; i++
  }
  while (i < n) {
    const c = code[i], d = code[i + 1]
    if (c === '/' && d === '/') { while (i < n && code[i] !== '\n') { out += ' '; i++ } }
    else if (c === '/' && d === '*') {
      while (i < n && !(code[i] === '*' && code[i + 1] === '/')) { out += code[i] === '\n' ? '\n' : ' '; i++ }
      out += '  '; i += 2
    }
    else if (c === '"' || c === "'") str(c)
    else if (c === '`') { out += ' '; i++; tpl(0) }
    else { out += c; i++ }
  }
  return out
}

function extractMeta(src) {
  const m = /export\s+const\s+meta\s*=\s*/.exec(blank(src))
  if (!m) throw new Fatal('o script precisa começar com `export const meta = {...}`')
  const start = m.index + m[0].length
  if (src[start] !== '{') throw new Fatal('meta precisa ser um objeto literal')
  let depth = 0, i = start, q = null
  for (; i < src.length; i++) {
    const c = src[i]
    if (q) { if (c === '\\') i++; else if (c === q) q = null; continue }
    if (c === '"' || c === "'" || c === '`') q = c
    else if (c === '{') depth++
    else if (c === '}') { depth--; if (depth === 0) break }
  }
  if (depth !== 0) throw new Fatal('meta: chaves não fecham')
  const literal = src.slice(start, i + 1)
  let end = i + 1
  while (/[ \t]/.test(src[end] ?? '')) end++
  if (src[end] === ';') end++
  let meta
  try { meta = new Function(`"use strict"; return (${literal})`)() } catch (e) { throw new Fatal(`meta não é um literal puro: ${e.message}`) }
  if (!meta || typeof meta.name !== 'string' || typeof meta.description !== 'string') throw new Fatal('meta precisa de name e description (texto)')
  return { meta, body: src.slice(0, m.index) + src.slice(end) }
}

function checkUnsupported(body) {
  const clean = blank(body)
  for (const g of UNSUPPORTED_GLOBALS) {
    const declared = new RegExp(`(?:const|let|var|function)\\s+${g}\\b|[(,]\\s*${g}\\s*[,)=]`).test(clean)
    if (declared) continue
    if (new RegExp(`(?<![.\\w$])${g}\\s*[(.]`).test(clean)) {
      throw new Fatal(`\`${g}\` não é suportado nesta versão do batch (subconjunto: meta, args, phase, agent, parallel, pipeline)`)
    }
  }
}

// ---- schema (subconjunto: type, required, properties, items, enum) ----
const KNOWN_KW = new Set(['type', 'required', 'properties', 'items', 'enum', 'description', 'title', 'additionalProperties', 'default', '$schema'])
const warned = new Set()
function typeOk(v, t) {
  if (t === 'null') return v === null
  if (t === 'array') return Array.isArray(v)
  if (t === 'object') return v !== null && typeof v === 'object' && !Array.isArray(v)
  if (t === 'integer') return Number.isInteger(v)
  if (t === 'number') return typeof v === 'number' && Number.isFinite(v)
  return typeof v === t
}
function validate(v, s, path = '$') {
  const errs = []
  if (!s || typeof s !== 'object') return errs
  for (const k of Object.keys(s)) {
    if (!KNOWN_KW.has(k) && !warned.has(k)) { warned.add(k); console.error(`batch: aviso: a palavra-chave de schema '${k}' é ignorada`) }
  }
  if (s.type !== undefined) {
    const ts = Array.isArray(s.type) ? s.type : [s.type]
    if (!ts.some((t) => typeOk(v, t))) return [`${path}: esperava ${ts.join('|')}`]
  }
  if (s.enum && !s.enum.some((e) => JSON.stringify(e) === JSON.stringify(v))) errs.push(`${path}: fora do enum ${JSON.stringify(s.enum)}`)
  if (typeOk(v, 'object')) {
    for (const r of s.required ?? []) if (!(r in v)) errs.push(`${path}.${r}: obrigatório ausente`)
    for (const [k, sub] of Object.entries(s.properties ?? {})) if (k in v) errs.push(...validate(v[k], sub, `${path}.${k}`))
  }
  if (Array.isArray(v) && s.items) v.forEach((x, i) => errs.push(...validate(x, s.items, `${path}[${i}]`)))
  return errs
}
function lastJson(text) {
  const blocks = [...text.matchAll(/```(?:json)?[ \t]*\n([\s\S]*?)```/g)]
  const cands = blocks.map((b) => b[1])
  if (!cands.length) cands.push(text)
  const last = cands[cands.length - 1].trim()
  try { return { value: JSON.parse(last) } } catch (e) { return { error: `o último bloco não é JSON válido: ${e.message}` } }
}

// ---- estado, journal, progresso ----
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 30) || 'x'
const { meta, body } = (() => {
  try { return extractMeta(source) } catch (e) { console.error(`batch: ${e.message}`); process.exit(2) }
})()
try { checkUnsupported(body) } catch (e) { console.error(`batch: ${e.message}`); process.exit(2) }
let fn
try { fn = new AsyncFunction('agent', 'parallel', 'pipeline', 'phase', 'args', 'meta', `"use strict";\n${body}`) } catch (e) {
  console.error(`batch: erro de sintaxe no script: ${e.message}`)
  process.exit(2)
}

const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '').replace('T', '-')
mkdirSync(join(RUNS_DIR, 'batches'), { recursive: true })
let batchId = `${stamp}-${slug(meta.name)}`, bdir
for (let n = 0; ; n++) {
  bdir = join(RUNS_DIR, 'batches', n ? `${batchId}-${n}` : batchId)
  try { mkdirSync(bdir); break } catch (e) { if (e.code !== 'EEXIST') throw e }
}
batchId = bdir.split('/').pop()
copyFileSync(scriptPath, join(bdir, 'script.mjs'))
const journalFile = join(bdir, 'journal.jsonl')
const journal = (ev) => appendFileSync(journalFile, JSON.stringify({ t: new Date().toISOString(), ...ev }) + '\n')
const say = (m) => console.error(`[batch ${batchId}] ${m}`)

// ---- semáforo e subprocessos ----
class Sem {
  constructor(n) { this.n = n; this.q = [] }
  async acquire() { if (this.n > 0) { this.n--; return } await new Promise((r) => this.q.push(r)) }
  release() { const r = this.q.shift(); if (r) r(); else this.n++ }
}
const sem = new Sem(max)
let running = 0, peak = 0, counter = 0, aborted = null
const children = new Set(), inflight = new Set(), agents = [], failures = []

function runSh(script, args, input) {
  return new Promise((res) => {
    const c = spawn('sh', [join(HERE, script), ...args], { stdio: ['pipe', 'pipe', 'pipe'], env: process.env })
    children.add(c)
    let out = '', err = ''
    c.stdout.on('data', (d) => (out += d))
    c.stderr.on('data', (d) => (err += d))
    c.on('close', (code) => { children.delete(c); res({ code, out, err }) })
    c.stdin.on('error', () => {})
    c.stdin.end(input ?? '')
  })
}

// ---- API do script ----
let curPhase = null
function phase(title) {
  if (typeof title !== 'string' || !title) throw new Fatal('phase(title): título obrigatório')
  curPhase = title
  journal({ ev: 'phase', title })
  say(`fase: ${title}`)
}

async function agent(prompt, opts = {}) {
  if (aborted) throw new Fatal(`batch abortado: ${aborted}`)
  if (typeof prompt !== 'string' || !prompt.trim()) throw new Fatal('agent(prompt): prompt precisa ser texto não vazio')
  if (opts === null || typeof opts !== 'object') throw new Fatal('agent(prompt, opts): opts precisa ser um objeto')
  for (const k of Object.keys(opts)) {
    if (!ALLOWED_OPTS.includes(k)) throw new Fatal(`agent: opção não suportada '${k}' (aceitas: ${ALLOWED_OPTS.join(', ')})`)
  }
  if (opts.mode === 'dangerous') throw new Fatal('agent: o modo dangerous não é aceito')
  if (opts.out !== undefined && (opts.out === null || typeof opts.out !== 'object')) throw new Fatal('agent: out precisa ser um objeto')
  const n = ++counter
  const label = opts.label ?? `agent-${n}`
  const ph = opts.phase ?? curPhase
  let full = prompt
  if (opts.schema) {
    full += `\n\n---\nResponda ao final com um único bloco de código \`\`\`json contendo um objeto JSON que obedeça a este JSON Schema, e nada depois dele:\n${JSON.stringify(opts.schema, null, 2)}\n`
  }
  await sem.acquire()
  running++
  peak = Math.max(peak, running)
  const rec = { n, label, phase: ph ?? null, status: 'running' }
  agents.push(rec)
  const p = (async () => {
    try {
      if (aborted) throw new Fatal(`batch abortado: ${aborted}`)
      say(`${label}: disparando`)
      journal({ ev: 'agent_start', n, label, phase: ph, running })
      const args = ['--repo', repo, '--stdin', '--name', `${n}-${slug(label)}`]
      if (opts.model) args.push('--model', opts.model)
      if (opts.mode) args.push('--mode', opts.mode)
      if (opts.base) args.push('--base', opts.base)
      let r
      for (let t = 0; t < 3; t++) {
        r = await runSh('run.sh', args, full)
        if (r.code === 0 || !/lock|File exists/i.test(r.err)) break
        await new Promise((x) => setTimeout(x, 700 * (t + 1)))
      }
      if (r.code !== 0) throw new Error(`run.sh falhou (${r.code}): ${r.err.trim()}`)
      const id = r.out.trim()
      rec.id = id
      rec.branch = `devin/${id}`
      journal({ ev: 'agent_run', n, label, id })
      const w = await runSh('wait.sh', [id])
      const state = w.out.trim().split('\n').pop()
      if (state !== 'done') {
        let tail = ''
        try { tail = readFileSync(join(RUNS_DIR, id, 'log.txt'), 'utf8').trim().split('\n').slice(-5).join(' | ') } catch {}
        throw new Error(`rodada ${id} terminou em '${state}' (wait ${w.code})${tail ? `: ${tail}` : ''}`)
      }
      const text = readFileSync(join(RUNS_DIR, id, 'answer.txt'), 'utf8').trimEnd()
      let result = text
      if (opts.schema) {
        const j = lastJson(text)
        if (j.error) throw new Error(`schema: ${j.error}`)
        const errs = validate(j.value, opts.schema)
        if (errs.length) throw new Error(`schema inválido: ${errs.slice(0, 5).join('; ')}`)
        result = j.value
        if (result !== null && typeof result === 'object') {
          Object.defineProperty(result, 'branch', { value: rec.branch, enumerable: false })
          Object.defineProperty(result, 'runId', { value: id, enumerable: false })
        }
      }
      if (opts.out) { opts.out.id = id; opts.out.branch = rec.branch }
      rec.status = 'ok'
      journal({ ev: 'agent_end', n, label, id, status: 'ok' })
      say(`${label}: ok (${id})`)
      return result
    } catch (e) {
      rec.status = 'failed'
      rec.error = e.message
      if (!e.fatal) failures.push({ n, label, id: rec.id ?? null, error: e.message })
      journal({ ev: 'agent_end', n, label, id: rec.id ?? null, status: 'failed', error: e.message })
      say(`${label}: FALHOU: ${e.message}`)
      throw e
    } finally {
      running--
      sem.release()
    }
  })()
  inflight.add(p)
  p.then(() => inflight.delete(p), () => inflight.delete(p))
  return p
}

async function parallel(thunks) {
  if (!Array.isArray(thunks)) throw new Fatal('parallel(thunks): precisa de um array de funções')
  for (const t of thunks) if (typeof t !== 'function') throw new Fatal('parallel: cada item precisa ser uma função () => ...')
  return Promise.all(thunks.map(async (t) => {
    try { return await t() } catch (e) { if (e && e.fatal) throw e; return null }
  }))
}

async function pipeline(items, ...stages) {
  if (!Array.isArray(items)) throw new Fatal('pipeline(items, ...stages): items precisa ser um array')
  for (const s of stages) if (typeof s !== 'function') throw new Fatal('pipeline: cada etapa precisa ser uma função (anterior, item, índice) => ...')
  return Promise.all(items.map(async (item, i) => {
    try {
      let prev = item
      for (const s of stages) prev = await s(prev, item, i)
      return prev
    } catch (e) { if (e && e.fatal) throw e; return null }
  }))
}

// ---- execução ----
function finish(state, result, error) {
  const out = { batch: batchId, name: meta.name, state, result: result ?? null, error: error ?? null, failures, agents, peak, max }
  writeFileSync(join(bdir, 'result.json'), JSON.stringify(out, null, 2) + '\n')
  journal({ ev: 'batch_end', state, failures: failures.length, peak })
}
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(sig, () => {
    aborted = sig
    for (const c of children) c.kill('SIGTERM')
    finish('interrupted', null, sig)
    say(`interrompido por ${sig}; os Devins já disparados seguem (veja check.sh)`)
    process.exit(130)
  })
}

journal({ ev: 'batch_start', name: meta.name, repo, max, args: scriptArgs ?? null })
say(`${meta.name}: ${meta.description} (max ${max})`)
let code = 0
try {
  const result = await fn(agent, parallel, pipeline, phase, scriptArgs, meta)
  const bad = failures.length > 0
  finish(bad ? 'failed' : 'ok', result, bad ? `${failures.length} etapa(s) falharam` : null)
  process.stdout.write(JSON.stringify(result ?? null) + '\n')
  if (bad) { say(`${failures.length} etapa(s) falharam: ${failures.map((f) => f.label).join(', ')}`); code = 1 }
} catch (e) {
  aborted = e.message
  await Promise.allSettled([...inflight])
  const msg = e instanceof ReferenceError ? `${e.message} (fora do subconjunto suportado: meta, args, phase, agent, parallel, pipeline)` : e.message
  finish('failed', null, msg)
  console.error(`batch: o script falhou: ${msg}`)
  code = e.fatal || e instanceof ReferenceError ? 2 : 1
  if (!e.fatal && !(e instanceof ReferenceError)) code = 1
}
process.exit(code)
