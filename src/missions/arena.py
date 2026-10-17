
"""Multiplayer arena maps and the deathmatch rules.

An arena is deliberately NOT a mission. Missions carry scripted timelines
(M1's breach spawn queue, M3's kill-order map) that assume exactly one
player and no respawns; replaying them for a second human would mean
inverting the campaign's pacing. These maps are built from scratch for
free-for-all play instead.

Maps are lists of strings, one char per TILE_SIZE tile, exactly like the
mission maps, so the same collision and camera code works unchanged. That
keeps a new arena to a couple of minutes of authoring rather than a new
renderer.

Tile legend
-----------
  #  solid wall (blocks movement AND bullets)
  +  doorway (blocks movement, but bullets pass through)
  .  open floor
  1-8 spawn points
  R  health pickup
  B  armour pickup
  W  OS-12 assault-rifle pickup
  M  K-9 SMG pickup

The module holds no drawing code: it is the authoritative rules, and the
host must be able to run a whole match headlessly for tests.
"""

import math

import pygame

from core import appearance
from core.config import TILE_SIZE
from net import protocol as P

# ── Arena 1: "Yard" ──
# Symmetric, four lanes, mid cover. Sightlines are long enough that players
# meet within seconds and short enough that nobody snipes from across the map
# for an entire match. The R/B tiles are reachable and out of the open lanes,
# so a fight is about who is willing to leave cover for a resupply.
ARENA_YARD = [
    "####################",
    "#....#.......#.....#",
    "#.1..#...3...#..2..#",
    "#....#..M....#.....#",
    "#....#..R....#..W..#",
    "#.........#........#",
    "#...####..#...####.#",
    "#...#..#..#...#..#.#",
    "#.3.#..#..#...#..#4#",
    "#...#..#..#...#..#.#",
    "#...####..#...####.#",
    "#.........#........#",
    "#..B......#.....1..#",
    "#....#..W.#..M.....#",
    "#....#.......#.....#",
    "#.........#........#",
    "####################",
]

# ── Arena 2: "Crossfire" ──
# Four corner spawns, two side lanes and a contested mid band. The old
# 10x10 version fit on one screen (640x640 on a 1000x700 viewport), so
# every fight was visible at once and there was nowhere to maneuver. At
# 16x12 the camera scrolls, and both halves mirror exactly -- walls and
# pickup kinds -- so no spawn gets a better side: health/SMGs up-mid,
# armour/rifles low-mid, stub walls breaking the top/bottom sightlines.
ARENA_CROSSFIRE = [
    "################",
    "#1............2#",
    "#..............#",
    "#...##....##...#",
    "#...##....##...#",
    "#.R...M..M...R.#",
    "#.B...W..W...B.#",
    "#...##....##...#",
    "#...##....##...#",
    "#..............#",
    "#3............4#",
    "################",
]

# ── Arena 3: "Foundry" ──
# Added for team play. Two long wings either side of a central hall, joined
# by a raised spine with a single choke per side, so a side that holds both
# flanks has to commit the middle. Spawns are grouped: 1/2 on the west side,
# 3/4 on the east, 5..8 in the inner ring, which gives team modes something to
# actually contest instead of four players meeting in the middle.
ARENA_FOUNDRY = [
    "########################",
    "#....#..........#......#",
    "#.1..#...####...#..2...#",
    "#....#...#..#...#......#",
    "#....+...#..#...+......#",
    "#....#...#..#...#......#",
    "#....#...####...#......#",
    "#..R......W......M.....#",
    "#....#...####...#......#",
    "#....+...#..#...+...B..#",
    "#....#...#..#...#......#",
    "#....#...####...#......#",
    "#.3..#..........#..4...#",
    "#....#..........#......#",
    "#....#...#####...#.....#",
    "#..5.....#...#.....6...#",
    "#....#...#R..#...#.....#",
    "#....#...#...#...#.....#",
    "#..7.#...#####...#..8..#",
    "#....#....7..#....#....#",
    "#....#...#####...#.....#",
    "########################",
]

ARENAS = {
    "yard": ARENA_YARD,
    "crossfire": ARENA_CROSSFIRE,
    "foundry": ARENA_FOUNDRY,
}

# Seat capacity per arena. A map can only hold as many players as it has
# distinct, safe spawn points: Crossfire has four corner spawns, so four
# players - a fifth would round-robin onto a spawn someone already owns.
ARENA_MAX_PLAYERS = {
    "yard": 8,
    "crossfire": 4,
    "foundry": 8,
}


def max_players(map_name):
    """Seat cap for an arena, never below the 2 a match needs."""
    return max(2, int(ARENA_MAX_PLAYERS.get(map_name, 2)))


SOLID_TILES = "#"
SPAWN_TILES = "12345678"
# '+' is a doorway: solid to movement, but it opens for anything that shoots
# through it, so the Foundry's spines are cover that does not block fire.
# Treating it as solid instead would make those two tiles pointless.
PASSABLE_TILES = "+"


def map_size(map_rows):
    """(cols, rows) in tiles."""
    return (max(len(r) for r in map_rows), len(map_rows))


def build_walls(map_rows):
    """Turn solid tiles into merged collision rects.

    Adjacent solid tiles are merged. Without this a 13x13 arena becomes ~90
    separate rects that every ``Player.move`` walks twice; merging cuts it
    to a handful, and it also stops a player catching on the seams between
    individually-sized tiles.
    """
    cols, rows = map_size(map_rows)
    seen = set()
    walls = []
    for r in range(rows):
        row = map_rows[r]
        for c in range(min(cols, len(row))):
            if row[c] not in SOLID_TILES or (c, r) in seen:
                continue
            width = 0
            while c + width < min(cols, len(row)) and row[c + width] in SOLID_TILES:
                width += 1
            height = 0
            while True:
                nr = r + height
                if nr >= rows:
                    break
                seg = map_rows[nr][c:c + width]
                if len(seg) < width or any(ch not in SOLID_TILES for ch in seg):
                    break
                height += 1
            for rr in range(r, r + height):
                for cc in range(c, c + width):
                    seen.add((cc, rr))
            walls.append(pygame.Rect(c * TILE_SIZE, r * TILE_SIZE,
                                     width * TILE_SIZE, height * TILE_SIZE))
    return walls


def spawn_points(map_rows):
    """Spawn tile centres in tile order. Empty if the map has none."""
    pts = []
    for r, row in enumerate(map_rows):
        for c, ch in enumerate(row):
            if ch in SPAWN_TILES:
                pts.append((c * TILE_SIZE + TILE_SIZE // 2,
                            r * TILE_SIZE + TILE_SIZE // 2))
    return pts


# Pickup tile -> (kind, value). Weapons carry the protocol weapon id so the
# host can grant the right one without a second lookup table at the call site.
PICKUP_TILES = {
    "R": ("health", 40),
    "B": ("armour", 60),
    "W": ("weapon", P.WPN_OS12),
    "M": ("weapon", P.WPN_K9),
}


def pickups(map_rows):
    """Pickup tiles as (x, y, kind, value), in tile order.

    ``value`` is the amount for health/armour and the protocol weapon id for
    weapons, so a caller that wants to apply a pickup needs no second table.
    """
    out = []
    for r, row in enumerate(map_rows):
        for c, ch in enumerate(row):
            entry = PICKUP_TILES.get(ch)
            if entry is None:
                continue
            kind, value = entry
            out.append((c * TILE_SIZE + TILE_SIZE // 2,
                        r * TILE_SIZE + TILE_SIZE // 2,
                        kind, value))
    return out


# ── Match rules ──
# Two modes over one rule set. TEAM_DEATHMATCH is the default because a
# shared objective makes two strangers talk to each other, which is the
# whole point of running a match; FREE_FOR_ALL stays because it is the
# fastest way to test a build with a friend.
MODE_FFA = "FFA"
MODE_TDM = "TDM"
MODES = (MODE_FFA, MODE_TDM)

TEAM_IPA = 0        # the state you are fighting for
TEAM_KRAP = 1
TEAM_NONE = -1      # FFA: nobody is on a side
TEAM_NAMES = {TEAM_IPA: "IPA", TEAM_KRAP: "KRAP"}

SCORE_LIMIT = 15
# Respawn delay. This was 30 ticks (0.5 s), which is not a death at all: you
# were dimmed for half a second and then standing again, so the match had no
# dead state to react to and nothing for a countdown to count down. Three
# seconds is the shortest delay that still lets a kill read as a loss -- long
# enough to see who got you and where the enemy pressure was, short enough
# that dying does not stall a fight. One constant, if it ever wants tuning.
RESPAWN_TICKS = 60 * 3        # 3 s
SPAWN_PROTECT_TICKS = 45      # 0.75 s of protection after spawning
# A round has to end somehow. Without a clock the leader simply refuses to
# die and the match never resolves, which is the most reliable way to make a
# session feel like nothing happened.
ROUND_TICKS = 60 * 300        # 5 minutes
INTERMISSION_TICKS = 60 * 5   # 5 s between rounds
# Pickups come back, or one fight drains the map and the rest of the match
# is fought at 10 HP with nothing left to pick up.
PICKUP_RESPAWN_TICKS = 60 * 12

MAX_HP = 100
MAX_ARMOUR = 100
PICKUP_RADIUS = 26.0
# The same delay in seconds, for the only consumer that thinks in wall time:
# the client-side respawn countdown plate. Derived rather than restated so the
# countdown cannot disagree with the rule that started it.
RESPAWN_SECONDS = RESPAWN_TICKS / float(P.TICK_RATE)
# Two spawn points closer than this count as the same spot, so two teammates
# are never dropped on top of each other.
SPAWN_CLEAR_PX = 96.0

# ── Round payout ────────────────────────────────────────────────────────
# Acaribucks come from results and from nothing else. There is no
# participation drip and no playtime trickle, so a round you never contested
# pays nothing and a round you took pays for itself. PAYOUT_BASE is the single
# constant to raise if a scoreless round turns out to feel like a punishment
# rather than a lost fight.
PAYOUT_KILL = 3
PAYOUT_WIN = 25
PAYOUT_PLACE = (12, 8, 5, 3)   # 1st..4th, nothing beyond
PAYOUT_MAX = 100               # per round, whatever the arithmetic says
PAYOUT_BASE = 0


def _published_int(value, lo, hi):
    """An integer read off the host's board, coerced and bounded.

    Bounds rather than validation: a board that claims 10^9 kills is either a
    bug or a lie, and in neither case should it multiply into currency.
    """
    try:
        if isinstance(value, bool):
            return lo
        n = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _team_of(teams, player_id):
    """Which side a slot is on, per a published table. None when unknown."""
    try:
        team = int((teams or {}).get(str(player_id)))
    except (TypeError, ValueError, AttributeError):
        return None
    return team if team in (TEAM_IPA, TEAM_KRAP) else None


def _score_of(team_scores, team):
    try:
        return _published_int((team_scores or {}).get(str(team)), 0, 10 ** 6)
    except (TypeError, ValueError, AttributeError):
        return 0


def compute_payout(mode, scoreboard, winner, my_id, teams, team_scores,
                   score_limit=SCORE_LIMIT):
    """What one participant earned this round. -> (amount, kills, place, won)

    Derived from the host's authoritative numbers, but LOCALLY by each
    participant, and that split is the point. This architecture has no trusted
    server, so if the host announced "you earned 40" then a hostile host could
    send its opponents zero. Every figure here instead comes off the same
    published board that decides the score, so the only party that can set
    your earnings is the one already deciding who shot whom. Kills in
    particular are host-owned, which is what stops a client from inflating its
    own by simply never decrementing local ammo.

    Never raises. A payout that throws would take the round-end card down with
    it, and losing the card is worse than losing the money.
    """
    try:
        my_id = int(my_id)
    except (TypeError, ValueError):
        return (0, 0, 0, False)
    try:
        kills = 0
        place = 0
        found = False
        for index, row in enumerate(scoreboard or ()):
            try:
                pid = int(row[0])
            except (TypeError, ValueError, IndexError):
                continue
            if pid == my_id:
                found = True
                kills = _published_int(row[1] if len(row) > 1 else 0,
                                       0, max(0, int(score_limit)))
                place = index
                break
        if not found:
            # Seated after the round started, or never registered at all.
            return (0, 0, 0, False)

        won = False
        if mode == MODE_TDM:
            mine = _team_of(teams, my_id)
            if mine is None:
                place = 0
            else:
                theirs = TEAM_KRAP if mine == TEAM_IPA else TEAM_IPA
                my_score = _score_of(team_scores, mine)
                their_score = _score_of(team_scores, theirs)
                if winner is not None:
                    # Winner is a player id even in team play, so the side has
                    # to be looked up rather than compared directly.
                    won = _team_of(teams, winner) == mine
                else:
                    # Clock timeout: the higher side took the round.
                    won = my_score > their_score
                # Two teammates must not both be told they finished 1st, so
                # placement counts sides, not players.
                place = 0 if my_score >= their_score else 1
        else:
            won = (winner is not None and int(winner) == my_id)

        amount = PAYOUT_BASE + PAYOUT_KILL * kills
        if won:
            amount += PAYOUT_WIN
        # Placement only pays when the round was contested. Without the kills
        # guard, simply sitting in a four-player match would bank 3 per round
        # forever, which is the playtime trickle this economy is meant to
        # exclude -- and it would be the cheapest thing in the shop to farm.
        if kills > 0 and place < len(PAYOUT_PLACE):
            amount += PAYOUT_PLACE[place]
        return (min(PAYOUT_MAX, amount), kills, place, bool(won))
    except Exception:
        return (0, 0, 0, False)


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class Deathmatch(object):
    """Authoritative free-for-all rules. Host only.

    Holds the scoreboard and respawn timers and decides who is alive.
    Clients never run this -- they are told the outcome in snapshots -- so
    there is exactly one authority and no way to argue about a kill.
    """

    def __init__(self, map_rows, score_limit=SCORE_LIMIT, mode=MODE_FFA):
        self.map_rows = map_rows
        self.walls = build_walls(map_rows)
        self.spawns = spawn_points(map_rows)
        self.score_limit = int(score_limit)
        self.mode = mode if mode in MODES else MODE_FFA
        self.kills = {}          # player_id -> kills
        self.deaths = {}         # player_id -> deaths
        self.respawn = {}        # player_id -> tick at which they return
        self.spawned_at = {}     # player_id -> tick they spawned on
        self.teams = {}          # player_id -> TEAM_*
        # Slots whose player CHOSE their side. Auto-balance fills around these
        # and never moves them; see claim_team().
        self.claims = set()
        self.winner = None
        self.round = 1
        self.phase = "live"      # "live" | "intermission" | "over"
        self.phase_until = 0
        self._positions = {}     # player_id -> last known (x, y)

    def register(self, player_id):
        self.kills.setdefault(player_id, 0)
        self.deaths.setdefault(player_id, 0)

    def team_of(self, player_id):
        """The side a player is on, or TEAM_NONE in free-for-all."""
        if self.mode == MODE_FFA:
            return TEAM_NONE
        return self.teams.get(player_id, TEAM_NONE)

    def team_score(self, team):
        """Kills banked by one side."""
        return sum(k for p, k in self.kills.items()
                   if self.team_of(p) == team)

    def balance_teams(self):
        """Put the next player on the smaller side.

        Balance on JOIN rather than at match start: players arrive one at a
        time, so a fixed assignment leaves one side permanently short.
        """
        if self.mode == MODE_FFA:
            return TEAM_NONE
        n_ipa = sum(1 for p in self.teams if self.teams[p] == TEAM_IPA)
        n_krap = sum(1 for p in self.teams if self.teams[p] == TEAM_KRAP)
        return TEAM_IPA if n_ipa <= n_krap else TEAM_KRAP

    def claim_team(self, player_id, team):
        """Seat ``player_id`` on ``team`` because they asked for it. -> bool.

        This exists because auto-balance alone cannot answer the question
        "which side is my friend on". A claim is sticky: rebalance() refills the
        seats around it but never moves somebody off a side they chose. An
        auto-balance that could reassign you after you picked would just be the
        original problem with an extra click.

        Deliberately NOT capped. Refusing a claim because a side is "too full"
        produces the exact failure this feature exists to remove -- you click
        KRAP, nothing happens, and no amount of UI explains why. If friends
        stack four-deep on one side, that is them choosing it, the lobby shows
        the numbers, and the host can move someone.
        """
        if self.mode != MODE_TDM:
            return False
        # `isinstance(True, int)` is True in Python, so a bool has to be refused
        # by name or team "True" silently means TEAM_KRAP. The protocol layer
        # already rejects it; this is the same rule at the second door, because
        # rebalance() and the local host's own pick arrive without a parser.
        if isinstance(team, bool) or team not in (TEAM_IPA, TEAM_KRAP):
            return False
        try:
            player_id = int(player_id)
        except (TypeError, ValueError):
            return False
        self.teams[player_id] = team
        self.claims.add(player_id)
        return True

    def release_team(self, player_id):
        """Hand a slot back to auto-balance. Used when a player leaves."""
        self.claims.discard(player_id)

    def rebalance(self):
        """Re-deal the UNCLAIMED seats so the sides come out even.

        Host action. Claims are left exactly where they are, which is what makes
        it safe to press after two friends have already grouped: it fixes the
        other four rather than undoing the pair.
        """
        if self.mode != MODE_TDM:
            return
        counts = {TEAM_IPA: 0, TEAM_KRAP: 0}
        for pid in self.teams:
            if pid in self.claims and self.teams[pid] in counts:
                counts[self.teams[pid]] += 1
        for pid in sorted(self.teams):
            if pid in self.claims:
                continue
            target = (TEAM_IPA if counts[TEAM_IPA] <= counts[TEAM_KRAP]
                      else TEAM_KRAP)
            self.teams[pid] = target
            counts[target] += 1

    def team_counts(self):
        """{TEAM_*: players on that side}. Empty in free-for-all."""
        if self.mode != MODE_TDM:
            return {}
        return {team: sum(1 for p in self.teams if self.teams[p] == team)
                for team in (TEAM_IPA, TEAM_KRAP)}

    def alive(self, player_id, tick):
        """True unless this player is mid-respawn."""
        return tick >= self.respawn.get(player_id, 0)

    def note_position(self, player_id, pos):
        """Record where the host last simulated this player.

        Used only to choose a spawn point away from the living enemy, so a
        stale value costs nothing.
        """
        self._positions[player_id] = pos

    def spawn_position(self, player_id, tick):
        """Pick a spawn point far from every living opponent.

        Spawning into someone's crosshair is the most annoying way to die,
        so take the point furthest from any living opponent. With nobody
        alive, fall back to round-robin so players do not stack.
        """
        pts = self.spawns or [(TILE_SIZE, TILE_SIZE)]
        mine = self.team_of(player_id)
        live = [p for p in self.kills
                if p != player_id and self.alive(p, tick)]
        # Only OPPONENTS decide which spawn is safest. In team play, counting a
        # teammate made a player spawn in the open just because a friend was
        # nearby.
        threats = [p for p in live
                   if self.mode == MODE_FFA or self.team_of(p) != mine]
        # Everyone else still blocks the point outright. Without this, both
        # members of a team are handed the SAME "furthest from the enemy"
        # spawn and appear stacked on top of each other, which reads as a
        # netcode bug and is not one.
        blockers = [p for p in live if p not in threats]
        if not live:
            return pts[player_id % len(pts)]
        best, best_d = pts[0], None
        for pt in pts:
            if any(_dist(pt, self._positions.get(p, (-9999, -9999)))
                   < SPAWN_CLEAR_PX for p in blockers
                   if p in self._positions):
                # Somebody is already standing here.
                continue
            d = (min(_dist(pt, self._positions.get(p, (-9999, -9999)))
                     for p in threats) if threats else float("inf"))
            if best_d is None or d > best_d:
                best, best_d = pt, d
        if best_d is None:
            # Every point is occupied (more players than spawns). Fall back to
            # round-robin, which at least spreads them deterministically.
            return pts[player_id % len(pts)]
        return best

    def respawn_at(self, player_id, tick):
        """Place a player at a safe spawn and start their protection."""
        pos = self.spawn_position(player_id, tick)
        self.note_position(player_id, pos)
        self.spawned_at[player_id] = tick
        return pos

    def kill(self, killer_id, victim_id, tick):
        """Record a kill. Returns True if it ended the round."""
        if victim_id == killer_id:
            return False            # no suicide points
        self.register(victim_id)
        mine, theirs = self.team_of(killer_id), self.team_of(victim_id)
        # Friendly fire kills the victim but credits nobody. Without this a
        # team match pays players for shooting each other.
        if self.mode == MODE_TDM and mine != TEAM_NONE and mine == theirs:
            self.deaths[victim_id] = self.deaths.get(victim_id, 0) + 1
            self.respawn[victim_id] = tick + RESPAWN_TICKS
            return False
        self.kills[killer_id] = self.kills.get(killer_id, 0) + 1
        self.deaths[victim_id] = self.deaths.get(victim_id, 0) + 1
        self.respawn[victim_id] = tick + RESPAWN_TICKS
        if self.mode == MODE_TDM:
            if mine != TEAM_NONE and self.team_score(mine) >= self.score_limit:
                self.winner = killer_id
                return True
            return False
        if self.kills[killer_id] >= self.score_limit:
            self.winner = killer_id
            return True
        return False

    def scoreboard(self):
        """[(player_id, kills, deaths)] best first."""
        rows = [(p, k, self.deaths.get(p, 0)) for p, k in self.kills.items()]
        rows.sort(key=lambda r: (-r[1], r[2], r[0]))
        return rows

    def protection_flag(self, player_id, tick):
        """F_INVULNERABLE while freshly spawned, else 0."""
        born = self.spawned_at.get(player_id)
        if born is not None and tick - born < SPAWN_PROTECT_TICKS:
            return P.F_INVULNERABLE
        return 0

    # ── round flow ──

    def team_winner(self):
        """Which side reached the score limit, or None."""
        if self.mode != MODE_TDM:
            return None
        for team in (TEAM_IPA, TEAM_KRAP):
            if self.team_score(team) >= self.score_limit:
                return team
        return None

    def round_over(self):
        """True once somebody has won the round."""
        return self.winner is not None

    def start_intermission(self, tick):
        """Close the round and start the intermission clock."""
        self.phase = "intermission"
        self.phase_until = tick + INTERMISSION_TICKS

    def reset_round(self, tick):
        """Clear the board for the next round."""
        self.round += 1
        self.kills = {}
        self.deaths = {}
        self.respawn = {}
        self.winner = None
        self.phase = "live"
        self.phase_until = 0


# ── Weapons ─────────────────────────────────────────────────────────────
# Three guns with genuinely different jobs. The arena used to have exactly
# one: 34 damage, five rounds a second, forever. That is not a loadout, it
# is a single number, and it made every fight the same fight.
#
#   damage      per projectile
#   pellets     how many projectiles one trigger pull throws
#   cooldown    ticks between shots (12 = 5 shots/sec at 60 Hz)
#   spread      degrees of cone; grows with sustained fire (see SPREAD_*)
#   move_mul    speed multiplier while held, so a heavier gun genuinely
#               commits you to a slower approach
#   kick/shake  per-weapon camera kick + screen shake, matching the value
#               the campaign uses for the same gun in weapons.py
WEAPONS = {
    P.WPN_PISTOL: {
        "name": "PISTOL", "damage": 34, "pellets": 1, "cooldown": 12,
        "mag": 12, "reload": 45, "range": 520.0, "spread": 1.2,
        "move_mul": 1.0, "kick": 20.0, "shake": 18,
    },
    P.WPN_OS12: {
        # The story's OS-12 is the AK-pattern ASSAULT RIFLE Seby hands you
        # in M2 (entities/weapons.py: "OS 12 assault rifle", mag 25,
        # 28 damage, 8-tick full-auto). The arena used to restat it as an
        # 8-pellet, 6-shell shotgun -- so the gun wearing the OS-12 name,
        # and now the OS-12 rifle sprite, fought like a different weapon
        # entirely. These are the campaign's numbers translated to arena
        # units: full-auto cadence, 25-round mag, 90-tick mag swap, one
        # projectile, tight cone. Range is the pistol's 520 scaled by the
        # rifle's longer bullet life (24 vs 20); kick/shake are the
        # rifle's 30/28 from weapons.py.
        "name": "OS-12", "damage": 28, "pellets": 1, "cooldown": 8,
        "mag": 25, "reload": 90, "range": 624.0, "spread": 1.0,
        # Heavier than the pistol, so you give up a little speed for it.
        "move_mul": 0.90, "kick": 30.0, "shake": 28,
    },
    P.WPN_K9: {
        "name": "K-9", "damage": 17, "pellets": 1, "cooldown": 7,
        "mag": 30, "reload": 60, "range": 470.0, "spread": 2.6,
        "move_mul": 0.94, "kick": 13.0, "shake": 11,
    },
}
# The weapon everyone spawns holding. The others have to be walked over.
DEFAULT_WEAPON = P.WPN_PISTOL
WEAPON_IDS = tuple(sorted(WEAPONS))


def weapon_stats(weapon_id):
    """Stats for a weapon id, falling back to the pistol.

    A peer can put any integer in the weapon field, so this must never
    raise and never hand back None for a caller that is about to index it.
    """
    return WEAPONS.get(weapon_id, WEAPONS[DEFAULT_WEAPON])


# ── Loadout ────────────────────────────────────────────────────────────
# A player OWNS a set of weapons, and may only switch to one they are
# carrying. Without this the number keys hand out the rifle and the SMG
# to anybody at any time, which makes every weapon pickup on the map
# pointless -- if the gun is free, nobody crosses the map for it, and the
# whole reason the OS-12 is slower and shorter-ranged evaporates.
#
# The spawn pistol is always owned. Pickups ADD to the set.


def owned_weapons(st):
    """Weapon ids this player is carrying, spawn pistol first."""
    carry = st.get("carry")
    if not carry:
        return [DEFAULT_WEAPON]
    return carry


def _grant(st, weapon_id):
    """Add a weapon to the player's set, preserving a stable order."""
    carry = st.setdefault("carry", [DEFAULT_WEAPON])
    if weapon_id not in carry:
        carry.append(int(weapon_id))
    st["weapon"] = int(weapon_id)
    st["ammo"] = weapon_stats(weapon_id)["mag"]
    st["reload"] = 0
    st["cooldown"] = 0
    st["spread"] = SPREAD_MIN


# ── Recoil / spread ─────────────────────────────────────────────────────
# A weapon that fires a perfect ray forever rewards holding the trigger and
# nothing else. Spread grows while the trigger is held and recovers while it
# is not, so sustained fire is a real decision.
#
# These two rates MUST be read together, and getting it wrong is silent.
# Growth happens ONCE PER SHOT -- the slowest gun in the game is the pistol,
# one shot every FIRE_COOLDOWN (12) ticks -- while recovery runs EVERY TICK.
# So the recovery that arrives between two pistol shots is
# SPREAD_RECOVER * 12, and if that is >= SPREAD_PER_SHOT the spread returns
# to exactly zero before the next shot and can never accumulate. The whole
# mechanic then does nothing at all, invisibly.
#
# The floor is therefore set by the SLOWEST weapon in the table, not the
# fastest: 0.55 / 12 ticks = 0.0458 per tick is the break-even rate.
SPREAD_PER_SHOT = 0.55
SPREAD_MAX = 11.0
# Deliberately under the pistol's break-even (0.0458), so every weapon can
# bank spread while firing and none of them can bank it while idle.
SPREAD_RECOVER = 0.04
# Below this the cone is invisible, so clamp it away entirely rather than
# making every bullet a random ray.
SPREAD_MIN = 0.0


def _collide(x, y, dx, dy, walls):
    """Axis-separated AABB slide, matching Player.move exactly."""
    box = pygame.Rect(int(x) - 16, int(y) - 16, 32, 32)
    box.x += int(dx)
    for w in walls:
        if box.colliderect(w):
            if dx > 0:
                box.right = w.left
            elif dx < 0:
                box.left = w.right
    box.y += int(dy)
    for w in walls:
        if box.colliderect(w):
            if dy > 0:
                box.bottom = w.top
            elif dy < 0:
                box.top = w.bottom
    return (box.centerx, box.centery)


def step_move(x, y, mx, my, speed, walls, diagonal=0.707):
    """Move one tick's worth, in px, and return the resolved (x, y).

    This is THE movement function, and both ends of the wire call it: the
    host while simulating, and the client while predicting. That is the
    entire reason a predicted position and an authoritative one can agree
    to the pixel -- a second copy of this maths would drift the moment one
    of them was tuned, and every prediction would visibly rubber-band.

    ``mx``/``my`` are the -1/0/1 axes the host already validated off the
    wire. ``speed`` is px per tick.
    """
    dx = mx * speed
    dy = my * speed
    if not dx and not dy:
        return (x, y)
    # Diagonal normalisation, matching m1's 0.707 factor: otherwise moving
    # diagonally is 41% faster than moving straight.
    if dx and dy:
        dx *= diagonal
        dy *= diagonal
    return _collide(x, y, dx, dy, walls)


# ── Host-side simulation ────────────────────────────────────────────────


class ArenaSim(object):
    """The authoritative match simulation. Host only, one instance.

    Deliberately headless: no drawing, no audio, no pygame surfaces beyond
    collision rects. That is what lets a whole match be run in a unit test
    in milliseconds, which is the only practical way to be confident about
    netcode.
    """

    def __init__(self, session, map_rows, score_limit=SCORE_LIMIT,
                 player_speed=5.0, map_name="yard", mode=MODE_FFA,
                 sprint_speed=8.2):
        self.session = session
        self.map_name = map_name
        # Minted by whoever starts hosting (see MatchScreen._start_hosting) and
        # published in match_state(). Empty on a client until the first state
        # packet arrives; the round-payout log keys on it so results from one
        # session can never be credited again in another.
        self.match_id = ""
        self.rules = Deathmatch(map_rows, score_limit, mode)
        self.walls = self.rules.walls
        self.speed = float(player_speed)
        # Sprint is a different top speed, not a multiplier on the weapon's,
        # so a rifle can still be slower than a sprinting pistol.
        self.sprint_speed = float(sprint_speed)
        self.tick = 0
        self.players = {}        # id -> lightweight state dict
        self.finished = False
        # Set by _shoot; None until the first shot in the match. Reading it
        # before any shot has happened would be an AttributeError, which is
        # exactly what the tracer code did.
        self.last_shot = None
        self.shots = []
        # Authoritative this-tick happenings for the client to play back.
        self.events = []
        # Pickups carry their own respawn timer so the host decides who gets
        # one; the client only ever draws what it is told exists.
        self.pickup_items = []
        for (px, py, kind, value) in pickups(map_rows):
            self.pickup_items.append({
                "x": float(px), "y": float(py), "kind": kind,
                "value": value, "ready_at": 0,
            })
        self.round_started = 0

    # ── roster ──

    def add_player(self, player_id, nickname="", appearance_dict=None):
        """Seat a player. ``appearance_dict`` is their claimed cosmetic loadout.

        The parameter is not named ``appearance`` because that name is the
        module this method has to call into.
        """
        if player_id in self.players:
            return self.players[player_id]
        self.rules.register(player_id)
        if self.rules.mode == MODE_TDM:
            self.rules.teams[player_id] = self.rules.balance_teams()
        pos = self.rules.respawn_at(player_id, self.tick)
        st = {
            "id": player_id,
            "nick": str(nickname)[:24],
            # Normalized here, at the seat, rather than trusting whatever
            # arrived on the wire: this is the point where a claimed item id
            # becomes a colour, and the catalog is the only thing allowed to
            # decide that. A peer wearing an item it never bought is a
            # cosmetic lie the victim sees, so it collapses to the default.
            "look": appearance.normalize(appearance_dict),
            "team": self.rules.team_of(player_id),
            "x": float(pos[0]),
            "y": float(pos[1]),
            "angle": 0.0,
            "hp": MAX_HP,
            "armour": 0,
            "dead": False,
            # Weapon state lives on the HOST, never the client. A client that
            # tracked its own ammo could simply decline to decrement it.
            "weapon": DEFAULT_WEAPON,
            "carry": [DEFAULT_WEAPON],
            "ammo": weapon_stats(DEFAULT_WEAPON)["mag"],
            "reload": 0,
            "cooldown": 0,
            # Latched while the trigger is held on an empty magazine, so one
            # dry pull is one dry click rather than one per tick. See the
            # firing block in _step_player.
            "dry_latch": False,
            "spread": SPREAD_MIN,
            "muzzle": 0,          # ticks left of muzzle flash, for the view
            "sprinting": False,
            # Whether the player actually moved this tick. Drives PS_MOVING so
            # a remote client can play the walk cycle: the sprite's bob keys
            # off the state, and reporting "moving" only while sprinting meant
            # ordinary walking arrived looking like standing still.
            "moving": False,
            # The last input sequence the host acted on. Echoed to the owner
            # so their client can drop exactly what was consumed.
            "ack": P.ACK_NONE,
        }
        self.players[player_id] = st
        return st

    def remove_player(self, player_id):
        self.players.pop(player_id, None)
        self.rules.teams.pop(player_id, None)
        # A returning player is a new decision, not a carried-over one: they get
        # auto-seated again rather than landing on a side they never asked for
        # in this session.
        self.rules.release_team(player_id)
        self.rules.kills.pop(player_id, None)
        self.rules.deaths.pop(player_id, None)
        self.rules.respawn.pop(player_id, None)

    def pick_team(self, player_id, team):
        """Seat a player on a side by choice, keeping the entity in step.

        The team lives in two places -- the rules table and the per-player
        record that becomes the snapshot -- and friendly-fire suppression reads
        the latter. Setting only one would let a player pick KRAP and still be
        shot by their own team.
        """
        try:
            player_id = int(player_id)
        except (TypeError, ValueError):
            return False
        if not self.rules.claim_team(player_id, team):
            return False
        st = self.players.get(player_id)
        if st is not None:
            st["team"] = self.rules.team_of(player_id)
        return True

    def rebalance_teams(self):
        """Host action: even up the seats nobody chose."""
        self.rules.rebalance()
        for player_id, st in self.players.items():
            st["team"] = self.rules.team_of(player_id)

    # ── simulation ──

    def step(self):
        """Advance one fixed sim tick and publish the resulting snapshot.

        Order matters: read intent, move, resolve deaths, then publish.
        Snapshotting before the move would send the world one tick stale
        every time, which reads to the client as input lag.
        """
        self.tick += 1
        t = self.tick
        # Clear per-tick view feedback. last_shot is only ever written by
        # _shoot, so without this a single shot would be re-read by every
        # later tick and the camera would kick forever.
        self.last_shot = None
        self.shots = []
        self.events = []

        for pid, st in list(self.players.items()):
            # Respawn before moving, so a returning player can act on the
            # very tick they appear rather than standing still for one.
            if st["dead"] and self.rules.alive(pid, t):
                self._reset_loadout(st, t)
            if st["dead"]:
                continue
            inp = self.session.consume_input(pid)
            self._step_player(st, inp)
            self._step_pickups(st)

        self._step_round(t)
        self.session.tick = t
        self.session.world = self.snapshot_entities()
        if self.session.is_host:
            # Events ride along with every snapshot rather than on their own
            # schedule: they are small, and tying them to the snapshot means
            # one packet per 3 ticks instead of two.
            if self.events:
                self.session.send_events(self.tick, self.events)
            if (t % 3 == 0):
                self.session.broadcast()
            # Match rules (scores, clock, teams, pickup timers) change far
            # more slowly than positions, so they ride at 2 Hz. Sending them
            # with every snapshot would triple the per-player list for data
            # that is identical twenty times in a row.
            if t % max(1, P.TICK_RATE // P.MATCH_STATE_HZ) == 0:
                # Defensive: a hand-rolled session (the headless tools and the
                # smoke-test fakes) implements only the methods it needs.
                # Rules reporting is presentation, so a transport that cannot
                # carry it must not take the whole match down with it.
                send_state = getattr(self.session, "send_match_state", None)
                if send_state is not None:
                    send_state(self.match_state())

    def _reset_loadout(self, st, t):
        """Full respawn: position, health, and the spawn pistol.

        Death strips every picked-up gun back to the spawn pistol, so a kill
        actually costs the victim their loadout and map control keeps
        mattering all match.
        """
        self._place(st, t)
        st["hp"] = MAX_HP
        st["armour"] = 0
        st["carry"] = [DEFAULT_WEAPON]
        st["weapon"] = DEFAULT_WEAPON
        st["ammo"] = weapon_stats(DEFAULT_WEAPON)["mag"]
        st["reload"] = 0
        st["cooldown"] = 0
        st["spread"] = SPREAD_MIN
        st["muzzle"] = 0
        st["dry_latch"] = False

    def _place(self, st, t):
        """Move a player to a safe spawn point."""
        pos = self.rules.respawn_at(st["id"], t)
        st["x"], st["y"] = float(pos[0]), float(pos[1])
        st["dead"] = False

    def _step_round(self, t):
        """Close the round on a score limit, or on the clock."""
        rules = self.rules
        if rules.phase == "live":
            if rules.winner is not None:
                self.finished = True
                rules.start_intermission(t)
            elif t - self.round_started >= ROUND_TICKS:
                # Time out rather than stall forever. In team play the side
                # ahead takes the round; in FFA nobody wins, it just ends.
                self.finished = True
                if rules.mode == MODE_TDM:
                    a = rules.team_score(TEAM_IPA)
                    b = rules.team_score(TEAM_KRAP)
                    if a != b:
                        rules.phase = "intermission"
                        rules.phase_until = t + INTERMISSION_TICKS
                        return
                rules.start_intermission(t)
        elif rules.phase == "intermission" and t >= rules.phase_until:
            rules.reset_round(t)
            self.finished = False
            self.round_started = t
            for st in self.players.values():
                self._reset_loadout(st, t)

    def _step_player(self, st, inp):
        """Advance one player one tick: weapons, movement, firing."""
        pid = st["id"]
        # The ack travels back so the owner's client knows exactly which of
        # its inputs the host has folded in. Everything after this point is
        # decided by the host, never the client.
        if inp:
            seq = inp.get("q")
            if seq is not None:
                st["ack"] = int(seq) & 0xFFFFFFFF

        # Spread recovers whether or not the trigger is held, so tapping is
        # accurate and holding is not.
        st["spread"] = max(SPREAD_MIN, st["spread"] - SPREAD_RECOVER)
        if st["muzzle"] > 0:
            st["muzzle"] -= 1

        stats = weapon_stats(st["weapon"])

        # ── weapon switch ──
        # Applied BEFORE the firing decision, so pressing 2 equips the OS-12
        # and that same tick fires it. Doing it after made the first press
        # fire the old gun and only equip the new one, which reads as the key
        # being ignored.
        #
        # Ownership is enforced here, on the host: a client that requests a
        # gun it has not picked up is refused, so pickups keep mattering.
        if inp:
            want = inp.get("w")
            if want is not None and want != st["weapon"] \
                    and want in owned_weapons(st):
                _grant(st, want)
                stats = weapon_stats(st["weapon"])
            elif inp.get("wcycle"):
                carry = owned_weapons(st)
                if len(carry) > 1:
                    try:
                        nxt = carry[(carry.index(st["weapon"]) + 1) % len(carry)]
                    except ValueError:
                        nxt = carry[0]
                    _grant(st, nxt)
                    stats = weapon_stats(st["weapon"])

        # ── reload ──
        # A reload freezes the fire cooldown rather than draining it. A
        # reload is a committed action, and letting the cooldown tick down
        # underneath it meant a held trigger fired again the instant the
        # magazine came back -- so a full reload ate the next round too.
        if st["reload"] > 0:
            st["reload"] -= 1
            if st["reload"] == 0:
                st["ammo"] = weapon_stats(st["weapon"])["mag"]
        elif inp and ((inp.get("b", 0) or 0) & P.F_RELOAD) \
                and st["ammo"] < stats["mag"]:
            st["reload"] = stats["reload"]

        if st["reload"] <= 0 and st["cooldown"] > 0:
            st["cooldown"] -= 1

        # ── movement ──
        buttons = (inp.get("b", 0) or 0) if inp else 0
        mx = inp.get("mx", 0) if inp else 0
        my = inp.get("my", 0) if inp else 0
        # Any input on either movement axis counts as walking, sprint included.
        # This is what the client's walk cycle reads; see the "moving" field.
        st["moving"] = bool(mx or my)
        # Sprinting is faster but slower to aim and blocks firing, so it is
        # a real commitment rather than a free movement upgrade.
        st["sprinting"] = bool(buttons & P.F_SPRINTING) and bool(mx or my) \
            and st["reload"] <= 0
        speed = (self.sprint_speed if st["sprinting"]
                 else self.speed * stats["move_mul"])
        angle = inp.get("a") if inp else None
        if angle is not None:
            st["angle"] = angle % 360.0
        st["x"], st["y"] = step_move(st["x"], st["y"], mx, my, speed,
                                     self.walls)
        self.rules.note_position(pid, (st["x"], st["y"]))

        # ── firing ──
        if not (buttons & P.F_FIRING):
            # Releasing the trigger rearms the dry click, so the next pull on
            # an empty magazine clicks again.
            st["dry_latch"] = False
            return
        if st["sprinting"]:
            return
        if st["ammo"] <= 0:
            # The trigger went nowhere. Latched so a HELD trigger emits one
            # click per dry magazine rather than one per tick: 45 clicks in a
            # second does not read as a dry trigger pull, it reads as a broken
            # gun, and it would put the same sound on every other player's
            # screen because the event is broadcast.
            if st.get("dry_latch"):
                return
            st["dry_latch"] = True
            # Stated as an event rather than left for the client to infer: ammo
            # is only published twice a second, so a client could not tell
            # "I fired and it went nowhere" from "my last packet was stale".
            self.events.append([P.EV_EMPTY, st["id"], 0, 0,
                                st["x"], st["y"]])
            if st["reload"] <= 0:
                st["reload"] = weapon_stats(st["weapon"])["reload"]
            return
        if st["reload"] > 0:
            return
        if st["cooldown"] > 0:
            return
        self._shoot(st, weapon_stats(st["weapon"]))

    def _step_pickups(self, st):
        """Take any pickup the player is standing on."""
        if st["dead"]:
            return
        for pk in self.pickup_items:
            if pk["ready_at"] > self.tick:
                continue
            if _dist((st["x"], st["y"]), (pk["x"], pk["y"])) > PICKUP_RADIUS:
                continue
            kind, value = pk["kind"], pk["value"]
            if kind == "health":
                if st["hp"] >= MAX_HP:
                    continue          # full: leave it for someone who needs it
                st["hp"] = min(MAX_HP, st["hp"] + value)
            elif kind == "armour":
                if st["armour"] >= MAX_ARMOUR:
                    continue
                st["armour"] = min(MAX_ARMOUR, st["armour"] + value)
            else:
                # Weapon: add it to the set and equip it. Walking over a gun
                # you already carry still refills it, so it is never a
                # downgrade -- unless you own every gun, in which case there
                # is nothing left to gain and the crate stays for someone
                # who needs it.
                if set(owned_weapons(st)) >= set(WEAPON_IDS):
                    continue
                _grant(st, value)
            pk["ready_at"] = self.tick + PICKUP_RESPAWN_TICKS
            self.events.append([P.EV_PICKUP, st["id"], value, 0,
                                pk["x"], pk["y"]])

    def _shoot(self, st, stats):
        """Trace this weapon's pellets and apply any damage.

        Every pellet is resolved independently against the same wall list, so
        a multi-pellet weapon can hit two different players with one pull.
        No arena gun throws more than one pellet today, but the mechanism
        stays so a shotgun can be added without touching hit resolution.
        """
        st["ammo"] -= 1
        st["cooldown"] = stats["cooldown"]
        st["muzzle"] = 4
        # A round is in the chamber now, so the next dry pull may click.
        st["dry_latch"] = False
        # Spread grows per SHOT, not per pellet, or a multi-pellet weapon
        # would be uncontrollable on its first pull and useless ever after.
        st["spread"] = min(SPREAD_MAX, st["spread"] + SPREAD_PER_SHOT)
        if st["ammo"] <= 0:
            st["reload"] = stats["reload"]

        targets = []
        for other in self.players.values():
            if other["id"] == st["id"] or other["dead"]:
                continue
            targets.append((other["id"], other["x"], other["y"]))

        # Team rules: a teammate is not a target. Firing through them is
        # still possible (the ray stops at the nearest body), but no damage
        # is applied -- otherwise team play is a shooting gallery at your own
        # side and every corridor is a dilemma.
        my_team = st.get("team", TEAM_NONE)
        friendly = self.rules.mode == MODE_TDM and my_team != TEAM_NONE

        # Farthest pellet impact, so a multi-pellet tracer reads as one blast.
        best_dist = 0.0
        hit_points = {}
        cone = stats["spread"] + st["spread"]
        pellets = max(1, int(stats["pellets"]))
        for i in range(pellets):
            angle = st["angle"]
            if cone > 0.0:
                # Deterministic fan rather than a random ray: the spread is a
                # cone the host owns, so keeping it reproducible means tests
                # can assert an exact hit pattern. Pellets alternate either
                # side, so the pattern stays centred on the crosshair instead
                # of drifting in one direction across the magazine.
                t = (i / float(pellets - 1)) * 2.0 - 1.0 if pellets > 1 else 0.0
                angle += t * cone * 0.5
            rad = math.radians(angle)
            kind, tid, dist = hitscan(st["x"], st["y"], angle % 360.0,
                                      self.walls, targets,
                                      range_px=stats["range"])
            if dist > best_dist:
                best_dist = dist
            if kind != "player":
                continue
            victim = self.players.get(tid)
            if victim is None or victim["dead"]:
                continue
            if friendly and victim.get("team") == my_team:
                # Friendly fire blocks the ray (nearest body wins) but deals
                # no damage.
                continue
            ix = st["x"] + math.cos(rad) * dist
            iy = st["y"] + math.sin(rad) * dist
            hit_points[tid] = (ix, iy,
                               hit_points.get(tid, (0, 0, 0))[2] + stats["damage"])

        # One hit event per victim, carrying the damage that actually landed
        # across all pellets -- so a multi-pellet blast shows one total rather
        # than one floater per pellet.
        any_hit = False
        for tid, (ix, iy, dmg) in hit_points.items():
            any_hit = True
            self.damage(tid, dmg, killer_id=st["id"])
            if not self.players.get(tid, {}).get("dead"):
                self.events.append([P.EV_HIT, st["id"], tid, dmg, ix, iy])

        # View-only: tells the renderer a shot happened, and by whom. Must
        # never influence the authoritative outcome, or a missing visual
        # would change who won the fight. The shooter id is what lets the
        # local view recoil on its own gunfire without shaking the screen
        # every time a remote player pulls the trigger.
        shot = (st["x"], st["y"], st["angle"], best_dist or stats["range"],
                st["id"], any_hit)
        self.last_shot = shot
        self.shots.append(shot)

    # ── damage ──

    def damage(self, victim_id, amount, killer_id=None):
        """Apply damage. Returns True if this killed them.

        Armour soaks two thirds of incoming damage while it lasts, which is
        what makes the armour pickups worth leaving cover for: they convert a
        60-damage burst that would kill you into 20.
        """
        st = self.players.get(victim_id)
        if st is None or st["dead"]:
            return False
        # Spawn protection is the only thing between a respawn and an
        # instant second death.
        if self.rules.protection_flag(victim_id, self.tick):
            return False
        amount = int(amount)
        armour = st.get("armour", 0)
        if armour > 0:
            soaked = amount - amount // 3
            st["armour"] = max(0, armour - soaked)
            amount -= soaked
        st["hp"] -= amount
        if st["hp"] > 0:
            return False
        st["hp"] = 0
        st["dead"] = True
        if killer_id is not None and killer_id != victim_id:
            self.events.append([P.EV_KILL, killer_id, victim_id,
                                st.get("weapon", DEFAULT_WEAPON),
                                st["x"], st["y"]])
            if self.rules.kill(killer_id, victim_id, self.tick):
                self.finished = True
        else:
            # No killer (a hazard): still honour the respawn timer.
            self.rules.respawn[victim_id] = self.tick + RESPAWN_TICKS
        return True

    # ── output ──

    def snapshot_entities(self):
        """Wire entities for every player, dead ones included.

        Dead players must stay in the snapshot so the client can play the
        death and then the respawn. Dropping them would make a corpse
        simply blink out of existence.
        """
        ents = []
        for st in self.players.values():
            pid = st["id"]
            flags = self.rules.protection_flag(pid, self.tick)
            # F_FIRING drives the muzzle flash on remote players, so a
            # client can see that someone is shooting without the host
            # having to send bullet positions.
            if st.get("muzzle", 0) > 0:
                flags |= P.F_FIRING
            if st.get("reload", 0) > 0:
                flags |= P.F_RELOADING
            ents.append(P.make_entity(
                pid,
                P.ENT_PLAYER if pid == self.session.local_id else P.ENT_REMOTE,
                st["x"], st["y"], st["angle"], max(0, st["hp"]),
                (P.PS_DEAD if st["dead"] else
                 P.PS_RELOADING if st.get("reload", 0) > 0 else
                 P.PS_SHOOTING if st.get("muzzle", 0) > 0 else
                 P.PS_MOVING if st.get("moving") else P.PS_IDLE),
                st.get("weapon", DEFAULT_WEAPON), flags,
                # The ack is per-player, so a client can reconcile its own
                # position without trusting anybody else's.
                st.get("ack", P.ACK_NONE)))
        return ents

    def scoreboard(self):
        return self.rules.scoreboard()

    def pickup_state(self):
        """Pickups as [(x, y, kind, value, ready_at)] for the client's view.

        Sent with the snapshot so a joiner sees the same respawn timers the
        host is running, instead of drawing a health pack that has already
        been taken.
        """
        return [(pk["x"], pk["y"], pk["kind"], pk["value"], pk["ready_at"])
                for pk in self.pickup_items]

    def respawn_state(self):
        """Seconds left on each dead player's respawn timer, keyed by slot.

        Published so a client can run its own countdown between these 2 Hz
        packets instead of freezing between them. Only players who are
        actually waiting appear: a player whose timer has expired is about to
        be back and must not be drawn as "respawning in 0".
        """
        out = {}
        for pid, at in self.rules.respawn.items():
            left = (at - self.tick) / float(P.TICK_RATE)
            if left > 0.0:
                out[str(pid)] = left
        return out

    def match_state(self):
        """Everything the client cannot infer from entities alone.

        Scoreboard, mode, clock and phase ride in one small packet so the HUD
        never has to guess at a rule the host owns.
        """
        rules = self.rules
        remaining = max(0, ROUND_TICKS - (self.tick - self.round_started))
        return {
            "mode": rules.mode,
            "phase": rules.phase,
            "round": rules.round,
            "clock": remaining,
            "winner": rules.winner,
            # Included HERE rather than only in the host's caller: this is
            # the packet's only source of truth for scores, and building it in
            # two places meant a client-driven path sent a board of None.
            "scoreboard": rules.scoreboard(),
            "teams": {str(p): rules.team_of(p) for p in rules.teams},
            "team_scores": {str(TEAM_IPA): rules.team_score(TEAM_IPA),
                            str(TEAM_KRAP): rules.team_score(TEAM_KRAP)},
            "pickups": self.pickup_state(),
            # What each player is carrying, so a client can grey out the
            # weapon it has not picked up instead of pressing a key that
            # the host is going to refuse.
            "carry": {str(p): list(owned_weapons(st))
                      for p, st in self.players.items()},
            "ammo": {str(p): st.get("ammo", 0)
                     for p, st in self.players.items()},
            # First-to target for the KRAP-terminal scoreboard strip. The
            # client cannot infer it from kills alone, and the host owns it.
            "score_limit": rules.score_limit,
            # Who each slot IS. Entities carry a slot id and nothing else, so
            # without this the kill feed, the name tags and the scoreboard all
            # have to invent a label -- which is exactly how eight anonymous
            # colour swatches ended up being the whole player list.
            "names": {str(pid): (st.get("nick") or P.default_name(pid))
                      for pid, st in self.players.items()},
            # Who each slot LOOKS like. Rides with names because it answers the
            # same question the HUD asks every time it draws a sprite, and on
            # the same 2 Hz packet -- cosmetics cannot change mid-round, so
            # putting them on the 20 Hz snapshot would be dead weight.
            "looks": {str(pid): (st.get("look") or appearance.DEFAULT)
                      for pid, st in self.players.items()},
            # Which session this state belongs to, so a client's payout log can
            # tell a new match from a host restart of an old one.
            "match_id": self.match_id,
            # Dead players' remaining respawn time, so death has a beat with
            # something in it instead of the sprite just going dim.
            "respawn": self.respawn_state(),
            # Who is down RIGHT NOW, independent of their countdown. The
            # respawn table above cannot carry this: it lists only slots whose
            # timer still has seconds on it, so a player killed by a hazard
            # that grants no wait, or one whose timer expired a tick before the
            # snapshot caught their PS_DEAD bit, is simply absent -- and a body
            # keyed on absence disappears from the floor while the corpse is
            # still plainly visible to everyone else.
            # get() rather than st["dead"] for the same reason the rows above
            # use it: a seat that has not been through add_player yet carries
            # no death flag, and inventing one must never take the whole rules
            # packet -- and with it every corpse on the board -- down.
            "dead": [pid for pid, st in self.players.items()
                     if st.get("dead")],
        }


# ── Client-side prediction ──────────────────────────────────────────────
# Before this, the client drew its own character from the same 100 ms-behind
# interpolation buffer as everybody else. So your own movement was always a
# frame-and-a-half late, the crosshair aimed from where you USED to be, and
# on any real connection the whole thing felt like wading through syrup.
#
# The fix is the standard one: apply your own input locally the instant you
# send it, keep the unacknowledged inputs, and when the host's authoritative
# position arrives, snap to it and replay everything after the ack. Under
# normal latency the replay reproduces your own prediction exactly, so the
# correction is zero and nothing visibly moves.


class Predictor(object):
    """Client-side prediction and reconciliation for the local player.

    Headless and pygame-free apart from ``step_move``'s rect maths, so a
    whole prediction/replay cycle can be tested without a display -- which is
    the only way to pin down the failure mode where it permanently
    rubber-bands.
    """

    # Inputs held for replay. One second is far more than any plausible
    # round trip; the cap is a safety net against a client that stops
    # receiving snapshots entirely.
    MAX_PENDING = 64

    def __init__(self, walls, speed=5.0, sprint_speed=8.2):
        self.walls = walls
        self.speed = float(speed)
        self.sprint_speed = float(sprint_speed)
        self.x = 0.0
        self.y = 0.0
        self.angle = 0.0
        # Set once the first authoritative snapshot arrives. Before that there
        # is nothing to predict FROM, and guessing an origin is exactly how a
        # joiner ends up stuck inside geometry.
        self.seeded = False
        self.dead = False
        # (seq, mx, my, angle, sprinting) in send order.
        self.pending = []
        # Last correction, in px. Exposed so a dev overlay can show whether
        # prediction is working; a large persistent value means the two
        # sides disagree, which is a bug rather than just lag.
        self.error = 0.0

    def _speed_for(self, sprinting, move_mul):
        if self.dead:
            return 0.0
        if sprinting:
            return self.sprint_speed
        return self.speed * move_mul

    def apply(self, mx, my, angle, sprinting, move_mul=1.0):
        """Advance the predicted position one tick. Does not record history."""
        if angle is not None:
            self.angle = angle % 360.0
        self.x, self.y = step_move(self.x, self.y, mx, my,
                                    self._speed_for(sprinting, move_mul),
                                    self.walls)

    def push(self, seq, mx, my, angle, sprinting=False, move_mul=1.0):
        """Record an input as sent and predict it immediately."""
        self.pending.append((seq, mx, my, angle, bool(sprinting), move_mul))
        if len(self.pending) > self.MAX_PENDING:
            del self.pending[:len(self.pending) - self.MAX_PENDING]
        self.apply(mx, my, angle, sprinting, move_mul)

    def reconcile(self, ax, ay, aangle, ack=P.ACK_NONE, dead=False):
        """Adopt the host's state and replay everything it has not seen.

        Returns the size of the correction in px. A large one that persists
        across snapshots means prediction has diverged from the host, which
        is a bug -- but it is corrected either way, never accumulated.
        """
        ax, ay = float(ax), float(ay)
        if not self.seeded:
            self.x, self.y, self.angle = ax, ay, float(aangle) % 360.0
            self.seeded = True
            self.dead = dead
            self.pending = []
            self.error = 0.0
            return 0.0
        ex, ey = ax - self.x, ay - self.y
        self.error = math.hypot(ex, ey)
        self.x, self.y, self.dead = ax, ay, dead
        self.angle = float(aangle) % 360.0
        if ack != P.ACK_NONE:
            self.pending = [p for p in self.pending if _seq_after(p[0], ack)]
        for (_seq, mx, my, angle, sprinting, move_mul) in self.pending:
            self.apply(mx, my, angle, sprinting, move_mul)
        return self.error


def _seq_after(seq, ack):
    """True if ``seq`` is strictly newer than ``ack``.

    Sequences are 32-bit and wrap, so a plain ``>`` breaks exactly once per
    wrap and then every pending input looks acked forever -- the player
    freezes and stays frozen. Comparing modulo half the range is the
    standard wrap-safe form.
    """
    return 0 < ((seq - ack) & 0xFFFFFFFF) < 0x80000000


def entity_ack(ent):
    """The ack from an entity tuple, or ACK_NONE if it is absent.

    Snapshots from a peer on an older build are nine fields wide and carry no
    ack at all, and parse_snapshot deliberately accepts them. Reading ent[9]
    directly would crash the render loop on exactly the packet we went out of
    our way to keep working.
    """
    return ent[9] if len(ent) > 9 else P.ACK_NONE


def _aim(dx, dy):
    return math.degrees(math.atan2(dy, dx)) % 360.0


# ── Hitscan ────────────────────────────────────────────────────────────
# Back-compat aliases for the single-weapon arena. They now READ the pistol
# out of WEAPONS rather than restating it, because two copies of the same
# number is exactly how a balance change ends up applied to one weapon and
# not the other. Tests and headless tools that still say WEAPON_DAMAGE keep
# working and keep meaning "the pistol".
WEAPON_DAMAGE = WEAPONS[DEFAULT_WEAPON]["damage"]
WEAPON_RANGE = WEAPONS[DEFAULT_WEAPON]["range"]
FIRE_COOLDOWN_TICKS = WEAPONS[DEFAULT_WEAPON]["cooldown"]
MAG_SIZE = WEAPONS[DEFAULT_WEAPON]["mag"]
RELOAD_TICKS = WEAPONS[DEFAULT_WEAPON]["reload"]
PLAYER_RADIUS = 16.0


def _ray_rect(x, y, dx, dy, rect):
    """Distance along the ray to the rect, or None if it misses.

    Slab method, written out rather than reusing weapons._wall_blocks_line
    because we need the DISTANCE to the nearest wall, not merely whether one
    blocks the line. With only a boolean you cannot tell "the wall stopped
    this shot at my feet" from "the wall is 400 px away", so a player
    standing beside a wall would be shot through it by anything aimed
    slightly past it.
    """
    inv_x = (1.0 / dx) if dx else float("inf")
    inv_y = (1.0 / dy) if dy else float("inf")
    t1 = (rect.left - x) * inv_x
    t2 = (rect.right - x) * inv_x
    t3 = (rect.top - y) * inv_y
    t4 = (rect.bottom - y) * inv_y
    tmin = max(min(t1, t2), min(t3, t4))
    tmax = min(max(t1, t2), max(t3, t4))
    if tmax < 0.0 or tmin > tmax:
        return None
    # tmin < 0 means the ray starts inside the wall. Treat that as an
    # immediate block so nobody can shoot from inside geometry.
    return tmin if tmin >= 0.0 else 0.0


def _ray_circle(x, y, dx, dy, cx, cy, r):
    """Distance along the ray to a circle, or None if it misses."""
    mx, my = cx - x, cy - y
    proj = mx * dx + my * dy
    if proj < 0.0:
        return None
    perp2 = (mx * mx + my * my) - proj * proj
    r2 = r * r
    if perp2 > r2:
        return None
    return proj - math.sqrt(r2 - perp2)


def hitscan(x, y, angle_deg, walls, targets, range_px=WEAPON_RANGE):
    """Trace a shot. Returns (kind, target_id, distance).

    ``targets`` is an iterable of (id, cx, cy). The nearest thing along the
    ray wins -- walls included -- so you cannot shoot through cover. That is
    the single most important rule in a shooter: if it is wrong, the game is
    not a shooter.
    """
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    best_t = float(range_px)
    hit = ("none", None, best_t)
    for w in walls:
        t = _ray_rect(x, y, dx, dy, w)
        if t is not None and t < best_t:
            best_t, hit = t, ("wall", None, t)
    for (tid, cx, cy) in targets:
        t = _ray_circle(x, y, dx, dy, cx, cy, PLAYER_RADIUS)
        if t is not None and t < best_t:
            best_t, hit = t, ("player", tid, t)
    return hit
