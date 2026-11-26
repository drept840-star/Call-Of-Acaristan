"""dev_jumps.py - registry of dev jump targets.

Side-effect free on purpose: imported by ``app._apply_dev_args`` (for
``--jump NAME`` / ``--list-jumps``) AND by ``tools/dev.py`` (for ``--list``
without starting pygame). Single source of truth - add new jump targets
here, then handle the canonical flag in ``app._apply_dev_args``.

Maps short target name -> (canonical CLI flag, one-line description).
"""
import os
import sys
DEV_JUMPS = {
    # ── Mission 0 (RPE6 Phase 10 tutorial mission) ──
    "m0": ("--dev-mission0",
           "Mission 0 - Depot (tutorial mission, playable)"),
    # ── Mission 1 ──
    "m1": ("--dev-m1",
           "Mission 1 opening handoff (dropoff radio cut, then playable)"),
    "m1-game": ("--dev-m1-game",
                "Mission 1 warehouse from the start (playable, no cutscene)"),
    "m1-safe": ("--dev-safe",
                "Mission 1 at the notebook safe keypad (code 742)"),
    # ── Walking sim ──
    "walk": ("--dev-walk",
             "Walking sim harbor exploration from the start"),
    "walk-after": ("--dev-walk-after",
                   "Walking sim harbor right after the rig-strike cutscene (van ready)"),
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
    "m6-game": ("--dev-mission6-game",
                "Mission 6 top-down gameplay from customs (no intro)"),
    "m6-crossing": ("--dev-mission6-crossing",
                    "Mission 6 top-down no-man's-land crossing"),
    "m6-rail": ("--dev-mission6-rail",
                "Mission 6 top-down rail yard"),
    "m6-boxcar": ("--dev-mission6-boxcar",
                  "Mission 6 rail yard at Volkov's boxcar (E starts the 3D talk)"),
    "m6-train": ("--dev-mission6-train", "Mission 6 train checkpoint"),
    "m6-3d": ("--dev-mission6-3d", "Mission 6 interactive 3D train scene (shootout)"),
    "m6-shootout": ("--dev-mission6-shootout", "Mission 6 interactive 3D train scene (shootout)"),
    "m6-yard": ("--dev-mission6-yard",
                "Mission 6 straight into the 'Who is Ucilev?' yard fight"),
    "m6-ending": ("--dev-mission6-ending", "Mission 6 ending cutscene"),
    "m6-heli": ("--dev-mission6-heli",
                "Mission 6 ending from the helicopter finale"),
    # ── Mission 7 ──
    "m7": ("--dev-mission7", "Mission 7 Fallow Ground from the top (arrival film)"),
    "m7-arrival": ("--dev-mission7-arrival", "Mission 7 drop-off film, then the chores"),
    "m7-chores": ("--dev-mission7-chores", "Mission 7 top-down farm chores"),
    "m7-runner": ("--dev-mission7-runner", "Mission 7 Alex-on-the-bike film"),
    "m7-prep": ("--dev-mission7-prep", "Mission 7 top-down prep (pick 2 of 3)"),
    "m7-raid": ("--dev-mission7-raid",
                "Mission 7 3D raid, no preps (--m7-preps=tractor,shed,loft --m7-cp=1|2)"),
    "m7-raid-prepped": ("--dev-mission7-raid-prepped",
                        "Mission 7 3D raid with all three preps"),
    "m7-raid-w2": ("--dev-mission7-raid-w2",
                   "Mission 7 3D raid from checkpoint 1 (orchard cleared, trucks next)"),
    "m7-raid-w3": ("--dev-mission7-raid-w3",
                   "Mission 7 3D raid from checkpoint 2 (trucks cleared, barn fire next)"),
    "m7-finale": ("--dev-mission7-finale", "Mission 7 burning-farm night film"),
    "m7-choice": ("--dev-mission7-choice", "Mission 7 radio choice (sets the Mission 8 route)"),
    "m7-outro": ("--dev-mission7-outro", "Mission 7 end, straight to mission complete (route defaults to duty)"),
    # ── Mission 8 (slice 1: Revenge route) ──
    "m8": ("--dev-mission8", "Mission 8 The Call, Revenge route from the top (meet beat)"),
    "m8-trap": ("--dev-mission8-trap", "Mission 8 3D trap fight on Route 12 (--m8-cp=1|2|3)"),
    "m8-gantry": ("--dev-mission8-gantry", "Mission 8 3D gantry climb to Vasile"),
    "m8-friends": ("--dev-mission8-friends", "Mission 8 catwalk beat with Vasile"),
    "m8-kill": ("--dev-mission8-kill", "Mission 8 standoff on the catwalk, one shot"),
    "m8-chase": ("--dev-mission8-chase", "Mission 8 tractor chase (--m8-cp=1|2|3|4)"),
    "m8-heli": ("--dev-mission8-heli", "Mission 8 tractor chase helicopter mini-boss"),
    "m8-ending": ("--dev-mission8-ending",
                  "Mission 8 chase ending at the crossing (last jeep down)"),
    "m8-epilogue": ("--dev-mission8-epilogue",
                    "Mission 8 epilogue films (State TV, Commander, funeral)"),
    "m8-credits": ("--dev-mission8-credits", "Mission 8 end credits"),
    # ── Mission 8 (Duty route: Head of State, Slice 1) ──
    "m8-duty": ("--dev-mission8-duty", "Mission 8 Head of State (Duty route) from approach"),
    "m8-mansion": ("--dev-mission8-mansion", "Mission 8 3D Mansion fight with Bodi & Alex (--m8-cp=0..4)"),
    "m8-hall": ("--dev-mission8-hall", "Mission 8 Mansion cp 1: Grand Hall & Andrei M. security room"),
    "m8-study": ("--dev-mission8-study", "Mission 8 Mansion cp 3: kick Retardovici's study door"),
    "m8-helipad": ("--dev-mission8-helipad", "Mission 8 Mansion cp 4: helipad terrace holdout"),
    "m8-liftoff": ("--dev-mission8-liftoff", "Mission 8 study & helicopter liftoff 3D film"),
    "m8-flight": ("--dev-mission8-flight", "Mission 8 Last Flight door-gunner chase (--m8-cp=0..4)"),
    "m8-flight-road": ("--dev-mission8-flight-road", "Mission 8 Last Flight cp 1: Curfew Road chase"),
    "m8-flight-tail": ("--dev-mission8-flight-tail", "Mission 8 Last Flight cp 3: Route 12 tail-rotor takedown"),
    "m8-flight-ucilev": ("--dev-mission8-flight-ucilev", "Mission 8 Last Flight cp 4: Ucilev gunship duel"),
    "m8-crash": ("--dev-mission8-crash", "Mission 8 Duty crash past the ridge 3D film"),
    "m8-ridge": ("--dev-mission8-ridge", "Mission 8 Duty sniper ridge finale (Ucilev & Retardovici)"),
    "m8-duty-epilogue": ("--dev-mission8-duty-epilogue",
                         "Mission 8 Duty epilogue films (Capital Square inauguration)"),
    # ── Trailer bot takes (AI 1 choreography) ──
    "trailer-m1": ("--dev-m1-game",
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


def is_dev_mode(argv=None):
    """Return True when developer hotkeys/tools should be active."""
    if os.environ.get("ACA_DEV") == "1":
        return True
    args = sys.argv[1:] if argv is None else argv
    if any(a.startswith("--dev") or a == "--jump" or a.startswith("--jump=") for a in args):
        return True
    if os.environ.get("ACA_RELEASE") == "1":
        return False
    return not getattr(sys, "frozen", False)
