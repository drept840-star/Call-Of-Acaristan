Resume the Mission 1 "Black Notebook" rework in Call of Acaristan.

WHERE
- Work only in the worktree E:/Code/Call of Acaristan/m1-rework, branch m1/rework (cut from main 6a8379c). No push.
- Do not touch, stage or switch the main checkout E:/Code/Call of Acaristan/First try (branch cutscene-holds, ~81 uncommitted files of other M5/M6 work).
- The plan is m1-rework/docs/MISSION1_REWORK_PLAN.md (map, dialogue, stealth numbers, wave table, WP0-WP9). Follow it.

WORKING RULES (strict, from the user)
- Main Opus never reads files or runs commands. It writes briefs and reviews reports.
- Haiku `searcher` subagents do ALL searching, reading for research, gate runs, renders and git commits.
- Opus `implementer` subagents (model: "opus") ONLY edit code, working from a Haiku digest pasted into the brief. No grepping, gates, git or renders.
- Loop for every WP: Haiku digest -> Opus edits -> Haiku gates + previews -> Opus fixes -> Haiku commits.
- Give every worker a self-contained brief: files it may touch, what done looks like, the gates. Never let two editors touch the same files. Commits one at a time. Spot-check claims.
- Gates ONLY in a fresh detached temp worktree, because the real worktree has stale ignored state that gives false failures:
  git -C "E:/Code/Call of Acaristan/m1-rework" worktree add --detach "$TEMP/x" <sha>, copy any uncommitted files in, then run
  python -m compileall -q src ; python tools/smoke_test.py (must end "SMOKE TEST: OK") ; python tools/ae_level_check.py -v ; python tools/ae_golden.py verify (only gp.m1.start, gp.m1.desks, gp.m1.warehouse may fail until WP9) ;
  then worktree remove --force and worktree prune.
- LF endings on every touched file (fix with sed -i 's/\r$//').
- Commit message "M1 rework WPn: <summary>", blank line, "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" (the trailer names the model that wrote the code).
- Art: art-pack tiles, dark ambient, hard edges, no soft blobs, noise or blur. Keep the blocky character models. The agent renders preview PNGs, looks at them and iterates. Send previews to the user before moving on.
- Leave assets/voice/*_matches.txt alone (CRLF noise). Never commit shots_wp4b/, shots_wp5/, shots_wp6/.

DONE (commits on m1/rework)
WP0 4328972, WP1 c869a9b, WP3 data bffc3d9, WP2 b63eb24, WP2b 5d69458, WP3 wiring a566995, WP4a 4f3762f (+ bake fixes 0caa27c, e993801), WP4b 2977bab, WP4c eabebdc, WP4b art fix 0228236, spawn fix 8cc1eb8 (gameplay starts at tile (3,9) where the dropoff ends), WP5 40734cf (suspicion stealth, V silent takedowns, Q bricks, fences block movement but not sight).

FIRST, CHECK STATE
The last session was stopped mid-commit. Have a Haiku searcher report git log --oneline -5, git status, and git worktree list for m1-rework. Remove any leftover temp worktree (e.g. $TEMP/m1wp6c) and prune.

THEN FINISH WP6 (Volkov standoff, scripted K alarm, water-damaged leaf)
- Code is written in 7 files: src/missions/m1/update.py, draw.py, main.py, src/core/interactions.py, src/ui/hud.py, src/app.py, tools/smoke_test.py. If it is not committed yet, gate it as above. The last clean-copy run had every M1 check green (volkov_foreshadowing, m1_volkov_escapes_both_routes, m1_stealth_suspicion, radio_gated_by_cutscenes) and failed only on mp_relay_roundtrip, a network flake, so rerun once. Commit as "M1 rework WP6: Volkov standoff, scripted K alarm, water-damaged leaf".
- Bug to fix next (user saw it): Volkov is drawn WAY too big in top-down gameplay. src/missions/m1/draw.py _draw_m1_actors draws him with the cutscene figure cutscenes/cast.py draw_volkov(surface, cx, foot_y, scale=0.35, facing_right) for both the standing pose (added in WP6) and the escape run. Have Haiku digest how the in-game player and enemies are drawn (Player.draw, Enemy.draw, sizes, how outfits vary, how M1 civilians are drawn, any figure_kit SPECS for volkov). Then Opus redraws Volkov as a top-down figure at the same size and style, facing the player, with no pop when the run starts. Re-render shots_wp6/standoff_beat2.png with scratchpad preview_wp6.py (recreate it if the scratchpad is gone), show the user, and commit as "M1 rework WP6 fix: ...".

THEN, IN ORDER
- WP7: waves, enemy roles, CIOCAN entrance, exfil. The M1_TRIGGERS street_exit and exfil_van have no runtime consumer yet. CIOCAN's SPEAKER_COLORS entry is a placeholder (205,75,60).
- WP8: lighting, ambience, music hooks. Music stays silent until the user supplies m1_infiltrate.ogg and m1_combat.ogg. The shutter floodlight is still a plain lamp radius. The shared lighting still adds a soft glow around street lamps in gameplay and must become hard-edged. No outdoor rain audio yet.
- WP9: re-bake the goldens (gp.m1.start, gp.m1.desks, gp.m1.warehouse) and confirm the m1.dropoff shots are covered. Re-record the M1 replay (ae_replay.py check --set baseline_v2 --only m1; the drift pre-dates the rework) and the loop. Run tools/ae_ci.py. Update the docs: LORE M1 section, BUGS B-004/B-034, .wolf/STATUS.md.

OPEN ITEMS TO RAISE WITH THE USER
- The plan says far/dark/still detection takes ~3.6 s, but its own formula gives ~5.2 s. The formula was kept.
- The calm-guard white suspicion meter is faint on dark asphalt.
- The street patrol route and the shutter guards facing each other are not done.
- In M1, Q throws a brick instead of switching weapons.
- The files_already radio line now plays after NOTEBOOK_INSPECT closes, right after BIRIBEL's leaf line.
- The house w_C wall tiles have soft stains baked in. The stockroom's outer walls (row 11 down) still use container panels.

KNOWN REDS THAT ARE NOT OURS
- ae_ci: mission4_stage_transitions, mission4_cinematic_arrest, mission5_shadow_finale, mission5_harbour_art.
- ae_bake --check is stale on m2 only. tools/check_boundaries.py fails at baseline.
- Smoke network flakes (rerun once): lag_compensation_real_network_path (WinError 10013), mp_relay_roundtrip.
