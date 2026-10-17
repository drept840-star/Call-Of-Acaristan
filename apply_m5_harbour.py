"""Install the M5 harbour graphics into the supplied project, with hash guards.
Usage: python apply_m5_harbour.py "PATH/TO/First try"
Accepts original, M5-reset or M5-rebuild source; never edits assets or saves.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path)
    args=ap.parse_args();root=args.project.resolve();bundle=Path(__file__).resolve().parent
    if not (root/'acaristan.py').is_file() or not (root/'src').is_dir():ap.error('Choose the game root containing acaristan.py and src/.')
    if root==bundle:ap.error('Choose the game folder, not this patch folder.')
    manifest=json.loads((bundle/'manifest.json').read_text());pending=[]
    # All checks complete before the first source file changes.
    for name,info in manifest.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts:ap.error('Unsafe manifest path.')
        source=bundle/rel;target=root/rel
        if digest(source)!=info['patched_sha256']:ap.error('Patch integrity check failed: '+name)
        if target.exists() and not target.is_file():ap.error('Target is not a file: '+name)
        actual=digest(target)
        if actual==info['patched_sha256']:continue
        if actual not in info['accepted_sha256']:ap.error(name+' differs from the supplied original/reset/rebuild. Nothing changed; merge manually to preserve your edits.')
        pending.append(name)
    if not pending:print('M5 harbour graphics already installed. Nothing changed.');return
    backup=root/('.m5_harbour_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));backup.mkdir()
    for name in pending:
        target=root/name
        if target.is_file():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
    (backup/'rollback.json').write_text(json.dumps({n:(backup/n).is_file() for n in pending},indent=2))
    (backup/'README.txt').write_text('Close the game before restoring. For each rollback.json key whose value is true, copy the corresponding backup file to the same relative path in the game root. For each false value, delete that newly installed file. Do not delete other files. Preserve any newer edits before restoring. No save, settings, profile or asset was modified by this installer.\n')
    installed=[]
    try:
        for name in pending:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            # Include the current attempt in rollback if a copy fails midway.
            installed.append(name);shutil.copy2(bundle/name,target)
    except Exception:
        for name in reversed(installed):
            target=root/name;saved=backup/name
            if saved.is_file():shutil.copy2(saved,target)
            elif target.exists():target.unlink()
        raise
    print('Installed M5 harbour graphics. Backup:',backup.name)
    print('Art check: python tools/m5_harbour_art_check.py')
    print('Playback check: python tools/m5_shadow_check.py')
    print('Launch: python acaristan.py')
if __name__=='__main__':main()
