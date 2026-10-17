
import pygame
from core.config import WIDTH, HEIGHT, font_terminal_small, C_TERMINAL
from core.state import STATE
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

class Console:
    def __init__(self):
        self.active = False
        self.input_text = ""
        self.history = []
        self.max_history = 50
        self.font = font_terminal_small
        self.bg_color = (0, 0, 0, 200)
        self.text_color = C_TERMINAL
        self._bindings = {}

    def toggle(self):
        self.active = not self.active
        self.input_text = ""

    def bind(self, name, fn):
        """RPE6 P10: app-injected actions (scene, timeline) for dev commands."""
        self._bindings[name] = fn

    def handle_event(self, event):
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKQUOTE:
                self.toggle()
                return True
            if event.key == pygame.K_RETURN:
                self.execute_command(self.input_text)
                self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.input_text += event.unicode
            return True
        return False

    def execute_command(self, cmd):
        cmd = cmd.strip()
        if not cmd:
            return
        self.history.append(f"> {cmd}")
        if len(self.history) > self.max_history:
            self.history.pop(0)

        parts = cmd.split()
        command = parts[0].lower()

        if command == "godmode":
            STATE.godmode = not getattr(STATE, "godmode", False)
            self.add_message(f"Godmode: {'ON' if STATE.godmode else 'OFF'}")

        elif command == "spawn_enemy":
            if STATE.player:
                px, py = STATE.player.rect.centerx, STATE.player.rect.centery
                try:
                    from entities.enemy_ai import Enemy
                    e = Enemy(px + 100, py)
                    STATE.enemies.append(e)
                    self.add_message("Enemy spawned")
                except ImportError:
                    self.add_message("Cannot import Enemy")
            else:
                self.add_message("No player")

        elif command == "teleport":
            if len(parts) >= 3 and STATE.player:
                try:
                    x, y = int(parts[1]), int(parts[2])
                    STATE.player.rect.centerx = x
                    STATE.player.rect.centery = y
                    self.add_message(f"Teleported to ({x}, {y})")
                except ValueError:
                    self.add_message("Usage: teleport X Y")
            else:
                self.add_message("Usage: teleport X Y")

        elif command == "give_ammo":
            wep = getattr(STATE, "current_weapon", "pistol")
            if wep == "os12":
                STATE.os12_ammo_in_mag = STATE.os12_mag_size
                STATE.os12_spare_mags = 10
            else:
                STATE.ammo_in_mag = STATE.mag_size
                STATE.spare_mags = 10
            self.add_message("Ammo refilled")

        elif command == "heal":
            if STATE.player:
                STATE.player.hp = getattr(STATE.player, "max_hp", 100)
                self.add_message("Player healed to full HP")

        elif command == "fixedstep":
            # Toggle the multiplayer fixed-timestep accumulator by hand.
            # Useful for A/B-ing game feel without needing a second player.
            from core import fixedstep as _fs
            if len(parts) >= 2 and parts[1].lower() in ("on", "off"):
                now = _fs.set_enabled(parts[1].lower() == "on")
                self.add_message("fixedstep %s" % ("ON" if _fs.is_enabled() else "OFF"))
            else:
                _fs.set_enabled(not _fs.is_enabled())
            c = _fs.clock()
            self.add_message("fixedstep %s | %d Hz | dropped %d"
                             % ("ON" if _fs.is_enabled() else "OFF",
                                int(c.hz), c.dropped_steps))

        elif command == "set_stage":
            if len(parts) >= 2:
                stage = parts[1]
                mission = getattr(STATE, "active_mission", "MISSION1")
                if mission == "MISSION2":
                    try:
                        from missions.m2 import STAGE_INVESTIGATE, STAGE_SNIPER, STAGE_COMBAT, STAGE_TRUCK, STAGE_TANKER, STAGE_RUN, STAGE_BLACKOUT, STAGE_EVIDENCE, STAGE_UPLOAD, STAGE_EXFIL, STAGE_DONE
                        stage_map = {
                            "investigate": STAGE_INVESTIGATE,
                            "sniper": STAGE_SNIPER,
                            "combat": STAGE_COMBAT,
                            "truck": STAGE_TRUCK,
                            "tanker": STAGE_TANKER,
                            "run": STAGE_RUN,
                            "blackout": STAGE_BLACKOUT,
                            "evidence": STAGE_EVIDENCE,
                            "upload": STAGE_UPLOAD,
                            "exfil": STAGE_EXFIL,
                            "done": STAGE_DONE,
                        }
                    except ImportError:
                        self.add_message("Cannot import mission2 stages")
                        return
                elif mission == "MISSION3":
                    try:
                        from missions.m3 import STAGE_INTERROGATION, STAGE_BREAKOUT, STAGE_COMMS, STAGE_ARCHIVES, STAGE_KILL_ORDER, STAGE_BROADCAST, STAGE_DONE
                        stage_map = {
                            "interrogation": STAGE_INTERROGATION,
                            "breakout": STAGE_BREAKOUT,
                            "comms": STAGE_COMMS,
                            "archives": STAGE_ARCHIVES,
                            "kill_order": STAGE_KILL_ORDER,
                            "broadcast": STAGE_BROADCAST,
                            "done": STAGE_DONE,
                        }
                    except ImportError:
                        self.add_message("Cannot import mission3 stages")
                        return
                else:
                    self.add_message(f"No stage support for {mission}")
                    return
                if stage in stage_map:
                    STATE.mission_stage = stage_map[stage]
                    if hasattr(STATE, "mission2_stage"):
                        STATE.mission2_stage = stage_map[stage]
                    if hasattr(STATE, "mission3_stage"):
                        STATE.mission3_stage = stage_map[stage]
                    self.add_message(f"Stage set to {stage}")
                else:
                    self.add_message(f"Unknown stage: {stage}")
            else:
                self.add_message("Usage: set_stage <stage>")

        elif command == "scene":
            fn = self._bindings.get("scene")
            if fn and len(parts) >= 2:
                self.add_message(fn(parts[1]))
            else:
                self.add_message("Usage: scene <STATE> (MENU, GAME, PAUSED...)")

        elif command == "timeline":
            fn = self._bindings.get("timeline")
            if fn and len(parts) >= 3 and parts[1] == "play":
                t = int(parts[3]) if len(parts) > 3 else 0
                self.add_message(fn(parts[2], t))
            else:
                self.add_message("Usage: timeline play <id> [t_ms]")

        elif command == "seed":
            import random
            from engine.core import LEGACY_RNG
            if len(parts) >= 2:
                n = int(parts[1])
                random.seed(n)
                LEGACY_RNG.seed(n)
                self.add_message(f"seed set to {n} (random + legacy streams)")
            else:
                self.add_message(f"seed: random idx={random.getstate()[1][-1]} legacy idx={LEGACY_RNG.getstate()[1][-1]}")

        elif command == "heat":
            fn = self._bindings.get("heat")
            self.add_message(fn(parts[1] if len(parts) > 1 else None) if fn
                             else "heat: no mission bound")

        elif command == "reload":
            fn = self._bindings.get("reload")
            self.add_message(fn() if fn else "reload: not bound")

        elif command == "golden":
            self.add_message(self._run_tool("ae_golden.py", ["capture"]))

        elif command == "bench":
            self.add_message(self._run_tool("ae_bench.py", []))

        elif command == "events":
            fn = self._bindings.get("events")
            if fn:
                for line in fn():
                    self.add_message(line)
            else:
                self.add_message("events: no bus bound")

        elif command == "set":
            from game.devtools import DEV as _DEV
            if len(parts) >= 3:
                self.add_message(_DEV.set_field(parts[1], " ".join(parts[2:])))
            else:
                self.add_message("Usage: set <field> <value> (F3 + click an entity first)")

        elif command == "spawn" and len(parts) >= 2 and parts[1] == "prefab":
            from game.devtools import DEV as _DEV
            if len(parts) >= 3:
                px = int(parts[3]) if len(parts) > 3 else (STATE.player.rect.centerx if STATE.player else 0)
                py = int(parts[4]) if len(parts) > 4 else (STATE.player.rect.centery if STATE.player else 0)
                self.add_message(_DEV.spawn_prefab(parts[2], px, py))
            else:
                self.add_message("Usage: spawn prefab <id> [x y]")

        elif command == "tl_list":
            import os
            from game import timelines as _tl
            ids = [f[:-len(".timeline.json")] for f in sorted(os.listdir(_tl.TIMELINES_DIR))
                   if f.endswith(".timeline.json")]
            self.add_message(f"timelines: {', '.join(ids)}")

        elif command == "tl_keys":
            from game import timelines as _tl
            try:
                tl = _tl.timeline(parts[1])
                self.add_message(f"{tl.id}: {len(tl.shots)} shots, tracks={list(tl.tracks)}")
                for i, sh in enumerate(tl.shots[:12]):
                    self.add_message(f"  [{i}] {sh.get('scene', '?')} t={sh.get('min_ms', '-')} sp={sh.get('speaker', '')}")
            except Exception as e:
                self.add_message(f"tl_keys failed: {e!r}")

        elif command in ("tl_set", "tl_nudge", "tl_mark"):
            self._tl_edit(command, parts)

        elif command == "list":
            self.add_message("Commands: godmode, spawn_enemy, spawn prefab <id>, teleport X Y, give_ammo, heal, set_stage <stage>, scene <STATE>, timeline play <id> [t], seed [n], heat [n], reload, golden, bench, events, set <field> <value>, list, help")

        elif command == "help":
            self.add_message("godmode - toggle invincibility")
            self.add_message("spawn_enemy - spawn enemy near player")
            self.add_message("teleport X Y - move player to coordinates")
            self.add_message("give_ammo - refill current weapon ammo")
            self.add_message("heal - restore player HP to max")
            self.add_message("set_stage <stage> - change mission stage")
            self.add_message("list - show all commands")

        else:
            self.add_message(f"Unknown: {command}. Type 'list' for commands.")

    def _tl_edit(self, command, parts):
        """Timeline editor commands (RPE6 P10, SS6.20): write data files only."""
        import json
        from game import timelines as _tl

        def _val(txt):
            try:
                return json.loads(txt)
            except Exception:
                return txt

        try:
            if command == "tl_mark":
                # tl_mark <id> <name> <t_ms> - append a marker to metadata
                tl = _tl.timeline(parts[1])
                data = json.loads(json.dumps(tl.data))
                marks = data.setdefault("metadata", {}).setdefault("markers", [])
                marks.append({"name": parts[2], "t": int(parts[3])})
                _tl.save_timeline(parts[1], data)
                self.add_message(f"marker {parts[2]!r}@{parts[3]}ms added to {parts[1]}")
                return
            tl = _tl.timeline(parts[1])
            data = json.loads(json.dumps(tl.data))
            shot = data["shots"][int(parts[2])]
            key = parts[3]
            if command == "tl_set":
                shot[key] = _val(" ".join(parts[4:]))
                msg = f"{parts[1]} shot {parts[2]}: {key} = {shot[key]!r}"
            else:
                shot[key] = float(shot.get(key, 0)) + float(parts[4])
                msg = f"{parts[1]} shot {parts[2]}: {key} -> {shot[key]}"
            _tl.save_timeline(parts[1], data)
            self.add_message(msg + " (saved; reload + replay to see it)")
        except Exception as e:
            self.add_message(f"{command} failed: {e!r}")

    def _run_tool(self, script, args):
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        try:
            r = subprocess.run([sys.executable, str(root / "tools" / script), *args],
                               cwd=str(root), capture_output=True, text=True, timeout=300)
            tail = (r.stdout or r.stderr).strip().splitlines()
            return f"{script}: {tail[-1] if tail else 'done'}"
        except Exception as e:
            return f"{script} failed: {e!r}"

    def add_message(self, msg):
        self.history.append(f"  {msg}")

    def draw(self, surface):
        if not self.active:
            return
        console_h = 250
        bg = pygame.Surface((WIDTH, console_h), pygame.SRCALPHA)
        bg.fill(self.bg_color)
        surface.blit(bg, (0, HEIGHT - console_h))

        line_h = 16
        visible = (console_h - 30) // line_h
        start = max(0, len(self.history) - visible)
        y = HEIGHT - console_h + 10
        for line in self.history[start:]:
            txt = self.font.render(line, True, self.text_color)
            surface.blit(txt, (10, y))
            y += line_h

        prompt = self.font.render(f"> {self.input_text}", True, self.text_color)
        surface.blit(prompt, (10, y))
        if _now_ms() % 800 < 400:
            cursor = self.font.render(_T("console.text"), True, self.text_color)
            surface.blit(cursor, (10 + prompt.get_width(), y))
