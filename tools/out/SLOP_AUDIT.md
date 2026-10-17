# M5 cutscene audit ("AI-slop" pass)

Sheets: `tools/out/audit_sheet_*.jpg` (re-render: `python tools/_audit_sheet.py`,
env `AUDIT_T`, `AUDIT_SCALE`, `AUDIT_ONLY`). Anchor shot: `bulletin_before.jpg`,
`bulletin_after.jpg`, `bulletin_2d.jpg`.

Categories: 1 staging/framing, 2 lighting/effects, 3 set dressing, 4 wording, 5 fallback/consistency.

## Fixed

| # | Where | Shot | Cat | Sev | Problem | Fix |
|---|-------|------|-----|-----|---------|-----|
| 1 | m5martial3d.py:_bulletin + new m5studio.py | m5_tv_bulletin | 1,3 | high | Generic studio: symmetrical flags, empty wall, no story on screen | Rebuilt set: news wall with mourning portrait of Balaceanu, BREAKING band, angled flats, lamp truss, one flag, push-in camera |
| 2 | m5studio.py:draw_bulletin_2d | m5_tv_bulletin (2D) | 5 | high | Old fallback drew Balaceanu as the anchor; the first new version hid the anchor behind the desk | Same layout as the 3D shot, anchor (vasile rig + ANCHOR_WARDROBE) shown from the chest up |
| 3 | m5mid3d.py:_breach | m5x_breach | 2 | med | Full-width anamorphic streak across the frame (stock lens-flare look) | `_glare(..., streak=False)`, smaller bloom |
| 4 | m5mid3d.py:_breach | m5x_breach | 1 | med | Guard's head cut by the top of the frame | Camera/target raised (1.35->1.45, 1.40->1.62) |
| 5 | m5mid3d.py:_squadmate | m5x_squadmate | 1 | med | Both faces cut off at the top during the handshake | Camera 1.40->1.52, target 1.35->1.50 |
| 6 | m5martial3d.py:_reveal | m5_ucilev_reveal | 1 | med | The reveal shot cut his face at the top of the frame | Target sy+1.35 -> sy+1.58 |
| 7 | missions/m5/meta.py (arrival) | m5x_pw_arrival_wide | 4 | low | Greeting-card line | see dialogue |
| 8 | missions/m5/meta.py (intro) | m5x_barracks | 4 | low | Over-written triple beat | see dialogue |

### Dialogue changes (old -> new)
- Arrival: "The MAG Print Works. Four floors of brick that still print the truth."
  -> "The MAG Print Works. Four floors of brick, and the presses still run."
- Barracks (Biribel): "My whole unit, in the President's black. My friends. If this ever turns, they're who I'll be shooting at."
  -> "My whole unit in the President's black. If this turns, I'll be shooting at my friends."

## Later (not fixed)

| Where | Shot | Cat | Sev | Note |
|-------|------|-----|-----|------|
| m5martial3d.py:_address | m5_retardovici_tv | 3 | low | Mirror-perfect curtains/flags; the president is small in frame. Could be intentional propaganda staging |
| m5mid3d.py:_breach | m5x_breach | 2 | low | Ucilev in the doorway reads as a grey blur, not a backlit silhouette |
| m5mid3d.py:_faces_set | m5x_faces_wide/release | 3 | low | Plain red block on the back wall looks like a placeholder |
| m5mid3d.py:_maru_close | m5x_maru_close | 1 | low | Very tight crop, eyes close to the frame top |
| m5mid3d.py:draw_m5x_2d | all m5x_* (2D) | 5 | low | Generic 2D fallback (gradient + cast in a row); only seen if 3D fails |
