# Revert Mission 5 audio upgrade

This restores the source from before the audio upgrade.

If you applied mission5_audio.patch, revert it from your repository root:

    git apply --reverse --check mission5_audio.patch
    git apply --reverse mission5_audio.patch

Otherwise, copy the original src/ files in this archive over the upgraded files, then remove these three files introduced by the upgrade:

- src/audio/m5_finale.py
- tests/unit/test_m5_finale_audio.py
- tools/export_m5_audio.py

Do not overwrite files if you have since made unrelated edits; reverse/merge only the upgrade changes instead.

game_source_reverted.txt is a byte-for-byte copy of your original supplied text export. No campaign saves or recorded audio assets were changed.
