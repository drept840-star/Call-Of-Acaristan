# Multiplayer review — Call of Acaristan

## Short version

The project already has a solid foundation: an authoritative host, fixed-tick simulation, client-side movement prediction, snapshot interpolation, validated messages, teams/score/respawns, in-match chat, and several ways to reach a room (LAN/port mapping/tunnel). This update adds a loss-tolerant fast path, fallback, reconnect, and fairer hit checks. The main remaining opportunities are real-world network playtesting, host-crash resilience, and more gameplay variety.

This review includes source inspection and simulated local network tests; it is not yet a playtest across real home routers or internet connections.

## Highest-impact improvements

### 1. Reduce freezes from delayed or lost gameplay updates — implemented

The game now uses authenticated UDP datagrams for high-rate movement inputs and world snapshots when that route is reachable. Each update is disposable, so a lost packet does not hold later positions behind it. Sequence/tick checks ignore reordered stale updates, and silent inputs expire so a disconnected player does not keep walking or firing. Match setup, chat, weapon changes, events and rules remain on reliable TCP. If UDP is blocked, clients and hosts automatically fall back to TCP; the public TCP tunnel continues to work in that mode. The host opens both protocols on the same port when automatic router mapping is available, and the match HUD shows whether the live path is UDP or TCP.

### 2. Make a bad connection visible and recoverable — implemented

The match readout tracks round-trip delay, jitter, update rate/gaps, and sent inputs; it warns when quality degrades or updates stall. Unexpected drops trigger a visible reconnect attempt for up to 20 seconds, while the host keeps a returning player's identity, team, score, position, health, and equipment reserved for 35 seconds. Intentional host exits and kicks do not retry.

### 3. Add lag-compensated hit validation — implemented

The authoritative host keeps a short position history and checks a remote target near the time the shooter saw it, rather than trusting a client-reported hit. Rewinds are capped at 12 simulation ticks (about 200 ms), invalid timing is rejected, and shots cannot hit a player using a position from before their respawn.

### 4. Reduce host dependence

Today the host is the match server; a host crash still ends everyone's match, and the host's machine/network determines tick reliability. Reconnect covers temporary client disconnects, not host failure. Next steps could include saving a compact round checkpoint or running a dedicated authoritative server. Host migration is a separate project because it needs safely replicated match state and election rules.

### 5. Improve joining and finding people

Room codes and the server browser are useful, but sharing codes out-of-band plus port forwarding/tunnels is friction. Improve the flow with a “copy invite” button, clear NAT status, direct LAN discovery, and friend/invite support. For public games, add quick-match filters (region, mode, map, open slots) and a server-side matchmaking service. Show actionable errors for incompatible versions, full rooms, and unreachable hosts.

## Gameplay / retention improvements

- Add more match rules: team deathmatch, free-for-all, capture/hold objectives, and configurable round length/score target.
- Add map voting and rotate maps automatically; track whether teams are balanced and allow auto-balance between rounds.
- Add a spectator/late-join flow, rematch vote, and persistent stat summary (kills, deaths, assists, accuracy, objective score).
- Add team voice or at least quick ping/radial commands (“enemy here,” “defend,” “need help”) so players can coordinate without typing during combat.
- Playtest weapon balance and spawn safety with several players; tune spawn selection to avoid immediate spawn-kills and add a brief spawn-protection window if needed.

## Implemented multiplayer improvements

The multiplayer transport and resilience work now includes:

- Added optional ping/pong heartbeats and client-side RTT/jitter, snapshot-rate, snapshot-gap, and input counters. The client shows a small network readout during a match; heartbeat replies are rate-limited by the host.
- Added `tools/mp_net_soak.py`, a headless 2–8 player test that runs the actual match screen/network code. Per-client proxies add delay, jitter, real UDP loss/reordering, and TCP retransmission-like stalls; tests can also block UDP entirely to check automatic fallback.
- Added automatic rejoin attempts after an unexpected connection break. It retries the same saved invite for up to 20 seconds; press Escape to stop. The host temporarily keeps the disconnected player's seat, team, score and game state; a returning player can reclaim them with a private, single-use token. If that saved place has expired, the player may return with a fresh seat. The host clears peers it has not heard from for 16 seconds.
- Added a clear reconnect screen, a warning when the connection is poor or match updates stop arriving, and distinct messages for an intentional host exit/kick versus an unexpected network break. Invites without the saved join credential fall back to a manual rejoin message.
- Added smoke coverage for heartbeat validation, telemetry counters, and a simulated socket-drop/rejoin.
- Added bounded lag compensation: clients report the world time they were displaying; the authoritative host keeps a brief position history and checks remote targets at that recent time. The host caps rewinds to 12 simulation ticks (about 200 ms), rejects invalid timing values, and will not apply a past-life hit after a respawn.
- Added a per-player secret for the datagram path, bounds on datagram size and input rate, wrap-safe sequence handling, reliable one-shot weapon actions, and automatic TCP recovery when UDP snapshots go stale. UPnP/NAT-PMP setup requests matching TCP and UDP mappings; TCP-only tunnels are clearly identified.
- Refreshed the multiplayer HUD to match the campaign's panel style: clearer health/ammo cards, numbered weapon slots using the campaign's magazine artwork, a larger score band, and a dedicated connection-quality card. Removed the redundant corner name/team and personal-stat boxes; detailed standings remain on the leaderboard.
- Extended `tools/mp_net_soak.py` with `--lag-shot-check` and `--block-udp --require-tcp-fallback`. The first sends a real shot through delayed UDP while the target moves; the second verifies continued snapshots when UDP is unavailable. Both checks run from the full smoke suite.

Example: `python tools/mp_net_soak.py --players 4 --seconds 12 --latency-ms 45 --jitter-ms 12 --loss-percent 1`

The host remains authoritative in both transport modes. UDP is used only for replaceable motion/input state; all important control messages and one-shot actions retain reliable TCP delivery. The displayed snapshot-gap metric still counts missing application snapshots, not raw packet loss.

**Verification:** targeted coverage passes for join/reconnect/host exit, token and datagram validation, replay/reordering and stale-input safety, sequence wraparound, router mapping behavior, and automatic TCP fallback when UDP is blocked. The real delayed-shot check passes at 35 ms one-way delay and confirms the host accepts a shot after the target has moved out of the current aim line, using its short rewind history. A 4-player, 10-second impaired soak at 50 ms one-way delay, 20 ms jitter, and 5% UDP loss passed: clients received about 18.7–19.5 snapshots/sec, with 7–12 gaps each; the HUD marked the most impaired routes as poor rather than hiding the trouble. A separate 4-player test at 35 ms, 15 ms jitter, and 1% loss also passed, at roughly 20 snapshots/sec. The blocked-UDP fallback check passed at about 20 snapshots/sec over TCP. The full smoke suite passes every multiplayer check; its only failure is the unrelated pre-existing Mission 6 viewmodel brightness assertion (`m6_train_viewmodel`, 45.1 vs. 39.9 required). Real-world router/firewall and internet playtesting remains outstanding.

## Remaining work

1. **Playtest real networks:** compare LAN, router-forwarded UDP, VPN/overlay, and TCP-only tunnel connections. Confirm the path indicator and fallback behavior on different routers and firewalls; tune retry/freshness limits from those results.
2. **Gameplay polish:** invite-copy, clearer join errors, map/rematch voting, spectator/late-join, and team pings.
3. **Scale and resilience:** dedicated-server option, persistence, moderation/reporting, and matchmaking. Host migration remains a separate project because it requires transferring authoritative match state safely.
