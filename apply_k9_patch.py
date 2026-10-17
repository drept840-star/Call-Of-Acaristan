"""Safely install this source patch into the supplied First try project.
Usage: python apply_k9_patch.py "C:\\path\\to\\First try"
No external dependencies. Never touches game saves, settings, or assets.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path,help='Existing game project root containing acaristan.py and src/')
    args=parser.parse_args()
    root=args.project.resolve();bundle=Path(__file__).resolve().parent
    if not (root/'acaristan.py').is_file() or not (root/'src').is_dir():
        parser.error('Choose the game project root containing acaristan.py and src/.')
    if root==bundle:parser.error('Choose your game project, not the patch folder.')
    manifest=json.loads((bundle/'manifest.json').read_text())
    pending=[]
    for name,info in manifest.items():
        source=bundle/name;target=root/name
        if digest(source)!=info['patched_sha256']:
            parser.error(f'Patch file failed its integrity check: {name}')
        actual=digest(target)
        if actual==info['patched_sha256']:continue
        if actual!=info['original_sha256']:
            parser.error(f'{name} differs from the supplied project. Nothing changed; merge it manually to preserve your edits.')
        pending.append(name)
    if not pending:
        print('K9 patch is already installed. Nothing changed.');return
    backup=root/('.k9_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    for name in pending:
        target=root/name
        if target.exists():
            saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
    (backup/'rollback.json').write_text(json.dumps({n:(backup/n).is_file() for n in pending},indent=2))
    installed=[]
    try:
        for name in pending:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(bundle/name,target);installed.append(name)
    except Exception:
        for name in reversed(installed):
            target=root/name;saved=backup/name
            if saved.is_file():shutil.copy2(saved,target)
            elif target.exists():target.unlink()
        raise
    print('Installed K9 cutscene upgrade. Original files backed up in:',backup.name)
    print('Run from your game folder: python tools/k9_pickup_check.py')
    print('Then launch normally: python acaristan.py')


if __name__=='__main__':main()
