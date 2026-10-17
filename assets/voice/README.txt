VOICE-OVER FILES
================
Put recorded lines here, named by their ID from voice_lines_by_speaker.xlsx:
    assets/voice/VO_025.ogg      (or .wav / .mp3 / .flac)
Sub-folders are fine:  assets/voice/VASILE/VO_025.ogg

Record EVERYTHING CLEAN (no radio effect). The game adds the radio filter
itself whenever a line is heard over comms (in-game radio, cutscene shots
tagged "radio": True, PA/dispatch voices, Balaceanu's monitor tape).
The same file plays clean when the character is in the room.

Lines with no file just stay as text, so you can add audio a bit at a time.
The game writes processed radio versions to assets/voice/_radio_cache/
(safe to delete; it rebuilds automatically).

NO TIME TO RENAME?
Put a speaker's files in a folder named after their tab in the spreadsheet
(Vasile, Volkov, Biribel, Maru, Balaceanu, Narrator, ...). Files that aren't
named VO_xxx are matched to that speaker's lines IN SPREADSHEET ORDER,
oldest file first (by the time in the file name, e.g. "Generated Audio
October 07, 2026 - 9_33_05 PM.wav", or by date modified) and lined up by
LENGTH, so a skipped line or an extra retake doesn't shift everything after
it. Extra takes are listed at the bottom of <speaker>_matches.txt; lines
with no audio are marked NO AUDIO there.
The game writes <speaker>_matches.txt here so you can check which file
plays for which line. To replace one bad take, drop in VO_031.wav - named
files always win, and the rest stay in order.

DEATH SCREAMS (Route 12 sniper film)
Option 1 (best): separate files - assets/voice/death/gabi.wav, seby.wav,
darius.wav (any name with the character + "death" or "scream" works, e.g.
Darius/darius_scream.wav). Each plays on the exact frame the round hits.
These never get mixed up with normal lines.
Option 2: scream recorded onto the END of the line clip (VO_110, VO_115,
VO_116). The game finds where the scream starts and fires the shot there.
If the timing's off, set it by hand in src/audio/voice_manifest.py:
    DEATH_AT = {"VO_110": 1.35}     # seconds into the clip
