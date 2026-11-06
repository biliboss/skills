# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "wordfreq>=3.1",
#   "spacy>=3.8,<3.9",
#   "pt_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl",
# ]
# ///
"""Métricas de prosa para um rascunho do Gabriel, com a faixa-alvo de cada uma.

A métrica é régua, não juiz: ela mostra onde o texto foge do que o Gabriel já
aprovou. A palavra final é o gosto dele. As métricas e as faixas estão
explicadas em .wiki/copywriting-metricas.md.

Uso:
  uv run scripts/metricas.py rascunho.md
  cat rascunho.md | uv run scripts/metricas.py
  uv run scripts/metricas.py doc.md --secao Post   # só a seção "## Post…"
  uv run scripts/metricas.py rascunho.md --json
  uv run scripts/metricas.py --pares                # aprovado x reprovado da voz
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
import unicodedata

# ---------------------------------------------------------------- faixas-alvo
# A referência principal é o Diário #01, a régua de estilo da série (regra 21
# da voz): cada faixa cobre o valor dele com folga. As frases aprovadas e
# reprovadas da página da voz ajustam o lado (ex.: 1ª pessoa). Ver
# .wiki/copywriting-metricas.md.
# (mín, máx); None = sem limite daquele lado.
FAIXAS = {
    "palavras_por_frase": (5, 11),
    "burstiness_cv": (0.45, None),
    "frases_longas_pct": (None, 10),        # frases com mais de 20 palavras
    "palavras_por_paragrafo": (None, 20),
    "paragrafos_curtos_pct": (85, None),    # parágrafos com até 2 frases
    "subordinadas_por_frase": (None, 0.7),
    "substantivos_por_verbo": (None, 1.2),
    "nominalizacoes_100": (None, 4.0),
    "contraste_pct": (5, 30),              # frases com contraste
    "formula_nao_e_x_e_y": (None, 1),       # "não é X, é Y" por texto
    "perguntas_pct": (3, 15),
    "imperativos_pct": (2, 15),
    "primeira_pessoa_100": (None, 8.0),
    "segunda_pessoa_100": (1.0, None),
    "raras_pct": (None, 5.0),               # palavras de conteúdo com Zipf < 3
    "flesch_pt": (50, None),
}

ROTULOS = {
    "palavras_por_frase": "Palavras por frase (média)",
    "burstiness_cv": "Variação do tamanho da frase (burstiness, CV)",
    "frases_longas_pct": "Frases com mais de 20 palavras (%)",
    "palavras_por_paragrafo": "Palavras por parágrafo (média)",
    "paragrafos_curtos_pct": "Parágrafos com até 2 frases (%)",
    "subordinadas_por_frase": "Subordinadas por frase",
    "coordenadas_por_frase": "Coordenadas por frase",
    "substantivos_por_verbo": "Substantivos por verbo (voz nominal)",
    "nominalizacoes_100": "Nominalizações (-ção, -mento…) por 100 palavras",
    "contraste_pct": "Frases com contraste (%)",
    "formula_nao_e_x_e_y": "Fórmula \"não é X, é Y\" (vezes)",
    "perguntas_pct": "Perguntas (% das frases)",
    "imperativos_pct": "Imperativos (% das frases)",
    "primeira_pessoa_100": "1ª pessoa do singular por 100 palavras",
    "segunda_pessoa_100": "2ª pessoa (você, te…) por 100 palavras",
    "raras_pct": "Palavras raras (Zipf < 3, %)",
    "zipf_medio": "Frequência média das palavras (Zipf)",
    "flesch_pt": "Flesch adaptado ao português",
}

# ---------------------------------------------------------------- pares da voz
# Aprovado x reprovado, copiados de .wiki/marketing-pessoal-voz.md.
PARES = [
    ("abertura com imagem",
     "Todo mundo quer um robô na recepção. Eu mandei os meus para o porão.",
     "Todo mundo quer colocar IA para atender o cliente. Eu estou fazendo o contrário."),
    ("toda frase trabalha",
     "A Velumma, meu cliente novo, é um BPO financeiro de três sócias que conhecem cada cliente pelo nome. E elas querem atender muito mais gente.",
     "Peguei um cliente novo: a Velumma, um BPO financeiro. Em breve conto mais."),
    ("abertura sem eu (regra 19)",
     "Quem vende a ferramenta nunca é o melhor juiz dela.",
     "Tem empresa colocando robô para atender gente. Eu estou usando robô para gente poder atender gente."),
    ("coesão (regra 15)",
     "Ninguém compra uma parafusadeira sem saber o que vai montar.",
     "E olha que eu não tenho nada contra a IA."),
]
APROVADAS_SOLTAS = [
    "O mercado inventou o robô que atende 24 horas. Agora só falta inventar o cliente que quer ser atendido por ele.",
    "Automatizar um processo ruim só acelera o erro.",
    "Vendedor de faca jura que ela corta tudo. Quem sabe se corta bem é quem cozinha.",
    "Começou com uma mulher só, cuidando por conta própria do financeiro de várias empresas. Um dia ela chamou as amigas.",
    "Três sócias, mais vividas, que curtem um pagode.",
]

# ---------------------------------------------------------------- léxico
PRIMEIRA_SG = {"eu", "me", "mim", "meu", "meus", "minha", "minhas", "comigo"}
PRIMEIRA_PL = {"nós", "nos", "nosso", "nossos", "nossa", "nossas", "conosco"}
SEGUNDA = {"você", "vocês", "te", "ti", "tu", "contigo", "teu", "teus", "tua", "tuas",
           "seu", "seus", "sua", "suas", "vc", "vcs"}
IMPERATIVOS = {
    "imagina", "imagine", "pensa", "pense", "olha", "olhe", "veja", "vê", "repara", "repare",
    "lembra", "lembre", "lembre-se", "faça", "faz", "pare", "use", "usa", "aprenda", "aprende",
    "conta", "conte", "comece", "começa", "escreva", "escreve", "leia", "tente", "tenta",
    "experimente", "pergunte", "responda", "deixe", "deixa", "venha", "pegue", "pega", "clique",
    "assista", "participe", "compre", "garanta", "inscreva-se", "acesse", "baixe", "descubra",
    "entenda", "siga", "segue", "confira", "anote", "guarde", "esqueça", "esquece", "escolha",
    "escolhe", "mande", "manda", "diga", "diz", "fale", "fala", "corra", "cuide", "cuida",
    "vem", "bora", "vamos", "choose", "pick",
}
NOMINALIZACAO = re.compile(r"(ção|ções|são|sões|mento|mentos|dade|dades|ância|ências|ência|ância|ismo|ismos|agem|agens)$")
VOGAIS = "aeiouáéíóúâêôãõàü"
DITONGOS = {"ai", "ei", "oi", "ui", "au", "eu", "ou", "iu", "ãe", "ão", "õe", "ãi", "éu", "éi", "ói"}


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- texto
def ler_texto(caminho: str | None) -> str:
    if caminho and caminho != "-":
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def recortar_secao(md: str, nome: str) -> str:
    """Devolve o texto sob o primeiro título que contém `nome`, até o próximo título do mesmo nível ou uma linha ---."""
    linhas = md.splitlines()
    for i, l in enumerate(linhas):
        m = re.match(r"^(#{1,6})\s+(.*)", l)
        if m and nome.lower() in m.group(2).lower():
            nivel = len(m.group(1))
            fim = len(linhas)
            for j in range(i + 1, len(linhas)):
                m2 = re.match(r"^(#{1,6})\s", linhas[j])
                if (m2 and len(m2.group(1)) <= nivel) or linhas[j].strip() == "---":
                    fim = j
                    break
            return "\n".join(linhas[i + 1:fim])
    sys.exit(f"seção '{nome}' não encontrada")


def limpar_markdown(md: str) -> str:
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)              # imagens
    md = re.sub(r"\[([^\]]*)\]\(<?[^)]*>?\)", r"\1", md)       # links
    md = re.sub(r"`[^`]*`", "", md)
    out = []
    for l in md.splitlines():
        s = l.strip()
        if re.match(r"^#{1,6}\s", s) or s in {"---", "***"}:
            out.append("")
            continue
        s = re.sub(r"^[>*\-+]\s+", "", s)
        s = s.replace("**", "").replace("__", "")
        s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+)\*", r"\1", s)
        s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", s)
        out.append(s)
    return "\n".join(out)


def paragrafos(texto: str) -> list[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]


FIM_FRASE = re.compile(r"(?<=[.!?…])[\"”’)]*\s+(?=[\"“‘(]?[A-ZÀ-Ý0-9])")


def frases(par: str) -> list[str]:
    return [f.strip() for f in FIM_FRASE.split(par) if f.strip()]


PALAVRA = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:-[A-Za-zÀ-ÿ]+)*")


def palavras(s: str) -> list[str]:
    return PALAVRA.findall(s)


def silabas(w: str) -> int:
    w = w.lower()
    if w.isdigit():
        return max(1, len(w))  # "424" lido como "quatrocentos e vinte e quatro" teria mais; aproximação
    w = re.sub(r"q(u)(?=[eiaoé])", "q", w)
    w = re.sub(r"g(u)(?=[eié])", "g", w)
    # Divisão escolar aproximada: ditongo decrescente (pai, céu) e crescente (história, água)
    # contam uma sílaba; vogal com acento agudo depois de outra (saída, país) abre sílaba.
    n = 0
    for grupo in re.findall(f"[{VOGAIS}]+", w):
        n += 1
        junto = False
        for a, b in zip(grupo, grupo[1:]):
            une = not junto and (
                a + b in DITONGOS
                or (a in "aeoáéóâêô" and b in "iu")
                or (a in "iu" and b in "aeoáéóâêôãõ")
            )
            junto = une
            if not une:
                n += 1
    return max(1, n)


# ---------------------------------------------------------------- métricas
def contraste(f: str) -> tuple[bool, bool]:
    s = f.lower()
    formula = bool(re.search(r"\bnão (é|são|era|foi|seja|está)\b[^.!?]{1,70}?[,;:—–.]\s*(é|são|era|foi|seja|está|mas)\b", s))
    outros = bool(re.search(r"\b(mas|porém|contudo|entretanto|só que|e sim|em vez de|ao invés de|ao contrário|no entanto|todavia|e mesmo assim|mesmo assim)\b", s))
    return formula, formula or outros


def eh_imperativo(f: str, doc_frase) -> bool:
    ws = [w.lower() for w in palavras(f)]
    if not ws:
        return False
    i = 1 if ws[0] in {"não", "e", "então", "agora", "só", "me", "por", "favor"} and len(ws) > 1 else 0
    if ws[i] in IMPERATIVOS or (ws[0] == "me" and len(ws) > 1 and ws[1] in IMPERATIVOS):
        return not f.rstrip().endswith("?") or ws[i] in {"imagina", "olha", "pensa"}
    return any("Imp" in t.morph.get("Mood") for t in doc_frase)


NAO_VERBO_EI = {"lei", "leis", "rei", "reis", "grei", "sei-lá"}


def eh_primeira_pessoa(t, d) -> bool:
    """O pronome (eu, me, meu…) ou o verbo na 1ª do singular sem "eu" antes (criei, estou).

    O spaCy pequeno erra o pretérito no começo da frase ("Peguei" vira nome próprio);
    por isso a palavra terminada em -ei também conta."""
    low = t.text.lower()
    if low in PRIMEIRA_SG:
        return True
    if t.i > 0 and d[t.i - 1].text.lower() == "eu":
        return False
    if t.pos_ in {"VERB", "AUX"} and "1" in t.morph.get("Person") and "Sing" in t.morph.get("Number"):
        return True
    return t.is_alpha and len(low) >= 4 and low.endswith("ei") and low not in NAO_VERBO_EI


def medir(texto: str, nlp, zipf) -> dict:
    pars = paragrafos(texto)
    fr_por_par = [frases(p) for p in pars]
    fs = [f for lst in fr_por_par for f in lst]
    if not fs:
        sys.exit("texto vazio")
    tam = [len(palavras(f)) for f in fs]
    ws = [w for f in fs for w in palavras(f)]
    nw = len(ws)
    m = {}
    m["frases"] = len(fs)
    m["paragrafos"] = len(pars)
    m["palavras"] = nw
    m["palavras_por_frase"] = st.mean(tam)
    m["mediana_palavras_por_frase"] = st.median(tam)
    m["burstiness_cv"] = (st.pstdev(tam) / st.mean(tam)) if len(tam) > 1 else 0.0
    m["frases_longas_pct"] = 100 * sum(t > 20 for t in tam) / len(fs)
    m["frase_mais_longa"] = max(tam)
    pal_par = [len(palavras(p)) for p in pars]
    m["palavras_por_paragrafo"] = st.mean(pal_par)
    m["paragrafos_curtos_pct"] = 100 * sum(len(x) <= 2 for x in fr_por_par) / len(pars)

    sub = coord = nomes = verbos = 0
    p1 = p2 = 0
    imp = 0
    pessoa = {"1": 0, "2": 0, "3": 0}
    conteudo = []
    for f in fs:
        d = nlp(f)
        if eh_imperativo(f, d):
            imp += 1
        for t in d:
            low = t.text.lower()
            if t.dep_ == "mark" or (t.pos_ == "SCONJ") or "Rel" in t.morph.get("PronType"):
                sub += 1
            elif t.pos_ == "CCONJ" and t.head.pos_ in {"VERB", "AUX"}:
                coord += 1
            if t.pos_ in {"NOUN", "PROPN"}:
                nomes += 1
            if t.pos_ in {"VERB", "AUX"}:
                verbos += 1
                if "Fin" in t.morph.get("VerbForm") or t.morph.get("Person"):
                    for p in t.morph.get("Person"):
                        pessoa[p] = pessoa.get(p, 0) + 1
            if eh_primeira_pessoa(t, d):
                p1 += 1
            if low in SEGUNDA:
                p2 += 1
            if t.is_alpha and not t.is_stop and t.pos_ in {"NOUN", "VERB", "ADJ", "ADV"}:
                conteudo.append((low, t.lemma_.lower()))
    m["subordinadas_por_frase"] = sub / len(fs)
    m["coordenadas_por_frase"] = coord / len(fs)
    m["substantivos_por_verbo"] = nomes / max(1, verbos)
    m["nominalizacoes_100"] = 100 * sum(bool(NOMINALIZACAO.search(w.lower())) and len(w) > 5 for w in ws) / nw
    cont = [list(contraste(f)) for f in fs]
    # "não é X." + "É Y." em duas frases seguidas também é a fórmula (o fecho do Diário #01)
    for i in range(len(fs) - 1):
        if (re.search(r"\bnão (é|são|era|foi|seja|está)\b", fs[i].lower())
                and re.match(r"^[\"“]?(é|são|era|foi|seja|está)\b", fs[i + 1].lower())):
            cont[i + 1] = [True, True]
    m["formula_nao_e_x_e_y"] = sum(c[0] for c in cont)
    m["contraste_pct"] = 100 * sum(c[1] for c in cont) / len(fs)
    m["perguntas_pct"] = 100 * sum(f.rstrip("\"”’) ").endswith("?") for f in fs) / len(fs)
    m["imperativos_pct"] = 100 * imp / len(fs)
    m["primeira_pessoa_100"] = 100 * p1 / nw
    m["segunda_pessoa_100"] = 100 * p2 / nw
    m["verbos_por_pessoa"] = pessoa
    zs = [zipf(w, "pt") for w, _ in conteudo]
    raras = sorted({w for (w, _), z in zip(conteudo, zs) if z < 3.0})
    m["raras_pct"] = 100 * len([z for z in zs if z < 3.0]) / max(1, len(zs))
    m["raras"] = raras
    m["zipf_medio"] = st.mean(zs) if zs else 0.0
    sil = sum(silabas(w) for w in ws)
    m["flesch_pt"] = 248.835 - 1.015 * (nw / len(fs)) - 84.6 * (sil / nw)
    # repetição: lemas de conteúdo que voltam (o refrão) e anáforas (frases seguidas que começam igual)
    cont_lemas = {}
    for _, lem in conteudo:
        cont_lemas[lem] = cont_lemas.get(lem, 0) + 1
    m["repetidas"] = sorted([(k, v) for k, v in cont_lemas.items() if v >= 2], key=lambda x: -x[1])[:8]
    inicios = [sem_acento(palavras(f)[0].lower()) for f in fs if palavras(f)]
    m["anaforas"] = sum(a == b for a, b in zip(inicios, inicios[1:]))
    # abertura (o gancho em até duas frases, regras 19 e 21) e fecho (regra 12)
    primeira = " ".join(fs[:2])
    m["abertura"] = primeira
    da = nlp(primeira)
    m["abertura_sem_eu"] = not any(eh_primeira_pessoa(t, da) for t in da)
    ult = [f for f in fs if not re.match(r"^Diário de um Dev", f)]
    m["fecho"] = ult[-1] if ult else fs[-1]
    m["fecho_e_pergunta"] = m["fecho"].rstrip().endswith("?")
    return m


def status(chave: str, v: float) -> str:
    if chave not in FAIXAS:
        return " "
    lo, hi = FAIXAS[chave]
    if lo is not None and v < lo:
        return "↓"
    if hi is not None and v > hi:
        return "↑"
    return "ok"


def faixa_txt(chave: str) -> str:
    if chave not in FAIXAS:
        return "—"
    lo, hi = FAIXAS[chave]
    if lo is None:
        return f"≤ {hi:g}"
    if hi is None:
        return f"≥ {lo:g}"
    return f"{lo:g}–{hi:g}"


def relatorio(m: dict) -> str:
    l = [f"{m['palavras']} palavras · {m['frases']} frases · {m['paragrafos']} parágrafos", ""]
    l.append(f"{'métrica':<50} {'valor':>7}  {'faixa':>9}  ")
    for k in ROTULOS:
        v = m[k]
        l.append(f"{ROTULOS[k]:<50} {v:>7.2f}  {faixa_txt(k):>9}  {status(k, v)}")
    vp = m["verbos_por_pessoa"]
    l += [
        "",
        f"Verbos por pessoa: 1ª {vp.get('1', 0)} · 2ª {vp.get('2', 0)} · 3ª {vp.get('3', 0)}",
        f"Frase mais longa: {m['frase_mais_longa']} palavras · mediana {m['mediana_palavras_por_frase']:g}",
        f"Repetidas (refrão?): {', '.join(f'{k} ×{v}' for k, v in m['repetidas']) or '—'}",
        f"Anáforas (frases seguidas que começam igual): {m['anaforas']}",
        f"Raras: {', '.join(m['raras']) or '—'}",
        f"Abertura sem \"eu\" (regra 19): {'sim' if m['abertura_sem_eu'] else 'NÃO'} → {m['abertura']}",
        f"Fecho é pergunta (regra 12): {'sim' if m['fecho_e_pergunta'] else 'NÃO'} → {m['fecho']}",
        "",
        "ok = dentro da faixa · ↑ acima · ↓ abaixo. A métrica é régua, não juiz: a palavra final é do Gabriel.",
    ]
    return "\n".join(l)


def pares(nlp, zipf) -> str:
    chaves = ["palavras_por_frase", "burstiness_cv", "subordinadas_por_frase", "substantivos_por_verbo",
              "primeira_pessoa_100", "raras_pct", "zipf_medio", "flesch_pt"]
    cab = f"{'par':<28} {'lado':<10}" + "".join(f"{c[:12]:>13}" for c in chaves) + "  abre sem eu"
    l = [cab]
    for nome, ap, rep in PARES:
        for lado, t in (("aprovado", ap), ("reprovado", rep)):
            m = medir(t, nlp, zipf)
            l.append(f"{nome:<28} {lado:<10}" + "".join(f"{m[c]:>13.2f}" for c in chaves)
                     + f"  {'sim' if m['abertura_sem_eu'] else 'não'}")
    a = medir("\n\n".join([p[1] for p in PARES] + APROVADAS_SOLTAS), nlp, zipf)
    r = medir("\n\n".join(p[2] for p in PARES), nlp, zipf)
    l.append("")
    for lado, m in (("TODOS aprovados", a), ("TODOS reprovados", r)):
        l.append(f"{lado:<39}" + "".join(f"{m[c]:>13.2f}" for c in chaves))
    return "\n".join(l)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", nargs="?", help="rascunho em markdown ou texto (sem arquivo, lê o stdin)")
    ap.add_argument("--secao", help="mede só a seção cujo título contém este texto (ex.: Post)")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--pares", action="store_true", help="compara os pares aprovado x reprovado da página da voz")
    a = ap.parse_args()

    import spacy
    from wordfreq import zipf_frequency

    nlp = spacy.load("pt_core_news_sm", disable=["ner"])
    if a.pares:
        print(pares(nlp, zipf_frequency))
        return
    md = ler_texto(a.arquivo)
    if a.secao:
        md = recortar_secao(md, a.secao)
    m = medir(limpar_markdown(md), nlp, zipf_frequency)
    if a.json:
        m["faixas"] = {k: FAIXAS[k] for k in FAIXAS}
        print(json.dumps(m, ensure_ascii=False, indent=1))
    else:
        print(relatorio(m))


if __name__ == "__main__":
    main()
