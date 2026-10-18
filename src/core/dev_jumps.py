
"""dev_jumps.py - registry of dev jump targets.

Side-effect free on purpose: imported by ``app._apply_dev_args`` (for
``--jump NAME`` / ``--list-jumps``) AND by ``tools/dev.py`` (for ``--list``
without starting pygame). Single source of truth - add new jump targets
here, then handle the canonical flag in ``app._apply_dev_args``.

Maps short target name -> (canonical CLI flag, one-line description).
"""
DEV_JUMPS = {
    # ── Mission 0 (RPE6 Phase 10 tutorial mission) ──
    "m0": ("--dev-mission0",
           "Mission 0 - Depot (tutorial mission, playable)"),
    # ── Mission 1 ──
    "m1": ("--dev-m1",
           "Mission 1 warehouse from the start (playable)"),
    "m1-safe": ("--dev-safe",
                "Mission 1 at the notebook safe keypad (code 742)"),
    # ── Walking sim ──
    "walk": ("--dev-walk",
             "Walking sim harbor exploration from the start"),
    # ── Mission 2 ──
    "m2": ("--dev-mission2",
           "Mission 2 intro cutscene"),
    "m2-game": ("--dev-mission2-game",
                "Mission 2 gameplay from the start"),
    "m2-sniper": ("--dev-mission2-sniper",
                  "Mission 2 Route 12 sniper ambush"),
    "m2-after-sniper": ("--dev-mission2-after-sniper",
                        "Mission 2 right after the sniper fight"),
    "m2-flank": ("--dev-mission2-flank",
                 "Mission 2 flank cutscene / phase"),
    "m2-truck": ("--dev-mission2-truck",
                 "Mission 2 truck stage"),
    "m2-evidence": ("--dev-mission2-evidence",
                    "Mission 2 evidence-completion cinematic"),
    # ── Mission 3 ──
    "m3": ("--dev-mission3",
           "Mission 3 intro cutscene"),
    "m3-game": ("--dev-mission3-game",
                "Mission 3 breakout gameplay (post-breach, chair leg)"),
    "m3-comms": ("--dev-mission3-comms",
                 "Mission 3 comms wing (via service transition cutscene)"),
    "m3-archives": ("--dev-mission3-archives",
                    "Mission 3 archives wing checkpoint"),
    "m3-kill-order": ("--dev-mission3-kill-order",
                      "Mission 3 kill-order ground floor (+ KO intro cutscene)"),
    "m3-ledger": ("--dev-mission3-ledger",
                  "Mission 3 black ledger debug"),
    "m3-vostral": ("--dev-mission3-vostral-cutscene",
                   "Mission 3 Vostral acquisition cinematic"),
    "m3-archives-cutscene": ("--dev-mission3-archives-cutscene",
                             "Mission 3 comms-to-archives transition cutscene"),
    "m3-broadcast-transition": ("--dev-mission3-broadcast-transition",
                             "Mission 3 kill-order-to-broadcast transition cutscene"),
    "m3-broadcast": ("--dev-mission3-broadcast",
                     "Mission 3 broadcast wing checkpoint (Slice 6 gauntlet)"),
    "m3-upload": ("--dev-mission3-upload",
                  "Mission 3 at the station PC, upload OS already open"),
    # ── Mission 4 ──
    "m4": ("--dev-mission4",
           "Mission 4 intro cutscene"),
    "m4-game": ("--dev-mission4-game",
                "Mission 4 aftermath street gameplay from the start"),
    "m4-station": ("--dev-mission4-station",
                   "Mission 4 radio-station interior checkpoint"),
    "m4-tower": ("--dev-mission4-tower",
                 "Mission 4 transmitter hold (siege checkpoint)"),
    # ── Mission 5 ──
    "m5": ("--dev-mission5",
           "Mission 5 intro bulletin cutscene"),
    "m5-hq": ("--dev-mission5-hq",
              "Mission 5 Guard HQ walking sim (Vasile's office)"),
    "m5-game": ("--dev-mission5-game",
                "Mission 5 Lower Quarter gameplay (HQ skipped)"),
    "m5-printworks": ("--dev-mission5-printworks",
                      "Mission 5 MAG print works (find Maru, then the raid)"),
    "m5-tunnel": ("--dev-mission5-tunnel",
                  "Mission 5 basement tunnel escort (deepest resume point)"),
    "m5-ending": ("--dev-mission5-ending",
                   "Mission 5 final cutscene (shadow finale at the river)"),
    "m6": ("--dev-mission6", "Mission 6 intro cutscene"),
    "m6-train": ("--dev-mission6-train", "Mission 6 train checkpoint"),
    "m6-3d": ("--dev-mission6-3d", "Mission 6 interactive 3D train scene (shootout)"),
    "m6-shootout": ("--dev-mission6-shootout", "Mission 6 interactive 3D train scene (shootout)"),
    "m6-ending": ("--dev-mission6-ending", "Mission 6 ending cutscene"),
    # ── Trailer bot takes (AI 1 choreography) ──
    "trailer-m1": ("--dev-m1",
            "Trailer Act I warehouse take (bot: breach/molotov)"),
    "trailer-m2-killbox": ("--dev-mission2-game",
            "Trailer Act II killbox take (bot: OS-12 hold + flank)"),
    "trailer-m2-evidence": ("--dev-mission2-evidence",
            "Trailer Act II evidence take (bot: control building)"),
    "trailer-m3-breakout": ("--dev-mission3-game",
            "Trailer Act III breakout take (bot: shiv/sidearm)"),
    "trailer-m3-comms": ("--dev-mission3-comms",
            "Trailer Act III relay take (bot: power->auth->tune, Volkov cover)"),
    # ── Misc ──
    "slot-select": ("--dev-slot-select",
                    "Save-slot screen directly (add --continue for CONTINUE variant)"),
    "audio-parade": ("--dev-audio-parade",
                     "Comms wing with verbose sound logging (volume tuning)"),
    # ── Multiplayer arena duo (tools/mp_arena_duo.py) ──
    "mp-host": ("--dev-mp-host",
                "Multiplayer arena panel, hosting on --mp-port (default 27017)"),
    "mp-join": ("--dev-mp-join",
                "Multiplayer arena panel, joining --mp-join ADDR (host:port)"),
}


def jump_flag(name):
    """Return the canonical CLI flag for a jump target, or None if unknown."""
    entry = DEV_JUMPS.get(name)
    return entry[0] if entry else None
