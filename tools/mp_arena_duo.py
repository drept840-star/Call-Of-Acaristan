"""Launch TWO full game windows already sitting in the multiplayer arena.

    tools/mp_arena_duo.py            # yard, 1v1, ports 27017
    tools/mp_arena_duo.py --map crossfire --players 4

Player 1 hosts, player 2 joins 127.0.0.1:<port>. Both windows boot with
--dev-mp-host / --dev-mp-join so the arena panel is already raised and
connected - no menu clicks. Press START MATCH on the host window to play.

Save files are sandboxed per window (ACA_SAVE_SUFFIX=_p1/_p2) so the two
processes never overwrite each other's save_data.json / settings.json
(see docs/KRAPNET_MULTIPLAYER.md - launching the game twice used to be
the documented way to corrupt your save).

Why two real windows instead of the headless bot: tools/mp_bot.py only
speaks lobby chat - it cannot move/shoot in an arena. Running the real
renderer + real ArenaSim over a real socket on loopback is the only way
to feel input latency, camera, fire rate and prediction with 2 players.
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACARISTAN = os.path.join(ROOT, "acaristan.py")


def _launch(env_extra, *game_args):
    env = dict(os.environ)
    env.update(env_extra)
    # Side-by-side windows so both arenas are visible at once.
    cmd = [sys.executable, ACARISTAN] + list(game_args)
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env)
    # Stagger the boots so the host's listener exists before P2 dials in.
    time.sleep(1.0)
    return proc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Boot 2 games into one arena")
    ap.add_argument("--map", default="yard",
                    help="arena map both windows use (default: yard)")
    ap.add_argument("--players", type=int, default=2,
                    help="seat cap, host included (2-8, default: 2)")
    ap.add_argument("--port", type=int, default=27017,
                    help="match port P1 hosts on (default: 27017)")
    args = ap.parse_args(argv)
    args.players = max(2, min(8, args.players))

    procs = []
    try:
        print("[duo] P1 hosting %s on 127.0.0.1:%d ..." % (args.map, args.port))
        procs.append(_launch(
            {"ACA_SAVE_SUFFIX": "_p1"},
            "--dev-mp-host",
            "--mp-map", args.map,
            "--mp-players", str(args.players),
            "--mp-port", str(args.port),
        ))
        print("[duo] P2 joining 127.0.0.1:%d ..." % args.port)
        procs.append(_launch(
            {"ACA_SAVE_SUFFIX": "_p2"},
            "--dev-mp-join", "127.0.0.1:%d" % args.port,
            "--mp-map", args.map,
            "--mp-players", str(args.players),
        ))
        print("[duo] Both windows up. START MATCH on the P1 (host) window.")
        print("[duo] Ctrl+C here kills both windows.")
        while True:
            time.sleep(1.0)
            if any(p.poll() is not None for p in procs):
                print("[duo] A window closed - shutting down the other.")
                break
    except KeyboardInterrupt:
        print("\n[duo] Stopping both windows ...")
    finally:
        for p in procs:
            try:
                if p.poll() is None:
                    p.terminate()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except OSError:
                    pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

