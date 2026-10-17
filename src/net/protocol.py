
"""Wire protocol for the Acaristan multiplayer master server.

Deliberately dependency-free: stdlib only, no pygame, no game modules. The
in-game client (``src/net/client.py``) and the standalone server
(``tools/mp_server.py``) both import this, so the framing rules can never
drift apart between the two ends.

Framing is newline-delimited JSON over TCP. That is deliberately boring: it is
trivially inspectable with ``netcat``/``telnet``, it survives partial reads
(we buffer until a newline arrives), and it needs no third-party serializer.
Payloads are tiny -- a server row is well under 200 bytes -- so the extra
bytes from JSON text versus a packed binary struct are irrelevant at the
request rates involved (a query every few seconds, chat messages at human
speed).
"""

import json
import math
import zlib

PROTO_VERSION = 1

# Default endpoints. The master listens on TCP; the discovery beacon is a
# separate UDP port so LAN clients can find a master without configuring an
# address (broadcast probe -> master replies with its TCP endpoint).
DEFAULT_MASTER_HOST = "127.0.0.1"
DEFAULT_MASTER_PORT = 27015
DISCOVERY_PORT = 27016
DISCOVERY_MAGIC = b"ACARISTAN-MP-DISCOVERY/1"
DISCOVERY_REPLY = b"ACARISTAN-MP-HOST/1"

# Message type constants. Kept as strings so a packet stays readable in a
# packet capture, which matters when debugging "the list is empty".
T_HELLO = "hello"
T_WELCOME = "welcome"
T_QUERY = "query"
T_SERVERS = "servers"
T_CHAT = "chat"
T_BYE = "bye"
T_REGISTER = "register"
T_ERROR = "error"

# A "soft" error is a note, not a disconnection. The flag matters because the
# client's reaction to `error` has always been "this session is broken, stop
# retrying" -- correct for a protocol mismatch, catastrophic for "you are
# sending too fast". Marking the throttling and refusal replies soft is what
# stops a player who types quickly from losing their server list over it.
T_ERROR_FIELD = "soft"


def make_error(text, soft=False):
    """Build an ``error`` packet. ``soft`` keeps the client's session alive."""
    msg = {"t": T_ERROR, "text": str(text or "")[:120]}
    if soft:
        msg[T_ERROR_FIELD] = 1
    return msg


def is_soft_error(msg):
    """True when an ``error`` packet is a note rather than a fault.

    A hard error remains the default, so an older master that knows nothing
    about soft errors keeps its original (fatal) meaning.
    """
    return isinstance(msg, dict) and msg.get(T_ERROR_FIELD) == 1
# ── Gameplay (step 2: snapshot layer) ──
# T_SNAPSHOT is host -> client, the authoritative world state. T_INPUT is
# client -> host, the player's intent for the coming tick. Both are additive:
# a peer that does not know these types simply never sends or expects them,
# so the existing chat/lobby protocol is unaffected.
T_SNAPSHOT = "snap"
T_INPUT = "in"
T_JOIN_MATCH = "joinmatch"
# T_YOU is host -> client, sent once when a connection is accepted: it tells
# the client which roster slot it owns. Without it a client had no way to
# know its own id and assumed 0 (the host's player) for aiming and local
# gunfeel, so a joiner was aiming and recoiling from the host's position.
T_YOU = "you"
# T_MATCH_CHAT is a chat line inside a running arena match, relayed by the
# HOST over the match socket. It is deliberately NOT the lobby's T_CHAT:
# that one is relayed by the master and reaches people who are not in your
# match at all, so reusing the type would make "who can hear this" depend on
# which socket a packet happened to arrive on. A match is its own channel.
T_MATCH_CHAT = "mchat"
# T_KICK is host -> client, sent before the socket closes when the host
# removes a player. The alternative is a closed socket, which a client
# cannot tell apart from its own wifi dropping, so it either sits in a dead
# arena or reports a network fault for something a human did.
T_KICK = "kick"
# T_HOST_LEFT is host -> client, sent once when the HOST ends the session:
# it pressed LEAVE, closed the game, or lost its connection. The host owns
# the whole match, so its departure is not "a player left", it is "the match
# no longer exists" -- every client must be torn down. Without an explicit
# packet a client can only infer that from the socket dying, which is
# indistinguishable from its own wifi dropping, so it sat in a dead arena
# waiting for a snapshot that could never arrive.
T_HOST_LEFT = "hostleft"
# T_TEAM_PICK is client -> host: "put me on this side". The host owns every
# team assignment, so a preference has to travel to it rather than be applied
# locally -- a client that moved itself would be a client whose teammates never
# see the move, and friendly-fire suppression would disagree with the roster.
# The answer comes back as the ordinary `teams` table on the next state packet.
T_TEAM_PICK = "tpick"
TEAM_PICK_IPA = 0
TEAM_PICK_KRAP = 1
TEAM_PICK_TEAMS = (TEAM_PICK_IPA, TEAM_PICK_KRAP)

# Fields are ints, not bools, because bool is a subclass of int in Python and
# `isinstance(True, int)` would let a malformed peer smuggle a bool through a
# validator that only checks for int. Keeping them ints also makes the JSON
# unambiguous across languages.
ENT_PLAYER = 0
ENT_ENEMY = 1
ENT_REMOTE = 2

# Player animation states. Sent by number rather than by name because these
# go out 20x a second per player and the string is pure overhead on the wire.
PS_IDLE = 0
PS_MOVING = 1
PS_SHOOTING = 2
PS_RELOADING = 3
PS_MELEE = 4
PS_DEAD = 5
PS_STATES = (PS_IDLE, PS_MOVING, PS_SHOOTING, PS_RELOADING, PS_MELEE, PS_DEAD)

# Weapons, also numeric for the same reason.
WPN_PISTOL = 0
WPN_OS12 = 1
WPN_K9 = 2
WPN_NONE = 3
WPN_BY_NAME = {"pistol": WPN_PISTOL, "os12": WPN_OS12, "k9": WPN_K9}
WPN_NAMES = {WPN_PISTOL: "pistol", WPN_OS12: "os12", WPN_K9: "k9", WPN_NONE: "none"}



def encode(obj):
    """Serialize one message to a newline-terminated bytes object."""
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode(line):
    """Parse one message. Returns None on malformed input (never raises).

    The client must tolerate garbage on the wire: a hostile or merely buggy
    peer should degrade to "ignore that packet", not crash the game loop.
    """
    if not line:
        return None
    try:
        obj = json.loads(line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else line)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def checksum(text):
    """Short stable digest used to derive a chat colour from a username.

    Deterministic across processes (unlike ``hash()``, which is salted per
    interpreter run), so a given player keeps the same colour between runs.
    """
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


CHAT_COLORS = (
    (180, 180, 180),
    (100, 160, 220),
    (80, 220, 100),
    (220, 180, 60),
    (220, 120, 45),
    (200, 120, 220),
    (120, 220, 200),
)


def color_for(user):
    """Map a username to a stable, legible chat colour."""
    return CHAT_COLORS[checksum(user or "?") % len(CHAT_COLORS)]


def normalize_row(raw):
    """Coerce a server row from the wire into the game's tuple shape.

    The UI stores rows as ``(name, current_players, max_players, ping)``
    tuples, so normalising at the boundary keeps every existing render and
    hit-test site working unchanged. Returns None if the row is unusable.

    Clamps are deliberate: a malformed or hostile master must not be able to
    make the browser render a negative player count or a 4-billion ping that
    overflows the layout maths.
    """
    if isinstance(raw, (list, tuple)):
        parts = list(raw) + [None] * (4 - len(raw))
        name, cur, mx, ping = parts[:4]
    elif isinstance(raw, dict):
        name = raw.get("name")
        cur = raw.get("current", raw.get("cur"))
        mx = raw.get("max", raw.get("max_players"))
        ping = raw.get("ping")
    else:
        return None

    if not isinstance(name, str) or not name:
        return None
    try:
        cur = int(cur)
        mx = int(mx)
        ping = int(ping)
    except (TypeError, ValueError):
        return None
    if mx < 1:
        mx = 1
    cur = max(0, min(mx, cur))
    ping = max(0, min(9999, ping))
    return (name, cur, mx, ping)


def normalize_rows(raw_list):
    """Normalize a list of wire rows, dropping junk. Never raises."""
    if not isinstance(raw_list, (list, tuple)):
        return []
    out = []
    for raw in raw_list:
        row = normalize_row(raw)
        if row is not None:
            out.append(row)
    return out


# ── Snapshot codec ──────────────────────────────────────────────────────
# A snapshot is the host's authoritative world at one tick, sent to every
# client. Two properties matter, and both are about the wire rather than the
# game:
#
# 1. SMALL. Measured: a chat line is 42 bytes; one entity as a verbose JSON
#    object is 118. At 20 Hz with 8 players that is ~19 KB/s per client, all
#    of it key names. Entities are therefore positional arrays -- the field
#    order is fixed and documented below -- which brings one entity to 64
#    bytes. Fewer keys is the single biggest win available, and it costs
#    only readability, which ENT_FIELDS below restores.
#
# 2. HOSTILE-PEER SAFE. This data arrives off a socket. A client must never
#    crash, allocate unboundedly, or be shoved off the map because a peer
#    sent a bad number. Every field is range-checked, and a structurally
#    wrong message is dropped whole.
#
# Entity tuple layout (positional; order is load-bearing):
#   0 id      int    stable per match
#   1 kind    int    ENT_PLAYER / ENT_ENEMY / ENT_REMOTE
#   2 x       float  px, clamped to a sane map range
#   3 y       float  px, clamped to a sane map range
#   4 angle   float  degrees, wrapped to 0..360
#   5 hp      int    clamped 0..MAX_HP
#   6 state   int    PS_* for players; ignored for enemies
#   7 weapon  int    WPN_*
#   8 flags   int    bitfield, see F_*
# Snapshot envelope: {"t": "snap", "k": tick, "e": [entity, ...]}

MAX_ENTITIES = 64
MAX_ENTITIES_PER_SNAPSHOT = 128
# Generous but finite. Maps are a few thousand px; anything beyond this is
# either a bug or an attempt to push a client off the map.
MAX_COORD = 20000.0
MAX_HP = 1000

# Flag bits.
F_FIRING = 1 << 0
F_RELOADING = 1 << 1
F_INVULNERABLE = 1 << 2
F_SPRINTING = 1 << 3

# Reload REQUEST. Distinct from F_RELOADING, which is the host's statement of
# current state: "please reload" is a rising edge the client sends once, while
# "reloading" is a level the host broadcasts for as long as it lasts. Reusing
# one bit for both would make a late duplicate packet restart a reload.
F_RELOAD = 1 << 4

# Entity field 9 is the input sequence the host has CONSUMED for this player,
# not the sequence it last received. Client-side prediction replays every input
# after that ack over the authoritative position, so this number is the whole
# reconciliation contract: get it wrong and the local player rubber-bands
# forever, get it right and corrections are sub-pixel.
#
# Wire shape is 9 fields (through "flags"); "ack" was added afterwards and is
# padded when absent, so a snapshot from an older peer still parses.
ENT_MIN_FIELDS = 9
ENT_FIELDS = ("id", "kind", "x", "y", "angle", "hp", "state", "weapon",
              "flags", "ack")
# Sentinel meaning "this peer told us nothing about acks". Treated as
# "replay everything", which is the safe direction: a redundant replay is
# corrected by the next snapshot, whereas a skipped one never self-heals.
ACK_NONE = -1

# ── Authoritative events ────────────────────────────────────────────────
# The host used to broadcast only positions, so the client re-traced its own
# shots locally to decide whether it hit. That cosmetic guess disagreed with
# the host whenever the world moved between the snapshot and the trace, which
# is most of the time -- you would see "HIT" on shots that hit a wall. The
# host now states what happened; the client only plays it.
T_EVENTS = "ev"

# Host -> client: the rules the client cannot infer from entity positions.
# Scores, the round clock, team assignment and which pickups are still on the
# map all live on the host. Without this packet a client has to guess them,
# and the guess is always wrong -- it cannot know the clock is running out.
#
# Sent at 2 Hz rather than with every snapshot: none of it changes fast, and
# the scoreboard is the only per-player list in the game.
T_MATCH_STATE = "ms"
MATCH_STATE_HZ = 2
# Simulation rate, stated here so both ends agree without importing the
# session module (which would drag pygame-free net code into arena.py).
TICK_RATE = 60
# Bound what we accept. A peer must not be able to make us allocate an
# arbitrarily large scoreboard or pickup list.
MAX_SCOREBOARD_ROWS = 16
MAX_PICKUPS = 64
MAX_LOBBY_PLAYERS = 8
SESSION_PHASES = ("lobby", "countdown", "playing")
# Identity. A name is drawn above a sprite, in the kill feed and in the
# scoreboard strip, so 16 characters is what those layouts can actually
# show; a longer one is truncated rather than wrapped.
MAX_NAME_CHARS = 16
DEFAULT_PLAYER_NAME = "PLAYER"
# One chat line, matching the lobby's cap. Long enough for a sentence,
# short enough that one packet is never a scrollback.
MAX_CHAT_CHARS = 180
# Ceiling on a published respawn timer. Bounds what a client will believe a
# countdown can be, so a bad (or hostile) match-state packet cannot park a
# "respawning in 9999" plate on someone's screen.
MAX_RESPAWN_SECONDS = 30.0

# Event kinds. Each event is a fixed 6-slot array [kind, a, b, c, d, e]:
# fixed-width so the payload stays positional (see the snapshot note above on
# why keys are a bandwidth regression) and so a short list cannot be
# misread field-by-field.
EV_HIT = 0       # a shooter  b victim  c damage  d x  e y
EV_KILL = 1      # a killer  b victim  c weapon  d x  e y
EV_PICKUP = 2    # a player  b pickup kind  c -  d x  e y
EV_SPAWN = 3     # a player  b -  c -  d x  e y
# EV_EMPTY is the trigger pull that went nowhere: the magazine was dry, so
# the host auto-started a reload and the shot never happened. It has to be an
# event rather than something a client infers from ammo, because only the
# host knows the magazine was empty AT THE MOMENT the player pulled -- the
# client sees ammo counts arrive twice a second, which is not the same
# moment. Without it a dry trigger pull is completely silent.
EV_EMPTY = 4     # a player  b -  c -  d x  e y
EV_FIELDS = 6
# A peer must not be able to make us allocate an unbounded event list.
MAX_EVENTS_PER_PACKET = 64


def _clamp_coord(v):
    """Coerce to a finite float inside the map range. Never raises."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f or f in (float("inf"), float("-inf")):   # NaN / inf
        return 0.0
    return max(-MAX_COORD, min(MAX_COORD, f))


def _wrap_angle(v):
    """Coerce to a finite float in 0..360. Never raises."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f or f in (float("inf"), float("-inf")):
        return 0.0
    return f % 360.0


def make_entity(eid, kind, x, y, angle=0.0, hp=100, state=PS_IDLE,
                weapon=WPN_PISTOL, flags=0, ack=ACK_NONE):
    """Build one sanitized entity tuple. Clamps every field."""
    return (
        int(eid) & 0xFFFF,
        int(kind) & 0xFF,
        _clamp_coord(x),
        _clamp_coord(y),
        _wrap_angle(angle),
        max(0, min(MAX_HP, int(hp))),
        int(state) & 0xFF,
        int(weapon) & 0xFF,
        int(flags) & 0xFFFF,
        _clean_ack(ack),
    )


def _clean_ack(ack):
    """Coerce an ack sequence to a sane int. Never raises.

    Negative values other than ACK_NONE are meaningless, and a huge one is
    either a malformed packet or a peer trying to make a client drop its
    whole pending-input history (which would leave the player frozen). So
    both collapse to ACK_NONE, which costs one redundant replay instead.
    """
    try:
        v = int(ack)
    except (TypeError, ValueError):
        return ACK_NONE
    if v == ACK_NONE or v < 0:
        return ACK_NONE
    return min(v, 0xFFFFFFFF)


def entity_to_dict(ent):
    """Expand a positional tuple into named keys (logging, tests, debugging)."""
    return dict(zip(ENT_FIELDS, ent))


def make_snapshot(tick, entities):
    """Build a wire snapshot, skipping any entity that is not well formed."""
    out = []
    for e in entities:
        if not isinstance(e, (list, tuple)) or len(e) < len(ENT_FIELDS):
            continue
        out.append(tuple(e[:len(ENT_FIELDS)]))
        if len(out) >= MAX_ENTITIES_PER_SNAPSHOT:
            break
    return {"t": T_SNAPSHOT, "k": int(tick) & 0xFFFFFFFF, "e": out}


def parse_snapshot(msg):
    """Validate an inbound snapshot. Returns (tick, entities) or None.

    Never raises, whatever the peer sent. A structurally wrong message is
    dropped whole rather than partially applied: a half-understood snapshot
    would desync the client silently, which is far worse than missing a
    frame. Values that are merely out of range are clamped, because a
    player at an odd angle is a cosmetic problem while a dropped frame is
    a visible stutter.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_SNAPSHOT:
        return None
    try:
        tick = int(msg.get("k", -1)) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None
    raw = msg.get("e")
    if not isinstance(raw, (list, tuple)):
        return None
    if len(raw) > MAX_ENTITIES_PER_SNAPSHOT:
        return None
    ents = []
    for e in raw:
        # Accept the historical 9-field shape as well as the current 10.
        # Rejecting a short entity would mean a client and host from
        # different builds drop each other's snapshots entirely, and a
        # dropped frame is far more visible than a defaulted field.
        if not isinstance(e, (list, tuple)) or len(e) < ENT_MIN_FIELDS:
            return None
        try:
            ents.append((
                int(e[0]) & 0xFFFF,
                int(e[1]) & 0xFF,
                _clamp_coord(e[2]),
                _clamp_coord(e[3]),
                _wrap_angle(e[4]),
                max(0, min(MAX_HP, int(e[5]))),
                int(e[6]) & 0xFF,
                int(e[7]) & 0xFF,
                int(e[8]) & 0xFFFF,
                _clean_ack(e[9]) if len(e) > 9 else ACK_NONE,
            ))
        except (TypeError, ValueError):
            return None
    return tick, ents


def sanitize_name(raw, fallback=None):
    """Clean a player-supplied name into something safe to draw.

    A name is drawn in three places -- above a sprite, in the kill feed, and
    in the scoreboard strip -- and it arrives straight off a socket, so the
    bar is: no control characters (a name is ONE line; an embedded newline
    would break every one of those layouts), no leading/trailing space, no
    runs of whitespace, and a hard length cap.

    Returns None when nothing printable is left, so the caller substitutes a
    slot label instead of rendering an empty tag. Never raises.
    """
    if not isinstance(raw, str):
        return fallback
    out = []
    for ch in raw:
        # Whitespace of any kind becomes a plain space FIRST, so a name typed
        # across two lines reads as two words instead of one glued one. Other
        # control characters are dropped rather than replaced: a name is not a
        # format string and there is nothing legitimate they can encode here.
        if ch.isspace():
            out.append(" ")
        elif ch < " " or ch == "\x7f":
            continue
        else:
            out.append(ch)
    text = " ".join("".join(out).split())[:MAX_NAME_CHARS]
    return text or fallback


def default_name(player_id):
    """The fallback label for a slot whose player named themselves nothing.

    Derived from the slot id rather than counted from zero, so it matches the
    P%d convention used in the protocol docs and the lobby roster.
    """
    try:
        return "P%d" % (int(player_id) & 0xFFFF)
    except (TypeError, ValueError):
        return DEFAULT_PLAYER_NAME


MAX_APPEARANCE_KEYS = 8
APPEARANCE_ID_CHARS = 32
APPEARANCE_GUNS = 3
"""Bounds for a cosmetic loadout bundle. See ``clean_appearance``."""


def clean_appearance(raw):
    """Bound an appearance bundle structurally - shape and size, not meaning.

    Deliberately does NOT resolve identifiers against the cosmetic catalog.
    This module is dependency-free on purpose (see the header) so the
    standalone server and the game can never drift apart about framing, and
    the catalog is game data. What happens here is the part that protects the
    parser: a bounded dict of short strings.

    The property that actually matters for cosmetics holds either way, because
    an appearance carries identifiers and never carries colours -- there is no
    field a peer could put an arbitrary RGB in, so the worst a hostile peer can
    claim is an item it does not own, and ``core.appearance.normalize()``
    collapses that to the free default where the sprite is built.

    Returns None when there is nothing valid to send, so the caller can omit
    the key rather than send an empty dict.
    """
    if not isinstance(raw, dict) or len(raw) > MAX_APPEARANCE_KEYS:
        return None
    out = {}
    for key in ("palette", "head"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            out[key] = value[:APPEARANCE_ID_CHARS]
    finish = raw.get("finish")
    if isinstance(finish, dict) and 0 < len(finish) <= APPEARANCE_GUNS:
        clean = {}
        for gun, fid in finish.items():
            if isinstance(gun, str) and isinstance(fid, str) and fid:
                clean[gun[:16]] = fid[:APPEARANCE_ID_CHARS]
        if clean:
            out["finish"] = clean
    return out or None


def make_join_match(map_name=None, name=None, appearance=None, token=None):
    """Client -> host: the FIRST packet a match client sends.

    A listening socket accepts anything that connects to it, and the host
    runs a lobby relay in the same process whose master address can be the
    same port. Without this handshake the relay's own connection was
    accepted as a player, which spawned a phantom opponent that never moved
    and started the round with nobody actually there. Requiring the client
    to announce itself is what separates "a connection" from "a player".

    The name rides along here rather than in its own packet because it is
    the same fact: "I am a match client, and this is who I am". A separate
    message would mean a peer could be seated with no name and then named
    itself later, which is one more state to get wrong.

    The cosmetic loadout rides here for exactly the same reason, and it is
    sent once: what colours an opponent wears cannot change between their join
    and their death, so a per-packet field would be 20 Hz of dead weight.
    Version skew is handled by absence rather than by a marker -- an old host
    reads only t/map/n and ignores this key, and an old client sends no key at
    all, which ``join_match_appearance`` reports as nothing-claimed and the
    arena draws in the free default. It is NOT suppressed when it happens to be
    all defaults, because deciding what a default looks like means knowing the
    cosmetic catalog, and this module is dependency-free on purpose.
    """
    msg = {"t": T_JOIN_MATCH, "proto": PROTO_VERSION}
    if isinstance(map_name, str) and map_name:
        msg["map"] = map_name[:32]
    nick = sanitize_name(name)
    if nick:
        msg["n"] = nick
    look = clean_appearance(appearance)
    if look:
        msg["a"] = look
    tok = clean_token(token)
    if tok:
        msg["k"] = tok
    return msg


def clean_token(raw):
    """Normalize a join token: str, <=32 chars of [A-Za-z0-9_-], upper-cased.

    Returns "" for anything else, so a malformed token can never match.
    """
    if not isinstance(raw, str):
        return ""
    raw = raw.strip().upper()
    if not raw or len(raw) > 32:
        return ""
    if not all(c.isalnum() and c.isascii() or c in "-_" for c in raw):
        return ""
    return raw


def join_match_token(msg):
    """The secret token a client presented in its join handshake, or ""."""
    if not is_join_match(msg):
        return ""
    return clean_token(msg.get("k"))


def is_join_match(msg):
    """True if this is a match join handshake."""
    return isinstance(msg, dict) and msg.get("t") == T_JOIN_MATCH


def join_match_name(msg):
    """The name a client announced in its join handshake, or None.

    Sanitized on the way out as well as in, because the host must not trust
    that the sender ran the same helper: this is the value that gets drawn.
    """
    if not is_join_match(msg):
        return None
    return sanitize_name(msg.get("n"))


def join_match_appearance(msg):
    """The cosmetic loadout a client announced at join, or None.

    Re-cleaned on the way in for the same reason as the name: the host must
    not assume the sender ran the same helper. None means "said nothing", and
    the arena draws that slot in the free default.
    """
    if not is_join_match(msg):
        return None
    return clean_appearance(msg.get("a"))


def sanitize_chat(raw):
    """Clean one chat line: a single run of printable text, or None.

    Same reasoning as ``sanitize_name`` -- all whitespace becomes single
    spaces so a line break cannot break the chat panel's layout, and the
    length is capped so one packet cannot be a megabyte of text.
    """
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split())[:MAX_CHAT_CHARS]
    return text or None


def make_match_chat(text):
    """Client or host -> everyone: one chat line for the current match.

    Returns None for text that sanitizes away to nothing, so a caller can
    skip a blank message instead of putting it on the wire.
    """
    body = sanitize_chat(text)
    if body is None:
        return None
    return {"t": T_MATCH_CHAT, "x": body}


def parse_match_chat(msg):
    """The chat body from an inbound match-chat packet, or None."""
    if not isinstance(msg, dict) or msg.get("t") != T_MATCH_CHAT:
        return None
    return sanitize_chat(msg.get("x"))


def match_chat_author(msg):
    """The host's attribution for a relayed chat line, or None.

    Present only on the copy the host broadcasts, because only the host knows
    who sent the original: a client's own outbound line carries no name field
    at all. A client that put one in anyway is ignored -- the host overwrites
    it with its own roster entry rather than forwarding it, which is what
    stops anyone posting as somebody else.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_MATCH_CHAT:
        return None
    return sanitize_name(msg.get("by"))


def make_team_pick(team):
    """Client -> host: ask to be seated on *team* (0 = IPA, 1 = KRAP)."""
    return {"t": T_TEAM_PICK, "team": int(team)}


def parse_team_pick(msg):
    """The requested side, or None when this is not a valid team pick.

    Re-checked against the two real sides instead of trusted, because this
    arrives from an arbitrary peer and is about to index a team table and drive
    a friendly-fire rule. A peer claiming team 47, or "banana", or True, is
    refused here at the edge like every other inbound field.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_TEAM_PICK:
        return None
    team = msg.get("team")
    if isinstance(team, bool) or not isinstance(team, int):
        return None
    return team if team in TEAM_PICK_TEAMS else None


def make_kick(reason="removed by the host"):
    """Host -> client: you have been removed from this match.

    Sent while the socket is still open, one beat before it closes, for the
    same reason T_HOST_LEFT exists: a client that only sees the socket die
    cannot distinguish "the host kicked me" from "my connection dropped",
    and it will report the wrong one to the player.
    """
    msg = {"t": T_KICK}
    text = sanitize_chat(reason)
    if text:
        msg["r"] = text[:64]
    return msg


def parse_kick(msg):
    """The host's stated reason, or None if this is not a kick packet.

    Returns '' (not None) for a reasonless kick, because "you were kicked" is
    a complete answer even when nobody bothered to say why.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_KICK:
        return None
    reason = msg.get("r")
    return reason[:64] if isinstance(reason, str) else ""


def make_assign(player_id, map_name=None, mode=None):
    """Host -> client: the roster slot this connection owns.

    Also carries the host's map name and game mode, because the client picks
    its own map and mode on the entry panel and would otherwise simulate and
    render geometry and rules the host is not using (positions would be
    nonsense, and a team match would run as free-for-all).
    """
    msg = {"t": T_YOU, "id": int(player_id) & 0xFFFF}
    if isinstance(map_name, str) and map_name:
        msg["map"] = map_name[:32]
    if isinstance(mode, str) and mode:
        msg["mode"] = mode[:8]
    return msg


def parse_assign(msg):
    """Validate an inbound assign packet. Returns the id, or None."""
    if not isinstance(msg, dict) or msg.get("t") != T_YOU:
        return None
    try:
        return int(msg.get("id", -1)) & 0xFFFF
    except (TypeError, ValueError):
        return None


# ── Authoritative events ─────────────────────────────────────────────────
# The host states what happened; the client only presents it. Before this,
# the client re-traced its own shot locally to guess whether it connected,
# and disagreed with the host whenever anything moved between the snapshot
# and the guess.


def make_host_left(reason="host left the match"):
    """Host -> client: this session is over because the host ended it.

    Sent while the sockets are still open, one frame before the host closes
    them, so a client can step out of the arena with an explanation instead
    of guessing whether its own connection dropped. A peer that does not
    know the type simply ignores it and still falls back on the socket
    closing, so an older client is no worse off than before.
    """
    msg = {"t": T_HOST_LEFT}
    if isinstance(reason, str) and reason:
        msg["r"] = reason[:64]
    return msg


def parse_host_left(msg):
    """The host's parting reason, or None if this is not a host-left packet.

    Returns '' (not None) for a packet with no reason, because "the host
    left" is still a complete answer even when it did not say why.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_HOST_LEFT:
        return None
    reason = msg.get("r")
    return reason[:64] if isinstance(reason, str) else ""


def make_events(tick, events):
    """Build one event packet, dropping malformed events rather than the lot.

    Individual events are junk-filtered instead of the whole packet being
    rejected: a single bad entry must not cost the kill feed a hit.
    """
    out = []
    for ev in events or ():
        if not isinstance(ev, (list, tuple)) or len(ev) < EV_FIELDS:
            continue
        kind = int(ev[0]) & 0xFF
        a = int(ev[1]) & 0xFFFF
        b = int(ev[2]) & 0xFFFF
        c = float(ev[3])
        d = _clamp_coord(ev[4])
        e = _clamp_coord(ev[5])
        out.append([kind, a, b, _clamp_coord(c), d, e])
        if len(out) >= MAX_EVENTS_PER_PACKET:
            break
    return {"t": T_EVENTS, "k": int(tick) & 0xFFFFFFFF, "x": out}


def parse_events(msg):
    """Validate an inbound event packet. Returns (tick, events) or None.

    Never raises, whatever the peer sent. One malformed entry drops that
    entry, not the packet -- the events that matter most (the kill you just
    scored) are rarely the one that got corrupted.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_EVENTS:
        return None
    try:
        tick = int(msg.get("k", -1)) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None
    raw = msg.get("x")
    if not isinstance(raw, (list, tuple)) or len(raw) > MAX_EVENTS_PER_PACKET:
        return None
    out = []
    for ev in raw:
        if not isinstance(ev, (list, tuple)) or len(ev) < EV_FIELDS:
            continue
        try:
            out.append((
                int(ev[0]) & 0xFF,
                int(ev[1]) & 0xFFFF,
                int(ev[2]) & 0xFFFF,
                int(float(ev[3]) & 0x7FFFFFFF),
                _clamp_coord(ev[4]),
                _clamp_coord(ev[5]),
            ))
        except (TypeError, ValueError):
            continue
    return tick, out


def make_match_state(state):
    """Build the match-state packet from ArenaSim.match_state().

    Keys are used here (not positional arrays) on purpose. This packet goes
    out twice a second, not twenty, and unlike an entity it is not on the
    hot path where a descriptive key costs bandwidth. It also travels with
    scoreboards and pickup lists that gain fields over time, which is much
    easier to evolve additively when a reader ignores what it does not know.
    """
    if not isinstance(state, dict):
        return {"t": T_MATCH_STATE}
    msg = {"t": T_MATCH_STATE}
    mode = state.get("mode")
    if isinstance(mode, str):
        msg["mode"] = mode[:8]
    phase = state.get("phase")
    if isinstance(phase, str):
        msg["phase"] = phase[:16]
    try:
        msg["round"] = max(1, int(state.get("round", 1)))
        msg["clock"] = max(0, min(0x7FFFFFFF, int(state.get("clock", 0))))
    except (TypeError, ValueError):
        return {"t": T_MATCH_STATE}
    winner = state.get("winner")
    if winner is not None:
        try:
            msg["winner"] = int(winner) & 0xFFFF
        except (TypeError, ValueError):
            pass
    board = state.get("scoreboard")
    if isinstance(board, (list, tuple)):
        rows = []
        for row in board[:MAX_SCOREBOARD_ROWS]:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                rows.append([int(row[0]) & 0xFFFF, int(row[1]) & 0xFFFF,
                             int(row[2]) & 0xFFFF])
            except (TypeError, ValueError):
                continue
        msg["scoreboard"] = rows
    # First-to target for the KRAP-terminal scoreboard strip (match_state
    # only; snapshots never carry it). Validated like clock: a sane int or
    # dropped, never a crash in the render loop.
    if "score_limit" in state:
        try:
            msg["score_limit"] = max(1, min(99, int(state["score_limit"])))
        except (TypeError, ValueError):
            pass
    # Small int-keyed maps: teams and ammo. JSON turns int keys into strings,
    # so these are normalised to strings here and back at the parse site.
    for src, dst in (("teams", "teams"), ("team_scores", "team_scores"),
                     ("ammo", "ammo")):
        table = state.get(src)
        if isinstance(table, dict):
            out = {}
            for k, v in list(table.items())[:MAX_SCOREBOARD_ROWS]:
                try:
                    out[str(int(k))] = int(v)
                except (TypeError, ValueError):
                    continue
            if out:
                msg[dst] = out
    # What each player is CARRYING. The HUD needs it to grey out the weapon
    # a player has not picked up, and weapon switching needs it locally so a
    # refused request can be explained instead of just doing nothing. Lists
    # rather than a scalar, so each value is validated element by element.
    carry = state.get("carry")
    if isinstance(carry, dict):
        out = {}
        for k, v in list(carry.items())[:MAX_SCOREBOARD_ROWS]:
            if not isinstance(v, (list, tuple)):
                continue
            try:
                ids = [int(w) & 0xFF for w in v[:8]]
            except (TypeError, ValueError):
                continue
            if ids:
                out[str(int(k))] = ids
        if out:
            msg["carry"] = out
    picks = state.get("pickups")
    if isinstance(picks, (list, tuple)):
        out = []
        for p in picks[:MAX_PICKUPS]:
            if not isinstance(p, (list, tuple)) or len(p) < 5:
                continue
            kind = p[2]
            if not isinstance(kind, str):
                continue
            try:
                out.append([_clamp_coord(p[0]), _clamp_coord(p[1]),
                            kind[:12], int(p[3]) & 0xFF,
                            max(0, min(0x7FFFFFFF, int(p[4])))])
            except (TypeError, ValueError):
                continue
        msg["pickups"] = out
    session_phase = state.get("session_phase")
    if session_phase in SESSION_PHASES:
        msg["session_phase"] = session_phase
    if "room_capacity" in state:
        try:
            msg["room_capacity"] = max(2, min(MAX_LOBBY_PLAYERS,
                                               int(state["room_capacity"])))
        except (TypeError, ValueError):
            msg["room_capacity"] = 2
    if "countdown" in state:
        try:
            countdown = float(state["countdown"])
            if not math.isfinite(countdown):
                countdown = 0.0
            msg["countdown"] = max(0.0, min(30.0, countdown))
        except (TypeError, ValueError):
            msg["countdown"] = 0.0
    roster = state.get("roster")
    if isinstance(roster, (list, tuple)):
        clean_roster = []
        seen = set()
        for row in roster[:MAX_LOBBY_PLAYERS]:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                pid = int(row[0]) & 0xFFFF
            except (TypeError, ValueError):
                continue
            if pid in seen:
                continue
            seen.add(pid)
            name = str(row[1])[:24]
            clean_roster.append([pid, name])
        msg["roster"] = clean_roster
    # Who each player IS, keyed by slot. The roster above only rides the
    # host's lobby/room-state packet, but names are needed for the whole
    # match -- every kill feed row, name tag and scoreboard chip resolves
    # through this -- so it ships on the 2 Hz rules packet where every
    # client already looks.
    msg.update(_names_table(state.get("names")))
    msg.update(_looks_table(state.get("looks")))
    msg.update(_respawn_table(state.get("respawn")))
    dead = _dead_slots(state.get("dead"))
    if dead:
        msg["dead"] = dead
    # Which session this state belongs to. The round-payout log keys on it so
    # a host restart is a genuinely new set of rounds rather than a chance to
    # be paid twice for the same result.
    match_id = state.get("match_id")
    if isinstance(match_id, str) and match_id:
        msg["mid"] = match_id[:MATCH_ID_CHARS]
    return msg


def _names_table(raw):
    """Normalize a {slot: name} map into a wire table, or {}."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in list(raw.items())[:MAX_SCOREBOARD_ROWS]:
        try:
            pid = int(k) & 0xFFFF
        except (TypeError, ValueError):
            continue
        clean = sanitize_name(v)
        if clean:
            out[str(pid)] = clean
    return {"names": out} if out else {}


MATCH_ID_CHARS = 16


def _looks_table(raw):
    """Normalize a {slot: appearance} map into a wire table, or {}.

    Structurally a twin of ``_names_table`` on purpose: same row cap, same
    slot-key normalization, same "omit the key when there is nothing to say".
    A peer that sends a hundred rows or a non-dict value gets those entries
    dropped rather than a crash.
    """
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in list(raw.items())[:MAX_SCOREBOARD_ROWS]:
        try:
            pid = int(k) & 0xFFFF
        except (TypeError, ValueError):
            continue
        clean = clean_appearance(v)
        if clean:
            out[str(pid)] = clean
    return {"looks": out} if out else {}


def _respawn_table(raw):
    """Normalize a {slot: seconds-remaining} map into a wire table, or {}."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in list(raw.items())[:MAX_SCOREBOARD_ROWS]:
        try:
            pid = int(k) & 0xFFFF
            secs = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(secs):
            continue
        secs = max(0.0, min(MAX_RESPAWN_SECONDS, secs))
        if secs > 0.0:
            out[str(pid)] = secs
    return {"respawn": out} if out else {}


def _dead_slots(raw):
    """Normalize a list of dead slot ids into a wire list, or [].

    A set rather than a {slot: seconds} map because the two facts are not the
    same: which players are down, and how long each one waits. Only the first
    is needed to keep a corpse on the floor, and deriving it from the second
    loses anybody whose countdown is zero while their body is not.
    """
    if not isinstance(raw, (list, tuple, set)):
        return []
    out = []
    for v in list(raw)[:MAX_SCOREBOARD_ROWS]:
        if isinstance(v, bool):
            continue
        try:
            pid = int(v) & 0xFFFF
        except (TypeError, ValueError):
            continue
        if pid not in out:
            out.append(pid)
    return out


def parse_match_state(msg):
    """Validate an inbound match-state packet. Returns a dict, or None.

    Every field is re-validated on the way in. This arrives from a peer like
    any other, and the HUD indexes straight into the result -- a malformed
    scoreboard row would raise inside the render loop.
    """
    if not isinstance(msg, dict) or msg.get("t") != T_MATCH_STATE:
        return None
    out = {}
    for key, limit in (("mode", 8), ("phase", 16)):
        val = msg.get(key)
        if isinstance(val, str):
            out[key] = val[:limit]
    try:
        out["round"] = max(1, int(msg.get("round", 1)))
        out["clock"] = max(0, min(0x7FFFFFFF, int(msg.get("clock", 0))))
    except (TypeError, ValueError):
        return None
    if "winner" in msg:
        try:
            out["winner"] = int(msg["winner"]) & 0xFFFF
        except (TypeError, ValueError):
            out["winner"] = None
    else:
        out["winner"] = None
    board = msg.get("scoreboard")
    if isinstance(board, (list, tuple)):
        rows = []
        for row in board[:MAX_SCOREBOARD_ROWS]:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                rows.append((int(row[0]) & 0xFFFF, int(row[1]) & 0xFFFF,
                             int(row[2]) & 0xFFFF))
            except (TypeError, ValueError):
                continue
        out["scoreboard"] = rows
    if "score_limit" in msg:
        try:
            out["score_limit"] = max(1, min(99, int(msg["score_limit"])))
        except (TypeError, ValueError):
            pass
    for key in ("teams", "team_scores", "ammo"):
        table = msg.get(key)
        if isinstance(table, dict):
            clean = {}
            for k, v in list(table.items())[:MAX_SCOREBOARD_ROWS]:
                try:
                    clean[str(int(k))] = int(v)
                except (TypeError, ValueError):
                    continue
            out[key] = clean
    carry = msg.get("carry")
    if isinstance(carry, dict):
        clean = {}
        for k, v in list(carry.items())[:MAX_SCOREBOARD_ROWS]:
            if not isinstance(v, (list, tuple)):
                continue
            try:
                ids = [int(w) & 0xFF for w in v[:8]]
            except (TypeError, ValueError):
                continue
            if ids:
                clean[str(int(k))] = ids
        out["carry"] = clean
    picks = msg.get("pickups")
    if isinstance(picks, (list, tuple)):
        out_p = []
        for p in picks[:MAX_PICKUPS]:
            if not isinstance(p, (list, tuple)) or len(p) < 5:
                continue
            if not isinstance(p[2], str):
                continue
            try:
                out_p.append((_clamp_coord(p[0]), _clamp_coord(p[1]),
                              p[2][:12], int(p[3]) & 0xFF,
                              max(0, min(0x7FFFFFFF, int(p[4])))))
            except (TypeError, ValueError):
                continue
        out["pickups"] = out_p
    session_phase = msg.get("session_phase")
    if session_phase in SESSION_PHASES:
        out["session_phase"] = session_phase
    if "room_capacity" in msg:
        try:
            out["room_capacity"] = max(2, min(MAX_LOBBY_PLAYERS,
                                              int(msg["room_capacity"])))
        except (TypeError, ValueError):
            out["room_capacity"] = 2
    if "countdown" in msg:
        try:
            countdown = float(msg["countdown"])
            if not math.isfinite(countdown):
                countdown = 0.0
            out["countdown"] = max(0.0, min(30.0, countdown))
        except (TypeError, ValueError):
            out["countdown"] = 0.0
    roster = msg.get("roster")
    if isinstance(roster, (list, tuple)):
        clean_roster = []
        seen = set()
        for row in roster[:MAX_LOBBY_PLAYERS]:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                pid = int(row[0]) & 0xFFFF
            except (TypeError, ValueError):
                continue
            if pid in seen:
                continue
            seen.add(pid)
            name = row[1] if isinstance(row[1], str) else "Player"
            clean_roster.append((pid, name[:24]))
        out["roster"] = clean_roster
    # Shared builders, so the names and respawn tables are validated by
    # exactly the same code on the way out as on the way in. A reader that
    # disagreed with its writer about clamping is how a client ends up
    # indexing a table that the host never sent.
    out.update(_names_table(msg.get("names")))
    out.update(_looks_table(msg.get("looks")))
    out.update(_respawn_table(msg.get("respawn")))
    out["dead"] = _dead_slots(msg.get("dead"))
    match_id = msg.get("mid")
    if isinstance(match_id, str) and match_id:
        out["match_id"] = match_id[:MATCH_ID_CHARS]
    return out


def assign_map(msg):
    """The map name from an assign packet, or None if absent/invalid."""
    if not isinstance(msg, dict) or msg.get("t") != T_YOU:
        return None
    name = msg.get("map")
    return name if isinstance(name, str) and name else None


def assign_mode(msg):
    """The game mode from an assign packet, or None if absent/invalid."""
    if not isinstance(msg, dict) or msg.get("t") != T_YOU:
        return None
    name = msg.get("mode")
    return name if isinstance(name, str) and name else None


def make_input(seq, move_x, move_y, aim, buttons=0, weapon=None, cycle=False):
    """Client -> host intent for one tick.

    ``move_x``/``move_y`` are -1/0/1 axes rather than pixels: the host
    multiplies by its own player speed, so a client cannot cheat by
    claiming a huge dx, and cannot gain an advantage by sending floats.

    ``weapon`` is a REQUEST to switch to one specific gun, and ``cycle`` is a
    request to move to the NEXT one carried. Both are requests: the host owns
    the loadout and refuses anything not picked up off the map. Both are
    omitted entirely when unused, because 60 of these go out a second and
    the common packet should stay as short as it has always been.
    """
    def axis(v):
        f = _clamp_coord(v)
        return -1 if f < -0.5 else (1 if f > 0.5 else 0)
    msg = {
        "t": T_INPUT,
        "q": int(seq) & 0xFFFFFFFF,
        "mx": axis(move_x),
        "my": axis(move_y),
        "a": _wrap_angle(aim),
        "b": int(buttons) & 0xFFFF,
    }
    if weapon is not None:
        msg["w"] = int(weapon) & 0xFF
    if cycle:
        msg["c"] = 1
    return msg


def parse_input(msg):
    """Validate an inbound input packet. Returns a dict or None."""
    if not isinstance(msg, dict) or msg.get("t") != T_INPUT:
        return None
    try:
        seq = int(msg.get("q", -1)) & 0xFFFFFFFF
        buttons = int(msg.get("b", 0)) & 0xFFFF
    except (TypeError, ValueError):
        return None

    def _axis(v):
        """Snap to -1/0/1 the same way make_input does.

        Deliberately NOT int(v): int() truncates toward zero, so a client
        sending -0.9 ("mostly left") would arrive as 0 -- silently dead
        input rather than an error. Snapping keeps the two ends in
        agreement about what a fractional axis means.
        """
        f = _clamp_coord(v)
        return -1 if f < -0.5 else (1 if f > 0.5 else 0)

    mx, my = _axis(msg.get("mx", 0)), _axis(msg.get("my", 0))
    out = {
        "q": seq,
        "mx": mx,
        "my": my,
        "a": _wrap_angle(msg.get("a", 0.0)),
        "b": buttons,
    }
    # "w" only appears when the peer actually asked to switch, so the common
    # packet keeps the exact five-key shape it has always had. Garbage here is
    # dropped rather than clamped, because "no switch requested" and "switch
    # to some weapon" are different intents and guessing would teleport a
    # player between guns mid-fight.
    if "w" in msg:
        try:
            out["w"] = int(msg["w"]) & 0xFF
        except (TypeError, ValueError):
            pass
    # "c" is the cycle request (Q / mouse wheel). It has to survive
    # validation or a client's key press is silently dropped here and the
    # host -- which only ever sees the parsed dict -- never learns anyone
    # asked to switch at all.
    if msg.get("c"):
        out["wcycle"] = 1
    return out
