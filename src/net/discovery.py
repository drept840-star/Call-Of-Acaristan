
"""LAN auto-discovery for the master server.

A separate module from the client because discovery is a fire-and-forget
UDP broadcast with a short timeout -- it is used at menu time, once, rather
than on a loop. Keeping it out of client.py means a headless tool can
import discovery without pulling in the client state machine.
"""

import socket

from net import protocol as P


def discover_master(timeout=1.5, broadcast_addr="255.255.255.255"):
    """Broadcast a probe and return (host, port) of the first master that answers.

    Returns None if nothing answers within ``timeout``. This is best-effort
    by design: a player with no LAN master simply gets None and falls back
    to the configured host.

    Note this does not work on every network -- a router that blocks
    broadcast, a VPN, or a subnet that does not route 255.255.255.255 will
    all make it silently return None. That is expected and harmless.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
    except OSError:
        return None

    try:
        sock.sendto(P.DISCOVERY_MAGIC, (broadcast_addr, P.DISCOVERY_PORT))
        try:
            data, addr = sock.recvfrom(512)
        except (socket.timeout, OSError):
            return None
        if not data.startswith(P.DISCOVERY_REPLY):
            return None
        # Reply format: DISCOVERY_REPLY + ":port"
        tail = data[len(P.DISCOVERY_REPLY):].decode("ascii", "replace")
        if tail.startswith(":"):
            tail = tail[1:]
        try:
            port = int(tail)
        except ValueError:
            port = P.DEFAULT_MASTER_PORT
        return (addr[0], port)
    finally:
        sock.close()
