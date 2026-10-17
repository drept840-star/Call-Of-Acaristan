"""Self-hosted KRAPNET server for Call of Acaristan.

This is the "host a game and give your friends the address" tool. A player
runs it (or the packaged EXE), it opens a port on their router, prints an
address, and their friends connect straight to it. No central server, no
account, no master.

    python tools/mp_host.py                       # host with defaults
    python tools/mp_host.py --name "Biribel's Server"
    python tools/mp_host.py --port 27020
    python tools/mp_host.py --no-forward          # skip UPnP/NAT-PMP
    python tools/mp_host.py --check               # diagnose, host nothing

How it works
------------
The hosted thing is a *lobby relay*, exactly like tools/mp_server.py: it
serves the server list and relays chat. It does NOT run the game. Two
people can connect to it and talk; they cannot yet play together. That
limit is honest and is called out in the startup banner, because selling
this as "play with your friends" would be a lie.

Getting reachable from the internet is the interesting part, and it is not
in our control:

  * If the router supports UPnP or NAT-PMP, the port is opened
    automatically and we print the public address.
  * If not, we still print the LAN address, and explain exactly what to
    forward by hand. Many routers simply have UPnP switched off.
  * Double NAT (ISP modem + own router) and CGNAT will defeat this no
    matter what we do; the tool says so rather than pretending.

Everything is stdlib-only so the packaged EXE stays small and has no
install-time surprises.
"""

import argparse
import os
import re
import shutil
import signal
import socketserver
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from net import portmap, tcp_tunnel  # noqa: E402
from net import protocol as P  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mp_server import (  # noqa: E402
    MasterHandler, MasterState, ThreadedTCPServer,
)

DEFAULT_PORT = 27015
DEFAULT_NAME = "Call of Acaristan -- hosted game"
DEFAULT_MAX_PLAYERS = 8

RULES_TEMPLATE = [
    "GAMEMODE:  Hosted lobby",
    "MAP:       (to be announced)",
    "RULES:     1. Be decent. This is the internet.",
    "           2. Cheating ruins it for everyone.",
    "           3. Host has the final say.",
]


def _c(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def start_tunnel(port, timeout=25.0):
    """Use the same tested raw-TCP tunnel path as the arena."""
    endpoint, proc, provider = tcp_tunnel.start_tunnel(port, timeout)
    if endpoint:
        return provider, "%s:%d" % endpoint, proc
    _c("  Tunnel unavailable: " + tcp_tunnel.explain_error(provider))
    return None, None, None


def build_state(args):
    """Create the master state with exactly one row: this host's server."""
    state = MasterState(seed=False)
    state.register((args.name, 0, args.max_players, 0), RULES_TEMPLATE)
    return state


def firewall_hint():
    """A hint about the host firewall, a problem separate from NAT.

    On Windows the game EXE can be blocked by Defender Firewall. The
    listening socket still works locally, but inbound connections from
    outside get dropped. We cannot detect this reliably from here, so we
    print a note rather than pretending to know.
    """
    return ("If friends cannot connect, allow the executable through "
            "Windows Defender Firewall (private and public).")


def report_status(args, local):
    """Print network diagnostics without binding anything."""
    ext = portmap.public_ip()
    _c("  Public IP   : %s" % (ext if ext else "unknown (STUN blocked?)"))
    _c("  Behind NAT  : %s" % ("yes" if portmap.is_private(local) else "no"))
    locs = portmap._ssdp_discover(timeout=2.0)
    _c("  UPnP gateway: %s" % ("found" if locs else "none found"))
    _c("")
    _c("  Notes:")
    _c("   - " + firewall_hint())
    _c("   - Double NAT (modem + router) or carrier CGNAT cannot be fixed")
    _c("     from software. You would need a tunnel or a VPS.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Host a Call of Acaristan lobby and share the address")
    ap.add_argument("--name", default=DEFAULT_NAME,
                    help="server name friends will see")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--max-players", type=int, default=DEFAULT_MAX_PLAYERS)
    ap.add_argument("--no-forward", action="store_true",
                    help="do not attempt UPnP/NAT-PMP port forwarding")
    ap.add_argument("--tunnel", action="store_true",
                    help="get a public address via bore/ngrok, "
                         "so you never need to configure your router")
    ap.add_argument("--prefer-tunnel", action="store_true",
                    help="try the tunnel first, before UPnP")
    ap.add_argument("--no-discovery", action="store_true",
                    help="do not answer LAN discovery probes")
    ap.add_argument("--check", action="store_true",
                    help="report network status and exit without hosting")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    args.max_players = max(1, min(64, args.max_players))
    local = portmap.local_ip()

    _c("=" * 66)
    _c("  CALL OF ACARISTAN -- SELF-HOSTED LOBBY")
    _c("=" * 66)
    _c("  This hosts a LOBBY: server list + chat.")
    _c("  It does NOT run the game yet -- you can talk to friends here,")
    _c("  but you cannot play together yet. That is a separate project.")
    _c("")
    _c("  Server name : %s" % args.name)
    _c("  Port        : %d" % args.port)
    _c("  Max players : %d" % args.max_players)
    _c("  Your LAN IP : %s" % local)

    if args.check:
        _c("")
        report_status(args, local)
        return 0

    state = build_state(args)
    try:
        server = ThreadedTCPServer(("0.0.0.0", args.port), MasterHandler,
                                   state, verbose=not args.quiet)
    except OSError as exc:
        _c("")
        _c("  FAILED to bind port %d: %s" % (args.port, exc))
        _c("  Another program may be using it. Try --port 27020.")
        return 1

    stop_evt = threading.Event()
    if not args.no_discovery:
        from mp_server import run_discovery
        threading.Thread(target=run_discovery,
                         args=(P.DISCOVERY_PORT, args.port, stop_evt,
                               not args.quiet), daemon=True).start()

    _c("")
    _c("  Listening on 0.0.0.0:%d" % args.port)
    _c("")
    _c("-" * 66)

    forwarded = False
    tunnel_proc = None
    share = "%s:%d" % (local, args.port)

    if args.tunnel or args.prefer_tunnel:
        exe, hp, tunnel_proc = start_tunnel(args.port)
        if hp:
            share = hp
            forwarded = True
            _c("  Public address via %s: %s" % (exe, hp))
        elif not args.prefer_tunnel:
            _c("  Try reinstalling the game, or tools/download_bore.py for source runs.")
            _c("  Continuing with the normal method...")
    if not args.prefer_tunnel:
        if args.no_forward:
            _c("  Port forwarding skipped (--no-forward).")
        elif not tunnel_proc:
            _c("  Asking your router to open the port (UPnP, then NAT-PMP)...")
            result = portmap.open_port(
                args.port, args.port,
                description="Call of Acaristan (%s)" % args.name)
            if result.ok:
                forwarded = True
                _c("  Port forwarded via %s." % result.method)
                ext = result.external_ip or portmap.public_ip()
                if ext:
                    share = "%s:%d" % (ext, args.port)
            else:
                _c("  Could not forward the port automatically.")
                _c("  Reason: %s" % result.error)
                if result.guidance:
                    _c("  Fix: %s" % result.guidance)

    _c("")
    _c("  GIVE YOUR FRIENDS THIS ADDRESS:")
    _c("")
    _c("      %s" % share)
    _c("")
    if not forwarded:
        _c("  NOTE: that is your LAN address. Friends on the SAME wifi can")
        _c("        use it. Friends elsewhere need the port forwarded, or")
        _c("        they need a VPN/tunnel with you (Tailnet, ZeroTier, ngrok).")
        _c("  EASIEST: re-run with --tunnel and we do it for you.")
    else:
        _c("  Anyone on the internet can use that address while this")
        _c("  window stays open.")
    _c("")
    _c("  Friends do NOT need the game to chat. They can just run:")
    _c("      python tools/mp_join.py")
    _c("  and paste the address above.")
    _c("")
    _c("  " + firewall_hint())
    _c("")
    _c("-" * 66)
    _c("  Press Ctrl+C to stop hosting.")
    _c("-" * 66)

    def _sig(_signum, _frame):
        stop_evt.set()
        server.stopping = True
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _sig)
    try:
        signal.signal(signal.SIGTERM, _sig)
    except (ValueError, AttributeError, OSError):
        pass

    seen = {"n": -1, "t": 0.0}

    def _reporter():
        """Periodically tell the host how many people are actually here."""
        while not stop_evt.is_set():
            time.sleep(2.0)
            try:
                count = len(state.clients)
            except Exception:
                continue
            now = time.time()
            if count != seen["n"] or now - seen["t"] > 30:
                seen["n"] = count
                seen["t"] = now
                if not args.quiet:
                    _c("  [%s] %d connected" % (time.strftime("%H:%M:%S"), count))

    threading.Thread(target=_reporter, daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        stop_evt.set()
        server.server_close()
        # The tunnel is a child process; leaving it running would keep our
        # local port exposed to the internet after we stop hosting. That is
        # a security problem, not just a stray handle, so it always dies
        # with us -- including on Ctrl+C and on an unhandled exception.
        if tunnel_proc is not None:
            tcp_tunnel.stop_process(tunnel_proc)
            _c("  Tunnel closed.")
        _c("")
        _c("  Hosting stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

