# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""auth: the agent's secure identity. Several accounts per provider (Google first), the OAuth client only in envless,
tokens kept by the provider's official CLI (gws: encrypted file per account, its key in the macOS Keychain), a grant per
Hermes/Claude profile, one journal with one writer (this file). The setup is the product: `setup` runs everything it can.

Design stage of the domain Auth (dev-console): provider.updated, account.updated, account.connected, account.checked,
account.disconnected. Reference design: Nango (connections per end user, the provider refreshes). OAuth 2.0 is RFC 6749
and PKCE RFC 7636. Sources: ../README.md.

Never prints, logs or journals a secret value; the journal and the config hold names, e-mails and states only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

EVENTS = {
    "provider": {
        # O cliente OAuth de um provedor foi posto no envless (só os nomes das chaves, nunca o valor), ou mudou.
        "update": "updated",
    },
    "account": {
        # Uma conta entrou, ou mudou: provedor, apelido, e-mail, serviços, só leitura, e quais perfis podem usá-la.
        "update": "updated",
        # O dono fez o login no navegador e a conta respondeu: o token existe e funciona.
        "connect": "connected",
        # Uma checagem sondou a conta: ok, precisa de login ou quebrada, e quando o token vence, se o provedor diz.
        "check": "checked",
        # O token local saiu (logout ou remove); nada foi revogado no provedor.
        "disconnect": "disconnected",
    },
}

TRANSITIONS = {
    "provider.updated": ["account.updated"],
    "account.updated": ["account.connected"],
    "account.connected": ["account.checked"],
    "account.checked": ["account.disconnected"],
    "account.disconnected": ["account.connected"],
}

STATUS_OK, STATUS_LOGIN, STATUS_BROKEN = "ok", "needs_login", "broken"
FORBIDDEN = re.compile(r"secret|token|password|senha|private|api[_-]?key", re.I)

PROVIDERS: dict[str, dict[str, Any]] = {
    "google": {
        "cli": "gws",  # googleworkspace/cli, Apache-2.0: its own OAuth login and refresh
        "dir_var": "GOOGLE_WORKSPACE_CLI_CONFIG_DIR",
        "base": "~/.config/gws/contas",
        "keys": ["GOOGLE_WORKSPACE_CLI_CLIENT_ID", "GOOGLE_WORKSPACE_CLI_CLIENT_SECRET"],
        "env": "google",
        "services": ["calendar", "gmail", "drive", "docs", "sheets"],
        "status": ["gws", "auth", "status"],
        "logout": ["gws", "auth", "logout"],
        "probes": {
            "calendar": ["gws", "calendar", "calendarList", "list", "--params", '{"maxResults":1,"fields":"items(id)"}'],
            "gmail": ["gws", "gmail", "users", "getProfile", "--params", '{"userId":"me"}'],
            "drive": ["gws", "drive", "about", "get", "--params", '{"fields":"user"}'],
        },
        "console": [
            ("Tela de consentimento (Externo; ponha o seu e-mail como usuário de teste)",
             "https://console.cloud.google.com/apis/credentials/consent"),
            ("Credenciais: Criar credenciais > ID do cliente OAuth > App para computador; baixe o JSON",
             "https://console.cloud.google.com/apis/credentials"),
            ("Ative as APIs usadas (Calendar, Gmail, Drive...)", "https://console.cloud.google.com/apis/library"),
        ],
    },
}


# ---- paths, config, journal -------------------------------------------------------------------------------------

def config_path() -> Path:
    return Path(os.environ.get("AUTH_HOME", "~/.config/auth")).expanduser() / "config.json"


def journal_path() -> Path:
    return Path(os.environ.get("AUTH_DIR", "~/.local/share/auth")).expanduser() / "events.jsonl"


def load() -> dict:
    p = config_path()
    return json.loads(p.read_text()) if p.exists() else {"providers": {}, "accounts": {}}


def save(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def profile() -> str:
    """Who is calling: AUTH_PROFILE, else the Hermes profile of HERMES_HOME, else the owner at a plain shell."""
    if os.environ.get("AUTH_PROFILE"):
        return os.environ["AUTH_PROFILE"]
    m = re.search(r"/profiles/([^/]+)/?$", os.environ.get("HERMES_HOME", ""))
    return m.group(1) if m else "owner"


def emit(event: str, value: dict, account: str | None = None) -> dict:
    valid = {f"{c}.{k}" for c, kinds in EVENTS.items() for k in kinds.values()}
    if event not in valid:
        raise ValueError(f"unknown event {event!r}")
    bad = [k for k in value if FORBIDDEN.search(k)]
    if bad:
        raise ValueError(f"refusing to journal secret-looking keys: {bad}")
    row: dict[str, Any] = {"id": uuid.uuid4().hex[:12], "event": event}
    if account:
        row["account"] = account
    row.update(at=datetime.now().astimezone().isoformat(timespec="seconds"), actor=profile(), value=value)
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def events() -> list[dict]:
    p = journal_path()
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _project(evs: list[dict]) -> dict:
    """An account as the journal leaves it: who it is, whether it works, who may use it."""
    if not evs:
        return {}
    s = {"id": evs[-1]["account"], "provider": "", "alias": evs[-1]["account"], "email": "", "services": [],
         "readonly": True, "profiles": [], "status": STATUS_LOGIN, "checked_at": "", "expires_at": None,
         "updated_at": evs[-1]["at"]}
    for e in evs:
        v, kind = e.get("value", {}), e["event"].split(".")[1]
        if kind == "updated":
            s.update({k: v[k] for k in ("provider", "alias", "email", "services", "readonly", "profiles") if k in v})
            if v.get("removed"):
                s["status"] = "removed"
        elif kind == "connected":
            s["status"] = STATUS_OK
        elif kind == "checked":
            s.update(status=v.get("status", STATUS_BROKEN), checked_at=e["at"], expires_at=v.get("expires_at"))
        elif kind == "disconnected":
            s["status"] = STATUS_LOGIN
    return s


def accounts_state() -> dict[str, dict]:
    groups: dict[str, list[dict]] = {}
    for e in events():
        if e.get("account"):
            groups.setdefault(e["account"], []).append(e)
    return {a: s for a, g in groups.items() if (s := _project(g)) and s["status"] != "removed"}


class AuthJournal:
    """Read-only view of the journal for the dev-console contract."""

    def read(self, query: dict | None = None) -> Any:
        query = query or {}
        evs = events()
        if "id" in query:
            m = [e for e in evs if e.get("account") == query["id"]]
            return m if query.get("history") else _project(m)
        if "event" in query:
            return [e for e in evs if e["event"] == query["event"]]
        if query.get("history"):
            return evs
        return list(accounts_state().values())


# ---- running a command as an account ------------------------------------------------------------------------------

def die(msg: str, code: int = 2) -> NoReturn:
    print(f"auth: {msg}", file=sys.stderr)
    sys.exit(code)


def find(cfg: dict, key: str) -> tuple[str, dict]:
    """An account by alias, or by e-mail."""
    if key in cfg["accounts"]:
        return key, cfg["accounts"][key]
    for a, v in cfg["accounts"].items():
        if v["email"] == key:
            return a, v
    die(f"conta desconhecida: {key} (veja: auth.sh list)")


def gate(alias: str, acct: dict) -> None:
    """A profile runs only the accounts it was granted; the owner at a plain shell runs all."""
    who = profile()
    if who != "owner" and who not in acct.get("profiles", []):
        die(f"o perfil '{who}' não tem a conta '{alias}'. O dono libera com: auth.sh grant {alias} --profile {who}", 4)


def build(cfg: dict, alias: str, acct: dict, cmd: list[str]) -> tuple[list[str], dict, str]:
    prov, pc = PROVIDERS[acct["provider"]], cfg["providers"].get(acct["provider"])
    if not pc:
        die(f"provedor {acct['provider']} sem setup: rode auth.sh setup {acct['provider']}", 3)
    env = os.environ.copy()
    env[prov["dir_var"]] = acct["dir"]
    env["AUTH_CWD"] = os.getcwd()
    env["AUTH_ALIAS"] = alias
    full = ["envless", "exec", f"--env={pc['env']}", "--", "sh", "-c", 'cd "$AUTH_CWD" && exec "$@"', "sh", *cmd]
    return full, env, str(Path(pc["cofre"]).expanduser())


def run_capture(cfg: dict, alias: str, acct: dict, cmd: list[str]) -> subprocess.CompletedProcess:
    full, env, cwd = build(cfg, alias, acct, cmd)
    return subprocess.run(full, cwd=cwd, env=env, capture_output=True, text=True)


# ---- commands ---------------------------------------------------------------------------------------------------

def color(s: str, bordo: bool) -> str:
    return f"\033[38;5;88m{s}\033[0m" if bordo and sys.stdout.isatty() and not os.environ.get("NO_COLOR") else s


def mark(status: str) -> str:
    return {STATUS_OK: "● ok", STATUS_LOGIN: color("◆ precisa de login", True), STATUS_BROKEN: color("✗ quebrada", True)}.get(status, status)


def cmd_list(a: argparse.Namespace) -> None:
    cfg, st = load(), accounts_state()
    rows = [(v["provider"], k, v["email"], st.get(k, {}).get("status", STATUS_LOGIN), v.get("profiles", []))
            for k, v in cfg["accounts"].items() if not a.provider or v["provider"] == a.provider]
    if a.json:
        print(json.dumps([dict(provider=p, alias=k, email=e, status=s, profiles=pr) for p, k, e, s, pr in rows], ensure_ascii=False))
        return
    if not rows:
        print("nenhuma conta ainda (auth.sh add <provedor> <apelido> <e-mail>)")
    w = [max((len(r[i]) for r in rows), default=0) for i in range(3)]
    for p, k, e, s, pr in rows:
        print(f"{p:<{w[0]}} · {k:<{w[1]}} · {e:<{w[2]}} · {mark(s)}" + (f"  [{', '.join(pr)}]" if pr else ""))


def cmd_aliases(a: argparse.Namespace) -> None:
    """The aliases the calling profile may run, one per line (gcal todas)."""
    cfg, who = load(), profile()
    for k, v in cfg["accounts"].items():
        if (not a.provider or v["provider"] == a.provider) and (who == "owner" or who in v.get("profiles", [])):
            print(k)


def cmd_add(a: argparse.Namespace) -> None:
    if a.provider not in PROVIDERS:
        die(f"provedor desconhecido: {a.provider} (um de {sorted(PROVIDERS)})")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", a.alias) or "@" not in a.email:
        die("apelido: minúsculas/números/-/_ ; e-mail com @")
    cfg, prov = load(), PROVIDERS[a.provider]
    services = [s for s in (a.services or "calendar").split(",") if s]
    bad = [s for s in services if s not in prov["services"]]
    if bad:
        die(f"serviço desconhecido: {bad} (um de {prov['services']})")
    d = Path(prov["base"]).expanduser() / a.email
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    old = cfg["accounts"].get(a.alias, {})
    acct = {"provider": a.provider, "email": a.email, "dir": str(d), "services": services,
            "readonly": not a.write, "profiles": sorted(set(old.get("profiles", [])) | set(filter(None, (a.grant or "").split(","))))}
    cfg["accounts"][a.alias] = acct
    save(cfg)
    emit("account.updated", {"provider": a.provider, "alias": a.alias, "email": a.email, "services": services,
                             "readonly": acct["readonly"], "profiles": acct["profiles"]}, a.alias)
    print(f"conta {a.alias} ({a.email}) registrada. Falta o login do dono: auth.sh login {a.alias}")


def cmd_grant(a: argparse.Namespace, give: bool) -> None:
    cfg = load()
    alias, acct = find(cfg, a.alias)
    pr = set(acct.get("profiles", []))
    (pr.add if give else pr.discard)(a.profile)
    acct["profiles"] = sorted(pr)
    save(cfg)
    emit("account.updated", {"profiles": acct["profiles"]}, alias)
    print(f"{alias}: perfis com acesso: {', '.join(acct['profiles']) or 'só o dono'}")


def cmd_login(a: argparse.Namespace) -> None:
    """The owner's step: opens the browser. Exact scopes come from the account's services."""
    cfg = load()
    alias, acct = find(cfg, a.alias)
    gate(alias, acct)
    login = ["gws", "auth", "login", "-s", ",".join(acct["services"])] + (["--readonly"] if acct["readonly"] else [])
    full, env, cwd = build(cfg, alias, acct, login)
    print(f"login de {alias} ({acct['email']}): escolha essa conta no navegador.", file=sys.stderr)
    rc = subprocess.run(full, cwd=cwd, env=env).returncode
    if rc == 0:
        check_one(cfg, alias, acct, quiet=True)
    sys.exit(rc)


def probe(cfg: dict, alias: str, acct: dict) -> dict:
    prov = PROVIDERS[acct["provider"]]
    st = run_capture(cfg, alias, acct, prov["status"])
    info: dict[str, Any] = {}
    try:
        info = json.loads(st.stdout[st.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        pass
    expires = next((str(v) for k, v in info.items() if "expir" in k.lower() and isinstance(v, (str, int))), None)
    if st.returncode != 0 or info.get("auth_method", "none") == "none" or info.get("storage", "") == "none":
        return {"ok": False, "status": STATUS_LOGIN, "reason": "sem token", "expires_at": None}
    svc = next((s for s in acct["services"] if s in prov["probes"]), None)
    if not svc:
        return {"ok": True, "status": STATUS_OK, "reason": "token presente (sem sonda para o serviço)", "expires_at": expires}
    r = run_capture(cfg, alias, acct, prov["probes"][svc])
    if r.returncode == 0:
        return {"ok": True, "status": STATUS_OK, "reason": "", "expires_at": expires}
    blob = (r.stdout + r.stderr).lower()
    if any(x in blob for x in ("invalid_grant", "autherror", "401", "unauthenticated", "expired or revoked")):
        return {"ok": False, "status": STATUS_LOGIN, "reason": "token vencido ou revogado", "expires_at": None}
    return {"ok": False, "status": STATUS_BROKEN, "reason": f"{svc} falhou (exit {r.returncode})", "expires_at": expires}


def check_one(cfg: dict, alias: str, acct: dict, quiet: bool = False) -> dict:
    res = probe(cfg, alias, acct)
    before = accounts_state().get(alias, {}).get("status")
    emit("account.checked", {k: res[k] for k in ("ok", "status", "reason", "expires_at")}, alias)
    if res["ok"] and before != STATUS_OK:
        emit("account.connected", {"email": acct["email"]}, alias)
    if not quiet:
        print(f"{alias:<10} {acct['email']:<32} {mark(res['status'])}" + (f"  ({res['reason']})" if res["reason"] else ""))
    return res


def cmd_check(a: argparse.Namespace) -> None:
    cfg = load()
    targets = [find(cfg, a.alias)] if a.alias else list(cfg["accounts"].items())
    out, bad = [], False
    for alias, acct in targets:
        gate(alias, acct)
        res = check_one(cfg, alias, acct, quiet=a.json)
        out.append({"alias": alias, "email": acct["email"], **res})
        bad |= not res["ok"]
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
    sys.exit(1 if bad else 0)


def cmd_run(a: argparse.Namespace) -> None:
    cmd = a.argv[1:] if a.argv and a.argv[0] == "--" else a.argv
    if not cmd:
        die("uso: auth.sh run <apelido> -- <comando…>")
    cfg = load()
    alias, acct = find(cfg, a.alias)
    gate(alias, acct)
    full, env, cwd = build(cfg, alias, acct, cmd)
    os.chdir(cwd)
    os.execvpe(full[0], full, env)


def cmd_remove(a: argparse.Namespace) -> None:
    cfg = load()
    alias, acct = find(cfg, a.alias)
    gate(alias, acct)
    if not a.yes:
        die(f"remove apaga o token LOCAL de {alias} ({acct['email']}) e tira a conta daqui; não revoga nada no provedor.\n"
            f"Confirme com o dono e rode: auth.sh remove {alias} --yes", 3)
    prov = PROVIDERS[acct["provider"]]
    try:
        run_capture(cfg, alias, acct, prov["logout"])
    except Exception:
        pass
    shutil.rmtree(acct["dir"], ignore_errors=True)
    del cfg["accounts"][alias]
    save(cfg)
    emit("account.disconnected", {"email": acct["email"], "removed": True, "revoked_remotely": False}, alias)
    emit("account.updated", {"removed": True}, alias)
    print(f"{alias}: token local apagado. Para revogar no provedor: https://myaccount.google.com/permissions")


def cmd_setup(a: argparse.Namespace) -> None:
    """Runs everything it can for a provider and stops, with the exact words, at what is the owner's."""
    prov = PROVIDERS.get(a.provider)
    if not prov:
        die(f"provedor desconhecido: {a.provider} (um de {sorted(PROVIDERS)})")
    for tool in ("envless", prov["cli"]):
        if not shutil.which(tool):
            die(f"falta o '{tool}' no PATH (brew install {'envless' if tool == 'envless' else 'googleworkspace-cli'})", 3)
    cfg = load()
    cofre = Path(a.cofre or cfg["providers"].get(a.provider, {}).get("cofre") or "~/.cofre-casa").expanduser()
    env = a.env or cfg["providers"].get(a.provider, {}).get("env") or prov["env"]
    if not (cofre / ".envless").is_dir():
        die(f"{cofre} não é um cofre do envless (sem .envless/). Use --cofre <pasta>", 3)

    def have() -> set[str]:
        r = subprocess.run(["envless", "list", f"--env={env}"], cwd=cofre, capture_output=True, text=True)
        return {k for k in prov["keys"] if k in r.stdout}

    if have() != set(prov["keys"]) and a.client_secret_json:
        data = json.loads(Path(a.client_secret_json).expanduser().read_text())
        c = data.get("installed") or data.get("web") or {}
        pairs = {prov["keys"][0]: c.get("client_id"), prov["keys"][1]: c.get("client_secret")}
        if not all(pairs.values()):
            die("o JSON não tem client_id/client_secret (baixe o 'App para computador')", 3)
        for k, val in pairs.items():  # the value goes by stdin, never argv
            subprocess.run(["envless", "set", k, f"--env={env}"], cwd=cofre, input=val, text=True, check=True,
                           capture_output=True)
        print(f"cliente OAuth guardado no envless ({env}): {', '.join(prov['keys'])}.")
        print(f"O arquivo {a.client_secret_json} ainda tem o segredo em texto: apague-o depois (é do dono).")
    present = have()
    if present != set(prov["keys"]):
        print("Falta o cliente OAuth do Google no envless. Passos do dono, nessa ordem:")
        for n, (txt, url) in enumerate(prov["console"], 1):
            print(f"  {n}. {txt}\n     {url}")
        print(f"Depois: auth.sh setup {a.provider} --client-secret-json <o JSON baixado>")
        sys.exit(3)
    cfg["providers"][a.provider] = {"cofre": str(cofre), "env": env}
    save(cfg)
    emit("provider.updated", {"provider": a.provider, "env": env, "keys": sorted(present)})
    print(f"provedor {a.provider} pronto: cliente no envless ({env}), chaves {', '.join(sorted(present))}.")
    pending = []
    for alias, acct in cfg["accounts"].items():
        if acct["provider"] != a.provider:
            continue
        os.makedirs(acct["dir"], exist_ok=True)
        os.chmod(acct["dir"], 0o700)
        if profile() == "owner" or profile() in acct.get("profiles", []):
            res = check_one(cfg, alias, acct, quiet=True)
            if not res["ok"]:
                pending.append(alias)
            print(f"  {alias:<10} {acct['email']:<32} {mark(res['status'])}")
    if pending:
        print("\nPassos do dono (abrem o navegador; escolha a conta indicada). Um comando por conta:")
        for alias in pending:
            print(f"  auth.sh login {alias}    # {cfg['accounts'][alias]['email']}")
        print("Depois: auth.sh check")


def main() -> None:
    p = argparse.ArgumentParser(prog="auth.sh", description="A identidade segura do agente: contas por provedor, segredos só no envless.")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup", help="prepara um provedor (cliente no envless, pastas, checagem)")
    s.add_argument("provider", nargs="?", default="google")
    s.add_argument("--client-secret-json")
    s.add_argument("--cofre")
    s.add_argument("--env")
    s = sub.add_parser("add", help="registra uma conta")
    s.add_argument("provider"), s.add_argument("alias"), s.add_argument("email")
    s.add_argument("--services", help="ex.: calendar,gmail (padrão calendar)")
    s.add_argument("--write", action="store_true", help="leitura e escrita (padrão: só leitura)")
    s.add_argument("--grant", help="perfis que podem usar, separados por vírgula")
    for name in ("grant", "revoke"):
        s = sub.add_parser(name, help=f"{name} a conta a um perfil")
        s.add_argument("alias"), s.add_argument("--profile", required=True)
    s = sub.add_parser("login", help="login no navegador (passo do dono)")
    s.add_argument("alias")
    s = sub.add_parser("list", help="contas e estado")
    s.add_argument("--provider"), s.add_argument("--json", action="store_true")
    s = sub.add_parser("aliases", help="apelidos que este perfil pode rodar")
    s.add_argument("provider", nargs="?")
    s = sub.add_parser("check", help="sonda as contas")
    s.add_argument("alias", nargs="?"), s.add_argument("--json", action="store_true")
    s = sub.add_parser("run", help="roda um comando com o ambiente da conta")
    s.add_argument("alias"), s.add_argument("argv", nargs=argparse.REMAINDER)
    s = sub.add_parser("remove", help="apaga o token local (nunca revoga no provedor)")
    s.add_argument("alias"), s.add_argument("--yes", action="store_true")
    a = p.parse_args()
    {"setup": cmd_setup, "add": cmd_add, "login": cmd_login, "list": cmd_list, "aliases": cmd_aliases,
     "check": cmd_check, "run": cmd_run, "remove": cmd_remove,
     "grant": lambda x: cmd_grant(x, True), "revoke": lambda x: cmd_grant(x, False)}[a.command](a)


if __name__ == "__main__":
    main()
