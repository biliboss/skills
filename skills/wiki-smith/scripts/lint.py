#!/usr/bin/env python3
"""lint.py - lint of a repo's .wiki/ (stdlib only; run with `python3 -I scripts/lint.py`).

Checks: broken links and GitHub-style anchors (accents kept), pages missing from the index, missing
footer, empty or orphan pages, the diary (day index equal to the generated one, note names and
headings, day linked from the inbox), notes in the old format inside the inbox, the created/updated
frontmatter and the History section. Pages ignored by git are skipped.

Usage: python3 -I scripts/lint.py [-w WIKI_DIR] [-P PROJECT] [-c CONFIG]
Output: `<wiki>/<file>:<line>: <type>: <message>`, one per problem, sorted. Exit 0 clean, 2 problems.
Config: <wiki>/wiki.config (KEY=value, same file the sh scripts source), see templates/.
Wiki lookup, same order as the sh lib: -w/$WIKI_DIR, then $WIKI_HOME/<-P or
$WIKI_PROJECT> (error when missing), then the $WIKI_HOME project whose
wiki.config REPO=owner/name matches the origin remote, then
$WIKI_HOME/biliboss. Never clones or pulls.
WIKI_LANG=pt-BR switches the types and messages to Portuguese (the original tool's output).
"""
import os
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote

DEFAULTS = {
    "WIKI_LANG": "en",
    "DIARY_DIR": "journal",
    "INBOX": "inbox.md",
    "INDEX": "index.md",
    "FOOTER_PREFIX": "Map:",
    "HISTORY_HEADING": "## History",
    "CREATED_KEY": "created",
    "UPDATED_KEY": "updated",
    "DAY_TITLE": "Journal of",
    "PREV_LABEL": "Previous day",
    "NEXT_LABEL": "Next day",
    "NO_TIME_PREFIX": "no-time",
    "GEN_NOTE": "Generated index (scripts/day-index.sh); do not edit. Each note is a file in `%s/`.",
    "CMD_DAY_INDEX": "scripts/day-index.sh",
    "CMD_DATES": "scripts/dates.sh",
}


def parse_config(path):
    """KEY=value lines; values may be 'single' or "double" quoted; no expansion (sh-sourceable subset)."""
    cfg = {}
    if not path or not os.path.isfile(path):
        return cfg
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            m = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
            if not m:
                continue
            val = m.group(2)
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            else:
                val = re.sub(r"\s+#.*$", "", val)
            cfg[m.group(1)] = val
    return cfg


# --- messages -------------------------------------------------------------------------------------

TYPES_PT = {
    "broken-link": "link-quebrado", "broken-anchor": "ancora-quebrada", "empty": "vazia",
    "not-in-index": "fora-do-index", "no-footer": "sem-rodape", "orphan": "orfa",
    "day-name": "nome-do-dia", "stale-index": "indice-desatualizado", "note-name": "nome-da-nota",
    "bad-note": "nota-mal-formatada", "day-not-in-inbox": "dia-fora-do-inbox",
    "note-in-inbox": "nota-no-inbox", "no-dates": "sem-datas", "bad-dates": "datas-invalidas",
    "bad-history": "historico-mal-formatado",
}

MSG_EN = {
    "missing": "{t} does not exist",
    "anchor": "{t}#{a} does not exist",
    "empty": "empty page: fill it or delete it",
    "not-in-index": "the page is not in the list of {index}",
    "no-footer": "missing the footer `{footer} ... · Related: ...`",
    "orphan": "no page links to this one",
    "note-in-inbox": "a note goes in <{diary}>/<day>/<HHMM>-<slug>.md, not in the inbox",
    "bad-note": "a note starts with `## HH:MM — title` (the date is already in the folder name)",
    "note-name": "the note is named {hora}-<title slug>.md (the heading's time, in UTC)",
    "day-name": "the diary holds {diary}/YYYY-MM-DD.md (the index) and {diary}/YYYY-MM-DD/HHMM-slug.md (the notes)",
    "day-not-in-inbox": "the day is not in the inbox's last days or archive ({inbox})",
    "stale-index": "the day index is not the one generated from the notes: run `{cmd}`",
    "no-dates": "missing `{c}` and `{u}` in the frontmatter: run `{cmd}`",
    "bad-dates": "`{c}` and `{u}` are YYYY-MM-DD, and `{u}` does not come before `{c}`",
    "hist-line": "each History line is `- YYYY-MM-DD: what changed`",
    "hist-order": "History goes from the newest change to the oldest",
    "hist-new": "the newest History change cannot be after `{u}`: run `{cmd}`",
}

MSG_PT = {
    "missing": "{t} não existe",
    "anchor": "{t}#{a} não existe",
    "empty": "página vazia: preencha ou apague",
    "not-in-index": "a página não está na lista do {index}",
    "no-footer": "falta o rodapé `{footer} … · Relacionadas: …`",
    "orphan": "nenhuma página aponta para esta",
    "note-in-inbox": "nota vai no fim de {diary}/<hoje>.md, não no inbox",
    "bad-note": "a nota começa com `## HH:MM — título` (a data já está no nome da pasta)",
    "note-name": "a nota se chama {hora}-<slug do título>.md (a hora do cabeçalho, em UTC)",
    "day-name": "o diário tem {diary}/AAAA-MM-DD.md (o índice) e {diary}/AAAA-MM-DD/HHMM-slug.md (as notas)",
    "day-not-in-inbox": "o dia não está em \"Os últimos dias\" nem no \"Arquivo\" do {inbox}",
    "stale-index": "o índice do dia não é o gerado das notas: rode `{cmd}`",
    "no-dates": "falta `{c}` e `{u}` no frontmatter: rode `{cmd}`",
    "bad-dates": "`{c}` e `{u}` são AAAA-MM-DD, e `{u}` não vem antes de `{c}`",
    "hist-line": "cada linha do Histórico é `- AAAA-MM-DD: o que mudou`",
    "hist-order": "o Histórico vai da mudança mais nova para a mais velha",
    "hist-new": "a mudança mais nova do Histórico não pode ser depois de `{u}`: rode `{cmd}`",
}


class Linter:
    def __init__(self, root, cfg):
        self.root = root
        self.c = dict(DEFAULTS)
        self.c.update(cfg)
        pt = self.c["WIKI_LANG"].lower().startswith("pt")
        self.msgs = MSG_PT if pt else MSG_EN
        self.pt = pt
        d = re.escape(self.c["DIARY_DIR"])
        self.prefix = self.c["DIARY_DIR"] + "/"
        self.dia_re = re.compile(r"^" + d + r"/(\d{4}-\d{2}-\d{2})\.md$")
        self.nota_re = re.compile(r"^" + d + r"/(\d{4}-\d{2}-\d{2})/([^/]+\.md)$")
        nt = re.escape(self.c["NO_TIME_PREFIX"])
        self.nome_re = re.compile(r"^(\d{4}|" + nt + r")-[a-z0-9]+(-[a-z0-9]+)*\.md$")
        self.com_hora = re.compile(r"^## (\d{2}):(\d{2})( UTC)? — (.*)$")
        self.nota_antiga = re.compile(r"^## (\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")
        self.entrada = re.compile(r"^- (\d{4}-\d{2}-\d{2}): \S")
        self.data = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        self.fm_re = re.compile(r"^---\n([\s\S]*?)\n---\n")
        self.problems = []

    # -- helpers
    def add(self, arq, linha, tipo, key, **kw):
        t = TYPES_PT[tipo] if self.pt else tipo
        kw.setdefault("index", self.c["INDEX"])
        kw.setdefault("inbox", self.c["INBOX"])
        kw.setdefault("diary", self.c["DIARY_DIR"])
        kw.setdefault("footer", self.c["FOOTER_PREFIX"])
        kw.setdefault("c", self.c["CREATED_KEY"])
        kw.setdefault("u", self.c["UPDATED_KEY"])
        self.problems.append((arq, linha, t, self.msgs[key].format(**kw)))

    def hora_da_nota(self, cab):
        m = self.com_hora.match(cab)
        return (m.group(1) + m.group(2)) if m else None

    def frontmatter(self, texto):
        m = self.fm_re.match(texto)
        if not m:
            return None
        out = {}
        for l in m.group(1).split("\n"):
            i = l.find(":")
            if i > 0 and not re.match(r"^\s", l):
                out[l[:i].strip()] = l[i + 1:].strip()
        return out

    def historico(self, texto):
        linhas = texto.split("\n")
        inicio = None
        for i, l in enumerate(linhas):
            if l.strip() == self.c["HISTORY_HEADING"]:
                inicio = i
                break
        if inicio is None:
            return []
        out = []
        for i in range(inicio + 1, len(linhas)):
            l = linhas[i]
            if l.startswith("#") or l.strip() == "---":
                break
            if l.strip() == "":
                continue
            m = self.entrada.match(l)
            out.append((i + 1, m.group(1) if m else None))
        return out

    def indice_do_dia(self, dia, dias, notas):
        todos = sorted(set(dias))
        anterior = [d for d in todos if d < dia]
        seguinte = [d for d in todos if d > dia]
        mapa = ["%s [inbox](../%s)" % (self.c["FOOTER_PREFIX"], self.c["INBOX"])]
        if anterior:
            mapa.append("%s: [%s](%s.md)" % (self.c["PREV_LABEL"], anterior[-1], anterior[-1]))
        if seguinte:
            mapa.append("%s: [%s](%s.md)" % (self.c["NEXT_LABEL"], seguinte[0], seguinte[0]))
        linhas = []
        for arq, texto in sorted(notas, key=lambda n: n[0][:-3]):
            titulo = texto.split("\n")[0]
            if titulo.startswith("## "):
                titulo = titulo[3:]
            titulo = titulo.replace("[", "\\[").replace("]", "\\]")
            linhas.append("- [%s](%s/%s)" % (titulo, dia, arq))
        return ("# %s %s\n\n%s\n\n%s\n" % (self.c["DAY_TITLE"], dia, " · ".join(mapa), self.c["GEN_NOTE"].replace("%s", dia))
                + ("\n" + "\n".join(linhas) + "\n" if linhas else ""))


def sem_codigo(texto):
    texto = re.sub(r"^ *```[\s\S]*?^ *```", lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto, flags=re.M)
    return re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), texto)


def slug(titulo):
    t = titulo.lower().replace("`", "")
    t = "".join(ch for ch in t if unicodedata.category(ch)[0] in "LN" or ch.isspace() or ch in "_-")
    return re.sub(r"\s", "-", t.strip())


def juntar(de, alvo):
    partes = de.split("/")[:-1]
    fora = []
    for p in alvo.split("/"):
        if p == "..":
            if partes:
                partes.pop()
            else:
                fora.append("..")
        elif p not in (".", ""):
            partes.append(p)
    return "/".join(fora + partes)


def links(arquivo, texto):
    out = []
    for i, l in enumerate(sem_codigo(texto).split("\n")):
        for m in re.finditer(r"\]\(([^)\s]+)\)", l):
            bruto = m.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*:", bruto, re.I):
                continue
            partes = bruto.split("#")
            caminho = partes[0]
            ancora = partes[1] if len(partes) > 1 else None
            out.append((arquivo if caminho == "" else juntar(arquivo, unquote(caminho)), ancora, i + 1))
    return out


def ancoras(texto):
    vistas = {}
    out = set()
    originais = texto.split("\n")
    for i, l in enumerate(sem_codigo(texto).split("\n")):
        if not l.startswith("#"):
            continue
        m = re.match(r"^#{1,6}\s+(.*)$", originais[i])
        if not m:
            continue
        s = slug(m.group(1))
        n = vistas.get(s, 0)
        out.add(s if n == 0 else "%s-%d" % (s, n))
        vistas[s] = n + 1
    return out


def lint(root, cfg, arquivos, existe_fora):
    L = Linter(root, cfg)
    c = L.c
    entrada = {}
    do_index = set()
    do_inbox = set()
    for arquivo, texto in arquivos.items():
        for alvo, ancora, linha in links(arquivo, texto):
            if not alvo.endswith(".md"):
                continue
            if alvo.startswith("../"):
                if not existe_fora(alvo):
                    L.add(arquivo, linha, "broken-link", "missing", t=alvo)
                continue
            dest = arquivos.get(alvo)
            if dest is None:
                L.add(arquivo, linha, "broken-link", "missing", t=alvo)
                continue
            if ancora is not None and unquote(ancora) not in ancoras(dest):
                L.add(arquivo, linha, "broken-anchor", "anchor", t=alvo, a=ancora)
            if alvo != arquivo:
                entrada[alvo] = entrada.get(alvo, 0) + 1
            if arquivo == c["INDEX"]:
                do_index.add(alvo)
            if arquivo == c["INBOX"]:
                do_inbox.add(alvo)
    sem_rodape = {c["INDEX"], c["INBOX"]}
    for arquivo, texto in arquivos.items():
        linhas = texto.split("\n")
        raiz = "/" not in arquivo
        if raiz:
            if texto.strip() == "":
                L.add(arquivo, 1, "empty", "empty")
            if arquivo != c["INDEX"] and arquivo not in do_index:
                L.add(arquivo, 1, "not-in-index", "not-in-index")
            if arquivo not in sem_rodape and texto.strip() != "" and not any(l.startswith(c["FOOTER_PREFIX"]) for l in linhas):
                L.add(arquivo, len(linhas), "no-footer", "no-footer")
            if arquivo != c["INDEX"] and arquivo not in entrada:
                L.add(arquivo, 1, "orphan", "orphan")
        if raiz and texto.strip() != "":
            fm = L.frontmatter(texto)
            criado = fm.get(c["CREATED_KEY"]) if fm else None
            atualizado = fm.get(c["UPDATED_KEY"]) if fm else None
            if criado is None or atualizado is None:
                L.add(arquivo, 1, "no-dates", "no-dates", cmd=c["CMD_DATES"])
            else:
                if not L.data.match(criado) or not L.data.match(atualizado) or atualizado < criado:
                    L.add(arquivo, 1, "bad-dates", "bad-dates")
                anterior = None
                for linha, data in L.historico(texto):
                    if data is None:
                        L.add(arquivo, linha, "bad-history", "hist-line")
                    elif anterior is not None and data > anterior:
                        L.add(arquivo, linha, "bad-history", "hist-order")
                    elif anterior is None and L.data.match(atualizado) and data > atualizado:
                        L.add(arquivo, linha, "bad-history", "hist-new", cmd=c["CMD_DATES"])
                    if data is not None:
                        anterior = data
        if arquivo == c["INBOX"]:
            for i, l in enumerate(linhas):
                if L.nota_antiga.match(l):
                    L.add(arquivo, i + 1, "note-in-inbox", "note-in-inbox")
        if arquivo.startswith(L.prefix):
            nota = L.nota_re.match(arquivo)
            if nota:
                cab = linhas[0]
                hora = L.hora_da_nota(cab)
                nome = nota.group(2)
                if not cab.startswith("## ") or L.nota_antiga.match(cab):
                    L.add(arquivo, 1, "bad-note", "bad-note")
                elif (not L.nome_re.match(nome) or (hora is None) != nome.startswith(c["NO_TIME_PREFIX"] + "-")
                      or (hora is not None and not nome.startswith(hora + "-"))):
                    L.add(arquivo, 1, "note-name", "note-name", hora=hora or c["NO_TIME_PREFIX"])
                continue
            if not L.dia_re.match(arquivo):
                L.add(arquivo, 1, "day-name", "day-name")
                continue
            if arquivo not in do_inbox:
                L.add(arquivo, 1, "day-not-in-inbox", "day-not-in-inbox")
    dias = {}
    for caminho, texto in arquivos.items():
        m = L.dia_re.match(caminho) or L.nota_re.match(caminho)
        if not m:
            continue
        notas = dias.setdefault(m.group(1), [])
        n = L.nota_re.match(caminho)
        if n:
            notas.append((n.group(2), texto))
    for dia, notas in dias.items():
        if arquivos.get("%s/%s.md" % (c["DIARY_DIR"], dia)) != L.indice_do_dia(dia, list(dias), notas):
            L.add("%s/%s.md" % (c["DIARY_DIR"], dia), 1, "stale-index", "stale-index", cmd=c["CMD_DAY_INDEX"])
    return L.problems


def paginas(d):
    out = []
    for nome in sorted(os.listdir(d)):
        p = os.path.join(d, nome)
        if os.path.isdir(p):
            out.extend(paginas(p))
        elif p.endswith(".md"):
            out.append(p)
    return out


def ignoradas(root, caminhos):
    try:
        r = subprocess.run(["git", "-C", root, "check-ignore", "--stdin"], input="\n".join(caminhos),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
        return set(x for x in r.stdout.split("\n") if x)
    except OSError:
        return set()


def git_stdout(args):
    try:
        return subprocess.run(["git"] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, universal_newlines=True).stdout.strip()
    except OSError:
        return ""


def find_wiki(proj, home):
    """The wiki_resolve order minus -w/$WIKI_DIR (handled by the caller) and minus
    clone/pull: -P/$WIKI_PROJECT, origin match, default project."""
    if proj:
        wiki = os.path.join(home, proj)
        if not os.path.isdir(wiki):
            sys.stderr.write("wiki-smith: project wiki not found: %s\n" % wiki)
            sys.exit(1)
        return wiki
    remote = git_stdout(["remote", "get-url", "origin"])
    repo = ""
    for pre in ("git@github.com:", "https://github.com/"):
        if remote.startswith(pre):
            repo = remote[len(pre):]
            break
    if repo.endswith(".git"):
        repo = repo[:-4]
    if repo and os.path.isdir(home):
        for name in sorted(os.listdir(home)):
            cfg = os.path.join(home, name, "wiki.config")
            if os.path.isfile(cfg) and parse_config(cfg).get("REPO") == repo:
                return os.path.dirname(cfg)
    return os.path.join(home, "biliboss")


def main(argv):
    wiki = os.environ.get("WIKI_DIR")
    cfgp = os.environ.get("WIKI_CONFIG")
    proj = os.environ.get("WIKI_PROJECT")
    i = 0
    while i < len(argv):
        if argv[i] == "-w" and i + 1 < len(argv):
            wiki = argv[i + 1]
            i += 2
        elif argv[i] == "-c" and i + 1 < len(argv):
            cfgp = argv[i + 1]
            i += 2
        elif argv[i] == "-P" and i + 1 < len(argv):
            proj = argv[i + 1]
            i += 2
        else:
            sys.stderr.write(__doc__)
            return 1
    if not wiki:
        home = os.environ.get("WIKI_HOME")
        if not home:
            envf = os.environ.get("WIKI_SKILL_ENV") or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            home = os.path.expandvars(parse_config(envf).get("WIKI_HOME", ""))
        if not home:
            home = os.path.join(os.path.expanduser("~"), "wiki")
        wiki = find_wiki(proj, home)
    if not os.path.isdir(wiki):
        sys.stderr.write("wiki-smith: no wiki folder found (use -w DIR)\n")
        return 1
    root = os.path.abspath(wiki)
    if cfgp is None:
        cfgp = os.path.join(root, "wiki.config")
    elif not os.path.isfile(cfgp):
        sys.stderr.write("wiki-smith: config not found: %s\n" % cfgp)
        return 1
    cfg = parse_config(cfgp)
    todas = paginas(root)
    fora = ignoradas(root, todas)
    arquivos = {}
    for p in todas:
        if p in fora:
            continue
        with open(p, encoding="utf-8", newline="") as fh:
            arquivos[os.path.relpath(p, root).replace(os.sep, "/")] = fh.read()
    probs = lint(root, cfg, arquivos, lambda caminho: os.path.exists(os.path.join(root, caminho)))
    name = os.path.basename(root)
    for arq, linha, tipo, msg in sorted(probs, key=lambda p: (p[0], p[1], p[2])):
        print("%s/%s:%d: %s: %s" % (name, arq, linha, tipo, msg))
    return 2 if probs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
