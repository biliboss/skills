"""The Playground's server side, absorbed from the design-playground (Bun/TS): the canvas mirror, the component
definitions, the operations the page runs for an agent, and the HTTP API the canvas web calls.

Why a sibling module and not inline: dev-console.py is the page; this is the data. The agent's tools (delivery 2:
`console.sh` commands in place of the old MCP tools) call the same functions, so each operation is a plain function
or method here, never code inside a route handler. TS origin of each piece: src/canvas.ts (Canvas), src/componentes.ts
(validation, lerPasta, Componentes), src/operacoes.ts (Operacoes), src/http.ts (the routes).

Data lives in one folder (DEV_CONSOLE_PLAYGROUND_DIR, default ~/.local/state/dev-console/playground), in the same
format the design-playground wrote, so `console.sh playground import` is a plain copy:
  canvas.json                       {"registros": {id: tldraw record}}
  componentes/<produto>/<peça>.json one definition each, with `versao`
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

PREFIX = "/playground"
API = f"{PREFIX}/api"
WEB = Path(__file__).parent / "playground"  # the canvas web: canvas.js, widgets.js, paleta.js, eventos.js, app.css
OPERACAO_S = 15.0  # how long an operation waits for the open page to answer


def data_dir() -> Path:
    return Path(os.environ.get("DEV_CONSOLE_PLAYGROUND_DIR", "~/.local/state/dev-console/playground")).expanduser()


def _write_atomic(path: Path, text: str) -> None:
    """Temp file and rename, so a reader never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------- the canvas mirror (src/canvas.ts): the page owns the drawing, this is its copy ----------

class Canvas:
    def __init__(self, folder: Path):
        self.file = folder / "canvas.json"
        self.lock = threading.Lock()
        self.registros: dict[str, Any] = {}
        try:
            dados = json.loads(self.file.read_text("utf-8"))
            if isinstance(dados.get("registros"), dict):
                self.registros = dados["registros"]
        except (OSError, ValueError, AttributeError):
            pass  # no file yet, or unreadable: start empty (the TS did the same)

    def ler(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.registros)

    def aplicar(self, put: dict[str, Any] | None = None, remove: list[str] | None = None) -> None:
        with self.lock:
            self.registros.update(put or {})
            for id_ in remove or []:
                self.registros.pop(id_, None)
            _write_atomic(self.file, json.dumps({"registros": self.registros}, ensure_ascii=False, separators=(",", ":")))


# ---------- the components (src/componentes.ts) ----------

KEBAB = r"[a-z0-9]+(?:-[a-z0-9]+)*"
ID_COMPONENTE = re.compile(rf"^{KEBAB}/{KEBAB}$")
COMO_VALIDO = re.compile(r"^(?:texto|html|lista|attr:[A-Za-z_:][-\w:.]*|estilo:-{0,2}[A-Za-z][-\w]*)$")
MAIOR_ARQUIVO = 4 * 1024 * 1024  # a wrapper's real CSS passes 70 KB
ARQUIVOS_DO_WRAPPER = {"json": "componente.json", "html": "peca.html", "css": "peca.css", "desktop": "desktop.css", "sprite": "sprite.svg"}


def _obj(v) -> bool:
    return isinstance(v, dict)


def _texto(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _lista_de_textos(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _medida(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 20_000


def _problema_da_variante(v, onde: str) -> str | None:
    if not _obj(v):
        return f"{onde} precisa ser um objeto {{ css, w, h, html? }}"
    if not isinstance(v.get("css"), str):
        return f"{onde}.css ausente (ou ponha um desktop.css na pasta do wrapper)"
    if "html" in v and not _texto(v["html"]):
        return f"{onde}.html, quando vem, precisa ser texto"
    if not _medida(v.get("w")) or not _medida(v.get("h")):
        return f"{onde}.w e .h precisam ser números positivos"
    return None


def problema_do_componente(v) -> str | None:
    """The first problem of the value as a component definition (the `versao` aside, the tool gives it), or None.
    The message is for the model to read and fix."""
    if not _obj(v):
        return "o componente precisa ser um objeto JSON"
    if not isinstance(v.get("id"), str) or not ID_COMPONENTE.match(v["id"]):
        return f'id inválido {json.dumps(v.get("id"), ensure_ascii=False)}: use "<produto>/<peça>" em kebab-case, ex.: "via/cartao-imovel"'
    if not _texto(v.get("nome")):
        return "nome ausente"
    if not isinstance(v.get("descricao"), str):
        return "descricao ausente (para que serve a peça)"
    if v.get("estado") not in ("rascunho", "real"):
        return 'estado precisa ser "rascunho" ou "real"'
    if v["estado"] == "real" and "fonte" not in v:
        return ('estado "real" exige fonte { repo, arquivo, simbolo?, commit, receita }: de onde no código do produto a peça saiu. '
                'Sem fonte, use estado "rascunho".')
    if v["estado"] == "rascunho" and "fonte" in v:
        return 'um rascunho não tem fonte: tire o campo fonte, ou use estado "real" se a peça já existe no código do produto'
    if not _texto(v.get("html")):
        return "html ausente (ou ponha um peca.html na pasta do wrapper)"
    if not isinstance(v.get("css"), str):
        return 'css ausente (ou ponha um peca.css na pasta do wrapper); use "" se a peça não tem CSS'
    if not _medida(v.get("w")) or not _medida(v.get("h")):
        return "w e h precisam ser números positivos (o tamanho natural no celular, 393 de largura)"
    if "variantes" in v:
        var = v["variantes"]
        if not _obj(var):
            return "variantes precisa ser um objeto { desktop? }"
        estranhas = [k for k in var if k != "desktop"]
        if estranhas:
            return f'variantes só aceita "desktop" (veio {", ".join(estranhas)})'
        if "desktop" in var:
            p = _problema_da_variante(var["desktop"], "variantes.desktop")
            if p:
                return p
    if not isinstance(v.get("slots"), list):
        return "slots precisa ser uma lista (pode ser vazia)"
    for i, s in enumerate(v["slots"]):
        onde = f"slots[{i}]"
        if not _obj(s) or not _texto(s.get("chave")) or not _texto(s.get("seletor")):
            return f"{onde} precisa de chave e seletor"
        if not isinstance(s.get("como"), str) or not COMO_VALIDO.match(s["como"]):
            return f"{onde}.como inválido: use texto, html, lista, attr:<atributo> ou estilo:<propriedade>"
    if not _obj(v.get("dados")):
        return "dados precisa ser um objeto chave → texto (ou lista de textos)"
    for chave, valor in v["dados"].items():
        if not isinstance(valor, str) and not _lista_de_textos(valor):
            return f"dados.{chave} precisa ser texto ou lista de textos"
    if "fonte" in v:
        f = v["fonte"]
        if not _obj(f):
            return "fonte precisa ser um objeto { repo, arquivo, simbolo?, commit, receita }"
        if not _texto(f.get("repo")) or not _texto(f.get("arquivo")) or not _texto(f.get("commit")):
            return "fonte precisa de repo, arquivo e commit"
        if "simbolo" in f and not _texto(f["simbolo"]):
            return "fonte.simbolo, quando vem, precisa ser texto"
        if f.get("receita") not in ("executar", "copiar"):
            return 'fonte.receita precisa ser "executar" ou "copiar"'
    if "fontes" in v and not _lista_de_textos(v["fontes"]):
        return "fontes precisa ser uma lista de URLs de folhas de estilo"
    if "sprite" in v and not isinstance(v["sprite"], str):
        return "sprite precisa ser o SVG (texto) com os <symbol>"
    return None


def _limpar(c: dict, versao: int) -> dict:
    """Only the contract's fields, in its order (extras are dropped)."""
    out = {"id": c["id"], "nome": c["nome"], "descricao": c["descricao"], "estado": c["estado"], "versao": versao,
           "html": c["html"], "css": c["css"], "w": c["w"], "h": c["h"],
           "slots": [{"chave": s["chave"], "seletor": s["seletor"], "como": s["como"]} for s in c["slots"]],
           "dados": c["dados"]}
    d = (c.get("variantes") or {}).get("desktop")
    if d:
        out["variantes"] = {"desktop": ({"css": d["css"], "w": d["w"], "h": d["h"]} if "html" not in d
                                        else {"html": d["html"], "css": d["css"], "w": d["w"], "h": d["h"]})}
    if c.get("fonte"):
        f = c["fonte"]
        out["fonte"] = {"repo": f["repo"], "arquivo": f["arquivo"], **({"simbolo": f["simbolo"]} if "simbolo" in f else {}),
                        "commit": f["commit"], "receita": f["receita"]}
    if c.get("fontes"):
        out["fontes"] = c["fontes"]
    if "sprite" in c:
        out["sprite"] = c["sprite"]
    return out


def chaves_de(c: dict) -> list[str]:
    """The keys an instance accepts in `dados`: the slots' and the default data's."""
    return list(dict.fromkeys([*(s["chave"] for s in c["slots"]), *c["dados"]]))


def ler_pasta(pasta: str) -> dict:
    """Read a wrapper folder: componente.json and, where the JSON lacks the field, peca.html (html), peca.css (css),
    desktop.css (variantes.desktop.css) and sprite.svg (sprite). Absolute path; no file may leave the folder (a symlink
    out is refused). Does not validate: returns the assembled object for `problema_do_componente`. Raises with a clear message."""
    if not isinstance(pasta, str) or "\0" in pasta:
        raise ValueError("pasta inválida")
    if not os.path.isabs(pasta):
        raise ValueError(f'a pasta precisa ser um caminho absoluto (veio "{pasta}")')
    if ".." in re.split(r"[\\/]", pasta):
        raise ValueError(f'a pasta não pode ter ".." no caminho (veio "{pasta}")')
    try:
        raiz = Path(pasta).resolve(strict=True)
    except OSError:
        raise ValueError(f"a pasta não existe: {pasta}") from None
    if not raiz.is_dir():
        raise ValueError(f"não é uma pasta: {pasta}")

    def ler(nome: str) -> str | None:
        caminho = raiz / nome
        if not caminho.is_symlink() and not caminho.exists():
            return None
        try:
            real = caminho.resolve(strict=True)
        except OSError:
            raise ValueError(f"{nome} aponta para um arquivo que não existe") from None
        if raiz not in real.parents:
            raise ValueError(f"{nome} aponta para fora da pasta do wrapper (recusado)")
        if not real.is_file():
            raise ValueError(f"{nome} não é um arquivo")
        if real.stat().st_size > MAIOR_ARQUIVO:
            raise ValueError(f"{nome} passa de {MAIOR_ARQUIVO // 1024 // 1024} MB")
        return real.read_text("utf-8")

    texto = ler(ARQUIVOS_DO_WRAPPER["json"])
    if texto is None:
        raise ValueError(f"a pasta não tem {ARQUIVOS_DO_WRAPPER['json']}: {pasta}")
    try:
        bruto = json.loads(texto)
    except ValueError as e:
        raise ValueError(f"{ARQUIVOS_DO_WRAPPER['json']} não é JSON válido: {e}") from None
    if not _obj(bruto):
        raise ValueError(f"{ARQUIVOS_DO_WRAPPER['json']} precisa ser um objeto")
    c = dict(bruto)
    for campo, arquivo in (("html", "html"), ("css", "css")):
        if campo not in c:
            lido = ler(ARQUIVOS_DO_WRAPPER[arquivo])
            if lido is not None:
                c[campo] = lido
    if "sprite" not in c:
        sprite = ler(ARQUIVOS_DO_WRAPPER["sprite"])
        if sprite is not None:
            c["sprite"] = sprite
    variantes = dict(c["variantes"]) if _obj(c.get("variantes")) else c.get("variantes")
    desktop = dict(variantes["desktop"]) if _obj(variantes) and _obj(variantes.get("desktop")) else None
    if desktop is not None:
        if "css" not in desktop:
            css = ler(ARQUIVOS_DO_WRAPPER["desktop"])
            if css is not None:
                desktop["css"] = css
        c["variantes"] = {**variantes, "desktop": desktop}
    elif variantes is None:  # no variant in the JSON: a desktop.css in the folder is the web variant (1280), with the phone's height
        css = ler(ARQUIVOS_DO_WRAPPER["desktop"])
        if css is not None:
            c["variantes"] = {"desktop": {"css": css, "w": 1280, "h": c.get("h")}}
    return c


class Componentes:
    def __init__(self, folder: Path, ao_definir=None):
        self.dir = folder / "componentes"
        self.ao_definir = ao_definir  # called per definition written (the server sends the SSE `componente`)

    def _arquivo(self, id_: str) -> Path:
        produto, peca = id_.split("/")
        return self.dir / produto / f"{peca}.json"

    def definir(self, entrada) -> dict:
        """Validate and write a definition with the next version. Raises with the problem."""
        problema = problema_do_componente(entrada)
        if problema:
            raise ValueError(problema)
        anterior = self.ler(entrada["id"])
        componente = _limpar(entrada, (anterior["versao"] if anterior else 0) + 1)
        _write_atomic(self._arquivo(entrada["id"]), json.dumps(componente, indent=2, ensure_ascii=False) + "\n")
        if self.ao_definir:
            try:
                self.ao_definir(componente)
            except Exception:  # a failed notice never loses the definition
                pass
        return componente

    def definir_da_pasta(self, pasta: str) -> dict:
        return self.definir(ler_pasta(pasta))

    def ler(self, id_: str) -> dict | None:
        if not ID_COMPONENTE.match(id_):
            return None
        arquivo = self._arquivo(id_)
        return self._ler_arquivo(arquivo, id_) if arquivo.exists() else None

    @staticmethod
    def _ler_arquivo(arquivo: Path, id_esperado: str | None = None) -> dict | None:
        try:
            bruto = json.loads(arquivo.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if problema_do_componente(bruto) or (id_esperado is not None and bruto["id"] != id_esperado):
            return None
        v = bruto.get("versao")
        return {**bruto, "versao": v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 1}

    def todos(self, produto: str | None = None) -> list[dict]:
        """Every valid definition in id order; one product's only, if asked."""
        try:
            produtos = sorted(p.name for p in self.dir.iterdir() if p.is_dir())
        except OSError:
            return []
        if produto is not None:
            produtos = [p for p in produtos if p == produto]
        saida = []
        for p in produtos:
            for a in sorted(f for f in (self.dir / p).iterdir() if f.name.endswith(".json")):
                c = self._ler_arquivo(a, f"{p}/{a.name[:-len('.json')]}")
                if c:
                    saida.append(c)
        return saida

    def listar(self, produto: str | None = None) -> list[dict]:
        """The summary for the model: no HTML, no CSS."""
        return [{"id": c["id"], "nome": c["nome"], "descricao": c["descricao"], "estado": c["estado"], "versao": c["versao"],
                 "w": c["w"], "h": c["h"], "chaves": chaves_de(c), "dados": c["dados"]} for c in self.todos(produto)]

    def conferir(self, id_: str, dados: dict | None) -> str | None:
        """Check the component exists and the keys of `dados` are its own. The error message for the model, or None."""
        c = self.ler(id_)
        if not c:
            produto = id_.split("/")[0]
            todos = self.todos()
            do_produto = [x for x in todos if x["id"].split("/")[0] == produto]
            lista = [x["id"] for x in (do_produto or todos)]
            existentes = ", ".join(lista) if lista else "nenhum ainda"
            onde = f"do produto {produto}" if do_produto else "definidos"
            return (f'não existe o componente "{id_}" ({onde}: {existentes}). Defina com componente_definir: a pasta do wrapper '
                    'da skill design, ou o JSON com estado "rascunho" para uma peça nova.')
        chaves = chaves_de(c)
        estranhas = [k for k in (dados or {}) if k not in chaves]
        if estranhas:
            return f'o componente "{id_}" não tem as chaves {", ".join(estranhas)} (chaves: {", ".join(chaves) or "nenhuma"})'
        return None


# ---------- the live line to the open page (the SSE of src/http.ts) and the operations on it (src/operacoes.ts) ----------

class Eventos:
    """The open pages' SSE connections. `publicar` reaches all; `para_um` the newest page only (the canvas operations)."""

    def __init__(self):
        self.assinantes: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []

    def assinar(self):
        q: asyncio.Queue = asyncio.Queue()
        item = (asyncio.get_running_loop(), q)
        self.assinantes.append(item)
        return q, lambda: self.assinantes.remove(item) if item in self.assinantes else None

    @property
    def ouvintes(self) -> int:
        return len(self.assinantes)

    @staticmethod
    def _enviar(item, tipo: str, dados: Any) -> None:
        loop, q = item
        loop.call_soon_threadsafe(q.put_nowait, (tipo, dados))  # thread-safe: a sync route may publish too

    def publicar(self, tipo: str, dados: Any) -> None:
        for item in list(self.assinantes):
            self._enviar(item, tipo, dados)

    def para_um(self, tipo: str, dados: Any) -> bool:
        if not self.assinantes:
            return False
        self._enviar(self.assinantes[-1], tipo, dados)
        return True


class Operacoes:
    """The server does not draw: it sends the operation to the open page (SSE `canvas`), which applies it with the
    tldraw editor and answers on POST /canvas/resposta. Each operation waits for the answer, with a time limit."""

    def __init__(self, eventos: Eventos, limite_s: float = OPERACAO_S):
        self.eventos, self.limite_s = eventos, limite_s
        self.pendentes: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future]] = {}

    async def executar(self, op: dict) -> Any:
        import uuid

        if not self.eventos.ouvintes:
            raise RuntimeError("a Web não está aberta: abra o /playground do dev-console e espere a página carregar")
        pedido = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.pendentes[pedido] = (loop, fut)
        self.eventos.para_um("canvas", {"pedido": pedido, "op": op})
        try:
            return await asyncio.wait_for(fut, self.limite_s)
        except asyncio.TimeoutError:
            raise RuntimeError("a página não respondeu a tempo (o canvas carregou?)") from None
        finally:
            self.pendentes.pop(pedido, None)

    def responder(self, pedido: str, ok: bool, resultado: Any = None, erro: str | None = None) -> bool:
        """The page's answer. False if the request does not exist (it expired)."""
        p = self.pendentes.pop(pedido, None)
        if not p:
            return False
        loop, fut = p
        done = (lambda: fut.set_result(resultado)) if ok else (lambda: fut.set_exception(RuntimeError(erro or "a página recusou a operação")))
        loop.call_soon_threadsafe(lambda: fut.done() or done())
        return True


# ---------- the whole, and the HTTP routes under /playground/api ----------

class Playground:
    def __init__(self, folder: Path | None = None):
        self.dir = folder or data_dir()
        self.canvas = Canvas(self.dir)
        self.eventos = Eventos()
        self.operacoes = Operacoes(self.eventos)
        # each definition tells every tab: they fetch the new one and redraw that id's instances
        self.componentes = Componentes(self.dir, lambda c: self.eventos.publicar("componente", {"id": c["id"], "versao": c["versao"]}))


def _json(dados, status: int = 200):
    from starlette.responses import JSONResponse

    # compact and UTF-8, like Bun's Response.json; never cached
    return JSONResponse(dados, status_code=status, headers={"cache-control": "no-store"},
                        media_type="application/json")


def _erro(status: int, msg: str):
    return _json({"erro": msg}, status)


async def _corpo(req):
    try:
        return await req.json()
    except Exception:
        return None


def mount(app, pg: Playground) -> None:
    """Add the routes to the app, in front of FastHTML's own (its static route takes any URL ending in .js or .css first)."""
    from starlette.responses import FileResponse, Response, StreamingResponse
    from starlette.routing import Route

    async def canvas_get(req):
        return _json({"registros": pg.canvas.ler()})

    async def canvas_diff(req):
        corpo = await _corpo(req)
        if not _obj(corpo):
            return _erro(400, "corpo precisa ser JSON { put?, remove? }")
        put, remove = corpo.get("put"), corpo.get("remove")
        if put is not None and not _obj(put):
            return _erro(400, "put precisa ser um objeto id → registro")
        if remove is not None and not _lista_de_textos(remove):
            return _erro(400, "remove precisa ser uma lista de ids")
        pg.canvas.aplicar(put, remove)
        return Response(status_code=204)

    async def canvas_resposta(req):
        corpo = await _corpo(req)
        if not _obj(corpo) or not isinstance(corpo.get("pedido"), str):
            return _erro(400, "corpo precisa ser { pedido, ok, resultado?, erro? }")
        achou = pg.operacoes.responder(corpo["pedido"], corpo.get("ok") is True, corpo.get("resultado"),
                                       corpo["erro"] if isinstance(corpo.get("erro"), str) else None)
        return Response(status_code=204) if achou else _erro(404, "pedido desconhecido ou vencido")

    async def componentes_get(req):
        return _json({"componentes": pg.componentes.todos()})

    async def eventos_sse(req):
        q, soltar = pg.eventos.assinar()

        async def corpo():
            try:
                yield "retry: 2000\n\n"
                while True:
                    try:
                        tipo, dados = await asyncio.wait_for(q.get(), 15)
                        yield f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"  # keeps proxies and the browser from closing an idle line
            finally:
                soltar()

        return StreamingResponse(corpo(), media_type="text/event-stream",
                                 headers={"cache-control": "no-store", "x-accel-buffering": "no"})

    async def web(req):
        raiz = WEB.resolve()
        arquivo = (raiz / req.path_params["caminho"]).resolve()
        if raiz not in arquivo.parents or not arquivo.is_file():
            return _erro(404, "não encontrado")
        return FileResponse(arquivo, headers={"cache-control": "no-store"})

    rotas = [
        Route(f"{API}/canvas", canvas_get, methods=["GET"]),
        Route(f"{API}/canvas/diff", canvas_diff, methods=["POST"]),
        Route(f"{API}/canvas/resposta", canvas_resposta, methods=["POST"]),
        Route(f"{API}/componentes", componentes_get, methods=["GET"]),
        Route(f"{API}/eventos", eventos_sse, methods=["GET"]),
        Route(f"{PREFIX}/web/{{caminho:path}}", web, methods=["GET", "HEAD"]),
    ]
    app.router.routes[0:0] = rotas


# ---------- `console.sh playground import`: copy the design-playground's data into the console's folder ----------

def importar(origem: Path, destino: Path, force: bool = False) -> list[str]:
    """Copy canvas.json and componentes/ from a design-playground `dados` folder. Refuses to overwrite without `force`."""
    itens = [n for n in ("canvas.json", "componentes") if (origem / n).exists()]
    if not itens:
        raise SystemExit(f"nada para importar em {origem} (sem canvas.json nem componentes/)")
    ja = [n for n in itens if (destino / n).exists()]
    if ja and not force:
        raise SystemExit(f"{destino} já tem {', '.join(ja)}; use --force para sobrescrever")
    destino.mkdir(parents=True, exist_ok=True)
    for n in itens:
        alvo = destino / n
        if (origem / n).is_dir():
            shutil.rmtree(alvo, ignore_errors=True)
            shutil.copytree(origem / n, alvo)
        else:
            shutil.copy2(origem / n, alvo)
    return itens


if __name__ == "__main__":  # python3 console_playground.py import [<dados dir>] [--force]
    import sys

    args = sys.argv[1:]
    if not args or args[0] != "import":
        raise SystemExit("usage: console_playground.py import [<dados dir>] [--force]")
    force = "--force" in args
    pos = [a for a in args[1:] if a != "--force"]
    src = Path(pos[0] if pos else "~/biliboss/dev/design-playground/dados").expanduser()
    dst = data_dir()
    print(f"importei {', '.join(importar(src, dst, force))} de {src} para {dst}")
