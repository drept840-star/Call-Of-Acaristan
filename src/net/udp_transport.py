"""Small, bounded helpers for the real-time match datagram channel.

Gameplay datagrams are intentionally disposable: each input replaces the
previous state and each snapshot is numbered by simulation tick. The reliable
TCP match socket remains the control channel and fallback when UDP cannot be
reached (for example through a TCP-only tunnel).
"""

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
