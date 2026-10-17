MULTIPLAYER UI OVERHAUL — PART 2

INSTALL
1. Close the game. Back up your current project.
2. Extract this ZIP into the project root (the folder containing acaristan.py).
3. Allow the two existing src/ui files to be overwritten. Keep the new
   src/ui/multiplayer_style.py alongside them. Launch acaristan.py normally.
This is a source patch for the supplied First try.zip, not a standalone EXE.
Existing assets and dependencies are reused; no new dependency is required.
The completed settings overhaul is left untouched.

PRESENTATION CHANGES
- Retro-tactical operations shell and prominent ARENA / HOST + JOIN entry.
- Two-column setup: actual map survey, mode/capacity picks, callsign,
  separate create-room and join-operation cards.
- Cached arena surveys read existing tile data; no map/gameplay changes.
- Shared pre-game lobby with map, full room-code/token, connection status,
  copy/start controls, explicit player slots and team selection/move/balance.
- Readable waiting/error states; start/copy targets are registered only when
  the original readiness rules permit them.
- Logical mouse coordinates for hover under the game's scaled display.
- Offline demonstration chat is labelled DEMO instead of LIVE.

NETCODE GUARANTEE
Only presentation methods, palette/geometry and their UI imports changed.
All existing non-presentation function ASTs in match_screen.py and mp.py were
compared with the supplied baseline and were identical. In particular:
ROOMCODE@TOKEN parsing/handshake, authentication, host/join operations,
tunnel generation/cancellation/cleanup, _check_tunnel_alive, room-state
publication, host authority, frozen input, countdown and event dispatch remain
unchanged. No net/*, app.py, mission/arena data, settings or gameplay files
were modified. Public tunnel/external internet hosting was not live-tested;
existing local regression tests and tunnel unit tests were run.

VALIDATION
PASS: python -m compileall -q src tools
PASS: python tools/test_multiplayer_ui.py (5 focused tests)
PASS: python tools/test_tcp_tunnel.py (existing tunnel regression suite)
PASS: python tools/smoke_test.py — SMOKE TEST: OK
The first smoke run failed an existing environment assumption: the private
IP 10.255.255.1 reached the local listener instead of refusing. The test now
uses a scoped refusal fixture for that one candidate; real loopback sockets,
authentication and all existing assertions remain unchanged. This tooling-only
portability correction does not modify the game's connection implementation.
The initial failure and final result are both retained in validation/.
Detailed test logs are in validation/. Environment-dependent skips/warnings,
if any, are recorded there. Dummy SDL was used on the Linux build machine.
Visual review covered setup, join error, host/client team lobby, full FFA
roster, full unbalanced team roster, server browser and connections view at
1000x700 logical resolution. Screenshots are examples with fixture names and
codes, not real sessions. No extra deep integrity/hitbox loops were run.

FILES
src/ui/match_screen.py            Existing owner; presentation-only updates
src/ui/mp.py                      Browser chrome/presentation/entry geometry
src/ui/multiplayer_style.py       New read-only rendering helpers
tools/test_multiplayer_ui.py      Focused UI regression suite
tools/smoke_test.py               Deterministic loopback-refusal fixture

After the final gate passed, work stopped and this patch was packaged.
