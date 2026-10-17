"""Render M5 with the production cutscene player, using the safe M4 capture kit.

Usage: python tools/render_m5_ending.py --label before [--stills-only]
       python tools/render_m5_ending.py --label before --export-video
No app startup, save/profile writes, or replacement of the game's renderer.
"""
import ast
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    label = "review"
    if "--label" in sys.argv:
        idx = sys.argv.index("--label")
        label = sys.argv[idx + 1]
        del sys.argv[idx:idx + 2]
    if not label.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Label must be a simple filename component")
    if "--export-video" in sys.argv:
        p = ROOT / "outputs" / ("m5_ending_" + label + ".mp4")
        data = p.read_bytes()
        index = int(sys.argv[sys.argv.index("--chunk") + 1]) if "--chunk" in sys.argv else 0
        offset, length = index * 160000, 160000
        if offset < 0 or offset >= len(data):
            raise ValueError("Chunk outside video")
        print(json.dumps({"name": p.name, "offset": offset, "total": len(data),
                          "b64": base64.b64encode(data[offset:offset + length]).decode()}))
        return
    source = (ROOT / "tools" / "render_m4_ending.py").read_text(encoding="utf-8-sig")
    source = source.replace("missions.m4.meta", "missions.m5.meta").replace(
        "mission4_ending_shots", "mission5_ending_shots").replace(
        "MISSION4_COMPLETE", "MISSION5_COMPLETE").replace(
        "acaristan_m4_preview_", "acaristan_m5_preview_").replace(
        "ending_camera_sheet.png", "m5_ending_" + label + "_sheet.png").replace(
        "ending_cinematic_preview.mp4", "m5_ending_" + label + ".mp4")
    source = source.replace("_current_ambience=set(),", "_current_ambience=set(), _ambience_epoch=0,")
    tree = ast.parse(source)
    samples = [(0, 900, "01  OTS / LAMP"), (0, 3600, "02  TRACK MARU"),
               (0, 6000, "03  THRESHOLD"), (0, 8600, "04  BIRIBEL / DOT"),
               (1, 2600, "05  SCOPE / SETTLE"), (1, 4600, "06  SCOPE / HOLD"),
               (2, 1200, "07  LIFT OFF"), (2, 3800, "08  FACE / LINE"), (2, 7200, "09  CARRY"),
               (3, 900, "10  TURN"), (3, 1900, "11  ROOF TRACK"), (3, 3500, "12  HANDLE"),
               (3, 3570, "13  CUT TO BLACK"), (4, 3000, "14  RADIO"), (5, 2400, "15  TITLE")]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "samples" for t in node.targets):
            node.value = ast.parse(repr(samples), mode="eval").body
        # Fifteen samples in three columns need five rows (no cropped beats).
        if isinstance(node, ast.Constant) and node.value == (1500, 960):
            node.value = (1500, 1600)
    # Tuples are AST Tuple nodes, not Constants.
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and ast.unparse(node) == "(1500, 960)":
            node.elts[1] = ast.Constant(1600)
    ast.fix_missing_locations(tree)
    ns = {"__file__": str(ROOT / "tools" / "render_m4_ending.py"), "__name__": "m5_capture_kit"}
    exec(compile(tree, "m5_capture_kit", "exec"), ns)
    ns["main"]()


if __name__ == "__main__":
    main()
