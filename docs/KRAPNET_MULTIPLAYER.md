# KRAPNET — self-hosted multiplayer (host a lobby, share an address)

Two different things live here and they do not touch each other:

- **ARENA MATCH** (`src/ui/match_screen.py`) is a real, playable
  host-authoritative multiplayer match: 2–8 players, team or free-for-all,
  three maps, in-match chat, and a public tunnel path so strangers can join.
  Start at [§2](#2-arena-match-the-actual-game).
- **The lobby** (`src/net/client.py` + `tools/mp_server.py`) is a server list
  and a global chat channel. It is real, but it carries no gameplay. Start at
  [§4](#4-the-lobby-relay-server-list--global-chat).

They are separate sockets on separate ports, on purpose — see
[the ports table](#ports-and-why-the-match-is-not-on-27015).

## 0. The 30-second version

**You (host)** run `dist\Host Acaristan Server.exe`. It prints one address.

**They (friend)** run `dist\Join Acaristan.exe`, paste that address, and
type. That is the whole procedure — no game install, no Python, no router
setup, no accounts.

```
  YOU                                    THEM
  ----                                    ----
  Host Acaristan Server.exe       -->     Join Acaristan.exe
  prints  1.2.3.4:27015                  paste it, press Enter
  window stays open                      type to chat
```

Build the joiner EXE with `tools\build_join_exe.bat`. If your friend already
has Python and the repo, `tools\join_lobby.bat` does the same thing.

If they *do* own the game, Multiplayer → CONNECT takes the same address.

**To actually play together**, both of you run the game:
MULTIPLAYER → ARENA MATCH. See [§2](#2-arena-match-the-actual-game).

## 1. Self-hosting (the "give your friends the address" flow)

One player hosts. Everyone else connects straight to them. No central
server, no account, no master.

**Build the EXE once:**

```bat
tools\build_host_exe.bat
```

That produces `dist\Host Acaristan Server.exe` (~9 MB, no Python needed on
the host's machine). Console mode is deliberate — the host has to be able
to *read* the address and any firewall instructions.

**Or run it from source:**

```bash
python tools/mp_host.py                       # defaults
python tools/mp_host.py --name "Biribel's Server"
python tools/mp_host.py --check               # diagnose, host nothing
```

It prints a big shareable address, then keeps running. Friends paste that
address into the **CONNECT** box on the multiplayer screen. It also prints
a live count of who's connected, every couple of seconds.

### Why your friends still might not connect

This is the part nobody can code around. Reachability depends entirely on
your router:

| Situation | What happens |
|---|---|
| **Same local network** | Usually works with the host's LAN IP (Wi-Fi or Ethernet); firewall rules or Wi-Fi client isolation can still block it. |
| UPnP or NAT-PMP enabled | Port opens automatically, you get a **public** address |
| UPnP disabled (very common) | Tool says so and tells you exactly which port to forward by hand |
| Windows Firewall blocking | Listening still works locally; inbound from outside is dropped. Allow the EXE through. |
| **Double NAT** (ISP modem + your own router) | Cannot be fixed in software. Use `--tunnel` |
| **Carrier CGNAT** (some fibre/mobile ISPs) | Same — no public IP at all. Use `--tunnel` |

The tool never pretends. If it can't forward the port, it prints the LAN
address and labels it LAN-only, because sharing a public address that
can't reach you is worse than sharing nothing.

### `--tunnel`: skip the router entirely

Port forwarding lives in your router's admin page and needs your login
password. Nothing a program can do will reach it. A tunnel sidesteps that
by borrowing someone else's reachable machine:

```bat
Host Acaristan Server.exe --tunnel
```

or from source:

```bash
python tools/mp_host.py --tunnel
```

It uses bundled [bore](https://github.com/ekzhang/bore) first, then a
configured ngrok on PATH. Bore exposes a real `bore.pub:PORT` TCP address;
friends paste it into CONNECT (lobby) or JOIN MATCH (arena). Joiners do not
need a tunnel binary or Hamachi installer. The host must keep the program open.

Windows x64 builds fetch and verify bore v0.6.0 automatically via
`python tools/download_bore.py`. Its executable is packaged from
`assets/bin/bore.exe`; its MIT licence is in `assets/bin/BORE-LICENSE.txt`.
For a source run, run that download script first on Windows. On Linux/macOS,
install the appropriate official bore release on PATH.

**Limitations:** bore.pub is a third-party free relay, not your own hosting
infrastructure. Traffic is unencrypted and the relay has no uptime or latency
guarantee. The address changes on restart, and outbound TCP port 7835 must be
reachable. Public exposure lasts until hosting stops. Do not send secrets over
the game's chat. Use this for friends/testing, not as a promised production
service. For a release, consider a managed or self-hosted relay and review the
protocol's authentication, encryption, and abuse handling.

If bore cannot connect, the game reports LAN-only; use a forwarded port or
have every player join the same Tailscale/ZeroTier/Hamachi network. Ngrok is
optional and requires account setup; its free TCP endpoint may require card
verification. Cloudflare quick tunnels are deliberately not used: their HTTP
address is not directly connectable by this game's plain-TCP joiner.

```bash
bore local 27015 --to bore.pub   # lobby; use 27017 for the arena
ngrok tcp 27015                 # optional, configured account required
```

## 2. ARENA MATCH (the actual game)

This is the part that is a game rather than a list of names.

**Host:** MULTIPLAYER → ARENA MATCH → HOST MATCH.

The match opens as a **frozen lobby**. Your character stands still, the round
does not tick, and a card shows the room code. Set your **CALLSIGN** on the
entry panel first — that is the name that goes over your head and into every
kill feed while somebody is trying to shoot you. It is remembered between
sessions, and it defaults to a minted handle rather than an empty box, because
an arena full of blank names is the thing this system exists to end.

**Friend:** MULTIPLAYER → ARENA MATCH → JOIN MATCH, then paste the room code
(or `host:port`).

**The round does NOT begin when someone joins.** Nobody starts until the host
presses **START MATCH**, which then runs a synchronized 3 / 2 / 1 / GO for
everyone. There is no bot: hosting alone leaves you alone, and the START
button stays disabled until a second player is actually seated.

While frozen, the roster shows every player's name, and **Enter opens the
match chat** — the people you are about to fight are the ones you can talk to.

### Playing across different networks

#### Public internet hosting (the default path)

When no virtual LAN adapter is active, the host tries, in order:

1. **A virtual LAN** (Hamachi, Tailscale, ZeroTier) — if an adapter is
   present its IP is used for the invite, because it already provides a
   private network and needs no port forwarding. Every player needs the
   client installed. Hamachi's free network limit is five members.
2. **Router port forwarding** (UPnP / NAT-PMP) — the no-provider option.
   Also reports your public IP so the code is shareable from anywhere.
3. **A public TCP tunnel** — bundled bore first, configured ngrok second.
   Bore needs no account and no joiner-side adapter; relay limits still apply.

The waiting card says which one you got, and the code only appears once the
address has settled — so a host is never told to read out an address that is
about to be replaced.

**If you end up LAN-only, inspect the failure message.** Bore may be missing,
the public relay may be unavailable, or your network may block its outbound
connection. Reinstall a packaged build if the binary is missing. Source users
on Windows can run `python tools/download_bore.py`. A mesh VPN or manually
forwarded port remains an alternative; no installer is bundled for those VPNs.

#### Hamachi (no router setup)

Hamachi is the simplest fit when everyone is willing to use a virtual LAN:
all players [install Hamachi](https://vpn.net/), join the same Hamachi
network, then the host selects HOST MATCH. The game detects the host's
Hamachi virtual IPv4 (`25.x.x.x`) and uses that address in the invite instead
of the ordinary Wi-Fi/Ethernet IP. The host listener binds all interfaces,
including Hamachi.

If Windows Firewall asks, allow the game on the Hamachi/virtual network. If it
was blocked previously, add/enable an inbound TCP rule for the game on the
Hamachi adapter. Keep both Hamachi clients online and in the same network.

### Ports, and why the match is not on 27015

| Service | Default port |
|---|---|
| Lobby master (`tools/mp_host.py`, `tools/mp_server.py`) | TCP 27015 |
| LAN discovery beacon | UDP 27016 |
| **Arena match** (`ui/match_screen.py`) | **TCP 27017** |

They were both 27015 once. The game keeps its lobby relay client running
while a match is hosted, and that client retries a fixed local address
forever — so the instant a player hosted, the relay's own reconnect was
accepted by the match listener as a **player**. That is the "useless bot"
that appeared on an empty lobby and started the round: a peer that never
sent input, because it was really the chat connection. Two independent
fixes now prevent it:

1. **A separate port.** The match never listens where the lobby lives.
2. **A join handshake.** An accepted socket is only a *candidate*. It is
   seated, assigned a slot and allowed into the room only after it sends
   `joinmatch` — the first packet a real match client sends, and the same
   packet that carries its callsign. Anything else that reaches the port (the
   relay's `hello`/`query`, a browser pre-connect, a port scan) is closed
   immediately, and a candidate that stays silent is dropped after a few
   seconds.

The room code carries whichever port the host actually bound, so players
never type these numbers.

The code's prefix is flavour, not data. A host is minted one of the
in-universe flavours at random (`src/net/roomcode.py::PREFIX_POOL` —
`ACAR`, `KRAP`, `KRPN`, `IPA`, `MAG`, `R12`, `MARU`, `BIRI`, `VOLK`), keeps
that flavour for the whole session, and `decode()` accepts every one of
them, so a code a friend copied from an older build still opens.

**Controls:** WASD move · mouse aim · hold left click to fire · R reload ·
1/2/3 pick a weapon · Q cycles · Esc opens match options · **Enter opens
match chat** · Tab is nothing in a match.

### What's implemented

- Host-authoritative simulation at 60 Hz, MP-only fixed timestep
- 20 Hz snapshots, client-side interpolation (100 ms behind, smooth),
  client-side prediction and reconciliation for the local player
- Hitscan with real wall occlusion, host-owned ammo/reload/fire rate
- **Two modes**: TEAM DEATHMATCH (default — a shared objective is what makes
  strangers talk) and FREE-FOR-ALL, first to 15
- **Three maps**: `yard` (8P), `crossfire` (4P), `foundry` (8P, built for
  team play — two wings and a single choke per side)
- A roster of up to 8 (map-dependent), with slots freed on disconnect
- **Player names end to end**: typed on the entry panel, sent in the join
  handshake, published in the 2 Hz rules packet, and drawn as name tags
  (with team side), a real kill feed (`NAME > NAME [os12]`), a local
  score chip and a full standings table on the pause card
- **In-match chat** (`mchat`), relayed by the host over the match socket, with
  a per-sender rate floor and host-side attribution so nobody can post under
  another player's name
- **Death that reads as a death**: a 3-second respawn countdown with the
  killer's name, a dead thud on death, a distinct crack on a kill you scored,
  and dimmed name tags on corpses
- **Pickups**: `R` health, `B` armour, `W` OS-12, `M` K-9, on a 12 s respawn
  timer, with a chimes and a particle flash
- **Real arena audio**: positioned remote gunfire (pan + falloff, and a
  distant variant past 640 px), impacts tied to where the bullet landed, a
  hit-confirm tick, reload, empty-magazine click, pickup, round-end sting
- Frozen waiting lobby: hosting alone does not start the round
- Host can **remove players** (pause → REMOVE ALL PLAYERS); the client is
  told it was removed rather than finding its socket closed and assuming its
  own wifi dropped
- **You choose your team.** In a team match the lobby splits the roster into
  IPA and KRAP, and clicking a side moves you there — the request goes to the
  host, which owns the table, and comes back on the next state packet so every
  screen agrees. A side you picked is sticky: auto-balance fills the seats
  around your choice and never moves you off it. The host gets a MOVE button per
  player and AUTO-BALANCE for the rest. Teams lock once the match starts.
- **Cosmetics everyone can see.** A player's palette, head gear and weapon
  finishes ride the match socket, so an opponent wears what they bought. See
  [§2a](#2a-cosmetics-and-acaribucks).
- **Acaribucks**, earned from arena results and spent in the OUTFITTER

### What is NOT in yet

- **No spectate, and no damage-direction indicator.** There is no damage
  indicator even though the host already publishes who hit you — only the
  rendering is missing.
  Kill-cam specifically is **declined, not pending**: `docs` history aside, it
  is not on the roadmap and should not be picked up as if it were.
- **No blood.** Impacts are particles.
- **No voice chat.** Text only.
- Co-op is still not a thing — see [§8](#8-why-co-op-is-still-not-a-thing).

---

## 2a. Cosmetics and Acaribucks

One global profile wallet (`profile.json`, next to `save_data.json` and
`settings.json`), shared across save slots and between campaign and arena.
Acaribucks come from **arena results only** — no campaign rank payout, no
playtime drip.

**The catalog is the security boundary.** An appearance is a bundle of item
identifiers (`pal_krap`, `head_goggles`, `os12_blued`) and there is no field
anywhere — on disk or on the wire — that can carry an RGB triple. A hostile
peer cannot paint itself arbitrary colours or send a megabyte as a colour; the
worst it can claim is an item it does not own, and `core.appearance.normalize()`
collapses that to the free default at the seat, before the state is published.
That is why cosmetics can ship ahead of the authentication work in §7.

- Wire: `"a"` on the `joinmatch` handshake (once — nobody changes hats
  mid-round), `"looks"` on the 2 Hz `ms` packet beside `names`. Never on the
  20 Hz `snap`. Absent means default, which is the whole old-client story.
- Render: `ui/arena_view.py` caches one `Player` per **slot**, and slots are
  reused as people join and leave, so the loadout is re-applied on change — a
  replaced player must not inherit the stranger's hat.
- Payout: `arena.compute_payout()` runs **locally on each participant** against
  the host's published board. There is no trusted server here, so a
  host-announced "you earned N" would let a hostile host pay its opponents
  zero. `PAYOUT_MAX` caps a round; the round-end card shows the number, or
  `NO PAYOUT - NO RESULT`.
- Double-payment is closed three ways: the `_round_end_played` edge, a
  `credit_round` key of `(match_id, round, slot, kills)`, and a bounded credit
  log. A host restart mints a new `match_id`.

What this does **not** prevent: hosting private matches to pay yourself, or
editing `profile.json` by hand. Both need relay-side identity, which is §7's
problem, and pretending otherwise would be worse than saying it.

The Outfitter (`ui/shop.py`) draws its icons and preview with the production
sprite code, so the shop cannot promise an art the game does not wear.

---

## 3. The lobby relay (server list + global chat)

### A shared master

One person runs `tools/mp_server.py` on a VPS or LAN box; everyone points
at it. Same protocol, same client.

```bash
python tools/mp_server.py --host 0.0.0.0
```

### What "lobby" means here (read this part)

**The hosted thing is a lobby: a server list and a chat channel.** Two
people can connect and talk to each other over it. **It carries no
gameplay** — no simulation, no shared world, no position sync. That is not
a gap in the relay, it is the relay's job: playable multiplayer lives in
ARENA MATCH ([§2](#2-arena-match-the-actual-game)) on its own socket and
never passes through the master at all.

---

### Background: the original relay

The multiplayer server browser used to be entirely fictional: a hardcoded
`server_list`, ping numbers jittered with `random.randint`, and a `CHAT_POOL`
of made-up regulars. It now talks to a real socket backend, and the fiction
is only used as a fallback when no master is reachable.

This is a **lobby relay**, in the same sense as a Steam/Source master
server. It carries exactly what the browser needs:


- the list of game servers (name, players, ping)
- per-server rules shown in the hover tooltip
- a global chat channel

It does **not** carry gameplay. There is no simulation, no player state, and
no position/traffic replication — that is the arena match's job, on a
different port.

There are no accounts, but there **are** limits, because "no login" must not
mean "unlimited". The master enforces:

| Limit | Value | Why |
|---|---|---|
| Chat rate | 0.4 s floor, burst of 5 | One client must not be able to fill everyone's chat panel. The floor means a fast human typist is never punished. |
| Register rate | 2 s per server name | Register rewrites *every* client's server list, so it is the most abusable verb on the wire. |
| Live rows | 64 | Bounds how much junk can appear in the browser. |
| Concurrent clients | 128 | Bounds thread usage. |
| Register `rules` | 16 entries × 64 chars | Otherwise one row can push megabytes into a payload every client parses and draws. |

These bound a flood. They are **not authentication** — anyone can still claim
any name. Refusals are sent as *soft* errors (`error` with `"soft": 1`), which
the client surfaces as a SYSTEM line in the chat panel rather than dropping
the session: a host that re-registers too fast is misconfigured, not
malicious, and losing its whole connection over it would look like the master
had gone down.

### Running it

Start a master:

```bash
python tools/mp_server.py                  # 127.0.0.1:27015 (this machine only)
python tools/mp_server.py --host 0.0.0.0   # reachable from the LAN
python tools/mp_server.py --port 27020     # different port
python tools/mp_server.py --no-seed        # start with zero servers
```

Then launch the game and open Multiplayer. The browser connects on entry and
shows the real list; the subtitle reports the live state and the real error
when it cannot connect.

For a LAN party, run the master on one machine with `--host 0.0.0.0`. Clients
on the same subnet find it automatically via the UDP discovery beacon on
port 27016 — no configuration needed. Set `ACA_MP_HOST` / `ACA_MP_PORT` to
point at a specific master and skip discovery:

```bash
set ACA_MP_HOST=192.168.0.10
set ACA_MP_PORT=27015
```

Chat is typed into the input line at the bottom of the GLOBAL CHAT panel and
sent with Enter.

### Testing multiplayer on one PC

Do **not** launch the game twice: both instances share `save_data.json` and
`settings.json`, so the second one overwrites the first's progress on exit.
Use the headless bot instead — it speaks the real protocol over a real
socket, so it exercises the same path a second player would, without a
window or touching your save.

**Terminal 1 — the host:**

```bash
python tools/mp_host.py --name "My Test Server"
```

**Terminal 2 — a fake second player:**

```bash
python tools/mp_bot.py --say "hello from the bot" --say "and again"
```

**Then launch the game** and open Multiplayer. You should see:

- your server in the list (one row, `00/08`)
- both bot lines appear in the GLOBAL CHAT panel as `[Tester2] ...`
- anything you type in the game shows up in the bot's terminal as
  `<Player1> ...` — that proves traffic flows both ways

Handy variants:

```bash
python tools/mp_bot.py --name Biribel --every 5     # chatter every 5s
python tools/mp_bot.py --every 5 --count 3          # ...only 3 times
python tools/mp_bot.py --say hi --seconds 30        # exit after 30s
```

Run two bots at once to see multi-client chat and a non-zero player count:

```bash
python tools/mp_bot.py --name Alice --seconds 60
python tools/mp_bot.py --name Bob   --seconds 60
```

### If you see the wrong servers

A leftover host from an earlier test holds port 27015 and the game
connects to *that* instead of yours:

```bat
netstat -ano | findstr 27015
```

Kill the PID it prints, or start yours on another port and paste
`127.0.0.1:27020` into the CONNECT box.

---

## 4. Protocol

Newline-delimited JSON over TCP, the way a Source master server works. Chosen
because it is trivially inspectable with `netcat`, survives partial reads
(the client buffers to the newline), and needs no third-party serializer.
Payloads are tiny — a server row is under 200 bytes.

### Lobby messages (port 27015)

| Message | Direction | Purpose |
|---|---|---|
| `hello` | client → master | announce nickname + protocol version |
| `welcome` | master → client | confirm id/name/uptime (sent twice: before and after `hello`) |
| `query` | client → master | request the server list |
| `servers` | master → client | the list, plus a `rules` side-table keyed by name |
| `chat` | both | relay a chat line to every client |
| `register` | server → master | publish a game server row (15s TTL) |
| `error` | master → client | protocol mismatch, bad packet, etc. |
| `error` + `"soft": 1` | master → client | a **note**, not a fault: throttled, or registering too often. The client shows it and keeps the session. |
| `bye` | either | graceful disconnect |

### Match messages (port 27017)

The arena match reuses the same framing on its own socket:

| Message | Direction | Purpose |
|---|---|---|
| `joinmatch` | client → host | **first** packet a match client sends; this is what earns a roster slot. Carries `map` and `n` (the callsign). |
| `you` | host → client | the slot this connection owns, plus the host's map and mode |
| `in` | client → host | movement axes + aim + the fire bit, one per tick; plus weapon-switch requests |
| `snap` | host → client | the authoritative world, 20 Hz |
| `ev` | host → client | authoritative events: hit, kill, pickup, **empty trigger pull** |
| `ms` | host → client | everything a client cannot infer: scores, clock, teams, pickup timers, **names**, **respawn countdowns**, roster, room phase |
| `mchat` | both | in-match chat. Clients send it up; the host relays it to everyone with **its own** attribution, so a client cannot post under another player's name. |
| `hostleft` | host → client | the session is over; the host is gone |
| `kick` | host → client | *you* were removed, and here is why — sent before the socket closes, because a closed socket is indistinguishable from your own wifi dropping |

Everything a peer sends is validated by `parse_*` in `net/protocol.py` before
anything acts on it. A structurally wrong packet is dropped whole rather than
partially applied, and out-of-range values are clamped — including names,
chat bodies, respawn timers and rules strings.

## 5. Layout

```
src/net/protocol.py   framing, codecs, validators, name/chat sanitising
src/net/client.py     MPRelayClient - one daemon thread, snapshot-based reads
src/net/discovery.py  LAN broadcast beacon client
src/net/portmap.py    UPnP IGD + NAT-PMP forwarding, STUN public-IP lookup
src/net/tcp_tunnel.py public TCP tunnels (bore first, then ngrok)
src/net/roomcode.py   the shareable invite code
src/net/match.py      host-authoritative session + snapshot fanout
src/missions/arena.py arena maps, weapons, pickups, deathmatch rules
src/ui/mp.py          relay_* helpers; CONNECT box; server_list synced in place
src/ui/match_screen.py  the in-game ARENA MATCH screen (host/join + live match)
src/ui/arena_view.py  arena renderer: tiles, remote sprites, HUD, gunfeel
src/core/settings_store.py  remembers your CALLSIGN between sessions
tools/mp_server.py    standalone master (stdlib only)
tools/mp_host.py      self-hosted lobby host (stdlib only)
tools/mp_host_main.py PyInstaller entry point for the host EXE
tools/build_host_exe.bat
```

### Threading

The pygame main loop must never block, and a TCP connect to an unreachable
host can stall for seconds. So **no socket call is ever made from the render
thread**. `MPRelayClient` owns exactly one daemon worker; the main thread
only calls `state()` (which returns an immutable tuple snapshot under a
lock) and `send_chat()` (which appends to a deque and returns). The worker
never holds the lock across a blocking call.

`state()` returning a **tuple of tuples** is deliberate: the UI iterates the
server list while rendering, and a live list mutated mid-iteration would be a
classic heisenbug.

`net` has no dependency on `ui`, `core`, or pygame, so it stays importable by
headless tools. The chat callback crosses back into the UI through an explicit
`register_chat_sink()` hook rather than an import, keeping the dependency
graph acyclic in both directions.

### Defensive parsing

`protocol.normalize_row()` rejects and clamps anything hostile or buggy,
because a master is an untrusted input: player counts are clamped to
`[0, max]`, pings to `[0, 9999]`, names are length-capped, and rows that
cannot be parsed are dropped rather than passed to the layout maths.

## 6. Testing

`tools/smoke_test.py` gates this:

- `mp_relay_roundtrip` — starts a real master on an ephemeral port in-process
  and drives a real client against it: handshake, server list, survival past
  a keepalive cycle, chat round-trip, junk rejection, dead-host degradation.
  Also covers the abuse limits end to end: a 60-line flood is cut down while
  a legitimate sender still gets through, a duplicate `register` inside the
  interval is refused, an oversized `rules` string never reaches the list, and
  the innocent client stays online throughout.
- `mp_relay_ui_integration` — the UI seams: `server_list` keeps its 4-tuple
  shape, helpers are safe offline, explicit hosts are never overridden, and a
  soft master note surfaces as a SYSTEM line *without* being mistaken for a
  disconnection.
- `mp_host_and_portmap` — the self-hosting path: address validation rejects
  junk without raising, the host publishes exactly one valid row, and the
  pure NAT/STUN helpers behave. Also both tunnel providers (parsing, launch
  argv, proxy-variable stripping, provider preference, and that a LAN-only
  host is told what to install). The live UPnP/NAT-PMP/STUN calls are
  deliberately *not* exercised — they depend on the machine's router and
  would make the suite flaky; `--check` covers those interactively.
- `match_identity_and_comms` — the whole identity and comms story against a
  real host and a real client over loopback: name sanitising (control
  characters, whitespace, length caps), the callsign crossing the handshake,
  host-side attribution of chat, the per-sender rate floor, the kick arriving
  as a *stated removal* rather than a dead socket, and the respawn countdown
  refusing to be lengthened by a rules packet.
- `arena_hud_legibility` — the new HUD surfaces actually render: name tags,
  the named kill feed, the local score chip, and the respawn plate (which must
  draw nothing for an expired timer, nothing for another player's timer, and
  must not cover the corpse).
- The arena match checks: `lobby_relay_is_not_a_player` (a connection that
  never sends `joinmatch` — the relay's `hello`/`query` — must not be seated,
  must not start the round, and must be closed), plus the roster, client
  join, loopback fallback and interpolation checks. `client_join_completes`
  also pins the frozen lobby: the host's sim tick must stay at 0 until
  somebody actually joins.

These checks are real, not vacuous. Re-introducing the original
`recv()`-timeout bug makes `mp_relay_roundtrip` fail with
`server list emptied after keepalive`; making every connection count as a
match client again makes `lobby_relay_is_not_a_player` fail with
`a lobby client was seated as a player`; disabling the master's chat gate
makes it fail with `the master relayed an unbounded chat flood`; and
removing bore from the provider order makes
`mp_host_and_portmap` fail with a provider-order assertion.

## 7. Known limitations

- **Clicking a row in the server browser still ends in the original fictional
  kick screen.** That list is the lobby, and only ARENA MATCH is a real
  session. (A row published by `tools/mp_host.py` is real; the seeded ones
  are fiction.) The in-match kick is real — see §2.
- **The CONNECTIONS tab (DMs) is still entirely fictional.**
- **No authentication.** The rate limits in §4 bound a flood; they do not
  establish identity. Anyone can claim any name, publish any row, and send
  `joinmatch` to take a slot in someone's match. A host can remove them, but
  only after they are in.
- **No encryption.** Lobby chat and match traffic are plain TCP. A tunnel
  provider can read everything.
- Discovery does not work across subnets or on networks that block broadcast.
  Expected; use `ACA_MP_HOST` in that case.
- Port forwarding is best-effort. Double NAT and CGNAT defeat it, and we
  cannot detect that from inside the box — hence the tunnel path.
- The public IP comes from STUN, so it can be wrong behind some VPNs or
  CGNAT setups. The host always shows its LAN address alongside.
- No spectate, no damage-direction indicator, no blood, no voice. (Kill-cam is
  declined — see §2 "What is NOT in yet".)

## 8. Why co-op is still not a thing

The arena is host-authoritative (`net/match.py`, `ui/match_screen.py`,
`ui/arena_view.py`): clients send input, the host broadcasts state, and
determinism stops mattering. That is why it was chosen over lockstep, and it
is also why the campaign cannot simply be pointed at it:

1. `app.py` runs a variable timestep (`dt = min(clock.tick(60)/1000, 0.05)`),
   and 27 call sites read `pygame.time.get_ticks()`. Deterministic lockstep
   is off the table without a fixed-timestep refactor — though note this no
   longer blocks *host-authoritative* co-op, only lockstep.
2. `core/state.py` is one large mutable singleton with no boundary between
   authoritative and visual state, which is what snapshots need.
3. M1/M2/M3 have scripted timelines (a forced breach queue, a timed zone
   cinematic, a strict `MISSION3_KILL_ORDER_MAP`) that assume one player —
   which is why co-op is still only the arena, not the campaign.

The useful seam for co-op already exists — `entities/enemy_ai.py` consumes a
`_FakeKeys(dx, dy)` object and drives the real weapon/interaction pipeline,
so remote input can be injected through the same path as bots.
