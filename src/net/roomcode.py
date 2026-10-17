
"""Short, game-branded room codes for direct arena matches.

A room code is the host's address in disguise. It packs the IPv4 and port
into a compact Crockford-base32 string with an in-universe prefix, so a host
can hand a friend a handful of characters instead of an IP (which is easy
to mistype) - and the friend can read it out loud over voice chat.

    >>> decode(encode("82.78.75.76", 27015))
    ('82.78.75.76', 27015)

No server is involved: the code *is* the address. That is deliberate. A
board that maps codes to addresses would be a rendezvous service - more
infrastructure, and a separate project. This works the moment the host can
accept an inbound connection at all (UPnP/NAT-PMP forwarding; see
net/portmap.py), which is the same requirement as sharing a raw address.

The prefix is pure flavour: it says which corner of Acaristan the match
belongs to (the coalition, the party, Route 12, ...). encode() mints one at
random so every host is not handed the same "ACAR-..." string, and decode()
accepts the whole pool so a code from an older build still opens. The last
symbol is a checksum, so a mistyped code is rejected instead of happily
connecting to some random address.
"""

import random
import socket

# In-universe prefixes. All of them fit the fiction, all of them are four
# characters or fewer (so the code stays short enough to read aloud), and
# none of them use "-". Adding one here is all it takes to make a new flavour
# decode; LEGACY_PREFIXES below is for flavours a friend may still be holding.
PREFIX_POOL = (
    "ACAR",   # Acaristan - the national registry everything is filed under
    "KRAP",   # the KRAP peacekeeping coalition
    "KRPN",   # KRAPNET, the relay the server browser talks to
    "IPA",    # Independent Party Acaristan - the ruling party
    "MAG",    # Maru's Anarchy Group
    "R12",    # the Route 12 corridor
    "MARU",   # Maru's underground cell
    "BIRI",   # Biribel's field callsign
    "VOLK",   # Volkov logistics
)

# Codes minted by an older build still decode. Kept separate from the pool so
# retiring a flavour can never orphan a code somebody already wrote down.
LEGACY_PREFIXES = ()

PREFIXES = PREFIX_POOL + LEGACY_PREFIXES
DEFAULT_PREFIX = "ACAR"

# Match the longest prefix first: "ACARIS" and "ACAR" must not be resolved by
# whichever happens to come first in the tuple.
_PREFIXES_LONGEST_FIRST = tuple(sorted(PREFIXES, key=len, reverse=True))

# Crockford base32: no I, L, O or U, so handwriting (and reading aloud)
# cannot be defeated by the I/1 and O/0 confusion.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CHECK_MOD = len(_ALPHABET)
_DECODE = {ch: i for i, ch in enumerate(_ALPHABET)}
# Fold the letters people still type onto the digits they resemble.
_DECODE.update({"I": 1, "L": 1, "O": 0, "U": 0})

# 4 (IPv4) + 2 (port) bytes = 48 bits -> exactly 10 base32 symbols,
# plus one checksum symbol.
_BODY_SYMBOLS = 10


def random_prefix(rng=None):
    """Pick one in-universe prefix. ``rng`` takes a seeded random.Random."""
    return (random if rng is None else rng).choice(PREFIX_POOL)


def _payload_values(host, port):
    raw = socket.inet_aton(str(host)) + int(port).to_bytes(2, "big")
    bits = "".join(format(b, "08b") for b in raw)     # 48 bits
    bits += "0" * ((-len(bits)) % 5)                  # pad to 50 = 10x5
    return [int(bits[i:i + 5], 2) for i in range(0, len(bits), 5)]


def encode(host, port, prefix=None):
    """(host, port) -> "KRAP-XXXXX-XXXXXX", or "" if not a usable IPv4/port.

    ``prefix`` defaults to a random in-universe flavour; pass one explicitly
    (e.g. a host that wants to keep a single flavour for a whole session).
    """
    try:
        vals = _payload_values(host, port)
    except (OSError, OverflowError, ValueError, TypeError):
        return ""
    if prefix is None:
        prefix = random_prefix()
    vals.append(sum(vals) % _CHECK_MOD)               # checksum symbol
    body = "".join(_ALPHABET[v] for v in vals)
    return "%s-%s-%s" % (str(prefix).upper(), body[:_BODY_SYMBOLS // 2],
                         body[_BODY_SYMBOLS // 2:])


def decode(code):
    """Room code -> (host, port), or None if it is not a valid code.

    Accepts any prefix in PREFIX_POOL (or LEGACY_PREFIXES) and is tolerant of
    case, spaces and dashes. Anything containing address punctuation (dots or
    colons) is rejected, so a plain "1.2.3.4:27015" is never mistaken for a
    code - callers can try this first and fall back to parsing a raw address.
    """
    if not isinstance(code, str):
        return None
    text = code.strip().upper().replace(" ", "")
    if not text or "." in text or ":" in text:
        return None
    for p in _PREFIXES_LONGEST_FIRST:
        if text.startswith(p + "-"):
            text = text[len(p) + 1:]
            break
    text = text.replace("-", "")
    if len(text) != _BODY_SYMBOLS + 1:
        return None
    vals = []
    for ch in text:
        v = _DECODE.get(ch)
        if v is None:
            return None
        vals.append(v)
    body, check = vals[:_BODY_SYMBOLS], vals[_BODY_SYMBOLS]
    if sum(body) % _CHECK_MOD != check:
        return None
    bits = "".join(format(v, "05b") for v in body)
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, 48, 8))
    host = ".".join(str(b) for b in data[:4])
    port = int.from_bytes(data[4:6], "big")
    if not (1 <= port <= 65535):
        return None
    return host, port
