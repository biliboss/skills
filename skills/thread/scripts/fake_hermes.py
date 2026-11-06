#!/usr/bin/env python3
"""Fake `hermes` for thread.sh tests: state in $FAKE_DIR; a raw-tty TUI that understands bracketed paste."""
import os, sys, tty, termios, glob

D = os.environ["FAKE_DIR"]
SESS = os.path.join(D, "sessions.tsv")


def rows():
    if not os.path.exists(SESS):
        return []
    return [l.rstrip("\n").split("\t") for l in open(SESS) if l.strip()]


def save(r):
    open(SESS, "w").write("".join("\t".join(x) + "\n" for x in r))


args = sys.argv[1:]
if "-p" in args:
    i = args.index("-p"); del args[i:i + 2]

if args[:2] == ["sessions", "list"]:
    print("Title                        Workspace          Last Active   ID")
    print("-" * 100)
    for sid, title in rows():
        print(f"{title:<28} {'biliboss':<18} {'just now':<13} {sid}")
    sys.exit(0)
if args[:2] == ["sessions", "rename"]:
    r = rows()
    for x in r:
        if x[0] == args[2]:
            x[1] = " ".join(args[3:])
    save(r)
    sys.exit(0)

# TUI
cont = args[1] if args[:1] in (["--continue"], ["--resume"]) else None
if cont:
    open(os.path.join(D, "resumed"), "a").write(" ".join(args) + "\n")
os.makedirs(os.path.join(D, "msgs"), exist_ok=True)
fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setraw(fd)
os.write(1, b"\x1b[?2004h")
os.write(1, b"ready \xe2\x80\xa2 sonnet\r\n")
buf, line, inpaste, made = b"", b"", False, cont is not None
try:
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        buf += chunk
        while buf:
            if buf.startswith(b"\x1b[200~"):
                inpaste, buf = True, buf[6:]; continue
            if buf.startswith(b"\x1b[201~"):
                inpaste, buf = False, buf[6:]; continue
            if inpaste and b"\x1b[201~" in buf:
                j = buf.index(b"\x1b[201~"); line += buf[:j]; buf = buf[j:]; continue
            if inpaste:
                line += buf; buf = b""; continue
            c, buf = buf[:1], buf[1:]
            if c in (b"\r", b"\n"):
                text = line.decode(); line = b""
                if text.startswith("/branch "):
                    r = rows(); r.append([f"branch-{len(r)+1}", text[8:]]); save(r); made = True
                    os.write(1, b"\r\nbranched \xe2\x86\x92 " + text[8:].encode() + b"\r\n")
                elif text:
                    n = len(glob.glob(os.path.join(D, "msgs", "*")))
                    open(os.path.join(D, "msgs", str(n + 1)), "wb").write(text.encode())
                    if not made:
                        r = rows(); r.append([f"new-{len(r)+1}", "(untitled)"]); save(r); made = True
            else:
                line += c
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
