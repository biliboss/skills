# Company finance: a client contract, its taxes and the split

When the owner talks about what a contract leaves after tax and costs (a renewal, a client's monthly entry, how the
money is divided), the answer is an interactive HTML report in his dev-console (`devc browse`, see skill
`dev-console`, Browser) plus the facts on the wiki page of the company. Estimates are fine; say which number came
from him and which is assumed.

## Procedure

1. **Get the structure right before any number.** Who are the partners, who operates, who is a PJ provider. A
   person the transcript treats as a partner may be a PJ: ask or check the wiki, and fix the wiki page in place when
   he corrects it. It changes how each one receives (profit distribution, tax-free, vs. payment against an invoice,
   taxed on the provider's side) and what counts as payroll.
2. **Take the monthly entry he gives** (the real figure beats the transcript's rounded one) and compute the Simples
   Nacional on that entry alone (formulas below).
3. **Default to the annex with the higher rate** (Anexo V for services without fator R). He asked for the
   conservative case; the cheaper annex is a toggle, never the headline.
4. **List costs as he listed them**, in his order (general costs and tax first, people last), each with % of the
   entry; total, then the remainder before the split, then the split. A budget he adds later (infrastructure) is its
   own row, outside his "tax and operations" rule unless he says otherwise.
5. **Every scenario he names is a toggle**, and a dependent scenario is enabled only when its parent is (a partial
   payment to a person only exists when that person is in). A free amount gets a range slider, starting at half. The
   page opens on the scenario they decided (when a conversation settles one, make it the default).
6. **Verify with a headless browser before reporting**: a uv Playwright script (`chromium.launch(channel="chrome")`)
   opens each state by its URL, reads the `data-k` values and page errors; report the table of scenarios it printed.

## Simples Nacional on one entry

- RBT12 = monthly entry × 12 (a company with under 12 months uses another average: the accountant confirms).
- Effective rate = (RBT12 × nominal − deduction) / RBT12. Second band (R$ 180 mil to R$ 360 mil):
  Anexo III 11,2% − R$ 9.360; Anexo V 18% − R$ 4.500. First band (up to R$ 180 mil): III 6%, V 15,5%, no deduction.
- **Fator R** (Anexo V → III): payroll of 12 months ≥ 28% of RBT12. Payroll is pró-labore plus salaries: a PJ
  provider never counts, and a partner who does not operate needs no pró-labore. So the minimum pró-labore to enter
  Anexo III is the operating partner's alone: **0,28 × monthly entry**, recomputed when the entry changes. It is a
  12-month ratio, so raising it today only crosses 28% as the low months leave the window (the accountant simulates
  month by month); below the threshold there is no partial gain, only more INSS and IR.
- **Net gain of fator R** = tax saved − INSS 11% of the pró-labore − IR on (pró-labore − INSS) by the monthly table
  (the 2026 exemption up to R$ 5 mil, with a reducer up to R$ 7.350; above it the plain table). In Anexo III the
  company's INSS (CPP) is inside the Simples.
- **The INSS is not lost money**: it builds the partner's retirement (on a pró-labore near the INSS ceiling, a benefit
  near the ceiling; on the minimum wage, a minimum-wage retirement). Only the IR is pure cost. Say both when
  comparing his net with the other side's.
- **When the operating partner declares the minimum pró-labore** (one minimum wage) and takes the rest as profit, the
  fator R is far below 28% and the company stays in Anexo V: that is the real case, and the Anexo III toggle is
  labelled with what it takes ("exige pró-labore de R$ X"). His net still loses the INSS 11% of the minimum pró-labore
  (no IR under R$ 5 mil). The way to Anexo III without a big pró-labore is payroll: a PJ hired under CLT counts
  (salary plus FGTS).
- **Profit distribution is tax-free only up to the profit the books prove.** Without full bookkeeping the presumed
  limit is 32% of the revenue minus the Simples paid; above it the excess can be taxed as income: tell him to confirm
  the accountant keeps full books. The 2026 withholding on dividends (10%) only applies above R$ 50 mil a month from
  one company to one person.
- **Say who bears it.** The pró-labore's INSS and IR fall on the operating partner alone: with a 50/50 split the
  other side (partner or PJ) takes half the tax saving and the operator can end up below the Anexo V case. Show his
  net after those taxes, explain the difference in the current state (which tax, how much, why only he pays it), and
  propose charging them as a company cost before the split. A PJ's part is optimistic: his invoice tax is not deducted.

## The report

- One data object in the page's script (entry, fixed costs, tax per annex, people) and one `draw()` that fills every
  `[data-k]` element; toggles call `draw()`. Never two static copies of each number per scenario: a third scenario
  makes them diverge.
- **Few elements, sticky controls.** One bar fixed at the top (`position: sticky`) with the controls (one segmented
  control per choice, not a toggle per option) and the few live numbers that matter (remainder, each person's part and
  hours); then a short document: one answer sentence, ONE month table (the rows that change highlighted), one dynamic
  paragraph on the split and the difference, ONE table of every scenario, a short notes list (facts, decisions, open
  questions). No duplicate cards, chips or sections that repeat a number; when he asks to cut elements, count
  `document.querySelectorAll('body *').length` before and after and keep every number identical per state.
- **The state lives in the URL** (`#a3=1&sem=0&parcial=1&t=2750`): restored on load, rewritten with
  `history.replaceState` on every change, plus a "copiar link deste cenário" button (the console's address line shows
  the frame's first URL, not its hash).
- Check his stated rules against the numbers and say when they do not close ("20% for tax and operations" vs. what
  tax, bookkeeping and admin actually add up to), and compare each one's part with the monthly amount he said is safe.
- **The hours budget** (what each one can give the contract): his ruler is "R$ 20 mil no bolso = 5 h por dia" on an
  **escala 4x3** (4 working days a week, 52/12 × 4 ≈ 17,3 a month), so every R$ 4.000 a month buys one hour a day.
  Show each person's net as hours per day and per week (× 4) and, as the label under it, full days of 5 h per month
  (net / 20.000 × 17,3) and per week; one card per person following the toggles, plus a table of every scenario. The
  operating partner counts with his net after pró-labore taxes; a PJ's hours are a ceiling (his invoice tax is unknown).
- Serve from `~/.local/share/bili-reports/` (http.server on 4400) and `devc browse` it; a new version is a new file
  when the old one cannot be read whole first. Patch the page with small Python scripts that assert each replacement.
