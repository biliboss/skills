#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Publica, edita e confere um post do Gabriel no LinkedIn, pelo Safari do Mac (já logado).

Subcomandos:
  compose <texto.md> [--image arq.png]   abre o compositor, põe imagem e texto. NÃO publica.
  publish                                clica 'Publicar' no compositor aberto (só com pedido explícito do dono).
  edit-last <texto.md> [--save]          abre a edição do último post e troca o texto; --save clica 'Salvar'.
  check                                  só leitura: lê o último post em recent-activity e imprime o que importa.

Formato do texto.md: parágrafos separados por linha em branco; **negrito** e _itálico_ inline.
Tudo roda como `osascript` -> `do JavaScript` na aba da frente do Safari.
"""
import argparse, base64, html, json, re, subprocess, sys, tempfile, time
from pathlib import Path

RECENT = "https://www.linkedin.com/in/me/recent-activity/all/"
FEED = "https://www.linkedin.com/feed/"
ED = ".ProseMirror[contenteditable=true]"


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"osascript falhou: {r.stderr.strip()}")
    return r.stdout.strip()


def js(code: str) -> str:
    """Roda JS na aba da frente. O JS vai por arquivo UTF-8: sem problema de aspas nem acento."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
    try:
        return osa(f'tell application "Safari" to do JavaScript (read POSIX file "{f.name}" as «class utf8») in current tab of front window')
    finally:
        Path(f.name).unlink(missing_ok=True)


def goto(url: str) -> None:
    osa(f'tell application "Safari" to set URL of current tab of front window to "{url}"')


def until(code: str, ok, what: str, secs: int = 25) -> str:
    """Repete o JS até `ok(resultado)`; o carregamento da página não tem evento, então é sondagem."""
    end, last = time.time() + secs, ""
    while time.time() < end:
        last = js(code)
        if ok(last):
            return last
        time.sleep(0.5)
    sys.exit(f"tempo esgotado esperando {what} (último: {last!r})")


def paragraphs(md: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def inline(p: str) -> str:
    e = html.escape(p, quote=False)
    e = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e, flags=re.S)
    return re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", e, flags=re.S)


def plain(p: str) -> str:
    return re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", p.replace("**", ""))


def js_clear() -> str:
    # Chamada própria: se o paste vier na mesma chamada, ele soma ao texto antigo e duplica.
    return f"(()=>{{const ed=document.querySelector('{ED}');if(!ed)return 'sem editor';ed.focus();document.execCommand('selectAll');document.execCommand('delete');return 'len '+ed.innerText.trim().length}})()"


def js_paste(md: str) -> str:
    ps = paragraphs(md)
    # <p><br></p> ENTRE os parágrafos: sem isso o LinkedIn publica tudo grudado.
    h = "<p><br></p>".join(f"<p>{inline(p)}</p>" for p in ps)
    t = "\n\n".join(plain(p) for p in ps)
    return (f"(()=>{{const ed=document.querySelector('{ED}');if(!ed)return 'sem editor';ed.focus();const dt=new DataTransfer();"
            f"dt.setData('text/html',{json.dumps(h)});dt.setData('text/plain',{json.dumps(t)});"
            "ed.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));"
            "const q=[...ed.querySelectorAll('p')];return q.length+' ps, vazios '+q.filter(p=>!p.innerText.trim()).length+', strong '+ed.querySelectorAll('strong,b').length+', len '+ed.innerText.length})()")


JS_OPEN = ("(()=>{const all=[...document.querySelectorAll('*')].filter(x=>x.children.length===0&&/Começar publicação/.test(x.textContent));"
           "if(!all.length)return 'nada';const t=all[0].closest('button,[role=button],a,[tabindex]')||all[0];t.click();return 'click'})()")
JS_HAS_ED = f"(()=>document.querySelector('{ED}')?'ed':'nada')()"
JS_NEXT = "(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='Avançar');if(!b)return 'nada';b.click();return 'ok'})()"
JS_PUB = (f"(()=>{{const ed=document.querySelector('{ED}');if(!ed)return 'sem editor';let box=ed;for(let i=0;i<14&&box.parentElement;i++){{box=box.parentElement;"
          "if([...box.querySelectorAll('button')].some(b=>(b.innerText||'').trim()==='Publicar'))break}"
          "const b=[...box.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='Publicar');if(!b)return 'sem publicar';if(b.disabled)return 'publicar desabilitado';b.click();return 'publicar clicado'})()")
JS_SAVE = ("(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^(Salvar|Publicar)$/.test((x.innerText||'').trim())&&!x.disabled);"
           "if(!b)return 'nada';b.click();return 'clicado '+b.innerText.trim()})()")
JS_MENU = ("(()=>{const b=[...document.querySelectorAll('button')].find(x=>/menu de controle da publicação/i.test(x.getAttribute('aria-label')||''));"
           "if(!b)return 'nada';b.click();return 'menu'})()")
JS_EDIT = ("(()=>{const it=[...document.querySelectorAll('[role=menuitem],[role=button],button,li div')].find(e=>/^Editar( publicação)?$/i.test((e.innerText||'').trim().split('\\n')[0]));"
           "if(!it)return 'nada';it.click();return 'editar'})()")
# As classes do LinkedIn são ofuscadas e mudam: acha o post pelo botão de menu (aria-label) e o texto pelo filho com <br> diretos.
JS_CHECK = ("(()=>{const m=[...document.querySelectorAll('button')].find(x=>/menu de controle da publicação/i.test(x.getAttribute('aria-label')||''));"
            "if(!m)return '';let p=m;for(let i=0;i<40&&p.parentElement;i++){p=p.parentElement;if(p.innerText.length>250)break}"
            "const c=[...p.querySelectorAll('span,div,p')].filter(e=>e.querySelectorAll(':scope > br').length>=2).sort((a,b)=>a.innerText.length-b.innerText.length);"
            "const t=c[0];if(!t)return JSON.stringify({texto:p.innerText.trim().slice(0,90),br:0,strong:0,em:0,imagens:[],tamanho:p.innerText.length});"
            "const im=[...p.querySelectorAll('img')].filter(i=>i.width>300).map(i=>i.width+'x'+i.height);"
            "return JSON.stringify({texto:t.innerText.trim().slice(0,90),br:t.querySelectorAll(':scope > br').length,strong:t.querySelectorAll('strong').length,em:t.querySelectorAll('em').length,imagens:im,tamanho:t.innerText.length})})()")


def js_hook(img: Path) -> str:
    """Troca o seletor de arquivo nativo (que não dá para dirigir) por um File montado de um data URL."""
    jpg = Path(tempfile.mkdtemp()) / "post.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", str(img), "--out", str(jpg)], check=True, capture_output=True)
    b64 = base64.b64encode(jpg.read_bytes()).decode()
    return ("(()=>{fetch('data:image/jpeg;base64," + b64 + "').then(r=>r.blob()).then(bl=>{const f=new File([bl],'post.jpg',{type:'image/jpeg',lastModified:Date.now()});"
            "const orig=HTMLInputElement.prototype.click;HTMLInputElement.prototype.click=function(){if(this.type==='file'){const dt=new DataTransfer();dt.items.add(f);this.files=dt.files;"
            "this.dispatchEvent(new Event('input',{bubbles:true}));this.dispatchEvent(new Event('change',{bubbles:true}));HTMLInputElement.prototype.click=orig;return}return orig.call(this)};"
            f"const ed=document.querySelector('{ED}');let box=ed;for(let i=0;i<12&&box.parentElement;i++){{box=box.parentElement;if(box.querySelectorAll('button').length>4)break}}"
            "const b=[...box.querySelectorAll('button')].find(x=>(x.innerText||x.getAttribute('aria-label')||'').trim()==='Mídia');if(b)b.click()});return 'armado'})()")


def cmd_compose(a):
    md = Path(a.texto).read_text(encoding="utf-8")
    if not js("location.href").startswith("https://www.linkedin.com/"):
        goto(FEED)
    until(JS_OPEN, lambda r: r == "click", "o botão 'Começar publicação'")
    until(JS_HAS_ED, lambda r: r == "ed", "o editor")
    if a.image:
        print("imagem:", js(js_hook(Path(a.image).expanduser())))
        print("avançar:", until(JS_NEXT, lambda r: r == "ok", "o botão 'Avançar' do editor de imagem"))
        until(JS_HAS_ED, lambda r: r == "ed", "o editor depois da imagem")
    # Imagem antes do texto: colar imagem no editor apaga o texto.
    print("texto:", js(js_paste(md)))
    print("compositor pronto; nada foi publicado. Para publicar: li.py publish (só com pedido explícito do Gabriel)")


def cmd_publish(a):
    print(js(JS_PUB))


def cmd_edit_last(a):
    md = Path(a.texto).read_text(encoding="utf-8")
    goto(RECENT)
    until(JS_MENU, lambda r: r == "menu", "o menu do último post", 40)
    until(JS_EDIT, lambda r: r == "editar", "o item 'Editar'")
    until(JS_HAS_ED, lambda r: r == "ed", "o editor da edição")
    print("limpar:", js(js_clear()))
    print("texto:", js(js_paste(md)))  # outra chamada, de propósito
    if a.save:
        print("salvar:", js(JS_SAVE))
    else:
        print("editor com o texto novo; nada salvo. Para salvar: repita com --save")


def cmd_check(a):
    goto(RECENT)
    out = until(JS_CHECK, bool, "o último post em recent-activity", 40)
    d = json.loads(out)
    print(json.dumps(d, ensure_ascii=False, indent=2))
    ok = d["br"] >= 2 and d["strong"] >= 1
    print("formato:", "ok (linhas em branco e negrito)" if ok else "SUSPEITO: sem <br><br> entre parágrafos ou sem <strong>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose"); c.add_argument("texto"); c.add_argument("--image"); c.set_defaults(f=cmd_compose)
    sub.add_parser("publish").set_defaults(f=cmd_publish)
    e = sub.add_parser("edit-last"); e.add_argument("texto"); e.add_argument("--save", action="store_true"); e.set_defaults(f=cmd_edit_last)
    sub.add_parser("check").set_defaults(f=cmd_check)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
