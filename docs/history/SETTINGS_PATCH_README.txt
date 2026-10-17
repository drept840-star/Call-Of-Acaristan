CALL OF ACARISTAN - SETTINGS UI PATCH / PART 1 ONLY

INSTALL
1. Extract the full original "First try.zip" into a folder.
2. Extract this patch INTO that project root and allow these files to overwrite.
   Do not put the patch inside an extra nested src/ folder.
3. Run your usual launcher: python acaristan.py (with project dependencies).
Keep assets/, tools/, and all other original files. This ZIP is not a full game.
No saved settings.json, settings backups, profiles, save slots, assets or binary
files are included, so applying the patch does not overwrite player data.

INCLUDED CODE
src/ui/system.py: Settings-only tactical console with six numbered tabs,
  amber/olive theme, corrected layout, control reference, honest video details,
  draggable audio/image meters, state labels, and an explicit command bar.
src/app.py: Settings live-preview and explicit commit flow; Ctrl+S, tab shortcuts,
  failed-save feedback, save-and-back/Esc, and Settings-aware F11 persistence.
src/core/settings_store.py: safe values, clamped ranges, validated enums,
  preserved unrelated keys, atomic commits/backups, and write success result.
RESUME_PROMPT.txt: exact bounded Multiplayer Menu handoff for the next session.

BEHAVIOR
Use Tab / Shift+Tab or 1-6 to change sections. Click toggles/arrow controls;
click or drag audio/image meters. APPLY / SAVE or Ctrl+S writes the profile.
SAVE & BACK or Esc saves before leaving. If saving fails, the menu stays open
with the draft intact; fix file access and retry APPLY. No per-drag write storm.
Window mode is adjustable; fullscreen uses the desktop resolution. The logical
render canvas is 1000x700. The previous resolution selector was non-functional
and is now replaced by accurate read-only information; legacy values are kept.
Cursor-based aim has no look sensitivity/inversion; fixed controls are shown
rather than pretending those options or key remapping work. Melee uses V.

VALIDATION
Bounded settings check passed: clamping/enums, unknown/omitted key preservation,
atomic save/backup recovery, no redundant or per-drag writes, slider endpoints,
keyboard shortcuts, failed-save retention and retry. All six tabs and the
save-error state were rendered at 1000x700 and visually inspected.
Final gate: python -m compileall -q src tools (successful before packaging).
No full-game smoke suite, actual fullscreen switch, Windows build or online-play
validation was run in this bounded pass. Those runtime paths are not certified.
Multiplayer/network modules and all non-settings app definitions were checked
against the original archive and remain unchanged. No Part 2 work was done.
