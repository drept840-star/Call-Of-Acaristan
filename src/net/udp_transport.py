"""Small, bounded helpers for the real-time match datagram channel.

Gameplay datagrams are intentionally disposable: each input replaces the
previous state and each snapshot is numbered by simulation tick. The reliable
TCP match socket remains the control channel and fallback when UDP cannot be
reached (for example through a TCP-only tunnel).
"""

import ipaddress
import socket
import threading
import time

from net import portmap
from net import protocol as P

# Stay below the common 1,280-byte IPv6 minimum MTU after IP/UDP headers.
# Large snapshots are sent over the reliable fallback rather than fragmented.
MAX_DATAGRAM_BYTES = 1200
MAX_DATAGRAMS_PER_PUMP = 64
MAX_INPUTS_PER_SECOND = 120.0
# Inputs one pump may take at once; covers a host frame hitch.
INPUT_BURST = 8.0
UDP_PROBE_INTERVAL = 0.5
UDP_STALE_SECONDS = 1.5
UDP_FALLBACK_RETRY = 2.0
# Hole punching: how often and for how long the host fires punch datagrams
# at a joiner's public endpoint. Any datagram works; one byte decodes to
# nothing on the client and is dropped there.
PUNCH_INTERVAL = 0.25
PUNCH_SECONDS = 15.0
PUNCH_DATAGRAM = b"\x00"
STUN_TRIES = 3
STUN_RETRY = 1.0


def encode_datagram(message):
    """Encode one JSON datagram, or return None rather than fragmenting it."""
    try:
        data = P.encode(message)
    except (TypeError, ValueError, OverflowError):
        return None
    return data if len(data) <= MAX_DATAGRAM_BYTES else None


def decode_datagram(data):
    """Decode a bounded datagram; malformed/oversized input is ignored."""
    if not isinstance(data, (bytes, bytearray)) or not data \
            or len(data) > MAX_DATAGRAM_BYTES:
        return None
    return P.decode(data)


def token_matches(candidate, expected):
    """Compare an assigned UDP token without timing-dependent string checks."""
    import hmac
    return bool(candidate and expected) and hmac.compare_digest(
        P.clean_token(candidate).encode("ascii"),
        P.clean_token(expected).encode("ascii"))


def punch_endpoint(ip, port):
    """A peer-reported public endpoint, or None if it is not one to punch.

    Loopback stays allowed so host and join on one PC still works.
    """
    try:
        addr = ipaddress.IPv4Address(ip)
        port = int(port)
    except (TypeError, ValueError):
        return None
    if (not 0 < port < 65536 or addr.is_multicast or addr.is_unspecified
            or addr == ipaddress.IPv4Address("255.255.255.255")):
        return None
    return (str(addr), port)


class StunMapper(object):
    """Learn the public endpoint of one game UDP socket.

    Requests go out from the game socket itself, so the router mapping they
    reveal is the one the match will use. Replies arrive in the game's own
    receive pump, which hands them to ``feed``. DNS and resends run on a
    daemon thread so the render loop never blocks.
    """

    def __init__(self, sock, servers=None):
        self.sock = sock
        self.servers = servers if servers is not None else portmap.STUN_SERVERS
        self.endpoint = None
        self.done = False
        self._txids = set()
        self._lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        addrs = []
        for host, port in self.servers:
            try:
                addrs.append((socket.gethostbyname(host), port))
            except OSError:
                pass
        for _ in range(STUN_TRIES):
            if self.endpoint is not None or not addrs:
                break
            for addr in addrs:
                packet, txid = portmap.stun_request()
                with self._lock:
                    self._txids.add(txid)
                try:
                    self.sock.sendto(packet, addr)
                except OSError:
                    pass
            time.sleep(STUN_RETRY)
        self.done = True

    def feed(self, data):
        """Consume a STUN reply; False means it is a game datagram."""
        if not portmap.is_stun(data):
            return False
        with self._lock:
            mapped = portmap.parse_stun_response(data, self._txids)
        if mapped is not None and self.endpoint is None:
            self.endpoint = mapped
        return True
