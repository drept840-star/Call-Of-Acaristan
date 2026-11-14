# Multiplayer update

## What players will notice

- If the connection gets very slow, the game displays a short warning.
- If the connection unexpectedly breaks, the game shows a “Trying to rejoin” screen and tries the same invite for up to 20 seconds. Press **Escape** to stop.
- If it gets back in soon enough, the game restores your same player, team, score, position, health, and equipment. The host holds that spot briefly while you reconnect. If the save window has expired, the game tells you that your score may have reset.
- If the host ends the match or removes you, the game says so instead of repeatedly trying to reconnect.
- The multiplayer HUD now uses the campaign's darker, glass-like panels. Health and ammo are easier to read, the weapon selector uses the campaign's magazine artwork with clear key numbers, and connection status has its own corner panel. The extra name/team and personal-score corner boxes are gone; the full leaderboard is still available when you open it.

## Fewer freezes when updates are lost

Movement and world updates can now use a separate fast path. If one update is lost, the game skips it and uses the next one instead of waiting for it. Important messages—such as joining, chat, and weapon switches—still use the reliable path. If the fast path is blocked by a router or tunnel, the game automatically keeps playing over the reliable path; the match screen shows which path is in use.

## Fairer shots on slower connections

The host briefly remembers where players were. When a shot arrives, it can check the target's position from the moment the shooter was looking at them, instead of only checking where they are now. This can make a moving opponent feel less likely to “warp away” from a shot on a slower connection. The host still decides every hit, and it only looks back a short, fixed amount of time.

## A limitation

Automatic rejoining works when the game still has the invite information it needs. If it cannot reconnect, it returns to the join panel so you can try again yourself.

## For testing

A developer test can run several pretend players locally and imitate a slow or jumpy connection. It also has a focused fair-shot check that sends an actual shot through the delayed connection while the target moves. Run it from the project folder with:

```text
python tools/mp_net_soak.py --lag-shot-check --latency-ms 35 --jitter-ms 0 --loss-percent 0
```

The test passes only if the host confirms damage after the target has moved away from the position the shooter is aiming at. It needs no second computer or online player.

To check that play continues when the fast path is blocked:

```text
python tools/mp_net_soak.py --players 2 --seconds 2 --block-udp --require-tcp-fallback
```

The test report also shows how often updates arrived during the run. To try a more difficult four-player simulated connection with delay, jitter, and packet loss:

```text
python tools/mp_net_soak.py --players 4 --seconds 10 --latency-ms 50 --jitter-ms 20 --loss-percent 5
```

The loss setting drops some fast-path updates and adds recovery-like waits to the reliable path. This is a repeatable local test, not proof that every real router or internet route will behave the same.