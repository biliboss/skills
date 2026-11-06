#!/usr/bin/env python3
"""fork.py <source-id> <title> [--profile P]: branch a Hermes session OFFLINE and print the new session id.

Run with Hermes's own interpreter (thread.sh finds it). Same lineage as /branch and the API server's
POST /api/sessions/{id}/fork: a child row with parent_session_id + the durable `_branched_from` marker,
the source's system prompt and active transcript copied, then the title. Unlike /branch it does NOT end
the source: the source may be a live chat, and ending it would break it. It never attaches to it either.
"""
import os
import sys
from contextlib import suppress

ROOT = os.environ.get("HERMES_AGENT_ROOT") or os.path.expanduser("~/.hermes/hermes-agent")


def main(argv):
    args, profile = [], None
    it = iter(argv)
    for a in it:
        if a in ("-p", "--profile"):
            profile = next(it, None)
        else:
            args.append(a)
    if len(args) != 2 or not args[0] or not args[1].strip():
        print("usage: fork.py <source-id> <title> [--profile P]", file=sys.stderr)
        return 2
    source_id, title = args[0], args[1].strip()
    sys.path.insert(0, ROOT)
    # Puts Hermes's dependencies on the path, as the launcher does; must run before HERMES_HOME is
    # pointed at a profile (a fresh home would trigger a dependency sync).
    keep = os.environ.pop("HERMES_HOME", None)
    import hermes_bootstrap  # noqa: F401
    if profile:  # explicit --profile wins over an inherited HERMES_HOME (the caller's own profile)
        home = os.path.expanduser("~/.hermes")
        os.environ["HERMES_HOME"] = home if profile == "default" else os.path.join(home, "profiles", profile)
    elif keep:
        os.environ["HERMES_HOME"] = keep
    from hermes_state import SessionDB
    from hermes_state_ids import new_session_id

    db = SessionDB()
    source = db.get_session(source_id)
    if not source:
        print(f"fork.py: no session '{source_id}' in {os.environ.get('HERMES_HOME', '~/.hermes')}", file=sys.stderr)
        return 1
    new_id = new_session_id()
    # The label must be one the gateway can adopt on resume (a pre-gateway local source, as /branch's own "cli"):
    # copying a gateway-owned source's "local" makes `--resume <new>` fail with not_found in the TUI.
    legacy = {"cli", "tui", "gui", "desktop", "oneshot", "tool", "acp"}
    label = source.get("source") if source.get("source") in legacy else "cli"
    db.create_session(new_id, label, model=source.get("model"),
                      system_prompt=source.get("system_prompt"), parent_session_id=source_id,
                      model_config={"_branched_from": source_id})
    try:
        db.replace_messages(new_id, db.get_messages(source_id))
        db.set_session_title(new_id, title)
    except Exception as exc:  # no half branch: it would show untitled in the list
        with suppress(Exception):
            db.delete_session(new_id)
        print(f"fork.py: {exc}", file=sys.stderr)
        return 1
    print(new_id)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
