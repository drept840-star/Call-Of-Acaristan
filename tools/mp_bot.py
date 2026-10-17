"""Headless fake player, for testing multiplayer on ONE PC.

Launching the game twice on one machine is a bad way to test this: both
instances share save_data.json and settings.json, so the second one
overwrites the first's progress and settings on exit. This tool avoids
that entirely -- it speaks the real protocol over a real socket, so it
exercises exactly the code path a second player would, without pygame,
a window, or touching your save file.

Typical use -- start tools/mp_host.py, open the game on Multiplayer, then:

    python tools/mp_bot.py                       # join and sit there
    python tools/mp_bot.py --say hi there        # join and say something
    python tools/mp_bot.py --name Biribel --every 8 --count 5

Every line the bot sends is echoed by the master and should appear in the
game's chat panel, which is the point: it proves the whole loop
(bot -> socket -> host -> your game) without a second human.
"""

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from net import protocol as P  # noqa: E402
from net.client import MPRelayClient  # noqa: E402

CHATTER = [
    "anyone else here?",
    "lobby works",
    "gg",
    "testing 1 2 3",
    "can you see this",
    "hello from the other pc (same pc)",
    "we're connected!",
    "no gameplay yet, but chat is real",
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fake player for MP testing")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=P.DEFAULT_MASTER_PORT)
    ap.add_argument("--name", default="Tester2")
    ap.add_argument("--say", action="append", default=[],
                    help="send this line (repeatable)")
    ap.add_argument("--every", type=float, default=0.0,
                    help="auto-send chatter every N seconds")
    ap.add_argument("--count", type=int, default=0,
                    help="stop after this many auto lines (0 = forever)")
    ap.add_argument("--seconds", type=float, default=0.0,
                    help="exit after N seconds (0 = until Ctrl+C)")
    args = ap.parse_args(argv)

    received = []
    client = MPRelayClient(host=args.host, port=args.port,
                           nickname=args.name, chat_enabled=True)

    # Reuse the same hook the game uses, so this sees identical messages.
    import net.client as _C
    _C.register_chat_sink(lambda m: received.append(m))

    print("Connecting to %s:%d as %r ..." % (args.host, args.port, args.name))
    client.start()
    client.request_connect()

    deadline = time.time() + 10
    while time.time() < deadline:
        status, error, servers, _nick = client.state()
        if status == "online":
            break
        if status == "error" and error:
            print("  could not connect: %s" % error)
            print("  is the host running?  python tools\\mp_host.py")
            client.stop()
            return 1
        time.sleep(0.2)
    else:
        print("  timed out")
        client.stop()
        return 1

    status, error, servers, nick = client.state()
    print("Connected. Host reports %d server(s):" % len(servers))
    for name, cur, mx, ping, _rules in servers:
        print("    %-40s %d/%d  %dms" % (name[:40], cur, mx, ping))
    print("Now switch to the game (Multiplayer). Ctrl+C here to leave.\n")

    for line in args.say:
        client.send_chat(line)
        print("  sent: %s" % line)
        time.sleep(0.3)

    sent = 0
    end_at = time.time() + args.seconds if args.seconds else None
    try:
        while True:
            # Echo anything the game's chat panel sent us, so you can see
            # traffic flowing in both directions from one terminal.
            while received:
                msg = received.pop(0)
                if msg.get("user") != args.name:
                    print("  <%s> %s" % (msg.get("user"), msg.get("text")))
            if args.every and (not args.count or sent < args.count):
                now = time.time()
                if now >= (getattr(main, "_next", 0.0)):
                    line = random.choice(CHATTER)
                    if client.send_chat(line):
                        print("  sent: %s" % line)
                        sent += 1
                    main._next = now + args.every
            if end_at and time.time() >= end_at:
                break
            if args.count and sent >= args.count and not args.every:
                # Nothing left to do and no linger requested.
                if not received:
                    break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nLeaving.")
        client.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

