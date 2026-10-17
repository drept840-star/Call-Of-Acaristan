
"""The in-game arena match: entry panel plus the live match runtime.

Extracted from tools/mp_match.py so the menu and the CLI tool can drive the
same code. Two implementations of a netcode host is how you end up
debugging a bug that only happens in the game, or only in the tool, but
never in both.

Why it needs its own socket
---------------------------
The game already holds a *relay client* connection for chat and the server
list, and that connection is outbound. Hosting a match means LISTENING, and
one socket cannot do both. So a match opens its own connection, exactly as
the standalone tool does. The relay keeps running alongside it, so lobby
chat still works during a match -- but it is a DIFFERENT channel to
different people.

That distinction is load-bearing and used to be papered over. The lobby
relay reaches everybody connected to the master, which in practice means
"people who are not in your match". So the match carries its own chat
(``mchat``, relayed by the host over the match socket) on purpose: talking
to the four people you are actually fighting is a different act from talking
in a channel, and one of them is a game mechanic.

Modes
-----
``panel``   map picker + HOST / JOIN, no socket open yet
``hosting`` listening, simulating, broadcasting
``playing`` connected to somebody else's match
Esc always steps back out; it never quits the game.
"""

import hmac
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import secrets
import select
import socket
import threading
import time

import pygame

from core.config import WIDTH, HEIGHT, get_scaled_mouse
from core import profile_store
from core import settings_store
from net import protocol as P
from net import roomcode
from net import portmap
from net import tcp_tunnel
from net.match import Fanout, MatchSession, TICK_RATE
from missions import arena as AR
from ui.arena_view import ArenaView
from ui.widgets import clipboard_text
from ui import multiplayer_style as _mp_style
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

STEP = 1.0 / TICK_RATE
SCORE_LIMIT = 15
MAX_PLAYERS = 8
# Movement, in px per 60 Hz tick. These MUST match the host's ArenaSim
# defaults, because the client's predictor runs the identical maths against
# the same walls -- if the two ever disagree, every correction snaps.
PLAYER_SPEED = 5.0
SPRINT_SPEED = 8.2
# How long a kill-feed row stays up.
KILLFEED_FRAMES = 300
# Weapon select keys. Q cycles, 1-3 pick directly. A switch is a REQUEST; the
# host owns the loadout, so a client cannot equip something it has not picked
# up off the map.
WEAPON_KEYS = {
    pygame.K_1: P.WPN_PISTOL,
    pygame.K_2: P.WPN_OS12,
    pygame.K_3: P.WPN_K9,
}
# Q, and the mouse wheel, step to the NEXT weapon carried. Numbers pick one
# outright; cycling is what you actually use mid-fight, because it never
# needs you to remember whether the OS-12 is on 2 or 3. Both go through
# the host, which owns the loadout.
WEAPON_CYCLE_KEYS = (pygame.K_q,)
# The arena match deliberately does NOT use the lobby's port (27015, where
# the relay master lives). Sharing it meant the game's own lobby relay -
# which retries 127.0.0.1:27015 every few seconds - connected straight into
# the match listener the moment a player hosted, was accepted as a player,
# and started a round against a "bot" that never moved. The room code
# carries whichever port we land on, so nobody has to know this number.
DEFAULT_PORT = 27017
# How long an accepted connection may stay silent before it is treated as a
# stray socket rather than a slow player. A real client sends its join
# handshake the instant connect() returns, so this only ever catches things
# that were never going to join.
# An unauthenticated socket is held only briefly and NEVER counts against the
# player slots: a real client sends its handshake the moment connect()
# returns, so anything silent for this long is a scanner.
PENDING_PEER_TIMEOUT = 2.0
# Hard cap on simultaneous unverified sockets (oldest is evicted first), so a
# scan flood cannot exhaust file descriptors either.
MAX_PENDING_PEERS = 8
ACCEPTS_PER_FRAME = 4
JOIN_TOKEN_BYTES = 4  # token_hex -> 8 chars

# How long a CLIENT may hear nothing at all before it decides the host is
# gone. The host owns the match, so silence is fatal: without this a host
# that lost power (rather than closing cleanly) leaves every client in a
# frozen arena forever, because a dead TCP peer that never sends RST simply
# looks like an idle one. Long enough to ride out a hitch or an alt-tab.
HOST_SILENCE_TIMEOUT = 8.0
# What a host sees where the room code will appear, while the address is
# still being settled. Showing the half-minted code here meant hosts read a
# code out loud that was about to be replaced by a better one.
ROOM_CODE_PENDING_TEXT = "(establishing connection...)"
# How long a refused weapon-switch note stays on screen.
TOAST_SECONDS = 1.8

# ── Identity ────────────────────────────────────────────────────────────
# The name is typed on the entry panel and sent in the join handshake, so a
# peer is never seated with a name it has to acquire later. Length is the
# protocol's business (net/protocol.MAX_NAME_CHARS); this is only the field's
# own cap, kept in step with it so the box cannot be filled with text that
# would be silently cut on the wire.
NAME_CHARS = P.MAX_NAME_CHARS
# Shown in an empty name box. Rotates on the same slow clock as the address
# sample so the panel never looks frozen.
NAME_SAMPLES = ("KARPIN", "MAG-7", "VOLKOV", "R12", "MARU")

# ── In-match chat ───────────────────────────────────────────────────────
# Every one of these is about not getting in the way of a fight. The
# composer swallows input wholesale while it is open, so chat is opened
# deliberately with Enter and closed the same way, never by accident mid-run.
CHAT_MAX_INPUT = P.MAX_CHAT_CHARS
CHAT_LINE_H = 16
# Lines shown with the composer open. Enough to follow a conversation without
# covering the player standing next to you.
CHAT_VISIBLE = 6
# How long a message stays legible with the composer CLOSED, in frames. You
# can be shot on the way to the reply, so messages cannot vanish the instant
# you are done typing.
CHAT_IDLE_FRAMES = 260
CHAT_IDLE_VISIBLE = 3
CHAT_MAX_MESSAGES = 40
# Floor on the gap between two lines from one player, in seconds. The host
# enforces this on the relay path so one client cannot flood every other
# player's screen; it is generous enough that a human cannot hit it.
CHAT_MIN_GAP = 0.5

# The drop into a live match. The arena stays frozen for 3 / 2 / 1 / GO;
# the host announces the remaining time so every client shows the same beat
# and waits for the host's explicit "playing" phase before accepting input.
INTRO_SECONDS = 3.2
INTRO_STEP = INTRO_SECONDS / 4.0
ROOM_STATE_INTERVAL = 0.15

# Presentation geometry: fits the logical 1000x700 canvas with safe gutters.
PANEL_W, PANEL_H = 940, 644
PAD = 24
GAP_LABEL, GAP_ROW, GAP_BLOCK = 10, 8, 18
CHIP_H, FIELD_H, CTA_H, BACK_H = 36, 42, 44, 32
PANEL_X = (WIDTH - PANEL_W) // 2
PANEL_Y = (HEIGHT - PANEL_H) // 2

# Palette lifted from ui/mp.py's server browser so this screen does not
# look like a different program bolted onto the same game.
C_PANEL_BG = (14, 21, 24)
# Side colours for the lobby board. Warm/cool rather than the factions' own
# uniform greens and blues, because on a dark panel both of those read as
# "rectangle" and the whole point of the board is telling two groups apart at a
# glance from across the room.
TEAM_TINTS = {AR.TEAM_IPA: (214, 132, 62), AR.TEAM_KRAP: (104, 164, 228)}


def _fit_to_font(font, text, max_w):
    """Ellipsize *text* to *max_w* pixels for an already-built font.

    Measured rather than counted: this face is monospace at roughly 9.6px a
    character at size 16, so a fixed character budget overruns the button it was
    written for. Kept local and simple because only status labels need it here.
    """
    text = str(text)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return (text.rstrip() + "...") if text else ""
C_PANEL_EDGE = (48, 64, 66)
C_ROW_BG = (9, 16, 19)
C_ROW_HOVER = (29, 43, 43)
C_ACCENT = (232, 166, 82)          # the game's orange
C_CYAN = (131, 191, 200)          # selection / focus
C_TEXT = (225, 229, 216)
C_DIM = (148, 162, 157)
C_BAD = (255, 96, 96)

# The three-step explanation on the entry panel. Hosting is the one action in
# this screen that is not self-evident: pressing HOST MATCH does not connect
# you to anyone, it makes YOU the thing other people connect to, and the thing
# they need (a room code) only appears afterwards. Without these lines the
# button reads like "start playing now" and the player waits alone forever.
#
# Stored as (number, action, note) so the panel can give each part its own
# weight and align the note column on the widest action. HOST_HELP is the
# flat, test-readable form of the same data, so the two can never disagree.
HOST_STEPS = (
    ("1", "PRESS HOST MATCH", "the code appears once the address settles"),
    ("2", "SEND THE CODE", "LAN, forwarded port, or public tunnel"),
    ("3", "THEY PASTE IT", "MULTIPLAYER > ARENA MATCH > JOIN MATCH"),
)
HOST_HELP = tuple("%s  %-18s %s" % step for step in HOST_STEPS)


class Wire(object):
    """Newline-JSON framing over a socket.

    Named _send, not send, because that is the contract
    ``MatchSession._send()`` looks for. Naming it ``send`` means the
    attribute lookup fails, every snapshot is silently dropped, and the
    client renders an empty world -- which reads like a rendering bug
    rather than a missing underscore.
    """

    def __init__(self, sock):
        self.sock = sock
        self.out = b""
        self.lock = threading.Lock()

    def _send(self, obj):
        with self.lock:
            self.out += P.encode(obj)
            if len(self.out) > 16384:
                self.flush()

    def flush(self):
        with self.lock:
            if not self.out:
                return
            data, self.out = self.out, b""
        try:
            self.sock.sendall(data)
        except OSError:
            pass


class Peer(object):
    """One connected client and the player slot it owns.

    Keeping the read buffer and the assigned id together on the connection
    is what stops the classic roster bug: assigning a player id at accept
    time but freeing it somewhere else, so a late joiner inherits a slot
    whose previous owner is still sending input.

    ``player_id`` is None until the connection proves it is a match client
    by sending a join handshake. An accepted socket is not yet a player:
    anything that can reach the port (a lobby relay, a browser, a port
    scan) must not be able to spawn an opponent or start the round.
    """

    def __init__(self, sock, addr, player_id=None):
        self.sock = sock
        self.addr = addr
        self.player_id = player_id
        # The name from the join handshake, or None until it arrives. Held on
        # the connection rather than looked up in the sim because the chat
        # relay has to attribute a line to a sender, and the sender is the
        # socket, not a player id.
        self.name = None
        self.wire = Wire(sock)
        self.buf = b""
        self.created = time.monotonic()
        self.deferred = None

    @property
    def verified(self):
        return self.player_id is not None

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def aim_degrees(mouse, player_xy, cam_x, cam_y):
    """Angle from the player toward the mouse, in degrees.

    The mouse is screen-space, so it is converted back to world space
    first. Getting this wrong makes everyone shoot in a direction that
    looks right on their own screen and is nonsense to everybody else.
    """
    wx, wy = mouse[0] + cam_x, mouse[1] + cam_y
    return math.degrees(math.atan2(wy - player_xy[1],
                                   wx - player_xy[0])) % 360.0


def local_axes(keys):
    """WASD / arrows -> (-1..1, -1..1)."""
    dx = dy = 0
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        dy -= 1
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        dy += 1
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        dx -= 1
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        dx += 1
    return dx, dy


# Callsigns minted for a player who has not typed one of their own. Real
# handles rather than "Player 1", because a stranger reading "P1" over your
# head learns exactly nothing, and learning who is on the other end of the
# gun is the entire point of the name. Built from the same in-universe
# register as the room-code prefixes so it does not look bolted on.
CALLSIGN_STEMS = ("KARPOV", "VOLKOV", "MARU", "SEVA", "OTTO", "LUDMILA",
                  "GRIG", "ZARA", "MIRA", "BORIS", "ANNIKA", "RASK")
CALLSIGN_DIGITS = 100          # lowest two-digit suffix


def mint_callsign():
    """A fresh callsign for a player who has not chosen one."""
    return "%s-%d" % (_rng_legacy.choice(CALLSIGN_STEMS),
                      _rng_legacy.randint(CALLSIGN_DIGITS, 999))


def parse_addr(text):
    """'host', 'host:port', or a pasted cloudflared/ngrok address."""
    t = (text or "").strip().strip('"').strip("'")
    for pre in ("tcp://", "http://", "https://"):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    t = t.rstrip("/")
    for sep in ("?", "#", "/"):
        if sep in t:
            t = t.split(sep, 1)[0]
    port = DEFAULT_PORT
    if t.count(":") == 1:
        h, _, p = t.partition(":")
        if p.isdigit() and 1 <= int(p) <= 65535:
            t, port = h, int(p)
    return t or "127.0.0.1", port


class MatchScreen(object):
    """Owns the match-entry panel and, once entered, the match itself.

    One instance lives for the lifetime of the process; ``open_panel``
    raises it from the server browser and ``close`` lowers it. Keeping it
    alive across sessions is what lets a player change map or rejoin
    without the whole thing being rebuilt.
    """

    # Font cache shared by all instances: {(size, bold, mono): pygame Font}.
    # Building a Font is expensive and this panel redraws every frame, so
    # a per-instance cache would still thrash on every screen transition.
    _fonts = {}

    def __init__(self):
        # "closed", NOT "panel". The multiplayer screen is the SERVER BROWSER;
        # the arena panel is raised on top of it by ``open_panel`` when the
        # player clicks ARENA MATCH. Starting at "panel" meant every gate in
        # app.py's _MultiplayerState (handle_event / update / render all test
        # ``mode in ("panel", "hosting", "playing")``) treated the panel as
        # live from the first frame, so clicking MULTIPLAYER drew the host/join
        # panel and the server list could never be reached.
        self.mode = "closed"
        self.map_name = "yard"
        # FFA or TDM. Picked on the entry panel, authoritative on the host,
        # and echoed to clients in the match-state packet.
        self.mode_name = AR.MODE_TDM
        self.players = 4
        self.address = ""
        # The name this player competes under. Typed on the entry panel and
        # remembered between sessions, because being asked to retype your
        # handle every time you want to play with strangers is how a name
        # system quietly stops existing.
        self.player_name = settings_store.player_name()
        self.status = ""
        self.srv = None
        self.peers = []
        # Accepted-but-unverified connections. They become peers only when a
        # join handshake arrives (see _promote_pending_peer).
        self._pending_peers = []
        self._match_started = False
        # Host session phases: lobby -> countdown -> playing. Clients read the
        # same phase from host match-state packets; no join ever starts play.
        self._session_phase = "lobby"
        self._countdown_left = 0.0
        self._room_state_last = 0.0
        # Countdown/fade are driven by the host's remaining time. Every player
        # is frozen locally until the host publishes session_phase=playing.
        self._intro_left = 0.0
        self._intro_armed = False
        self._intro_black = None
        self._intro_plate = None
        self.sock = None
        self.wire = None
        self.sess = None
        self.sim = None
        self.view = None
        self._peer_addr = None
        # Client render clock: advances at 60 Hz, clamped to the newest
        # snapshot tick, so remote motion interpolates smoothly between the
        # 20 Hz packets instead of stepping at packet rate.
        self._client_tick = 0.0
        self._latest_snap_tick = None
        self.buf = b""
        self.seq = 0
        self._tracer = None
        self._tracer_t = 0.0
        self._pending = []          # [(host, port)] to try next update
        # Which entry-panel field has the caret: "name" or "address". This used
        # to be a constant "address", so there was no way to reach any second
        # field at all -- and a panel with two text boxes and one of them
        # unreachable is worse than one box.
        self.selected_field = "address"
        # In-match chat. The composer is a mode, not a widget: while it is
        # open every key belongs to it, because a chat line typed over a live
        # match has to not also strafe and fire. Named _composing rather than
        # _chat_open so it cannot be confused with open_chat()/close_chat().
        self._composing = False
        self._chat_input = ""
        # Newest last: [age_frames, author, text].
        self._chat_messages = []
        # player_id -> seconds of respawn left, counted down locally between
        # the host's 2 Hz rules packets. See _sync_respawn.
        self._respawn = {}
        self._host_dead = set()
        # Slots the host says are down, from its own sim rather than from a
        # countdown. Drives whose corpse stays on the floor; see _down_ids.
        self._host_dead = set()
        # Host tick our death was seen on. A world sample older than this is
        # evidence from BEFORE the kill, so it must not clear the corpse;
        # nothing newer can be filtered out at all. See _alive_from_world.
        self._death_sample_tick = None
        # Who killed us last, for the ELIMINATED plate. Cleared on respawn.
        self._last_killer = None
        # Latched so the round-end sting plays once per round rather than on
        # every frame the round is still over.
        self._round_end_played = False
        # What the round that just ended paid, as (amount, kills, place, won),
        # latched at the same edge. Cached because draw() must not write to
        # disk, and the card stays up for three hundred frames.
        self._last_payout = None
        # peer_id -> monotonic time of their last accepted chat line, for the
        # per-player rate floor on the relay.
        self._peer_chat_last = {}
        # In-match menu. Networking keeps running while paused so sockets
        # never back up; only the local player's input is zeroed.
        self.paused = False
        self._pause_rects = {}
        self._wait_rects = {}
        self._lobby_rects = {}
        # Hold-Tab standings overlay. Kept as a flag set on keydown and cleared
        # on keyup rather than read from the global key state, so a Tab that was
        # already down when the window gained focus cannot leave it stuck open.
        self._scoreboard = False
        self._local_firing_prev = False
        self._remote_firing_prev = {}
        # Client-side prediction. Own-character movement is applied locally
        # the instant the key is pressed and reconciled against the host,
        # instead of being drawn from the 100 ms-behind snapshot like
        # everybody else. This is the single biggest feel win in the arena.
        self._pred = None
        # A pending weapon-switch request, consumed by the next input packet.
        self._want_weapon = None
        # ...and "next weapon, whatever that is", from Q or the wheel.
        self._want_cycle = False
        # Short-lived HUD note (a refused switch, a dropped host). Seconds
        # remaining; 0 means nothing is being said.
        self._toast = ""
        self._toast_left = 0.0
        # Wall-clock of the last byte received from the host. None means
        # "never heard anything", which is also "not connected yet" -- the
        # silence watchdog must not fire before the first packet.
        self._last_recv = None
        # Authoritative events received from the host this frame.
        self._pending_events = []
        # Kill feed rows, newest last: [age_frames, killer, victim, weapon].
        self._killfeed = []
        # Scoreboard / mode / clock, as last reported by the host.
        self._match_state = {}
        # Invite state. A room code is the host's address in disguise; the
        # forwarding worker fills these in a moment after hosting starts.
        # code_prefix is chosen once per host session and reused for every
        # re-encode, so the flavour in front of the host cannot change while
        # they are reading it out (see net/roomcode.py PREFIX_POOL).
        self.room_code = ""
        self.join_token = ""
        self.code_prefix = None
        self.share_host = ""
        self.share_port = 0
        self.forwarded = False
        self.forward_note = ""
        self._tunnel_pending = False
        self._tunnel_active = False
        self._hamachi_active = False
        self._network_check_pending = False
        self._tunnel_proc = None
        # Guards _tunnel_proc/_host_token hand-off between the forwarding
        # worker and teardown, so a tunnel published during LEAVE is stopped.
        self._tunnel_lock = threading.Lock()
        self._host_token = None

    # ── panel ──

    def is_open(self):
        return self.mode != "closed"

    def session_phase(self):
        """Host-owned room phase, shared through match-state packets."""
        if self.mode == "hosting":
            return self._session_phase
        if self.mode == "playing":
            return (self._match_state or {}).get("session_phase", "lobby")
        return "lobby"

    def waiting_for_player(self):
        """True while the host's room is waiting for an explicit start."""
        return self.mode == "hosting" and self._session_phase == "lobby"

    def wants_menu_cursor(self):
        """True while the pointer belongs to the menu arrow, not the reticle.

        Host and joiner, deliberately. The old app.py test used
        waiting_for_player(), which is hardcoded to mode == "hosting", so a
        joiner sitting in the SAME frozen lobby was treated as being in live
        play: no arrow to click the team panels with, and a combat reticle
        floating over the MATCH LOBBY panel. input_frozen() already answers the
        right question for both sides -- nothing is aimable yet -- so the cursor
        follows it rather than following who happens to own the room.

        The pause menu also needs the arrow back to click RESUME / LEAVE MATCH.
        """
        if self.mode not in ("hosting", "playing"):
            return True
        if self.paused:
            return True
        return self.input_frozen()

    def in_match_lobby(self):
        """Whether a connected player is still in the pre-game lobby."""
        return self.mode in ("hosting", "playing") and \
            self.session_phase() == "lobby"

    def input_frozen(self):
        """No movement, firing, or switching until the host starts play."""
        return self.mode in ("hosting", "playing") and \
            self.session_phase() != "playing"

    def _arm_intro(self, seconds=INTRO_SECONDS):
        """Start the host-synchronized countdown once per match start."""
        if self._intro_armed:
            return False
        self._intro_armed = True
        try:
            self._intro_left = max(0.0, min(INTRO_SECONDS, float(seconds)))
        except (TypeError, ValueError):
            self._intro_left = INTRO_SECONDS
        return True

    def _begin_countdown(self):
        """Host-only Start Match action. Joining alone never starts play."""
        if self.mode != "hosting" or self._session_phase != "lobby":
            return False
        if not self.peers:
            self.status = "at least one other player must join first"
            return False
        blocked = self._unstartable_reason()
        if blocked:
            self.status = blocked
            return False
        self._session_phase = "countdown"
        self._match_started = False
        self._countdown_left = INTRO_SECONDS
        self._arm_intro(INTRO_SECONDS)
        self._acc = 0.0
        self._publish_room_state(force=True)
        self.status = "match starting"
        return True

    def _unstartable_reason(self):
        """Why START cannot run right now, or None when it can.

        A team match with an empty side is not a match at all. Round victory is
        "reach the score limit", so the side with nobody on it can never be
        reached and the round can only end by the five-minute clock expiring in
        a draw -- three players running around shooting each other while the
        scoreboard says they are teammates, which reads as broken rather than as
        unfair. The host has to notice, so the button notices for them.

        This deliberately does NOT forbid a lopsided-but-playable split (3 v 1):
        friends stacking together is the point of the feature, and both sides
        can still win it.
        """
        if self.sim is None:
            return None
        rules = self.sim.rules
        if rules.mode != AR.MODE_TDM:
            return None
        counts = rules.team_counts()
        empty = [AR.TEAM_NAMES[t] for t in (AR.TEAM_IPA, AR.TEAM_KRAP)
                 if not counts.get(t)]
        if not empty:
            return None
        if len(empty) == 1:
            return "%s IS EMPTY - PICK A SIDE" % empty[0]
        return "NO TEAMS YET"

    def _lobby_roster(self):
        """Return the authoritative player list in slot order."""
        if self.sim is None:
            return []
        return [(pid, st.get("nick") or P.default_name(pid))
                for pid, st in sorted(self.sim.players.items())]

    # ── team choice ─────────────────────────────────────────────────────

    def _local_slot(self):
        """Which seat is ours. The host is always slot 0."""
        return self.sess.local_id if self.sess is not None else 0

    def _teams_table(self):
        """{player_id: TEAM_*} as the local side currently knows it.

        The host reads its own rules; a client reads the table the host
        published. Keys come back from JSON as strings, so both go through here
        rather than indexing wherever they happen to be and hoping.
        """
        if self.sim is not None:
            return dict(self.sim.rules.teams)
        out = {}
        for key, value in ((self._match_state or {}).get("teams") or {}).items():
            try:
                out[int(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return out

    def _team_play(self):
        """True when this match assigns sides.

        The host knows from the sim it built; a client only learns the mode from
        the packets, and a lobby that guessed would offer team buttons for a
        free-for-all.
        """
        if self.sim is not None:
            return self.sim.rules.mode == AR.MODE_TDM
        return (self._match_state or {}).get("mode") == AR.MODE_TDM

    def _apply_team_pick(self, player_id, team):
        """Host side: seat a player where they asked. -> bool.

        Lobby only. Mid-round the teams are load-bearing: scores are banked per
        side, the round clock compares two fixed sides, and everyone is standing
        where their team's spawn put them. Flipping a player during a firefight
        would hand the other side a free kill and orphan the score he banked.
        """
        if self.sim is None or self._session_phase != "lobby":
            return False
        if not self.sim.pick_team(player_id, team):
            return False
        # Push it out immediately. The state packet runs on a slow cadence, and
        # a player who picks a side and sees nothing move concludes the button
        # is broken rather than that it worked and is waiting for a tick.
        self._publish_room_state(force=True)
        return True

    def request_team(self, team):
        """Ask to be seated on *team*. True means the request went out, not
        that it landed -- the host answers on the next state packet.

        A client changes nothing locally first. The host owns team assignment
        exactly as it owns ammo: a client that moved itself would be drawing a
        side its teammates cannot see, while friendly-fire suppression ran on
        the host's word, not his.
        """
        if team not in (AR.TEAM_IPA, AR.TEAM_KRAP):
            return False
        if not self.in_match_lobby():
            self.status = "teams are locked once the match starts"
            return False
        if self.mode == "hosting":
            return self._apply_team_pick(self._local_slot(), team)
        if self.wire is None:
            return False
        self.wire._send(P.make_team_pick(team))
        self.wire.flush()
        return True

    def _move_player_to(self, player_id, team):
        """Host override: put somebody else on a side."""
        return self._apply_team_pick(player_id, team)

    def play_name(self):
        """The name to compete under. Always something drawable.

        Falls back to a minted callsign rather than an empty string. Joining
        anonymously is precisely the behaviour this system exists to stop, so
        the default has to be a name and not a blank -- a player can still
        retype it in the entry panel, and it is remembered from then on.
        """
        name = P.sanitize_name(self.player_name)
        if name:
            return name
        name = P.sanitize_name(mint_callsign())
        self.player_name = name
        return name

    def name_of(self, player_id):
        """Display name for a slot, as the host last reported it.

        One resolver for every name this screen draws. It reads the view's
        table rather than keeping its own copy, because the view is already
        fed from the host's rules packet every frame -- a second copy here
        would be one more thing to fall a packet behind.
        """
        if self.view is not None:
            return self.view.name_for(player_id)
        return P.default_name(player_id)

    def _publish_room_state(self, force=False):
        """Send lobby/countdown phase and roster on a small wall-clock cadence."""
        if self.sim is None or self.sess is None or not self.peers:
            return False
        now = time.monotonic()
        if not force and now - self._room_state_last < ROOM_STATE_INTERVAL:
            return False
        self._room_state_last = now
        state = self.sim.match_state()
        state["session_phase"] = self._session_phase
        state["room_capacity"] = self.players
        state["roster"] = self._lobby_roster()
        if self._session_phase == "countdown":
            state["countdown"] = self._countdown_left
        else:
            state["countdown"] = 0.0
        state["scoreboard"] = self.sim.scoreboard()
        self._match_state = state
        return self.sess.send_match_state(state)

    def share_code(self):
        """Room code plus the secret join token ("CODE@TOKEN") to hand out."""
        tok = getattr(self, "join_token", "")
        return "%s@%s" % (self.room_code, tok) if tok and self.room_code else self.room_code

    def room_code_ready(self):
        """True once the connection has SETTLED and the code is final.

        Hosting mints a code from the LAN address straight away, and a
        background worker then goes looking for something better -- Hamachi,
        then a router mapping, then a public tunnel. Until that search
        finishes the code can still be replaced, so showing it early meant
        the host read a code out loud that was already wrong by the time the
        friend typed it.

        So the rule is: no code while searching, checking, or connecting;
        the code appears the moment the status settles, whichever way that
        went (LAN-only is a settled answer -- it is a worse address, not a
        provisional one).
        """
        if not self.room_code:
            return False
        return not (self._network_check_pending or self._tunnel_pending)

    def open_panel(self):
        self.mode = "panel"
        self.status = ""
        self.players = min(self.players, self.max_players())

    def max_players(self):
        """Seat cap for the selected map, clamped to the hard maximum."""
        return max(2, min(MAX_PLAYERS, AR.max_players(self.map_name)))

# ── starting a match ──

    def request_host(self, port=None):
        """Begin listening. The socket opens in update() rather than here,
        so a failure surfaces as a status line the player can read instead
        of an exception thrown out of a click handler."""
        self._teardown()
        # Enforce the selected map's seat cap even if the panel was never
        # redrawn after a map change.
        self.players = min(self.players, self.max_players())
        # `port is None` means "use the default"; an explicit 0 means
        # "ephemeral". `port or DEFAULT_PORT` conflated the two, so a caller
        # asking for an ephemeral port silently got the default and could
        # collide with whatever already held it.
        self._pending = [("host", DEFAULT_PORT if port is None else port)]
        self.status = "starting..."

    def request_join(self, text=None):
        if text is not None:
            self.address = text
        # A room code is an address in disguise; try it first, then fall
        # back to a raw host / host:port / tunnel URL.
        # An optional "@TOKEN" suffix is the host's join secret.
        addr_text, _, tok = (self.address or "").rpartition("@")
        if not addr_text:
            addr_text, tok = tok, ""
        self._join_token = P.clean_token(tok) or None
        decoded = roomcode.decode(addr_text)
        if decoded is not None:
            host, port = decoded
        else:
            host, port = parse_addr(addr_text)
        if not host:
            self.status = "type a room code or address first"
            return False
        self._teardown()
        self._pending = [("join", (host, port))]
        self.status = "connecting to %s:%d..." % (host, port)
        return True

    def _bind_listener(self, port):
        """Bind the first free TCP port at or after *port*.

        SO_REUSEADDR is deliberately NOT set. On Windows it lets a second
        process "bind" a port another process is already listening on, so
        the new host silently receives nothing and every joiner gets
        "actively refused" - a maddening, invisible failure. Letting the
        bind raise and stepping to the next port instead is honest, and
        costs nothing because the room code carries whichever port we land
        on. (The match port is deliberately NOT the lobby master's 27015, so
        a running lobby can never be mistaken for a match listener - but a
        leftover host from an earlier session is still how a port gets
        stolen, and stepping forward handles it.)

        *port* 0 means "any free port" (ephemeral), which tests use.
        """
        candidates = [0] if port == 0 else [port + i for i in range(12)]
        last_exc = None
        for cand in candidates:
            srv = socket.socket()
            try:
                srv.bind(("0.0.0.0", cand))
                srv.listen(max(self.players, 32))
                srv.setblocking(False)
                return srv
            except OSError as exc:
                last_exc = exc
                try:
                    srv.close()
                except OSError:
                    pass
        raise last_exc

    def _start_hosting(self, port):
        srv = self._bind_listener(port)
        self.srv = srv
        # Fanout, not a single wire: the roster grows while the match runs,
        # so the session needs a live list of sockets, not one socket.
        self.sess = MatchSession(Fanout(lambda: self.peers), is_host=True,
                                 local_id=0)
        self.sim = AR.ArenaSim(self.sess, AR.ARENAS[self.map_name],
                                 score_limit=SCORE_LIMIT,
                                 map_name=self.map_name,
                                 player_speed=PLAYER_SPEED,
                                 sprint_speed=SPRINT_SPEED,
                                 mode=self.mode_name)
        # A fresh session identity per hosting run. The round-payout log keys
        # on it, so re-hosting the same map cannot re-credit rounds somebody
        # was already paid for, and a client that rejoins gets a new one.
        self.sim.match_id = "%08x" % _rng_legacy.getrandbits(32)
        # The host wears its own purchased loadout through the same seat call
        # a peer uses, so there is no separate "the host looks like the host"
        # path that could drift from what the host is actually wearing.
        self.sim.add_player(0, self.play_name(), profile_store.equipped())
        self.sess.world = self.sim.snapshot_entities()
        self.view = ArenaView(self.map_name)
        self._local_firing_prev = False
        self._remote_firing_prev = {}
        self._pending_peers = []
        self._match_started = False
        self._session_phase = "lobby"
        self._countdown_left = 0.0
        self._room_state_last = 0.0
        self._intro_left = 0.0
        self._intro_armed = False
        self.mode = "hosting"
        self.status = "waiting for players"
        self._host_token = object()
        # A code from the LAN IP exists immediately, so there is always
        # something to share; the worker upgrades it to the public address
        # once the router mapping is up. Skipped for port 0 (ephemeral),
        # which only tests use - we must not hit real routers from a test.
        bound = srv.getsockname()[1]
        self.share_port = bound
        # One flavour for the whole session: the LAN code and the public code
        # this worker may replace it with must share a prefix, or the host
        # reads out one code and the card shows another.
        self.code_prefix = roomcode.random_prefix()
        self.join_token = secrets.token_hex(JOIN_TOKEN_BYTES).upper()
        self.share_host = portmap.local_ip()
        self.room_code = roomcode.encode(self.share_host, bound,
                                         prefix=self.code_prefix)
        self._network_check_pending = port != 0
        if port != 0:
            threading.Thread(target=self._begin_forwarding,
                             args=(bound, self._host_token), daemon=True).start()

    def _begin_forwarding(self, bound, host_token):
        """Choose the best reachable address: Hamachi, router, then tunnel.

        Hamachi is checked first because it already provides a private virtual
        network and does not need public port forwarding. This runs off the
        render thread; stale workers cannot replace an invite for a later host.
        """
        try:
            hamachi_ip = portmap.hamachi_ipv4()
        except Exception:
            hamachi_ip = None
        if self._host_token is not host_token:
            return
        code = (roomcode.encode(hamachi_ip, bound, prefix=self.code_prefix)
                if hamachi_ip else "")
        if code:
            self.share_host = hamachi_ip
            self.room_code = code
            self._hamachi_active = True
            self.forwarded = False
            self.forward_note = "Hamachi overlay ready."
            self._network_check_pending = False
            return

        try:
            res = portmap.open_port(bound, bound, lifetime=7200,
                                    description="Call of Acaristan arena")
        except Exception as exc:
            res = None
            router_error = "port mapping failed: %s" % (exc,)
        else:
            router_error = ((getattr(res, "error", "") or
                             getattr(res, "guidance", "")) if res else
                            "router did not allow automatic port forwarding")

        if self._host_token is not host_token:
            return
        if res is not None and res.ok:
            ext = res.external_ip
            if not ext or portmap.is_private(ext):
                ext = portmap.public_ip()
            if ext and not portmap.is_private(ext):
                code = roomcode.encode(ext, bound, prefix=self.code_prefix)
                if code:
                    self.share_host = ext
                    self.forwarded = True
                    self.room_code = code
                    self._network_check_pending = False
                    return
            router_error = (
                "router mapping exists but no public IPv4 is reachable; "
                "trying a TCP tunnel")

        self._tunnel_pending = True
        try:
            # Bundled raw-TCP bore first; configured ngrok is a fallback.
            endpoint, proc, tunnel_note = tcp_tunnel.start_tunnel(
                bound, cancelled=lambda: self._host_token is not host_token)
        except Exception as exc:
            endpoint, proc = None, None
            tunnel_note = "could not start a public TCP tunnel: %s" % (exc,)
        with self._tunnel_lock:
            stale = self._host_token is not host_token
            if not stale and endpoint:
                self._tunnel_proc = proc
        if stale:
            tcp_tunnel.stop_process(proc)
            return
        self._tunnel_pending = False
        if endpoint:
            host, port = endpoint
            self._tunnel_active = True
            self.forwarded = True
            self.share_host = host
            self.share_port = port
            self.room_code = "%s:%d" % endpoint
            self.forward_note = "Public TCP tunnel ready (%s)." % tunnel_note
            self._network_check_pending = False
            return

        tunnel_error = tcp_tunnel.explain_error(tunnel_note)
        self.forward_note = "%s; %s" % (
            router_error or "router port forwarding unavailable",
            tunnel_error or "public TCP tunnel unavailable")
        self._network_check_pending = False
        self.status = tunnel_error

    def _connect_socket(self, host, port):
        """Open a TCP connection, retrying loopback for a private target.

        Returns (sock, address_used). A host's own LAN address can be
        unroutable from the same machine - a VPN or Hyper-V adapter, or
        local_ip() having picked the wrong interface - while 127.0.0.1
        always reaches a listener bound to 0.0.0.0. That matters because
        "host and join on one PC" is the most common way people test. Only
        private targets get the retry, so a public address is never
        silently swapped for loopback.
        """
        candidates = [host]
        if host != "127.0.0.1" and portmap.is_private(host):
            candidates.append("127.0.0.1")
        last = None
        for cand in candidates:
            sock = socket.socket()
            sock.settimeout(3.0)       # fail fast instead of hanging
            try:
                sock.connect((cand, port))
                return sock, cand
            except OSError as exc:
                last = exc
                try:
                    sock.close()
                except OSError:
                    pass
        raise last

    def _start_playing(self, host, port):
        try:
            sock, used = self._connect_socket(host, port)
        except OSError as exc:
            self.mode = "panel"
            self.status = "could not connect to %s:%d (%s)" % (
                host, port,
                exc.strerror if getattr(exc, "strerror", None) else exc)
            return False
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setblocking(False)
        self.sock = sock
        self.wire = Wire(sock)
        self.sess = MatchSession(self.wire, is_host=False, local_id=0)
        self.view = ArenaView(self.map_name)
        self._local_firing_prev = False
        self._remote_firing_prev = {}
        # Predict our own movement from the very first frame. It seeds from
        # the first authoritative snapshot rather than a guessed origin, so
        # joining while standing in geometry is still impossible.
        self._pred = AR.Predictor(self.view.walls, PLAYER_SPEED, SPRINT_SPEED)
        self._killfeed = []
        self._match_state = {}
        # A client joins into a frozen lobby until a host room-state packet
        # says countdown or playing. It never locally assumes play started.
        self._session_phase = "lobby"
        self._countdown_left = 0.0
        self._room_state_last = 0.0
        self._intro_left = 0.0
        self._intro_armed = False
        # Announce ourselves before anything else. The host holds every new
        # connection unverified until this arrives, which is what stops its
        # own lobby relay from being accepted as an opponent. The name rides
        # in the same packet: it is the same declaration, and a second
        # message would mean a peer could be seated nameless and have to
        # introduce itself later. So does the cosmetic loadout, for the same
        # reason -- nobody changes hats mid-round, and a peer that has to ask
        # twice is a peer that can be seated wearing nothing.
        self.wire._send(P.make_join_match(self.map_name, self.play_name(),
                                          profile_store.equipped(),
                                          token=getattr(self, "_join_token", None)))
        self.wire.flush()
        # Enter the live-match mode HERE. Without this the client stayed in
        # "panel", so update() never dispatched to _update_client and the
        # handshake never completed -- the join sat on "connecting..." until
        # the player gave up.
        self._peer_addr = (used, port)
        self.mode = "playing"
        self.status = "connecting to %s:%d..." % (used, port)
        # Arm the silence watchdog from the moment we are connected, so a
        # host that accepts us and then never speaks times out instead of
        # leaving us on "connecting..." forever.
        self._last_recv = time.monotonic()
        return True

    # ── per-frame ──

    def update(self, keys, mouse, dt):
        """Advance the match, or start a pending one. Called every frame
        while the multiplayer screen is up."""
        if self._pending:
            action, arg = self._pending.pop(0)
            if action == "host":
                try:
                    self._start_hosting(arg)
                except OSError as exc:
                    self.mode = "panel"
                    self.status = "could not host: %s" % (
                        exc.strerror if getattr(exc, "strerror", None) else exc,)
            else:
                self._start_playing(arg[0], arg[1])
        if self._toast_left > 0:
            self._toast_left -= dt
            if self._toast_left <= 0:
                self._toast = ""
        # Chat ages on every mode, and so does the respawn clock: both are
        # wall-clock, not sim-clock, so they keep running in the frozen lobby
        # and while paused -- a countdown that stopped when you opened the
        # menu would be a countdown you could cheat.
        self._age_chat()
        self._tick_respawn(dt)
        # Fallen bodies age on the frame clock, alongside the respawn countdown
        # that decides how long they stay on the floor.
        if self.view is not None:
            self.view.advance_corpses()
        # Intro/countdown clock. The host owns its full countdown; clients
        # count down locally between host corrections and remain frozen until
        # the explicit live phase arrives.
        if self.mode == "hosting" and self._session_phase == "countdown":
            self._countdown_left = max(0.0, self._countdown_left - dt)
            self._intro_left = self._countdown_left
        elif self._intro_left > 0.0:
            self._intro_left = max(0.0, self._intro_left - dt)
        if self.mode == "hosting":
            self._update_host(keys, mouse, dt)
        elif self.mode == "playing":
            self._update_client(keys, mouse, dt)
        self._push_hud_tables()

    def _push_hud_tables(self):
        """Hand the host's name, team and appearance tables to the view.

        Done once per frame in update(), NOT as a side effect of drawing.
        Names are needed by more than the renderer -- the pause card, the
        lobby roster and the round-over banner all read them -- and a value
        that only lands during draw() is invisible to every non-drawing
        caller, which is how a "who is this" lookup ends up answering with a
        slot label while the same name is drawn correctly one line away.

        Looks are pushed here for the same reason, and the need is sharper:
        the view repaints a cached sprite when its owner changes, and that
        repaint happens in the pose lookup rather than in a draw call.
        """
        if self.view is None:
            return
        st = self._match_state or {}
        self.view._names = st.get("names", {}) or {}
        self.view._teams = st.get("teams", {}) or {}
        # Who is awaiting respawn, so the view can keep their corpse on the
        # floor. Pushed from the dead set plus the locally-ticked countdown,
        # never from the entity state bit alone: that appears only in 2 Hz
        # packets, so a body keyed on it strobes between drawn and not-drawn
        # between updates -- and keyed on the countdown alone it missed every
        # death with no wait attached, which is how a client could be killed
        # twice in a row and watch the arena stay spotless both times.
        self.view._respawn_waiting = tuple(self._down_ids())
        # Whether this frame is an aiming frame. Pushed from the same authority
        # the cursor logic in app.py uses, so the combat reticle and the menu
        # arrow can never disagree about who owns the pointer: during the lobby
        # and the start countdown the arrow is live and the crosshair is not,
        # and in a round it is the reverse. The local entity is ALIVE in the
        # lobby -- the host seats and snapshots you before the sim runs -- so
        # without this the arena drew an aiming reticle over a MATCH LOBBY panel
        # that has nothing in it to aim at.
        self.view.aim_frozen = self.input_frozen()
        looks = dict(st.get("looks", {}) or {})
        # Seed our own slot from the local profile when the host said nothing
        # about it. A host predating cosmetics publishes no looks table at all
        # and would otherwise silently repaint us in default olive; and even a
        # current host only publishes what each peer CLAIMED, so this is the
        # one path where our own loadout is read from disk rather than from a
        # socket.
        mine = str(getattr(self.sess, "local_id", 0) if self.sess else 0)
        if mine not in looks:
            looks[mine] = profile_store.equipped()
        self.view._looks = looks

    def _check_tunnel_alive(self):
        """Detect a relay process that died mid-session and say so honestly.

        Remote players were connected through it, so they are cut off; the
        address on screen is dead. Fall back to the LAN code and tell the host
        to host again for a fresh address rather than leaving a stale invite.
        """
        proc = self._tunnel_proc
        if proc is None or proc.poll() is None:
            return
        with self._tunnel_lock:
            if self._tunnel_proc is proc:
                self._tunnel_proc = None
        tcp_tunnel.stop_process(proc)
        self._tunnel_active = False
        self.forwarded = False
        self.share_host = portmap.local_ip()
        if self.srv is not None:
            self.share_port = self.srv.getsockname()[1]
        self.room_code = roomcode.encode(self.share_host, self.share_port,
                                         prefix=self.code_prefix)
        self.forward_note = "public TCP tunnel lost (relay exited)"
        self.status = "internet tunnel lost - leave and host again for a new address"

    def _update_host(self, keys, mouse, dt):
        srv = self.srv
        if srv is None:
            return
        self._check_tunnel_alive()
        # ── accept ──
        # An accepted socket is only a CANDIDATE. It gets a roster slot when
        # its join handshake arrives, so the lobby relay (which connects to
        # 127.0.0.1 on a fixed port and never speaks the match protocol)
        # cannot become a phantom opponent.
        # Pending sockets never reserve a player slot (slots are only taken at
        # promotion), so a scanner cannot lock out real players. They are
        # capped, and the oldest is evicted when the cap is hit.
        for _ in range(ACCEPTS_PER_FRAME):
            try:
                conn, addr = srv.accept()
            except (BlockingIOError, OSError):
                break
            try:
                conn.setblocking(False)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                try:
                    conn.close()
                except OSError:
                    pass
                continue
            while len(self._pending_peers) >= MAX_PENDING_PEERS:
                self._drop_peer(self._pending_peers[0])
            self._pending_peers.append(Peer(conn, addr))
        # ── read every candidate and every player ──
        # Drop sockets that are already dead before selecting. A closed fd
        # makes select() fail for the whole batch, so one bad peer would
        # otherwise stall input from everyone else.
        for peer in list(self._pending_peers) + list(self.peers):
            try:
                if peer.sock.fileno() < 0:
                    self._drop_peer(peer)
            except (OSError, ValueError):
                self._drop_peer(peer)
        # A candidate that never says anything is a stray connection, not a
        # slow player: a real client sends its handshake the moment connect()
        # returns. Without this the slot would be held forever.
        now = time.monotonic()
        for peer in list(self._pending_peers):
            if getattr(peer, "deferred", None) is not None and \
                    peer in self._pending_peers:
                if self._promote_pending_peer(peer, peer.deferred):
                    continue
            if now - peer.created > PENDING_PEER_TIMEOUT:
                self._drop_peer(peer)
        watch = self._pending_peers + self.peers
        if watch:
            try:
                ready, _, _ = select.select([p.sock for p in watch], [], [], 0)
            except (OSError, ValueError):
                ready = []
            for sock in ready:
                peer = next((p for p in watch if p.sock is sock), None)
                if peer is None:
                    continue
                try:
                    chunk = sock.recv(65536)
                except (BlockingIOError, OSError):
                    continue
                if chunk == b"":
                    self._drop_peer(peer)
                    continue
                peer.buf += chunk
                if len(peer.buf) > 1 << 20:
                    # A peer streaming without newlines must not eat RAM.
                    self._drop_peer(peer)
                    continue
                while b"\n" in peer.buf:
                    line, peer.buf = peer.buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    # Hand the RAW dict to the consumer and let it do the
                    # validating. Parsing here first strips the "t" field,
                    # and the validation inside _accept_input then rejects
                    # the packet as "not an input" -- so every remote
                    # player's input was silently dropped while local play
                    # worked fine.
                    raw = P.decode(line)
                    if not isinstance(raw, dict):
                        continue
                    if not peer.verified:
                        # Only a join handshake promotes a candidate. Anything
                        # else (lobby hello/query, a probe) ends the connection.
                        if not self._promote_pending_peer(peer, raw):
                            break
                        continue
                    # Chat is read before input and is allowed in every phase,
                    # including the frozen lobby: talking to the people you
                    # are about to play with is most useful BEFORE the round
                    # starts, which is exactly when the host has the sim
                    # stopped and would otherwise drop the packet.
                    body = P.parse_match_chat(raw)
                    if body is not None:
                        self._relay_match_chat(peer, body)
                        continue
                    # A team preference, read before the input gate and allowed
                    # in every phase like chat: the frozen lobby is precisely
                    # when it matters, and it has to reach the host because the
                    # host owns the table every client is drawn from.
                    pick = P.parse_team_pick(raw)
                    if pick is not None:
                        self._apply_team_pick(peer.player_id, pick)
                        continue
                    # The host never queues pre-game intent. Otherwise a
                    # malicious/stale movement, reload, or weapon-switch packet
                    # sent during the lobby/countdown could execute on the very
                    # first live tick after GO.
                    if self._session_phase == "playing":
                        self.sess._accept_input(raw, peer_id=peer.player_id)
        # The lobby is a real pre-game state, not an auto-start wait: accepted
        # players and their roster remain visible, but the simulation does not
        # consume input or advance until the host presses START MATCH.
        if self._session_phase == "lobby":
            self._publish_room_state()
            self._acc = 0.0
            return
        if self._session_phase == "countdown":
            remaining = self._countdown_left
            self._intro_left = remaining
            self._publish_room_state()
            if remaining > 0.0:
                self._acc = 0.0
                return
            # GO: publish the authoritative live phase before accepting any
            # movement/fire input. Clients stay frozen until this arrives.
            self._session_phase = "playing"
            self._match_started = True
            self._countdown_left = 0.0
            self._intro_left = 0.0
            self._acc = 0.0
            self._publish_room_state(force=True)
        if self._session_phase != "playing":
            self._acc = 0.0
            return
        # ── the host's own input, through the same path as everyone ──
        me = self.sim.players.get(0)
        if me is not None:
            # Paused: keep the match and the sockets alive, but stand still
            # and hold fire so the local player is not acting from a menu.
            # Typing counts as being in a menu: a player who opened chat must
            # not walk into a crosshair because they pressed W.
            still = self.paused or self._composing
            ax, ay = (0, 0) if still else local_axes(keys)
            firing = bool(mouse[2]) and not still
            sprinting = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) \
                and not still
            buttons = 0
            if firing:
                buttons |= P.F_FIRING
            if sprinting:
                buttons |= P.F_SPRINTING
            if not still and keys[pygame.K_r]:
                buttons |= P.F_RELOAD
            inp = {"t": P.T_INPUT, "q": self.sim.tick, "mx": ax, "my": ay,
                   "a": aim_degrees(mouse, (me["x"], me["y"]),
                                    self.view.cam_x, self.view.cam_y),
                   "b": buttons}
            if self._want_weapon is not None:
                inp["w"] = self._want_weapon
            if self._want_cycle:
                # "c" survives parse_input as "wcycle", which is what the
                # simulation reads. Without it the host never sees the
                # request at all and Q silently does nothing.
                inp["c"] = 1
            self._want_weapon = None
            self._want_cycle = False
            self.sess._accept_input(inp, peer_id=0)
        # ── simulate ──
        acc = getattr(self, "_acc", 0.0) + min(dt, 0.1)
        steps = 0
        while acc >= STEP and steps < 5:
            self.sim.step()
            # last_shot carries the shooter's id so only OUR gunfire kicks
            # the local camera. Firing on a remote player's shot would shake
            # the screen at the wrong moments and feel like input lag.
            shots = getattr(self.sim, "shots", [self.sim.last_shot] if self.sim.last_shot else [])
            for shot in shots:
                if shot[4] == 0:
                    # The host owns the gun table too, so read the shooter's
                    # weapon straight from the sim: the rifle must kick like
                    # the rifle, not like the pistol it used to default to.
                    shooter = self.sim.players.get(0) or {}
                    self.view.on_local_shot(shot[0], shot[1], shot[2], shot[3],
                                            shot[5], shooter.get("weapon"))
                else:
                    self.view.on_remote_shot(shot[4], shot[0], shot[1], shot[2],
                                             shot[3], shot[5])
            # The host is authoritative, so it plays its own events locally
            # exactly as a client would -- one code path, so the host and a
            # joiner see the same feedback for the same fight.
            self._play_events()
            acc -= STEP
            steps += 1
        self._acc = acc
        # Match rules the client cannot infer from entity positions: scores,
        # teams, the round clock and which pickups are still on the map.
        if self.sim is not None:
            st = self.sim.match_state()
            st["scoreboard"] = self.sim.scoreboard()
            # Seed the countdown from the host's own tables before adopting
            # them, exactly as a client does with the packet it receives.
            # Without this the host only ever counted down its OWN deaths --
            # _respawn is otherwise written solely by the EV_KILL branch for
            # local_id -- so every remote corpse vanished on the machine that
            # owns the sim, and the one screen where you watch a whole fight go
            # down had bodies on it for nobody but you.
            # Seed the countdown from the host's own tables before adopting
            # them, exactly as a client does with the packet it receives.
            # Without this the host only ever counted down its OWN deaths --
            # _respawn is otherwise written solely by the EV_KILL branch for
            # local_id -- so every remote corpse vanished on the machine that
            # owns the sim, and the one screen where you watch a whole fight go
            # down had bodies on it for nobody but you.
            self._sync_respawn(st)
            self._match_state = st
            # ...and publish it. Until now the host sent the rules packet once,
            # at GO, and never again during a round -- so every client's
            # scoreboard, clock and team totals froze at zero for the whole
            # match. The pause standings table and the HUD score strip were
            # equally stale on a joiner; the hold-Tab board just made it obvious
            # enough to chase. Same cadence as the lobby's, which already had it.
            self._publish_room_state()
        self._advance_killfeed()
        self.view.update_feel()

    def _promote_pending_peer(self, peer, raw):
        """Turn a candidate connection into a roster player, or drop it.

        The ONLY thing that earns a slot is a join handshake. Everything
        else that can reach the port - the lobby relay's hello/query, a
        browser pre-connect, a port scan - is closed immediately, so no
        phantom opponent can appear and the round cannot start on its own.
        """
        if not P.is_join_match(raw):
            self._drop_peer(peer)
            return False
        # Secret-token handshake: reject before any slot is touched.
        want = getattr(self, "join_token", "")
        if want and not hmac.compare_digest(
                P.join_match_token(raw).encode("ascii", "replace"),
                want.encode("ascii", "replace")):
            self._drop_peer(peer)
            return False
        used = set(p.player_id for p in self.peers)
        free = [i for i in range(1, self.players) if i not in used]
        if not free:
            # Authenticated but the room is momentarily full (often a
            # reconnect racing the old socket's EOF). Park the handshake and
            # retry each frame; the short pending timeout still bounds it.
            if peer in self._pending_peers:
                peer.deferred = raw
            else:
                self._drop_peer(peer)
            return False
        peer.deferred = None
        pid = free[0]
        peer.player_id = pid
        if peer in self._pending_peers:
            self._pending_peers.remove(peer)
        # The name the client sent in its handshake. Sanitized again here,
        # because the host must not assume the peer ran the same helper as
        # us -- this string is about to be drawn over a sprite and into the
        # kill feed. A peer that named itself nothing gets its slot label,
        # never an empty tag.
        nick = P.join_match_name(raw) or P.default_name(pid)
        peer.name = nick
        # Tell the client which slot it owns, and which map, before any
        # snapshot that refers to it. Without this the client assumed id 0
        # (the host's player) and its own map choice.
        peer.wire._send(P.make_assign(pid, self.map_name, self.mode_name))
        peer.wire.flush()
        self.peers.append(peer)
        # The loadout claimed in the handshake, bounded on the wire and
        # resolved against the catalog inside add_player. A peer that claims
        # an item it never bought is wearing a lie the whole match can see,
        # so the claim is not what gets drawn -- the normalized version is.
        self.sim.add_player(pid, nick, P.join_match_appearance(raw))
        # Joining updates the frozen room roster; it does NOT start the game.
        # Seed one static snapshot so the client can render the arena behind
        # its lobby immediately, then publish the roster/room phase now.
        self.sess.world = self.sim.snapshot_entities()
        self.sess.broadcast()
        self._publish_room_state(force=True)
        return True

    def _drop_peer(self, peer, graceful=False):
        """Drop a connection, whether it ever earned a slot or not.

        ``graceful`` flushes queued output and half-closes before the close,
        so a last packet the peer needs to read actually arrives. Only worth
        it when something was just said to the peer.
        """
        if peer in self._pending_peers:
            self._pending_peers.remove(peer)
        if peer in self.peers:
            if peer.player_id is not None:
                if self.sim is not None:
                    self.sim.remove_player(peer.player_id)
                if self.sess is not None:
                    self.sess.forget_peer(peer.player_id)
                self._peer_chat_last.pop(peer.player_id, None)
            self.peers.remove(peer)
        if graceful:
            self._flush_and_close(peer)
        else:
            peer.close()
        # If somebody leaves during GET READY, don't start with a stale room
        # state or a vanished participant: cancel back to the host-start lobby.
        if self._session_phase == "countdown" and not self.peers:
            self._session_phase = "lobby"
            self._match_started = False
            self._countdown_left = 0.0
            self._intro_left = 0.0
            self._intro_armed = False
            self._acc = 0.0
        if self.peers and self._session_phase != "playing":
            self._publish_room_state(force=True)
        # If somebody leaves during GET READY, don't start with a stale room
        # state or a vanished participant: cancel back to the host-start lobby.
        if self._session_phase == "countdown" and not self.peers:
            self._session_phase = "lobby"
            self._match_started = False
            self._countdown_left = 0.0
            self._intro_left = 0.0
            self._intro_armed = False
            self._acc = 0.0
        if self.peers and self._session_phase != "playing":
            self._publish_room_state(force=True)

    def _update_client(self, keys, mouse, dt):
        """Receive host state, submit gated input, and render-predict locally."""
        sock = self.sock
        if sock is None:
            return
        # Watchdog: the host owns the match, so total silence means the
        # session is over even if the socket never reports it. A host that
        # loses power or its uplink never sends a FIN or an RST, so without
        # this the client waits in a frozen arena indefinitely.
        if self._last_recv is not None and time.monotonic() - self._last_recv \
                > HOST_SILENCE_TIMEOUT:
            self._end_session_remotely("host stopped responding")
            return
        try:
            chunk = sock.recv(65536)
        except BlockingIOError:
            chunk = None
        except OSError:
            # A reset, not a quiet frame. ConnectionResetError (and its
            # ECANCELED / ECONNABORTED cousins) means the connection is
            # GONE: the peer's stack threw away everything in flight,
            # including the announcement it may have just sent. Lumping
            # this in with BlockingIOError -- "nothing to read, carry on" --
            # left the client sitting in a dead match forever, which is
            # precisely the failure the host-left packet exists to prevent.
            self._end_session_remotely("host closed the match")
            return
        if chunk == b"":
            # The socket closed without saying why. This is the fallback for
            # an older host that does not send the host-left packet; assume
            # the session is gone rather than sitting in it.
            self._end_session_remotely("host closed the match")
            return
        if chunk:
            self._last_recv = time.monotonic()
            self.buf += chunk
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                if not line.strip():
                    continue
                raw = P.decode(line)
                if not isinstance(raw, dict):
                    continue
                # A chat line from the host's relay. Read before the gameplay
                # dispatch because it shares the socket with snapshots, and
                # the author is the HOST's attribution, never anything the
                # payload claimed about itself.
                body = P.parse_match_chat(raw)
                if body is not None:
                    self._push_chat(P.match_chat_author(raw)
                                    or P.default_name(self.sess.local_id),
                                    body)
                    continue
                # The host telling us the session is over, or removing us.
                # Both are things a human did, and both must arrive while the
                # socket is still open -- a client that only sees the socket
                # close reports its own wifi dropping.
                reason = P.parse_kick(raw)
                if reason is not None:
                    self._end_session_remotely(reason or "the host removed you")
                    return
                # The host telling us the session is over. It owns the
                # match, so this is terminal: we leave immediately rather
                # than waiting for the socket to close behind it.
                gone = P.parse_host_left(raw)
                if gone is not None:
                    self._end_session_remotely(gone or "host ended the session")
                    return
                # The host tells us our slot on connect. Until then we
                # cannot know which entity is ours.
                assigned = P.parse_assign(raw)
                if assigned is not None:
                    self.sess.local_id = assigned
                    # Adopt the host's map: the client picks its own on the
                    # entry panel, and rendering the wrong geometry would put
                    # every player on the wrong tiles.
                    host_map = P.assign_map(raw)
                    if host_map in AR.ARENAS and host_map != self.map_name:
                        self.map_name = host_map
                        self.view = ArenaView(host_map)
                        # The predictor holds a wall list from when it was
                        # built. Adopting the host's map replaces the walls,
                        # so a stale predictor would predict movement through
                        # the old geometry and correct hard every frame.
                        self._pred = AR.Predictor(self.view.walls,
                                                  PLAYER_SPEED, SPRINT_SPEED)
                    # The host owns the mode too, or a client that picked TDM
                    # would be told FFA and render the wrong scoreboard.
                    host_mode = P.assign_mode(raw)
                    if host_mode in AR.MODES:
                        self.mode_name = host_mode
                    if self.view is not None:
                        self.view._local_id = assigned
                    continue
                msg = P.parse_snapshot(raw)
                if msg is not None:
                    self.sess._accept_snapshot(P.make_snapshot(*msg))
                    self._latest_snap_tick = msg[0]
                    # Lobby snapshots seed positions but do not start play; the
                    # only authority for that transition is the host's room
                    # state, followed by the frozen countdown.
                    self._reconcile_local(msg[1])
                elif P.parse_events(raw) is not None:
                    self.sess._accept_events(raw)
                state = P.parse_match_state(raw)
                if state is not None:
                    # Scores, clock, teams, pickup timers AND the lobby phase
                    # are host-owned. Keep room phase/roster when a regular
                    # 2Hz round-state update omits those lobby-only fields.
                    if "session_phase" in state:
                        self._apply_room_state(state)
                    else:
                        state["session_phase"] = self._match_state.get(
                            "session_phase", "lobby")
                        if "roster" not in state and "roster" in self._match_state:
                            state["roster"] = self._match_state["roster"]
                    self._sync_dead(state)
                    self._sync_respawn(state)
                    self._match_state.update(state)

        # Smooth client clock. Snapshots land in 3-tick steps (20 Hz), so
        # sampling at the newest snapshot tick made the interpolated world
        # hold between packets and lurch on each one - 20 Hz motion, which
        # reads exactly like low FPS on the joining machine. Advance a local
        # tick at 60 Hz instead and keep it near the newest snapshot tick:
        # the render time is (clock - interp_delay), so the world is drawn a
        # fixed 100 ms in the past but MOVES every frame.
        if self._latest_snap_tick is not None:
            latest = float(self._latest_snap_tick)
            if self._client_tick <= 0:
                self._client_tick = latest
            else:
                self._client_tick += dt * TICK_RATE
            margin = getattr(self.sess._buf, "interp_delay", 0.1) * TICK_RATE
            # Snap only on a real clock divergence (a stall, alt-tab, a
            # hitch); a few ticks of lead/lag advance smoothly.
            if abs(self._client_tick - latest) > margin:
                self._client_tick = latest
            self.sess.tick = self._client_tick
        world = self.sess.sample_world() or {}
        local_id = self.sess.local_id
        me = world.get(local_id)
        if me is not None:
            # Note: reconciliation happens where the snapshot is parsed,
            # against the authoritative entities. It must NOT run here
            # against ``me``, which came out of sample_world() and is
            # 100 ms behind the host.
            # Send input only once we know where we are. Guessing an origin
            # before the first snapshot is how players end up stuck inside
            # geometry on join.
            frozen = self.session_phase() != "playing" or self._composing
            ax, ay = ((0, 0) if self.paused or frozen else local_axes(keys))
            firing = bool(mouse[2]) and not self.paused and not frozen
            sprinting = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) \
                and not self.paused and not frozen
            reloading = bool(keys[pygame.K_r]) and not frozen
            # Aim from the PREDICTED position, not the interpolated one. This
            # is the difference between the crosshair matching the cursor and
            # trailing it by 100 ms plus a round trip.
            origin = ((self._pred.x, self._pred.y)
                      if (self._pred is not None and self._pred.seeded)
                      else (me[2], me[3]))
            angle = aim_degrees(mouse, origin, self.view.cam_x, self.view.cam_y)
            buttons = 0
            if firing:
                buttons |= P.F_FIRING
            if sprinting:
                buttons |= P.F_SPRINTING
            if reloading:
                buttons |= P.F_RELOAD
            msg_in = {"t": P.T_INPUT, "q": self.seq,
                     "mx": ax, "my": ay, "a": angle,
                     "b": buttons}
            if not frozen and self._want_weapon is not None:
                msg_in["w"] = self._want_weapon
            if not frozen and self._want_cycle:
                msg_in["c"] = 1
            self.wire._send(msg_in)
            # Predict the same movement locally, immediately. The host will
            # arrive here in RTT/2; the player should not have to wait.
            if self._pred is not None:
                self._pred.push(self.seq, ax, ay, angle, sprinting,
                                AR.weapon_stats(me[7])["move_mul"])
            self.seq = (self.seq + 1) & 0xFFFFFFFF
            self._want_weapon = None
            self._want_cycle = False
            # Local shot feel comes from the host's own F_FIRING flag, so the
            # camera kicks exactly when the host actually pulled the trigger
            # and not on a local guess.
            was_firing = self._local_firing_prev
            self._local_firing_prev = bool(me[8] & P.F_FIRING)
            if self._local_firing_prev and not was_firing:
                dist, hit = self._local_trace(me, world, local_id)
                self.view.on_local_shot(origin[0], origin[1], me[4], dist, hit,
                                        me[7])

        # Authoritative events: hit markers, damage numbers, kill feed.
        self._play_events()

        # Remote shots feel. Detect when any other player starts firing,
        # and spawn their bullet bolt, casing, gunshot sound, and hit particles.
        live_pids = set(world.keys())
        for pid in list(self._remote_firing_prev.keys()):
            if pid not in live_pids:
                del self._remote_firing_prev[pid]

        for pid, ent in world.items():
            if pid == local_id or ent[6] == P.PS_DEAD:
                continue
            was_f = self._remote_firing_prev.get(pid, False)
            is_f = bool(ent[8] & P.F_FIRING)
            self._remote_firing_prev[pid] = is_f
            if is_f and not was_f:
                dist, hit = self._local_trace(ent, world, pid)
                self.view.on_remote_shot(pid, ent[2], ent[3], ent[4], dist, hit)

        # Advance the local cosmetic timers (tracer, hit-confirm flash and
        # floating "HIT" markers). The host does this in _update_host; the
        # client never did, so its own hit markers never faded and hung in
        # the world.
        self.view.update_feel()
        self.wire.flush()
        self.mode = "playing"
        if self._peer_addr:
            self.status = "connected to %s:%d" % self._peer_addr
        else:
            self.status = "connected"
        return True

    def _apply_room_state(self, state):
        """Apply host-owned lobby/countdown state without restarting the intro."""
        phase = state.get("session_phase")
        previous = self._match_state.get("session_phase", "lobby")
        if phase not in P.SESSION_PHASES:
            return
        self._session_phase = phase
        if phase == "lobby":
            self._intro_left = 0.0
            self._intro_armed = False
        elif phase == "countdown":
            remaining = state.get("countdown", INTRO_SECONDS)
            if previous != "countdown":
                self._intro_armed = False
                self._arm_intro(remaining)
            else:
                # Countdown packets correct drift only downward; network
                # jitter must never make an already elapsed second reappear.
                self._intro_left = min(self._intro_left, remaining)
        else:  # host says live: accept input only now
            self._intro_left = 0.0
            self._intro_armed = True

    def _reconcile_local(self, entities):
        """Feed the local player's authoritative state into the predictor.

        Called the moment a snapshot lands, before this frame's input is
        built, so the input is derived from the corrected position.
        """
        if self._pred is None:
            return
        me = None
        for ent in entities:
            if ent[0] == self.sess.local_id:
                me = ent
                break
        if me is None:
            return
        self._pred.reconcile(me[2], me[3], me[4], AR.entity_ack(me),
                             dead=(me[6] == P.PS_DEAD))

    def _play_events(self):
        """Turn the host's authoritative events into local feedback.

        This is what replaced the client's own re-trace. The host knows which
        shots connected; guessing against an interpolated world disagreed
        with it constantly, and a "HIT" on a wall shot is worse than no hit
        marker at all.
        """
        events = self.sess.drain_events()
        if not events:
            return
        local_id = self.sess.local_id
        for (kind, a, b, c, d, e) in events:
            if kind == P.EV_HIT:
                # Damage numbers are for the victim; the shooter already gets
                # the hit marker. Showing both to both players is noise.
                if b == local_id:
                    self.view.spawn_damage_number(d, e, int(c))
                elif a == local_id:
                    self.view.confirm_hit(d, e)
            elif kind == P.EV_KILL:
                self._killfeed.append([0, a, b, int(c)])
                # Death and kill get their own sounds, and they are different
                # sounds on purpose: hearing the same cue for "I got them" and
                # "I am dead" teaches a player nothing about which one happened.
                if b == local_id:
                    self._last_killer = None if a == b else a
                    # Start the countdown NOW rather than waiting for the next
                    # rules packet. Those arrive at 2 Hz, so waiting for one
                    # would leave up to half a second of a dead player with no
                    # clock at all -- which is precisely the "dimmed sprite"
                    # this is meant to replace.
                    self._respawn[local_id] = AR.RESPAWN_SECONDS
                    # Watermark: samples taken up to now describe us alive.
                    self._death_sample_tick = self._host_tick_now()
                    self.view.on_local_death()
                elif a == local_id:
                    self.view.on_local_kill()
            elif kind == P.EV_PICKUP:
                self.view.on_pickup(d, e, int(c))
            elif kind == P.EV_EMPTY:
                # Only for the person who pulled the trigger. Playing it for
                # everyone would fill the arena with clicks from dry players
                # across the map.
                if a == local_id:
                    self.view.on_empty_click()

    def _down_ids(self):
        """Every slot that should currently have a body on the floor.

        The dead set, minus any slot the newest snapshot says is standing. Two
        sources are needed because each alone is wrong:

        - the dead set is authoritative for every slot. On the host it is read
          straight from the sim it owns; on a client it comes from the host's
          ``dead`` table. Neither side infers it from the respawn countdown,
          which lists only slots whose timer still has seconds left and so
          drops anybody killed without a wait -- including us, since our own
          EV_KILL fires before the packet that would describe the death.
        - the locally ticked respawn countdown fills the gap between the 2 Hz
          packets, so a corpse does not blink out mid-wait. It is subtractive
          rather than additive: a countdown can outlive the death it was
          started for (the host revives a slot the moment its timer expires,
          while our own clock keeps ticking down), and a player who is back on
          their feet must never be drawn flat -- that shows a full-health bar
          over a body and leaves the real sprite undrawn.

        Only REMOTE slots are filtered that way. Our own death is the one case
        where the countdown legitimately runs ahead of the evidence: EV_KILL
        starts it the frame we die, and the snapshot carrying our PS_DEAD bit
        lands up to 100ms later. Requiring proof for ourselves would delete the
        corpse at exactly the moment the player is looking for it.
        """
        waiting = set(self._respawn)
        if self.sim is not None:
            waiting.update(pid for pid, st in self.sim.players.items()
                           if st["dead"])
        else:
            waiting.update(self._host_dead)
        # A countdown that has finished is not evidence of anything -- but only
        # for a slot the countdown was ever started FOR. It is dropped when it
        # runs out, so a slot sitting in the dead set with no timer behind it
        # must be left alone rather than filtered as "expired". The tolerance is
        # one frame: dt accumulates in floats, so a timer that has run out
        # routinely lands at 5e-15 rather than 0.
        fresh = {pid for pid, secs in self._respawn.items()
                 if secs > STEP}
        waiting = (waiting & fresh) | (waiting - set(self._respawn))
        me = self.sess.local_id if self.sess is not None else None
        revived = {pid for pid in self._alive_from_world() if pid != me}
        if revived:
            waiting -= revived
        return waiting

    def _host_tick_now(self):
        """Newest host tick we have any data for, or None."""
        sess = self.sess
        if sess is None:
            return None
        with sess._buf_lock:
            newest = sess._buf.latest_tick()
        if newest is not None:
            return newest
        snap = getattr(self, "_latest_snap_tick", None)
        return int(snap) if snap is not None else None

    def _alive_from_world(self):
        """Slots a sample NEWER than our death reports as standing.

        Only PS_DEAD counts, and only from a snapshot taken after the kill: a
        world sampled before the death still shows full health, and trusting it
        would erase the corpse on the very frame it appeared. A slot missing
        from the sample entirely stays as it was -- absence means "not yet",
        not "alive".
        """
        sess = self.sess
        if sess is None or self._death_sample_tick is None:
            return set()
        with sess._buf_lock:
            newest = sess._buf.latest_tick()
        if newest is None or newest <= self._death_sample_tick:
            return set()
        world = sess.sample_world() or ()
        ents = world.values() if isinstance(world, dict) else world
        out = set()
        for ent in ents:
            try:
                if ent[6] != P.PS_DEAD:
                    out.add(ent[0])
            except (IndexError, TypeError):
                continue
        return out

    def _sync_dead(self, state):
        """Adopt the host's published set of downed slots."""
        dead = state.get("dead")
        if isinstance(dead, (list, tuple, set)):
            self._host_dead = set(dead)

    def _sync_respawn(self, state):
        """Reconcile the local respawn countdown against the host's packet.

        The host publishes seconds-remaining at 2 Hz, which is far too coarse
        to count down on: between two packets a three-second timer would sit
        frozen and then jump. So the host's number is used only to START a
        countdown that has not begun, and to restart one whose local clock has
        already expired while the host still says there is time.

        It is deliberately never allowed to LENGTHEN a countdown that is
        already running. Packets are sampled at different points in the same
        timer, and a respawn clock that can jump back up reads as a stutter --
        or worse, as the host resetting you mid-respawn.

        A player missing from the host's table is NOT removed here. Absence is
        only weak evidence: a packet built just before the kill also lacks
        them, and deleting on that would wipe a countdown the EV_KILL event
        just started. The local clock clears the entry on its own.
        """
        host = state.get("respawn")
        if not isinstance(host, dict):
            return
        for key, secs in host.items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            try:
                secs = float(secs)
            except (TypeError, ValueError):
                continue
            if self._respawn.get(pid, 0.0) <= 0.0 and secs > 0.0:
                self._respawn[pid] = secs

    def _tick_respawn(self, dt):
        """Count the local respawn timers down. Once per frame."""
        local_id = self.sess.local_id if self.sess is not None else 0
        for pid in list(self._respawn.keys()):
            left = self._respawn[pid] - dt
            if left <= 0.0:
                del self._respawn[pid]
                if pid == local_id:
                    self._last_killer = None
            else:
                self._respawn[pid] = left

    def _advance_killfeed(self):
        """Age the kill feed and drop rows that have faded out."""
        for row in self._killfeed:
            row[0] += 1
        self._killfeed = [r for r in self._killfeed if r[0] < KILLFEED_FRAMES]

    # ── in-match chat ──

    def _push_chat(self, author, text):
        """Record a chat line locally. Newest last."""
        self._chat_messages.append([0, str(author)[:NAME_CHARS],
                                    str(text)[:CHAT_MAX_INPUT]])
        if len(self._chat_messages) > CHAT_MAX_MESSAGES:
            del self._chat_messages[:len(self._chat_messages) - CHAT_MAX_MESSAGES]

    def _age_chat(self):
        for row in self._chat_messages:
            row[0] += 1
        self._chat_messages = [r for r in self._chat_messages
                               if r[0] < CHAT_IDLE_FRAMES + CHAT_LINE_H * CHAT_VISIBLE]

    def kick_peer(self, peer, reason="removed by the host"):
        """Host only: remove one player, and say so before closing the socket.

        Sent on the peer's OWN wire rather than through the session, because
        Fanout would broadcast the kick to everyone -- which would tell the
        whole room who was removed, and is not what a kick is.

        The packet exists at all because the alternative is a closed socket.
        A client that only sees that reports its own connection dropping, and
        the player is told to check their wifi for something a human did.
        """
        if self.mode != "hosting" or peer not in self.peers:
            return False
        name = peer.name or (self.name_of(peer.player_id)
                             if peer.player_id is not None else "a player")
        try:
            peer.wire._send(P.make_kick(reason))
        except Exception:
            # A dead socket is the peer's problem, not ours. The drop below is
            # still the correct outcome either way.
            pass
        self._drop_peer(peer, graceful=True)
        self._say("%s REMOVED" % name.upper())
        return True

    def kick_players(self):
        """Remove every connected player but stay in the room.

        The host keeps the lobby, the room code and the sim: they are still
        hosting, just with an empty room, and can start again as soon as
        somebody rejoins. Ending the session instead would throw away the
        room code that was just read out to a group chat.
        """
        if self.mode != "hosting":
            return 0
        count = 0
        for peer in list(self.peers):
            if self.kick_peer(peer, "removed by the host"):
                count += 1
        self._session_phase = "lobby"
        self._match_started = False
        self._countdown_left = 0.0
        self._intro_left = 0.0
        self._intro_armed = False
        self._acc = 0.0
        self._round_end_played = False
        return count

    def _relay_match_chat(self, peer, text):
        """Host only: pass one client's chat line on to the whole match.

        The host is the relay because it is the only party every client is
        connected to. Re-broadcasting a sanitized copy -- rather than passing
        the raw packet through -- is what makes the sender's name come from
        the host's roster, so a client cannot post a line under somebody
        else's name by putting their handle in the payload.
        """
        if self.sim is None or self.sess is None:
            return False
        pid = peer.player_id
        if pid is None:
            return False
        # Per-sender rate floor. Without it one client can fill every other
        # player's chat panel faster than they can read, which in a match is
        # indistinguishable from being grieffed. Refused silently: telling
        # the spammer they were throttled only invites a lower rate.
        now = time.monotonic()
        last = self._peer_chat_last.get(pid)
        if last is not None and now - last < CHAT_MIN_GAP:
            return False
        self._peer_chat_last[pid] = now
        author = peer.name or self.name_of(pid)
        self._push_chat(author, text)
        # To every peer EXCEPT the sender. The sender already echoed its own
        # line locally in send_match_chat (waiting a round trip to see your
        # own message feels like it was dropped), so including it here showed
        # the sender every one of its lines twice while everyone else saw it
        # once. A chat log that differs between clients is not a conversation,
        # but neither is one where your own lines are doubled.
        msg = P.make_match_chat(text)
        if msg is None:
            return False
        if author:
            msg["by"] = author
        data = P.encode(msg)
        for other in list(self.peers):
            if other is peer or other.player_id is None:
                continue
            try:
                other.sock.sendall(data)
            except OSError:
                pass
        return True

    def send_match_chat(self):
        """Submit whatever is in the composer."""
        text = P.sanitize_chat(self._chat_input)
        self._chat_input = ""
        self._composing = False
        if text is None:
            return False
        if self.mode == "hosting":
            # The host has no socket of its own to send on, so its line goes
            # straight into the shared transcript and out to every client.
            self._push_chat(self.play_name(), text)
            if self.sess is not None:
                self.sess.send_match_chat(text, author=self.play_name())
            return True
        if self.wire is not None and self.sess is not None:
            # Echo locally too. Waiting for the host's relay to come back
            # would make your own message feel dropped on a bad connection,
            # and the host attributes it to its own roster anyway.
            self._push_chat(self.play_name(), text)
            self.sess.send_match_chat(text)
            return True
        return False

    def toggle_chat(self):
        """Open or close the composer.

        Opening is explicit because closing is not a separate keypress: Enter
        both opens and submits. That means there is no "cancel" gesture, so
        Esc is it -- and Esc is already the game's universal "back out of
        this", which is exactly the right meaning here.
        """
        self._composing = not self._composing
        if not self._composing:
            self._chat_input = ""

    def _chat_event(self, event):
        """Keyboard input for the open composer. Returns True when consumed.

        Every key is consumed, including keys with no character: while the
        composer is open, a WASD press must not strafe and a 1 must not
        switch weapons. Returning False for those would let a player walk off
        a ledge while typing "gg".
        """
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_ESCAPE:
            self._composing = False
            self._chat_input = ""
            return True
        if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            self.send_match_chat()
            return True
        if event.key == pygame.K_BACKSPACE:
            self._chat_input = self._chat_input[:-1]
            return True
        if event.key == pygame.K_v and (
                event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
            paste = clipboard_text(CHAT_MAX_INPUT - len(self._chat_input))
            if paste:
                self._chat_input += paste
            return True
        if event.unicode and event.unicode.isprintable() \
                and len(self._chat_input) < CHAT_MAX_INPUT:
            self._chat_input += event.unicode
            return True
        return True

    def _draw_chat(self, surface):
        """The match chat panel: transcript, then the composer.

        Bottom-right, above the loadout and clear of the kill feed, because
        that corner is the only part of a firefight screen nothing else
        claims. The transcript stays readable with the composer CLOSED: you
        can be shot on the way to the reply, so a message cannot vanish the
        instant you stop typing.

        The panel is sized from the lines it is actually going to draw. It
        used to be a fixed CHAT_VISIBLE count with the transcript clipped to
        whatever fitted, which silently ate the OLDEST line -- so a message
        you had read appeared and disappeared depending on how many had piled
        up behind it.
        """
        if not self._chat_messages and not self._composing:
            return
        try:
            font = self._font(12, False, True)
            bold = self._font(12, True, True)
        except Exception:
            return
        w, h = surface.get_width(), surface.get_height()
        # Lines newest-at-the-bottom, so the newest thing you were told is the
        # one nearest the composer and never scrolled off the top.
        want = (CHAT_VISIBLE if self._composing else CHAT_IDLE_VISIBLE) * 2
        lines = []
        for age, author, text in self._chat_messages[-want:]:
            lines.append(("head", "[%s]" % author, author))
            lines.append(("body", text, None))
        if not lines and not self._composing:
            return
        composer_h = CHAT_LINE_H + 6 if self._composing else 0
        ph = len(lines) * CHAT_LINE_H + 14 + composer_h
        pw = 320
        px, py = w - pw - 12, h - ph - 46
        panel = pygame.Rect(px, py, pw, ph)
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((4, 8, 12, 205))
        surface.blit(bg, panel.topleft)
        pygame.draw.rect(surface, (30, 50, 60), panel, 1)
        y = py + 6
        for kind, text, author in lines:
            col = P.color_for(author) if (kind == "head" and author) else C_DIM
            if kind == "body":
                col = (198, 204, 214)
            surf = (bold if kind == "head" else font).render(text, True, col)
            surface.blit(surf, (px + 8, y))
            y += CHAT_LINE_H
        if self._composing:
            rule_y = py + ph - composer_h - 4
            pygame.draw.line(surface, (40, 70, 86), (px + 6, rule_y),
                             (px + pw - 6, rule_y), 1)
            caret = "|" if (_now_ms() // 500) % 2 else " "
            shown = self._clip("> " + self._chat_input + caret, font, pw - 18)
            surface.blit(font.render(shown, True, (170, 200, 210)),
                         (px + 8, rule_y + 4))

    def _local_trace(self, me, world, local_id):
        """Cosmetic client-side trace for tracer length only.

        Uses the same ``arena.hitscan`` the host uses, against the
        interpolated world, so the tracer stops roughly where the shot did.
        It is view-only: nothing here feeds back into the match, and the
        hit/no-hit decision comes from the host's events instead.
        """
        targets = [(pid, e[2], e[3]) for pid, e in world.items()
                   if pid != local_id and e[6] != P.PS_DEAD]
        kind, _tid, dist = AR.hitscan(me[2], me[3], me[4],
                                      self.view.walls, targets)
        return dist, kind == "player"

# ── panel input ──

    def handle_event(self, event, mouse_pos):
        """Handle a pygame event while the match screen owns input.

        Returns True if the event was consumed, so the caller knows not to
        pass it on to the server browser underneath.
        """
        # A closed screen is not on top of anything, so it must not claim a
        # single event. Without this guard the typed-address and Esc handling
        # below ran anyway: Esc closed (a no-op) and every printable
        # character was swallowed into ``self.address`` instead of reaching
        # the browser's chat composer and address box underneath.
        if self.mode == "closed":
            return False
        if self.mode in ("hosting", "playing"):
            # Tab is hold-to-view, so it needs both edges and it needs to be
            # read before anything else can claim the key. It also has to work
            # while paused -- opening the menu with Esc and then wanting the
            # standings is the same urge, and making the player release Esc to
            # get them would be a joke.
            if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                self._scoreboard = True
                return True
            if event.type == pygame.KEYUP and event.key == pygame.K_TAB:
                self._scoreboard = False
                return True
            if self.paused:
                return self._pause_event(event, mouse_pos)
            # The composer owns the keyboard outright. Checked before Esc,
            # because while typing, Escape means "abandon this message" and
            # not "open the match menu".
            if self._composing:
                return self._chat_event(event)
            # Esc opens the in-match menu. Without this Esc did nothing
            # during a live match, so there was no way out but the window.
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.paused = True
                return True
            # Enter opens the chat composer. Deliberately the only key that
            # opens it: a chat panel you can summon with any key is a chat
            # panel you summon by accident mid-fight.
            if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_RETURN, pygame.K_KP_ENTER):
                if self._chat_allowed():
                    self.toggle_chat()
                return True
            # The pre-game lobby owns every input except ESC and its explicit
            # host controls. In particular, clicking/holding fire or moving
            # keys cannot leak into the game before GO.
            if self.in_match_lobby():
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    start_r = self._lobby_rects.get("start")
                    if self.mode == "hosting" and start_r is not None \
                            and start_r.collidepoint(mouse_pos):
                        self._begin_countdown()
                        return True
                    copy_r = self._wait_rects.get("copy")
                    if self.mode == "hosting" and copy_r is not None \
                            and copy_r.collidepoint(mouse_pos):
                        self._copy_room_code()
                        return True
                    # Team controls, in two passes. The MOVE chips and the
                    # AUTO-BALANCE chip are drawn INSIDE the column rects, so a
                    # single pass would let the enclosing "join this side"
                    # target win and move the wrong player -- the host clicking
                    # a friend's MOVE button would instead re-seat the host.
                    for key, rect in self._lobby_rects.items():
                        if not rect.collidepoint(mouse_pos):
                            continue
                        if self.mode != "hosting":
                            continue
                        if key == "balance" and self.sim is not None:
                            self.sim.rebalance_teams()
                            self._publish_room_state(force=True)
                            return True
                        if key.startswith("swap_"):
                            try:
                                pid = int(key.split("_", 1)[1])
                            except (TypeError, ValueError):
                                continue
                            current = self._teams_table().get(pid)
                            if current in (AR.TEAM_IPA, AR.TEAM_KRAP):
                                self._move_player_to(
                                    pid,
                                    AR.TEAM_KRAP if current == AR.TEAM_IPA
                                    else AR.TEAM_IPA)
                            return True
                    for key, rect in self._lobby_rects.items():
                        if not key.startswith("team_"):
                            continue
                        if rect.collidepoint(mouse_pos):
                            try:
                                self.request_team(int(key.split("_", 1)[1]))
                            except (TypeError, ValueError):
                                pass
                            return True
                return True
            # Countdown phase is frozen too; keep only the escape hatch.
            if self.input_frozen():
                return True
            # Weapon select. The switch is a REQUEST: it rides out on the next
            # input packet and the host decides whether it happens, so a
            # client cannot equip a gun it never picked up.
            if event.type == pygame.KEYDOWN:
                want = WEAPON_KEYS.get(event.key)
                if want is not None:
                    self._request_weapon(want)
                    return True
                # Q (and the wheel) cycle through what we are actually
                # carrying, which is the switch you make under fire.
                if event.key in WEAPON_CYCLE_KEYS:
                    self._request_cycle()
                    return True
            if event.type == pygame.MOUSEWHEEL and event.y:
                self._request_cycle()
                return True
            # The waiting card's COPY CODE button. It only exists while the
            # host is alone, so it can never swallow a shot at a real
            # opponent -- firing is read from mouse state, not events.
            copy_r = self._wait_rects.get("copy")
            if copy_r is not None and copy_r.collidepoint(mouse_pos) \
                    and event.type == pygame.MOUSEBUTTONDOWN \
                    and event.button == 1:
                self._copy_room_code()
                return True
            # While the host is waiting, this is a lobby UI, not gameplay:
            # swallow clicks/keys other than Esc and COPY CODE so the pointer
            # stays available and no accidental shot leaks through.
            return self.waiting_for_player()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = mouse_pos
            # Field focus is resolved BEFORE the row chips, because the name
            # and address boxes are inside the panel and a click on either
            # must move the caret rather than fall through to a mode/map row
            # underneath it.
            name_r = getattr(self, "_name_rect", None)
            if name_r is not None and name_r.collidepoint(m):
                self.selected_field = "name"
                return True
            addr_r = getattr(self, "_addr_rect", None)
            if addr_r is not None and addr_r.collidepoint(m):
                self.selected_field = "address"
                return True
            for i, r in getattr(self, "_mode_rects", {}).items():
                if r.collidepoint(m):
                    self.mode_name = (AR.MODE_TDM, AR.MODE_FFA)[i]
                    return True
            for i, r in getattr(self, "_map_rects", {}).items():
                if r.collidepoint(m):
                    self.map_name = self.maps()[i]
                    # A smaller map cannot seat the count picked for the
                    # previous one, so pull it back to the new cap.
                    self.players = min(self.players, self.max_players())
                    return True
            for n, r in getattr(self, "_pl_rects", {}).items():
                if r.collidepoint(m):
                    self.players = n
                    return True
            for tag, r in getattr(self, "_btn_rects", {}).items():
                if r.collidepoint(m):
                    if tag == 1:
                        self.request_host()
                    elif tag == 2:
                        self.request_join()
                    elif tag == 3:
                        self.close()
                    return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            if event.key == pygame.K_TAB:
                # Two fields, so Tab is a two-way toggle rather than a dead
                # key. Both ways round, because a player who clicked into the
                # wrong box must be able to reach the other one.
                self.selected_field = ("address" if self.selected_field == "name"
                                       else "name")
                return True
            if self.selected_field == "name":
                return self._name_field_key(event)
            if event.key == pygame.K_BACKSPACE:
                self.address = self.address[:-1]
                return True
            if event.key == pygame.K_RETURN:
                self.request_join()
                return True
            # Ctrl+V (and Cmd+V on mac): a paste is not a keypress, so the
            # unicode append below never sees it. Pull the clipboard.
            if event.key == pygame.K_v and (
                    event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                paste = clipboard_text(60 - len(self.address))
                if paste:
                    self.address += paste
                return True
            if event.unicode and event.unicode.isprintable() \
                    and len(self.address) < 60:
                self.address += event.unicode
                return True
        return False

    def _name_field_key(self, event):
        """Keyboard input for the callsign field. Returns True when consumed.

        Consumes everything, for the same reason the chat composer does: a
        stray keypress must not also fire a weapon switch or close the panel
        while the player is halfway through typing their name.

        The value is sanitized in memory on every keystroke but only WRITTEN
        on ENTER. Persisting per character would mean an fsync-per-keystroke
        (json_store.atomic_write fsyncs), which is a visible hitch in a
        panel that redraws every frame.
        """
        if event.key == pygame.K_RETURN:
            self._commit_name(save=True)
            self.selected_field = "address"
            return True
        if event.key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
            self._commit_name(save=False)
            return True
        if event.key == pygame.K_v and (
                event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
            paste = clipboard_text(NAME_CHARS - len(self.player_name))
            if paste:
                self.player_name = paste
                self._commit_name(save=False)
            return True
        if event.unicode and event.unicode.isprintable() \
                and len(self.player_name) < NAME_CHARS:
            self.player_name += event.unicode
            self._commit_name(save=False)
            return True
        return True

    def _commit_name(self, save=True):
        """Sanitize the typed callsign, and remember it.

        The in-memory clamp happens every time so the field can never hold
        something the protocol would later cut -- a name that looks longer in
        the box than it is over your head is its own small lie.
        """
        self.player_name = P.sanitize_name(self.player_name, "") or ""
        if save:
            settings_store.set_player_name(self.player_name)

    def _chat_allowed(self):
        """Whether chat may be opened right now.

        Anywhere in a match or its lobby, including while the round is over.
        There is no reason to withhold a text channel from people who are
        looking at the same results screen, and a rule that switches chat off
        at a phase boundary is a rule somebody will read as a bug.
        """
        return self.mode in ("hosting", "playing")

    def _pause_event(self, event, mouse_pos):
        """Input for the in-match menu. Returns True when consumed."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.paused = False
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            copy_r = self._pause_rects.get("copy")
            resume = self._pause_rects.get("resume")
            leave = self._pause_rects.get("leave")
            kick = self._pause_rects.get("kick")
            if copy_r is not None and copy_r.collidepoint(mouse_pos):
                self._copy_room_code()   # stay paused so it can be pasted
                return True
            if resume is not None and resume.collidepoint(mouse_pos):
                self.paused = False
                return True
            if kick is not None and kick.collidepoint(mouse_pos):
                # Stay paused: the player has to see the result, and unpausing
                # straight after everybody left would drop them into an empty
                # live room with no explanation.
                self.kick_players()
                return True
            if leave is not None and leave.collidepoint(mouse_pos):
                self.paused = False
                self.close()
                return True
            return True     # swallow clicks so the frozen match never fires
        return False

    # ── drawing ──

    def draw(self, surface):
        """Draw whichever of the three things we currently are."""
        if self.mode == "hosting" or self.mode == "playing":
            self._draw_match(surface)
        elif self.mode == "panel":
            self.draw_panel(surface)

    def _hud_kwargs(self, local_id, world):
        """Everything the HUD needs that does not come from entity positions.

        The host owns the scoreboard, the clock and the pickup timers, so the
        client renders whatever it was last told rather than deriving a rule
        the host already decided.
        """
        st = self._match_state or {}
        if self.sim is not None:
            # Host: read the sim directly, no packet round trip. Guarded
            # because tests and the panel-preview tools substitute a stub sim
            # that only answers what they render; a HUD that raises there
            # would take the whole frame down.
            state_fn = getattr(self.sim, "match_state", None)
            if callable(state_fn):
                state = state_fn()
                sb_fn = getattr(self.sim, "scoreboard", None)
                state["scoreboard"] = sb_fn() if callable(sb_fn) else ()
                st = state
        me = world.get(local_id)
        self.view._host_tick = int(getattr(self.sim, "tick", 0)
                                   or (getattr(self.sess, "tick", 0)
                                       if self.sess else 0) or 0)
        ammo = None
        armour = 0
        weapon = me[7] if me is not None else None
        # Host: authoritative, straight from the sim.
        sim_players = getattr(self.sim, "players", None) or {}
        local = sim_players.get(local_id) if isinstance(sim_players, dict) \
            else None
        if local is not None:
            ammo = local.get("ammo")
            armour = local.get("armour", 0)
        elif self.sim is None:
            # Client: the snapshot carries the weapon but not the magazine
            # count, so the HUD reads the last count the host reported. One
            # snapshot of lag on a number that is otherwise invisible is a
            # fair trade for widening the entity for every player.
            ammo = (st.get("ammo") or {}).get(str(local_id))
            armour = 0
        return {
            "mode": st.get("mode", self.mode_name),
            "clock": st.get("clock"),
            "score_limit": st.get("score_limit"),
            "phase": (self._session_phase if self.sim is not None
                      else st.get("session_phase", "playing")),
            "team_scores": (st.get("team_scores")
                            if st.get("mode") == AR.MODE_TDM else None),
            "killfeed": self._killfeed,
            "pickups": st.get("pickups"),
            # Only ever non-empty for a player who is actually waiting. The
            # view reads the local slot for its plate and draws everyone else's
            # above their corpse, so a match full of dead players stays legible
            # without a screen full of cards.
            "respawn": self._respawn,
            "respawn_killer": self._last_killer,
            "local_weapon": weapon,
            "local_ammo": ammo,
            "local_armour": armour,
            # What we are CARRYING, not just what we are holding: the HUD
            # greys out the keys that would be refused, which is what makes
            # switching discoverable at all.
            "local_carry": self._local_carry(),
        }

    def _round_result(self):
        """(over, winner): the round outcome, for the host AND for clients.

        The host reads its own sim; a client has no sim and reads the host's
        last match-state packet instead (``winner`` plus the ``live`` →
        ``intermission`` phase edge). Before this only the host branch of
        _draw_match checked anything, so the win screen only ever appeared
        for the host while every client kept playing a finished round.
        """
        st = self._match_state or {}
        winner = st.get("winner")
        if self.sim is not None:
            if getattr(self.sim, "finished", False):
                return True, winner
            return False, winner
        if winner is not None:
            return True, winner
        if st.get("phase") == "intermission":
            return True, None
        return False, None

    def _credit_round_result(self):
        """Bank the round's Acaribucks, exactly once, and latch the number.

        Runs on the same edge as the round-end sting because that edge is
        already the one place in the file that fires precisely once per round
        on a host AND on a client.

        The amount is derived here from the host's published board rather than
        sent as a figure, and that is the load-bearing choice: this
        architecture has no trusted server, so a host that announces "you
        earned 40" is a host that can pay its opponents zero.

        What this does NOT protect against, said out loud rather than left as
        a surprise: hosting private matches and editing profile.json by hand.
        Both need relay-side identity to close, which the multiplayer roadmap
        lists as unbuilt work in its own right. What IS closed: two credits for
        one round, credit for kills the host never scored, and an unbounded
        balance.
        """
        st = self._match_state or {}
        local_id = self.sess.local_id if self.sess is not None else 0
        amount, kills, place, won = AR.compute_payout(
            st.get("mode"), st.get("scoreboard") or (), st.get("winner"),
            local_id, st.get("teams") or {}, st.get("team_scores") or {},
            st.get("score_limit") or AR.SCORE_LIMIT)
        # Match token, round number, our slot, our kills. Identical on host and
        # client for the same round, and different for every round.
        try:
            round_no = int(st.get("round") or 0)
        except (TypeError, ValueError):
            round_no = 0
        key = "%s:%d:%d:%d" % (st.get("match_id") or "-", round_no,
                               local_id, kills)
        if profile_store.credit_round(key, amount):
            self._last_payout = (amount, kills, place, won)
        else:
            # Either already banked or the write failed. Either way, showing a
            # number here would promise money that is not in the wallet.
            self._last_payout = None

    def _round_end_title(self, winner):
        """(title, color, subtitle): personalized VICTORY/DEFEAT card text.

        FFA names the winning player; TDM names the winning side (from the
        host's team_scores, since ``winner`` itself is the final killer's
        slot, not a team). A clock timeout with no winner is a draw.
        """
        local_id = self.sess.local_id if self.sess is not None else 0
        st = self._match_state or {}
        mode = st.get("mode", self.mode_name)
        if mode == AR.MODE_TDM:
            scores = st.get("team_scores") or {}
            try:
                a = int(scores.get("0", scores.get(0, 0)))
            except (TypeError, ValueError):
                a = 0
            try:
                b = int(scores.get("1", scores.get(1, 0)))
            except (TypeError, ValueError):
                b = 0
            if a == b:
                return "DRAW", (170, 180, 200), "IPA %d : %d KRAP" % (a, b)
            won_team = AR.TEAM_IPA if a > b else AR.TEAM_KRAP
            my_team = None
            if self.sim is not None:
                my_team = self.sim.rules.team_of(local_id)
            else:
                teams = st.get("teams") or {}
                raw = teams.get(str(local_id), teams.get(local_id))
                try:
                    my_team = int(raw) if raw is not None else None
                except (TypeError, ValueError):
                    my_team = None
            won = (my_team == won_team)
            name = AR.TEAM_NAMES.get(won_team, "TEAM")
            color = (120, 220, 150) if won else (255, 96, 96)
            title = "VICTORY" if won else "DEFEAT"
            return title, color, "%s WINS  ·  IPA %d : %d KRAP" % (name, a, b)
        if winner is None:
            return "DRAW", (170, 180, 200), "TIME  ·  NOBODY TAKES THE ROUND"
        won = (winner == local_id)
        color = (120, 220, 150) if won else (255, 96, 96)
        title = "VICTORY" if won else "DEFEAT"
        return title, color, "%s WINS THE ROUND" % self.name_of(winner).upper()

    def _draw_round_end(self, surface, winner):
        """Centered round-over card in the lobby/pause panel language.

        The old banner was one small amber line at the top of the screen with
        no backing, unreadable over a bright arena floor. This is a dimmed
        screen + panel card (same dark plate, orange header rule and corner
        ticks as the match lobby) with a big personalized result, the
        winner/team sub-line, and the intermission note while the host
        counts down to the next round.
        """
        title, color, subtitle = self._round_end_title(winner)
        w, h = surface.get_width(), surface.get_height()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surface.blit(dim, (0, 0))
        pw, ph = 520, 250
        px, py = (w - pw) // 2, (h - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surface, C_PANEL_BG, panel)
        pygame.draw.rect(surface, C_ACCENT, (px, py, pw, 3))
        pygame.draw.rect(surface, C_ACCENT, panel, 2)
        pygame.draw.rect(surface, (90, 50, 20), panel.inflate(-4, -4), 1)
        for tx, ty in ((px + 10, py + 10), (px + pw - 10, py + 10),
                       (px + 10, py + ph - 10), (px + pw - 10, py + ph - 10)):
            dx = 1 if tx < px + pw // 2 else -1
            dy = 1 if ty < py + ph // 2 else -1
            pygame.draw.line(surface, C_ACCENT, (tx, ty), (tx + dx * 16, ty), 2)
            pygame.draw.line(surface, C_ACCENT, (tx, ty), (tx, ty + dy * 16), 2)
        cx = panel.centerx
        self._blit(surface, cx, "// ROUND OVER //", py + 20, 11,
                   C_ACCENT, center=True, mono=True, bold=True)
        self._blit(surface, cx, title, py + 48, 64, color,
                   center=True, bold=True)
        self._blit(surface, cx, subtitle, py + 128, 14, C_TEXT,
                   center=True, mono=True, bold=True)
        st = self._match_state or {}
        limit = st.get("score_limit")
        board = st.get("scoreboard") or ()
        extra = ""
        reached = False
        if isinstance(limit, int) and limit > 0:
            scores = st.get("team_scores") or {}
            try:
                reached = max(int(scores.get("0", scores.get(0, 0))),
                              int(scores.get("1", scores.get(1, 0)))) >= limit
            except (TypeError, ValueError):
                reached = False
            if not reached and board:
                try:
                    reached = max(int(r[1]) for r in board) >= limit
                except (TypeError, ValueError, IndexError):
                    reached = False
            if reached:
                extra = "FIRST TO %d" % limit
        if board:
            try:
                top = sorted(board, key=lambda r: (-r[1], r[2], r[0]))[0]
                extra = (extra + "  ·  " if extra else "") + "%s %d K" % (
                    self.name_of(top[0]).upper(), top[1])
            except (TypeError, ValueError, IndexError):
                pass
        if extra:
            self._blit(surface, cx, extra, py + 154, 12, C_DIM,
                       center=True, mono=True)
        # What the round paid. A zero is spelled out rather than left blank:
        # an empty slot on a results card reads as a broken shop, and "you
        # earned nothing because you scored nothing" is the rule this economy
        # runs on, so it should be legible.
        if self._last_payout is not None:
            amount, kills, place, won = self._last_payout
            if amount:
                order = ("1ST", "2ND", "3RD", "4TH")
                self._blit(
                    surface, cx,
                    "+%d ACARIBUCKS   ·   %d K   ·   %s" % (
                        amount, kills,
                        order[place] if place < len(order) else "TOP"),
                    py + 178, 13, C_ACCENT, center=True, mono=True, bold=True)
            else:
                self._blit(surface, cx, "NO PAYOUT - NO RESULT", py + 178, 12,
                           C_DIM, center=True, mono=True)
        phase = st.get("phase")
        if phase == "intermission" or self.sim is not None:
            self._blit(surface, cx, "NEXT ROUND STARTING...", py + ph - 40,
                       12, C_DIM, center=True, mono=True)

    def _draw_match(self, surface):
        # Our own slot. The host is always 0; a client learns its slot from
        # the host's assign packet, so colour/tags and (on the client) the
        # shot trace use the right entity.
        local_id = self.sess.local_id if self.sess is not None else 0
        if self.sim is not None:
            world = dict((e[0], e) for e in self.sess.world)
            # The host needs the same HUD kwargs as a client. It used to draw
            # with defaults only, so the host's own frame labelled a TDM match
            # "FFA", showed no team scores and no loadout -- the host was the
            # one player who could not see the rules of the match they were
            # running.
            self.view.draw(surface, world, local_id, self.sim.scoreboard(),
                           **self._hud_kwargs(local_id, world))
        else:
            world = self.sess.sample_world() or {}
            # Draw our own character from the PREDICTED position, not the
            # interpolated snapshot. Remote players keep interpolating -- that
            # is correct for them, they have no input to predict -- but the
            # local player must be drawn at the position the player just
            # asked for, which is the entire point of predicting.
            if self._pred is not None and self._pred.seeded:
                mine = world.get(local_id)
                if mine is not None:
                    world = dict(world)
                    mine = list(mine)
                    mine[2] = self._pred.x
                    mine[3] = self._pred.y
                    mine[4] = self._pred.angle
                    world[local_id] = tuple(mine)
            self.view.draw(surface, world, local_id, self._match_state
                            .get("scoreboard", ()),
                            **self._hud_kwargs(local_id, world))
        if self.sim is not None:
            count = len(self.peers) + 1
            self._blit(surface, 10, "PLAYERS %d/%d" % (count, self.players),
                       26, 17, (170, 180, 200))
        else:
            self._blit(surface, 10, "CONNECTED", 26, 17, (150, 220, 160))
        # The round-end sting + card fire on the shared outcome, on the edge.
        # They used to key off sim.finished inside the host branch only, so
        # clients (sim is None) never saw or heard the result. Checking the
        # flag every frame and playing on it would be a 5-second siren.
        round_over, round_winner = self._round_result()
        if round_over and not self._round_end_played:
            self._round_end_played = True
            if self.view is not None:
                self.view.on_round_end()
            # The payout rides this same edge. It is once per round by
            # construction, and profile_store.credit_round() refuses a key it
            # has already banked, so a card that lingers for five seconds pays
            # once and a client that redraws the round pays nothing.
            self._credit_round_result()
        elif not round_over:
            self._round_end_played = False
            # Cleared with the round, not with the match: the next round has to
            # earn its own line on the card.
            self._last_payout = None
        round_card_up = bool(round_over) and not self.in_match_lobby()
        # Cleared unconditionally, then repopulated only while the card is up.
        # Leaving the old rect in place meant that after a friend joined, a
        # click on the spot where COPY CODE used to be silently copied to the
        # clipboard instead of firing -- the button was invisible but live.
        self._wait_rects = {}
        # The whole pre-game room is a lobby: every joiner sees the same
        # roster and waits for the host. It disappears only when the host's
        # explicit countdown begins.
        self._lobby_rects = {}
        if self.in_match_lobby():
            self._draw_waiting(surface)
        # A note that has to be seen without opening a menu: a switch the
        # host refused, or the session ending underneath us.
        if self._toast and self._toast_left > 0:
            self._blit(surface, surface.get_width() // 2, self._toast,
                       surface.get_height() - 78, 15, C_ACCENT,
                       center=True, mono=True, bold=True)
        # The round-over card sits above the world/HUD but below chat, so a
        # conversation stays readable through the intermission. The pause
        # card stays on top of everything.
        if round_card_up:
            self._draw_round_end(surface, round_winner)
        if self.paused:
            self._draw_pause(surface)
        # Tab last, above even the pause card: it was asked for on purpose, and
        # while paused nothing else is competing for the view. Hidden before the
        # round starts, where there is no scoreboard yet and the overlay would
        # only cover the room code a joiner is trying to read.
        if self._scoreboard and (self.paused or not self.input_frozen()):
            self._draw_scoreboard(surface)
        # The chat panel sits above the loadout but below the pause card, so
        # a message you typed is still readable behind the menu.
        self._draw_chat(surface)
        # Last thing on top of the frame: the intro fade + countdown. Skipped
        # while paused so it never fights the pause card.
        self._draw_intro(surface)

    def _copy_room_code(self):
        """Put the room code or public address on the clipboard, best effort."""
        if not self.room_code_ready():
            self.status = "network address is still being checked"
            return
        if not self.room_code:
            return
        try:
            if pygame.scrap.get_init() or pygame.scrap.init():
                pygame.scrap.put(pygame.SCRAP_TEXT,
                                 self.share_code().encode("ascii"))
                self.status = "room code copied"
                return
        except Exception:
            pass
        self.status = "copy unavailable - read the code aloud"

    def _forward_status(self):
        """One honest line about whether this code reaches the internet.

        Shared by the waiting card and the pause menu. When these were two
        separate inline blocks they could drift, and the host would be told
        the code was fine in one place and unusable in the other.
        """
        if self._hamachi_active:
            return ("Hamachi ready - same network; allow game in Windows Firewall.",
                    (120, 220, 150))
        if self._tunnel_active:
            return ("Public TCP tunnel ready - share this address.",
                    (120, 220, 150))
        if self.forwarded:
            return ("Router port opened - share the public room code.",
                    (120, 220, 150))
        if self._tunnel_pending:
            return ("Router blocked; trying automatic internet tunnel...",
                    (240, 200, 80))
        if self.forward_note:
            if "8013" in self.forward_note:
                return ("LAN only - ngrok wants a card; use Hamachi/Tailscale or forward the port.",
                        (240, 200, 80))
            if "9009" in self.forward_note:
                return ("LAN only - ngrok proxy_url needs a paid plan.",
                        (240, 200, 80))
            if "tunnel lost" in self.forward_note:
                return ("Internet tunnel lost - LAN only; leave and host again.",
                        (240, 200, 80))
            if "bore was not found" in self.forward_note:
                return ("LAN only - bore missing; reinstall, use Hamachi/Tailscale or forward.",
                        (240, 200, 80))
            if "cloudflared is not installed" in self.forward_note:
                return ("LAN only - tunnel missing; use Hamachi/Tailscale or forward the port.",
                        (240, 200, 80))
            return ("LAN only - tunnel failed; use Hamachi/Tailscale or forward the port.",
                    (240, 200, 80))
        return ("Checking router and public connection options...", C_DIM)

    def _draw_waiting(self, surface):
        """Shared frozen lobby. Host authorization remains in handle_event."""
        _mp_style.draw_lobby(self, surface, pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H))

    def _draw_team_board(self, surface, board, roster, teams, my_slot, host):
        """Presentation-only team slots using existing move/join click keys."""
        _mp_style.draw_teams(self, surface, board, roster, teams, my_slot, host)

    def _draw_intro(self, surface):
        """Host-synchronized fade + GET READY countdown over a frozen match.

        The host has already stopped all simulation and input. Clients follow
        its countdown timer and remain locally frozen until the host publishes
        session_phase=playing. The black eases away while 3 / 2 / 1 / GO runs;
        no movement, shots, weapon changes, or simulation ticks happen beneath
        it.
        """
        if self._intro_left <= 0.0 or self.paused:
            return
        w, h = surface.get_width(), surface.get_height()
        cx, cy = w // 2, h // 2
        # elapsed runs 0 -> INTRO_SECONDS as _intro_left runs INTRO_SECONDS -> 0.
        elapsed = INTRO_SECONDS - self._intro_left

        # Fade from black, easing out over the first ~70% of the intro.
        frac = max(0.0, 1.0 - elapsed / (INTRO_SECONDS * 0.7))
        alpha = int(255 * frac * frac)
        if alpha > 0:
            if self._intro_black is None or \
                    self._intro_black.get_size() != (w, h):
                self._intro_black = pygame.Surface((w, h))
                self._intro_black.fill((0, 0, 0))
            self._intro_black.set_alpha(min(255, alpha))
            surface.blit(self._intro_black, (0, 0))

        # The text eases in just after the black starts lifting, and out
        # again right at the end so it never just blinks off.
        a_in = min(1.0, max(0.0, (elapsed - 0.15) / 0.35))
        a_out = min(1.0, max(0.0, self._intro_left / 0.4))
        ta = int(255 * a_in * a_out)
        if ta <= 0:
            return

        idx = min(3, int(elapsed / INTRO_STEP))
        num = ("3", "2", "1", "GO")[idx]
        p = (elapsed - idx * INTRO_STEP) / INTRO_STEP     # 0..1 within a beat

        # A soft scrim so the countdown survives a bright arena floor.
        if self._intro_plate is None or \
                self._intro_plate.get_size() != (w, 168):
            self._intro_plate = pygame.Surface((w, 168), pygame.SRCALPHA)
            pygame.draw.rect(self._intro_plate, (6, 8, 12, 170), (0, 0, w, 168))
        self._intro_plate.set_alpha(ta)
        surface.blit(self._intro_plate, (0, cy - 84))

        title = self._font(19, bold=True, mono=True).render(
            _T("match_screen.get_ready"), True, C_ACCENT)
        title.set_alpha(ta)
        surface.blit(title, (cx - title.get_width() // 2, cy - 66))

        # Each beat pops in large and settles, which reads as a pulse rather
        # than a static slide of digits. Rendered once at a fixed size and
        # scaled, so the pop never bloats the shared font cache.
        big = self._font(84, bold=True).render(num, True, (245, 248, 255))
        scale = 1.0 + 0.32 * max(0.0, 1.0 - p * 1.35)
        if scale > 1.02:
            big = pygame.transform.smoothscale(
                big, (max(1, int(big.get_width() * scale)),
                      max(1, int(big.get_height() * scale))))
        big.set_alpha(ta)
        surface.blit(big, (cx - big.get_width() // 2,
                           cy - big.get_height() // 2 + 12))

    def _draw_pause(self, surface):
        """In-match menu, styled to match the single-player pause.

        Framed terminal panel: corner ticks, a classification banner, an
        Impact-style "PAUSED" title and an orange accent bar - the same
        language as ui/system.draw_pause_menu(), so pausing in a match does
        not look like a different program bolted on. Networking keeps
        running underneath; this only stops the local player acting (see
        update()).

        It also carries the FULL standings table. The in-match HUD strip can
        only afford one row -- with a name on it, a six-row rank column would
        not fit in the 30px bar without drawing over the mode dossier and the
        clock -- so this is where a player goes to read the table, and it is
        the natural place: they opened a menu to look.
        """
        w, h = surface.get_width(), surface.get_height()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        surface.blit(dim, (0, 0))
        # Height is derived from the content, and every y below is derived
        # from the SAME constants, because guessing one of the two is how a
        # hand-sized card ends up with its buttons hanging off the bottom on
        # an eight-player map (which is exactly what the first version of this
        # did -- a fixed 452px card plus a standings block that grew).
        _STAND_TOP = 322            # STANDINGS header, measured from py
        _STAND_ROW = 17
        _STAND_HEAD = 18            # header -> first row
        _BTN_GAP = 14               # last row -> first button
        _BTN_H = 42
        _BUTTONS_H = 132            # RESUME + LEAVE + REMOVE
        _CARD_PAD = 28              # below the last button
        pw = 480
        _rows = self.standings()
        ph = (_STAND_TOP + _STAND_HEAD + len(_rows) * _STAND_ROW
              + _BTN_GAP + _BUTTONS_H + _CARD_PAD)
        px = (w - pw) // 2
        # Clamped for the same reason the entry panel is: content does not get
        # a vote from the window height, and an eight-player table on a short
        # window should slide up rather than lose its buttons off-screen.
        py = max(8, (h - ph) // 2)
        px, py = (w - pw) // 2, (h - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surface, C_PANEL_BG, panel)
        pygame.draw.rect(surface, C_ACCENT, (px, py, pw, 3))
        pygame.draw.rect(surface, C_ACCENT, panel, 2)
        pygame.draw.rect(surface, (90, 50, 20), panel.inflate(-4, -4), 1)
        # Corner ticks, matching the main menu / single-player pause.
        for cx, cy in ((px + 10, py + 10), (px + pw - 10, py + 10),
                       (px + 10, py + ph - 10), (px + pw - 10, py + ph - 10)):
            dx = 1 if cx < px + pw // 2 else -1
            dy = 1 if cy < py + ph // 2 else -1
            pygame.draw.line(surface, C_ACCENT, (cx, cy), (cx + dx * 16, cy), 2)
            pygame.draw.line(surface, C_ACCENT, (cx, cy), (cx, cy + dy * 16), 2)
        # Classification banner.
        by = py + 20
        pygame.draw.line(surface, C_ACCENT, (px + 26, by), (px + pw - 26, by), 1)
        pygame.draw.line(surface, C_ACCENT, (px + 26, by + 18),
                         (px + pw - 26, by + 18), 1)
        self._blit(surface, px + pw // 2,
                   "// KRAPNET TERMINAL - MATCH SUSPENDED //",
                   by + 4, 10, C_ACCENT, center=True, mono=True, bold=True)
        # Title, subtitle, accent bar.
        self._blit(surface, px + pw // 2, "PAUSED", py + 52, 40, C_TEXT,
                   center=True, mono=True, bold=True)
        self._blit(surface, px + pw // 2,
                   "DEATHMATCH  //  %s" % self.map_name.upper(),
                   py + 104, 12, C_DIM, center=True, mono=True)
        pygame.draw.rect(surface, C_ACCENT,
                         (px + pw // 2 - 100, py + 126, 200, 3))
        self._pause_rects = {}
        # Status block: label left, value right.
        lx, rx = px + 28, px + pw - 28

        def row(y, label, value):
            self._blit(surface, lx, label, y, 11, C_DIM, mono=True, bold=True)
            val = self._font(14, True, True).render(str(value), True, C_TEXT)
            surface.blit(val, (rx - val.get_width(), y - 2))

        row(py + 150, "PLAYERS", "%d / %d" % (len(self.peers) + 1, self.players))
        row(py + 172, "MAP", self.map_name.upper())
        iy = py + 204
        # Same gate as the waiting card: no code is shown until the address
        # has settled, so the pause menu can never hand out a stale one.
        if self.sim is not None and self.room_code_ready():
            self._blit(surface, lx, "ROOM CODE", iy, 11, C_DIM,
                       mono=True, bold=True)
            self._blit(surface, lx, self.share_code(), iy + 16, 20, C_ACCENT,
                       mono=True, bold=True)
            r_copy = pygame.Rect(rx - 132, iy + 12, 132, 40)
            self._action(surface, r_copy, "COPY CODE", True)
            self._pause_rects["copy"] = r_copy
            if self.share_host:
                self._blit(surface, lx,
                           "ADDRESS  %s:%d" % (self.share_host,
                                               self.share_port),
                           iy + 62, 12, C_TEXT, mono=True)
            note, col = self._forward_status()
            self._blit(surface, lx, note[:66], iy + 86, 11, col, mono=True)
        elif self.sim is not None:
            self._blit(surface, lx, "ROOM CODE", iy, 11, C_DIM,
                       mono=True, bold=True)
            self._blit(surface, lx, ROOM_CODE_PENDING_TEXT, iy + 16, 16,
                       C_DIM, mono=True)
            note, col = self._forward_status()
            self._blit(surface, lx, note[:66], iy + 44, 11, col, mono=True)
        else:
            self._blit(surface, px + pw // 2, "MATCH IN PROGRESS",
                       iy + 24, 16, C_CYAN, center=True, mono=True, bold=True)
        # ── standings ───────────────────────────────────────────────────
        # Name, side, kills, deaths. Ranked by the host's own ordering, which
        # is kills-then-deaths, so the table and the HUD chip can never
        # disagree about who is first.
        sy = py + _STAND_TOP
        self._blit(surface, lx, "STANDINGS", sy, 11, C_DIM, mono=True,
                   bold=True)
        pygame.draw.line(surface, C_PANEL_EDGE, (lx + 74, sy + 6),
                         (rx, sy + 6), 1)
        self._blit(surface, rx - 30, "K", sy, 11, C_DIM, mono=True, bold=True)
        self._blit(surface, rx, "D", sy, 11, C_DIM, mono=True, bold=True)
        for i, line in enumerate(_rows):
            ry = sy + _STAND_HEAD + i * _STAND_ROW
            mine = line[3]
            col = C_CYAN if mine else C_TEXT
            tag = AR.TEAM_NAMES.get(line[4], "") if line[4] is not None else ""
            self._blit(surface, lx, line[1][:20], ry, 13, col, mono=True,
                       bold=mine)
            self._blit(surface, lx + 168, tag, ry, 12, C_DIM, mono=True)
            self._blit(surface, rx - 30, line[2], ry, 13, col, mono=True,
                       bold=True)
            self._blit(surface, rx, line[0], ry, 13, col, mono=True, bold=True)
        # ── buttons ─────────────────────────────────────────────────────
        by_btn = sy + _STAND_HEAD + len(_rows) * _STAND_ROW + _BTN_GAP
        r_resume = pygame.Rect(px + 70, by_btn, pw - 140, _BTN_H)
        r_leave = pygame.Rect(px + 70, by_btn + _BTN_H + 8, pw - 140, _BTN_H)
        self._action(surface, r_resume, "RESUME", True)
        self._action(surface, r_leave, "LEAVE MATCH", False)
        self._pause_rects["resume"] = r_resume
        self._pause_rects["leave"] = r_leave
        # Host-only, and only with somebody to remove. Sitting permanently on
        # screen would be noise for a host playing alone, and a button that is
        # always there invites being hit by accident -- which is what a kick
        # in somebody else's match would do.
        if self.sim is not None and self.peers:
            r_kick = pygame.Rect(px + 70, by_btn + (_BTN_H + 8) * 2, pw - 140, 32)
            self._action(surface, r_kick,
                         "REMOVE ALL PLAYERS (%d)" % len(self.peers), False)
            self._pause_rects["kick"] = r_kick
        self._blit(surface, px + pw // 2, "ESC - RESUME", py + ph - 20, 12,
                   C_DIM, center=True, mono=True)

    def _draw_scoreboard(self, surface):
        """Hold-Tab standings overlay.

        Exists because the pause menu's table is the only full standings view in
        a match, and reaching it means stopping: ESC pauses, which is useless as
        an answer to "who is winning right now" mid-fight. Tab is the convention
        for exactly this -- read the board without leaving the round.

        Built on standings() rather than a second sort, so the HUD chip, the
        pause table and this can never disagree about rank. The host publishes
        kills-then-deaths ordering and all three read that list.

        Deliberately shows no ping column. Latency is not measured or carried on
        the match socket today, and a scoreboard with a fabricated ping column is
        worse than one without it -- players will act on the number.
        """
        rows = self.standings()
        st = self._match_state or {}
        w, h = surface.get_width(), surface.get_height()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 165))
        surface.blit(dim, (0, 0))
        pw = 520
        head_h = 96
        row_h = 19
        teams_h = 26 if (st.get("mode") or self.mode_name) == AR.MODE_TDM else 0
        # Every block below is counted here on purpose. The first pass sized the
        # panel from a fixed footer allowance and let the table run into it, so
        # the wallet line printed straight over the fourth player's row -- a bug
        # that only appeared at four or more players, i.e. exactly the matches
        # where a scoreboard matters.
        foot_h = 34
        body_h = 18 + teams_h + 16 + len(rows) * row_h
        ph = head_h + body_h + foot_h
        px = (w - pw) // 2
        py = max(10, (h - ph) // 2)
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surface, C_PANEL_BG, panel)
        pygame.draw.rect(surface, C_ACCENT, (px, py, pw, 3))
        pygame.draw.rect(surface, C_ACCENT, panel, 2)
        for cx, cy in ((px + 10, py + 10), (px + pw - 10, py + 10),
                       (px + 10, py + ph - 10), (px + pw - 10, py + ph - 10)):
            dx = 1 if cx < px + pw // 2 else -1
            dy = 1 if cy < py + ph // 2 else -1
            pygame.draw.line(surface, C_ACCENT, (cx, cy), (cx + dx * 16, cy), 2)
            pygame.draw.line(surface, C_ACCENT, (cx, cy), (cx, cy + dy * 16), 2)
        lx, rx = px + 26, px + pw - 26
        cxm = px + pw // 2
        by = py + 20
        pygame.draw.line(surface, C_ACCENT, (lx, by), (rx, by), 1)
        pygame.draw.line(surface, C_ACCENT, (lx, by + 18), (rx, by + 18), 1)
        self._blit(surface, cxm, "// KRAPNET TERMINAL - LIVE STANDINGS //",
                   by + 4, 10, C_ACCENT, center=True, mono=True, bold=True)
        mode = st.get("mode") or self.mode_name or AR.MODE_FFA
        title = "TEAM DEATHMATCH" if mode == AR.MODE_TDM else "DEATHMATCH"
        self._blit(surface, cxm, title, py + 48, 26, C_TEXT, center=True,
                   mono=True, bold=True)
        limit = st.get("score_limit") or 0
        clock = st.get("clock")
        bits = [self.map_name.upper()]
        if isinstance(clock, (int, float)) and clock >= 0:
            bits.append("%d:%02d" % (int(clock) // 60, int(clock) % 60))
        if limit:
            bits.append("FIRST TO %d" % limit)
        self._blit(surface, cxm, "  //  ".join(bits), py + 78, 11, C_DIM,
                   center=True, mono=True)

        # Team totals above the table when there are teams. This is the number
        # a round is actually decided on -- individual kills are the breakdown.
        y = py + head_h
        if teams_h:
            scores = st.get("team_scores") or {}
            cells = []
            for team in (AR.TEAM_IPA, AR.TEAM_KRAP):
                got = scores.get(str(team), scores.get(team))
                try:
                    got = int(got)
                except (TypeError, ValueError):
                    got = 0
                cells.append((AR.TEAM_NAMES[team], got, TEAM_TINTS[team]))
            half = (rx - lx) // 2
            for i, (name, got, tint) in enumerate(cells):
                bx = lx + i * half
                pygame.draw.rect(surface, (10, 16, 22),
                                 (bx, y - 2, half - 8, 24))
                pygame.draw.rect(surface, tint, (bx, y - 2, half - 8, 24), 1)
                self._blit(surface, bx + 8, name, y + 2, 12, tint, mono=True,
                           bold=True)
                val = self._font(15, True, True).render(str(got), True, C_TEXT)
                surface.blit(val, (bx + half - 16 - val.get_width(), y))
            y += teams_h

        self._blit(surface, rx - 26, "K", y, 10, C_DIM, mono=True, bold=True)
        self._blit(surface, rx, "D", y, 10, C_DIM, mono=True, bold=True)
        y += 16
        for rank, line in enumerate(rows):
            deaths, name, kills, mine, team = line
            col = C_ACCENT if mine else C_TEXT
            if mine:
                # Behind the text: a marker that survives a monospace font
                # substitution. Bold alone disappears on some faces, and finding
                # yourself in an eight-row table by reading every name is not a
                # design. Drawn first so the row's own glyphs stay crisp.
                pygame.draw.rect(surface, (46, 32, 8),
                                 (lx - 8, y - 3, rx - lx + 16, row_h))
            self._blit(surface, lx, "%d." % (rank + 1), y, 12,
                       C_DIM, mono=True)
            self._blit(surface, lx + 26, name[:18], y, 13, col, mono=True,
                       bold=mine)
            if team is not None:
                tag = AR.TEAM_NAMES.get(team, "")
                self._blit(surface, lx + 196, tag, y, 11,
                           TEAM_TINTS.get(team, C_DIM), mono=True)
            val_k = self._font(13, True, True).render(str(kills), True, col)
            surface.blit(val_k, (rx - 34 - val_k.get_width(), y - 2))
            val_d = self._font(13, False, True).render(str(deaths), True, C_DIM)
            surface.blit(val_d, (rx - 4 - val_d.get_width(), y - 2))
            y += row_h

        earned = getattr(self, "_last_payout", None)
        wallet = profile_store.balance()
        note = "ACARIBUCKS  %s" % "{:,}".format(wallet)
        if earned:
            note += "   THIS ROUND +%d" % int(earned[0])
        self._blit(surface, cxm, note, py + ph - 34, 12, C_ACCENT, center=True,
                   mono=True, bold=True)
        self._blit(surface, cxm, "RELEASE TAB TO CLOSE", py + ph - 16, 10,
                   C_DIM, center=True, mono=True)

    def standings(self):
        """The full ranked table as [(deaths, name, kills, is_me, team)].

        Ranked by the host's ordering, not re-sorted here. The host already
        publishes kills-then-deaths and both the HUD chip and this table read
        that same list, so re-sorting in the UI is the one way to end up with
        a chip that says "3/5" next to a table that has you second.
        """
        rows = []
        if self.sim is not None:
            board = self.sim.scoreboard()
        else:
            board = (self._match_state or {}).get("scoreboard") or ()
        local_id = self.sess.local_id if self.sess is not None else 0
        teams = (self._match_state or {}).get("teams", {}) or {}
        for pid, kills, deaths in list(board)[:MAX_PLAYERS]:
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            rows.append((int(deaths), self.name_of(pid), int(kills),
                         pid == local_id, teams.get(str(pid))))
        return rows


    def draw_panel(self, surface):
        """Read-only two-column operations setup; original event keys retained."""
        _mp_style.draw_entry(self, surface, pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H))

    def _draw_name_box(self, surface, box):
        """The callsign field: focus ring, caret, and a sample when empty.

        Same treatment as the address field, and for the same reason: an empty
        box with no hint teaches nothing about what belongs in it.
        """
        focused = self.selected_field == "name"
        pygame.draw.rect(surface, C_ROW_BG, box)
        pygame.draw.rect(surface, C_CYAN if focused else C_PANEL_EDGE, box,
                         2 if focused else 1)
        font = self._font(14, False, True)
        if self.player_name:
            shown, col = self.player_name, C_TEXT
        else:
            # Bucketed on the clock, never per frame, so the hint does not
            # flicker into a different name every few milliseconds.
            sample = NAME_SAMPLES[(_now_ms() // 3000)
                                  % len(NAME_SAMPLES)]
            shown = "CALLSIGN / %s-204" % sample
            col = C_DIM
        blink = (_now_ms() // 500) % 2 == 0
        caret = "_" if (focused and blink) else ""
        text = self._clip(shown + caret, font, box.w - 24)
        self._blit(surface, box.x + 12, text, box.centery, 14, col,
                   mono=True, middle=True)
        self._name_rect = box

    def _draw_addr_box(self, surface, box):
        """The room-code / address field: focus ring, caret, and a real example.

        A blank box tells a first-time player nothing about the format they
        are meant to type, so an empty field shows a sample room code instead
        of being empty.
        """
        focused = self.selected_field == "address"
        pygame.draw.rect(surface, C_ROW_BG, box)
        pygame.draw.rect(surface, C_CYAN if focused else C_PANEL_EDGE, box,
                         2 if focused else 1)
        font = self._font(14, False, True)
        if self.address:
            shown, col = self.address, C_TEXT
        else:
            # The sample prefix rotates slowly through the in-universe pool so
            # the hint teaches that codes are not all "ACAR-...". Bucketed on
            # the clock, never per frame, or the field would flicker.
            pool = roomcode.PREFIX_POOL
            sample = pool[(_now_ms() // 3000) % len(pool)]
            shown = "ROOMCODE@TOKEN or host:port"
            col = C_DIM
        # Only the caret blinks; blinking the whole line read as a glitch.
        blink = (_now_ms() // 500) % 2 == 0
        caret = "_" if (focused and blink) else ""
        text = self._clip(shown + caret, font, box.w - 24)
        self._blit(surface, box.x + 12, text, box.centery, 14, col,
                   mono=True, middle=True)
        self._addr_rect = box

    def _draw_host_steps(self, surface, x, y):
        """The three hosting steps: accent number, bold action, dim note.

        Each part gets its own weight and the note column is aligned on the
        widest action, so the block scans as three parallel instructions
        instead of one run of monospace.
        """
        act_x = x + 26
        note_x = act_x + max(self._font(12, True, True).size(a)[0]
                             for _, a, _ in HOST_STEPS) + 18
        for i, (num, action, note) in enumerate(HOST_STEPS):
            ly = y + i * 18
            self._blit(surface, x + 2, num, ly, 12, C_ACCENT, mono=True,
                       bold=True)
            self._blit(surface, act_x, action, ly, 12, C_TEXT, mono=True,
                       bold=True)
            self._blit(surface, note_x, note, ly, 12, C_DIM, mono=True)

    def _draw_footer_note(self, surface, panel, back_r, iw):
        """Right half of the footer: the status line, or an ESC hint.

        The status used to be drawn under the BACK button, which is what made
        the panel grow past its own bottom edge on a long error; a fixed
        footer row gives it a home that cannot overflow.
        """
        font = self._font(12, False, True)
        if self.status:
            bad = ("could not" in self.status or "closed" in self.status)
            col = C_BAD if bad else C_ACCENT
            text = self._clip(self.status, font, iw - 174)
        else:
            col, text = C_DIM, "ESC  BACK"
        surf = font.render(text, True, col)
        cy = back_r.centery
        surface.blit(surf, (panel.x + panel.w - PAD - surf.get_width(),
                            cy - surf.get_height() // 2))

    def _section(self, surface, label, x, y, w):
        """Small-caps section header with a trailing rule, like the tabs.

        Returns the y for the section's first control, one GAP_LABEL below.
        """
        self._blit(surface, x, label, y, 11, C_DIM, mono=True, bold=True)
        tw = self._font(11, True, True).size(label)[0]
        pygame.draw.line(surface, C_PANEL_EDGE,
                         (x + tw + 10, y + 6), (x + w, y + 6), 1)
        return y + 8 + GAP_LABEL

    def _row(self, surface, r, label, selected):
        """A selectable row: orange when chosen, lit on hover."""
        hovered = r.collidepoint(get_scaled_mouse())
        if selected:
            bg, fg, border = (36, 27, 12), C_ACCENT, C_ACCENT
        elif hovered:
            bg, fg, border = C_ROW_HOVER, C_TEXT, C_PANEL_EDGE
        else:
            bg, fg, border = C_ROW_BG, C_DIM, (30, 44, 56)
        pygame.draw.rect(surface, bg, r)
        pygame.draw.rect(surface, border, r, 1)
        if selected:
            # Solid orange spine on the left: the browser's selection cue.
            pygame.draw.rect(surface, C_ACCENT, (r.x, r.y, 3, r.h))
        self._blit(surface, r.centerx, label, r.centery, 14, fg,
                   center=True, mono=True, bold=selected, middle=True)

    def _action(self, surface, r, label, primary):
        """HOST is the primary action, so it gets the orange treatment."""
        hovered = r.collidepoint(get_scaled_mouse())
        if primary:
            bg = (250, 189, 107) if hovered else C_ACCENT
            fg = (14, 21, 24)
        else:
            bg = C_ROW_HOVER if hovered else C_ROW_BG
            fg = C_TEXT if hovered else C_CYAN
        pygame.draw.rect(surface, bg, r)
        pygame.draw.rect(surface, C_ACCENT if primary else C_PANEL_EDGE,
                         r, 1)
        label = self._clip(label, self._font(16, True, True), r.w - 20)
        self._blit(surface, r.centerx, label, r.centery, 16, fg, center=True,
                   mono=True, bold=True, middle=True)

    def _back(self, surface, r):
        """A real bordered button, not a bare word: the old text-only BACK
        gave a 150px-wide hit target that looked like plain footer text."""
        hovered = r.collidepoint(get_scaled_mouse())
        pygame.draw.rect(surface, C_ROW_HOVER if hovered else C_ROW_BG, r)
        pygame.draw.rect(surface, C_ACCENT if hovered else C_PANEL_EDGE, r, 1)
        self._blit(surface, r.centerx, "BACK", r.centery, 13,
                   C_TEXT if hovered else C_DIM, center=True, mono=True,
                   bold=hovered, middle=True)

    def _clip(self, text, font, max_w):
        """Truncate *text* to *max_w* with an ellipsis.

        Text drawn past its control's edge does not wrap in pygame -- it just
        spills over the border, so every value that can grow (a typed
        address, a status line) is fitted before it is drawn.
        """
        text = str(text)
        if font.size(text)[0] <= max_w:
            return text
        while text and font.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."


    def _btn(self, surface, label, x, y, tag):
        r = pygame.Rect(x, y, 210, 30)
        hovered = r.collidepoint(get_scaled_mouse())
        pygame.draw.rect(surface, (40, 60, 80) if hovered else (26, 30, 38), r)
        pygame.draw.rect(surface, (90, 130, 170), r, 1)
        self._blit(surface, x + r.w // 2, label, y + 8, 18, (210, 225, 240),
                   center=True)
        self._btn_rects[tag] = r

    def _blit(self, surface, x, text, y, size, color, center=False,
              mono=False, bold=False, middle=False):
        """Draw one line of text at (x, y) -- or centred on x.

        ``mono`` switches to Consolas to match the rest of the game's UI.
        ``center`` centres horizontally on x; ``middle`` centres vertically
        on y (optical centring inside a control, instead of the old "y + half
        the font size - 7" guess, which drifted as the chip heights changed).
        Fonts are cached per (size, bold): building a pygame Font every call
        is the single most expensive thing a hand-rolled panel can do.
        """
        surf = self._font(size, bold, mono).render(str(text), True, color)
        sx = (x - surf.get_width() // 2) if center else x
        sy = (y - surf.get_height() // 2) if middle else y
        surface.blit(surf, (int(sx), int(sy)))

    @staticmethod
    def _font(size, bold=False, mono=False):
        key = (int(size), bool(bold), bool(mono))
        cache = MatchScreen._fonts
        f = cache.get(key)
        if f is None:
            try:
                if mono:
                    f = pygame.font.SysFont("Consolas", int(size), bold=bold)
                else:
                    f = pygame.font.Font(None, int(size))
            except Exception:
                f = pygame.font.Font(pygame.font.get_default_font(),
                                     int(size))
            cache[key] = f
        return f

    def _flush_and_close(self, peer):
        """Deliver everything queued, then half-close before closing.

        Closing a socket that still holds UNREAD data makes Windows abort the
        connection (RST) instead of finishing it, and an abort DISCARDS the
        announcement still sitting in the peer's receive buffer -- so the peer
        only ever learns that something went wrong, never what. Draining the
        peer's input and shutting down only the WRITE side is what makes the
        last packet actually land.

        Shared by the host-left announcement and the kick, because they have
        exactly the same requirement and getting it right in one place and not
        the other means a kicked player is told their wifi failed.
        """
        try:
            peer.wire.flush()
        except Exception:
            pass
        for _ in range(64):
            try:
                if not peer.sock.recv(65536):
                    break
            except (BlockingIOError, OSError):
                break
        try:
            peer.sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        peer.close()

    def _end_hosted_session(self, reason):
        """Tell every client this session is over, while we can still talk.

        The host IS the match: there is no host migration, so the host
        leaving ends the session for everybody, not just for itself. This is
        the packet that makes that official -- a client that merely sees the
        socket die cannot tell "host quit" from "my connection dropped", and
        the honest answer changes what you do next (rejoin vs. wait).

        Safe to call on any path: a client has no peers and no sim, so it
        does nothing, which is why teardown can call it unconditionally.
        """
        sess = self.sess
        if sess is None or self.sim is None:
            return
        if not self.peers and not self._pending_peers:
            return
        try:
            sess.send_host_left(reason)
        except Exception:
            # A dead socket is the caller's problem, not ours; this is a
            # courtesy message and must never block the teardown behind it.
            pass
        for p in list(self.peers):
            self._flush_and_close(p)

    def _end_session_remotely(self, reason):
        """The host ended the match we were playing in. Leave it.

        Not "a player left": with no host there is no simulation, no
        scoreboard and nobody to hand the match to, so the only correct
        client behaviour is to close the session down and say why.
        """
        self.leave_match()
        self.status = reason or "host ended the session"
        self._say("HOST ENDED THE SESSION", 3.0)

    def _local_carry(self):
        """Weapon ids the local player is carrying, newest information first.

        The host is authoritative, so it reads the sim directly; a client
        reads the loadout the host published in the match-state packet. Both
        feed the same two things: the HUD strip that shows which number keys
        do anything, and the note that explains a refused switch.
        """
        local_id = self.sess.local_id if self.sess is not None else 0
        sim_players = getattr(self.sim, "players", None)
        if isinstance(sim_players, dict) and local_id in sim_players:
            return list(AR.owned_weapons(sim_players[local_id]))
        carry = (self._match_state or {}).get("carry") or {}
        # Every player spawns with a pistol. The first match-state packet is
        # published at 2 Hz, so a newly joined client must not spend its
        # first half-second with no known loadout and a silent Q key.
        return list(carry.get(str(local_id)) or (AR.DEFAULT_WEAPON,))

    def _request_weapon(self, weapon_id):
        """Ask the host to equip *weapon_id*, or say why we cannot.

        The request always goes out -- the host has the final say, because
        letting a client equip whatever it names would make every weapon
        pickup on the map pointless. But the host refusing is invisible to
        the player who pressed the key, so when we already know the gun is
        not in our loadout we say so immediately instead of letting the key
        feel broken.
        """
        self._want_weapon = weapon_id
        carry = self._local_carry()
        if carry and weapon_id not in carry:
            self._say("%s NOT PICKED UP" % AR.weapon_stats(weapon_id)["name"])

    def _request_cycle(self):
        """Cycle once, and explain why nothing changes with one gun.

        A new player starts with only the pistol; rifle/SMG crates add
        weapons. Without a note, pressing Q before the first pickup looks
        exactly like a broken control. Still send the request if a client's
        last loadout packet is stale and the host just granted a pickup.
        """
        if self.waiting_for_player():
            return
        self._want_cycle = True
        carry = self._local_carry()
        if len(carry) == 1:
            self._say("PICK UP A WEAPON CRATE TO SWITCH")

    def _say(self, text, secs=TOAST_SECONDS):
        """Show a short-lived note on the match screen."""
        self._toast = text
        self._toast_left = secs

    def leave_match(self):
        """Back to the entry panel, keeping the map choice.

        (This used to call _teardown() twice and then force mode "closed",
        so a dropped host threw the player all the way back to the server
        browser instead of the panel the docstring promises.)
        """
        self._teardown()
        self.mode = "panel"
        self.status = "left the match"

    def _teardown(self):
        # Say goodbye BEFORE the sockets close. Every path that ends a
        # hosted session funnels through here, so announcing from here is
        # what guarantees a client is never simply abandoned: without it, a
        # host pressing LEAVE looked exactly like the client's own wifi
        # dropping, and the client sat in a dead arena waiting for a
        # snapshot that could not come.
        self._end_hosted_session("host ended the session")
        with self._tunnel_lock:
            self._host_token = None
            proc, self._tunnel_proc = self._tunnel_proc, None
        if proc is not None:
            tcp_tunnel.stop_process(proc)
        self._tunnel_active = False
        self._tunnel_pending = False
        for p in self.peers:
            p.close()
        self.peers = []
        for p in self._pending_peers:
            p.close()
        self._pending_peers = []
        self._match_started = False
        self._session_phase = "lobby"
        self._countdown_left = 0.0
        self._room_state_last = 0.0
        self._intro_left = 0.0
        self._intro_armed = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.srv is not None:
            try:
                self.srv.close()
            except OSError:
                pass
            self.srv = None
        self.sim = None
        self.view = None
        self.sess = None
        self._peer_addr = None
        self._client_tick = 0.0
        self._latest_snap_tick = None
        self.buf = b""
        self.paused = False
        self._pause_rects = {}
        self._wait_rects = {}
        self._lobby_rects = {}
        # Hold-Tab standings overlay. Kept as a flag set on keydown and cleared
        # on keyup rather than read from the global key state, so a Tab that was
        # already down when the window gained focus cannot leave it stuck open.
        self._scoreboard = False
        self._local_firing_prev = False
        self._remote_firing_prev = {}
        self._want_weapon = None
        self._want_cycle = False
        self._toast = ""
        self._toast_left = 0.0
        self._last_recv = None
        # Chat, respawn clocks and killer attribution are all per-session
        # state. Left in place across sessions they would surface the last
        # match's messages on the next one's opening frame.
        self._composing = False
        self._chat_input = ""
        self._chat_messages = []
        self._respawn = {}
        self._host_dead = set()
        self._last_killer = None
        self._round_end_played = False
        self._peer_chat_last = {}
        self._killfeed = []
        self.room_code = ""
        self.code_prefix = None
        self.share_host = ""
        self.share_port = 0
        self.forwarded = False
        self.forward_note = ""
        self._tunnel_pending = False
        self._tunnel_active = False
        self._hamachi_active = False
        self._network_check_pending = False

    def maps(self):
        return sorted(AR.ARENAS)

    def close(self):
        """Leave the match and drop every socket."""
        self._teardown()
        self.mode = "closed"
        self.status = ""
