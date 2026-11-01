"""Replace the M4 intro shot-list table in missions/m4/meta.py.

The legacy table is the single-owner source for the intro; the JSON timeline
(m4.intro.timeline.json) is its data mirror and was edited first. Both now
describe the same three shots, so the table is rewritten to match.
"""
from pathlib import Path

p = Path("src/missions/m4/meta.py")
raw = p.read_bytes()
assert b"m3_end_nation" in raw, "intro table not found"

start = raw.index(b"import game.timelines as _timelines")
end = raw.index(b"mission4_intro_shots = _timelines.shots(")
end = raw.index(b"\n", end) + 1

new = (
    "import game.timelines as _timelines  # RPE6 P8: timeline data access\r\n"
    "mission4_intro_shots = [\r\n"
    "    {\r\n"
    '        "scene": "m4_street_curfew",\r\n'
    '        "speaker": "NARRATOR",\r\n'
    '        "text": "Forty-eight hours after the Vostral, the address is still\\n"\r\n'
    '                "reading on every screen in the capital.",\r\n'
    '        "lighting": (10, 14, 20),\r\n'
    '        "min_ms": 4200,\r\n'
    '        "caption_after_ms": 2400,\r\n'
    '        "quiet_ui": True,\r\n'
    '        "cues": ((0, "rain", 0.3), (300, "radio_static", 0.12),\r\n'
    '                 (1500, "gunshot_distant", 0.22), (2600, "footstep_walk", 0.14)),\r\n'
    '        "dialogue_events": ((2400, "NARRATOR",\r\n'
    '                             "Forty-eight hours after the Vostral, the address is still\\n"\r\n'
    '                             "reading on every screen in the capital.", False),),\r\n'
    "    },\r\n"
    "    {\r\n"
    '        "scene": "m4_city_curfew",\r\n'
    '        "speaker": "VASILE",\r\n'
    '        "text": "And this is what it bought us. A curfew nobody can enforce\\n"\r\n'
    '                "and a regime that shoots its own order.",\r\n'
    '        "lighting": (12, 10, 16),\r\n'
    '        "min_ms": 3400,\r\n'
    '        "caption_after_ms": 1800,\r\n'
    '        "quiet_ui": True,\r\n'
    '        "cues": ((0, "radio_static", 0.1), (1200, "gunshot_distant", 0.18),\r\n'
    '                 (2200, "m4_breath", 0.3)),\r\n'
    '        "dialogue_events": ((1800, "VASILE",\r\n'
    '                             "And this is what it bought us. A curfew nobody can enforce\\n"\r\n'
    '                             "and a regime that shoots its own order.", True),),\r\n'
    "    },\r\n"
    "    {\r\n"
    '        "scene": "title_card",\r\n'
    '        "speaker": "",\r\n'
    '        "text": "MISSION 4\\nTHE AFTERMATH",\r\n'
    '        "lighting": (5, 5, 8),\r\n'
    '        "min_ms": 2000,\r\n'
    "    },\r\n"
    "]\r\n"
    "mission4_intro_shots = _timelines.shots(\"m4.intro\", mission4_intro_shots)  # RPE6 P8: timeline data\r\n"
).encode("utf-8")

p.write_bytes(raw[:start] + new + raw[end:])
print("patched", p)