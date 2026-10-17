"""Join a friend's Call of Acaristan lobby and chat. No game required.

    python tools/mp_join.py                  # asks for the address
    python tools/mp_join.py 1.2.3.4:27015   # or pass it straight in

This exists because the hard part of "test it with a friend" was never the
networking -- it was that your friend had to already own the game, install
Python, and know what a CONNECT box is. They do not. So this asks for one
thing (the address you texted them) and drops them into the chat.

The game itself offers the same chat under Multiplayer. This is the
zero-friction path for anyone who just wants to talk.
"""

import argparse
import os
import sys
import threading
import time

# Chat must appear line-by-line even when stdout is a pipe or a log file.
# Python block-buffers redirected output, so without this a friend running
# the EXE with output captured would see nothing until the buffer filled.
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass  # very old Python; nothing to do

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from net import protocol as P  # noqa: E402
from net.client import (  # noqa: E402
    MPRelayClient, register_chat_sink,
    ST_CONNECTING, ST_ERROR, ST_ONLINE,
)

LOCK = threading.Lock()
LINES = []          # (who, text) newest last
SEEN = set()        # dedupe so a backfilled line is not reprinted
MAXKEEP = 400


def sink(msg):
    """Chat sink. Runs on the client's worker thread, so guard the list."""
    who = msg.get("user", "?")
    text = msg.get("text", "")
    with LOCK:
        key = (who, text)
        if key in SEEN:
            return
        SEEN.add(key)
        LINES.append((who, text))
        if len(LINES) > MAXKEEP:
            del LINES[0:len(LINES) - MAXKEEP]


def parse_addr(text):
    """Accept 'host', 'host:port', or a pasted ngrok/url style string.

    Returns (host, port) or None. Forgiving here matters: your friend will
    paste whatever you sent them, stray slash and scheme included.
    """
    t = (text or "").strip().strip('"').strip("'")
    if not t:
        return None
    for pre in ("tcp://", "http://", "https://"):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    t = t.rstrip("/")
    for sep in ("?", "#", "/"):
        if sep in t:
            t = t.split(sep, 1)[0]
    port = P.DEFAULT_MASTER_PORT
    if t.count(":") == 1:
        h, _, p = t.partition(":")
        if p.isdigit() and 1 <= int(p) <= 65535:
            t, port = h, int(p)
    if not t or " " in t or not all(c.isalnum() or c in ".-" for c in t):
        return None
    return t, port


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Join a Call of Acaristan lobby and chat")
    ap.add_argument("address", nargs="?", default=None,
                    help="host or host:port (skips the prompt)")
    ap.add_argument("--name", default=None, help="your display name")
    args = ap.parse_args(argv)

    addr = args.address
    if not addr:
        print("=" * 58)
        print("  CALL OF ACARISTAN -- JOIN A FRIEND'S LOBBY")
        print("=" * 58)
        print("")
        print("  Your friend should have sent you an address that")
        print("  looks like  1.2.3.4:27015")
        print("")
        try:
            addr = input("  Paste it here: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 1

    parsed = parse_addr(addr)
    if not parsed:
        print("")
        print("  That does not look like an address.")
        print("  It should look like  1.2.3.4:27015  or just  1.2.3.4")
        print("")
        return 1
    host, port = parsed

    nick = args.name
    if not nick:
        default = (os.environ.get("USERNAME")
                   or os.environ.get("USER") or "friend")
        try:
            nick = input("  Your name [%s]: " % default).strip() or default
        except (EOFError, KeyboardInterrupt):
            nick = default

    client = MPRelayClient(host=host, port=port, nickname=nick)
    # Chat arrives on the client's worker thread; sink() is lock-guarded.
    register_chat_sink(sink)
    client.start()

    print("")
    print("  Connecting to %s:%d as %s ..." % (host, port, nick))
    print("  Type a message and press Enter to send it.")
    print("  Ctrl+C to leave.")
    print("")

    stop = threading.Event()

    # Input() blocks, so reading it on a worker keeps incoming chat
    # scrolling while you are half-way through typing a reply.
    def _reader():
        while not stop.is_set():
            try:
                line = input("")
            except (EOFError, KeyboardInterrupt):
                stop.set()
                return
            if stop.is_set():
                return
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("/quit", "/exit", "/q"):
                stop.set()
                return
            try:
                client.send_chat(line)
                # Type-and-quit is normal for a friend who fires off a last
                # line and closes the window; don't let that message vanish.
                client.flush(timeout=1.0)
            except Exception as exc:
                print("  Could not send: %s" % exc)

    threading.Thread(target=_reader, daemon=True).start()

    printed = 0
    last_status = None
    try:
        while not stop.is_set():
            time.sleep(0.1)
            status, error, _servers, _nick = client.state()
            if status != last_status:
                last_status = status
                if status == ST_ONLINE:
                    print("  [connected] say something")
                elif status == ST_ERROR and error:
                    print("  [problem] %s" % error)
                elif status == ST_CONNECTING:
                    print("  [connecting]")
            with LOCK:
                batch = LINES[printed:]
                printed = len(LINES)
            for who, text in batch:
                print("  <%s> %s" % (who, text))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        client.flush(timeout=1.0)
        client.stop()

    print("")
    print("  Disconnected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

