import pathlib
p=pathlib.Path("src/cutscenes/m5shadow3d.py")
s=p.read_text(encoding="utf-8-sig")
lines=s.splitlines()
# find _camera
for i,l in enumerate(lines,1):
    if l.startswith("def _camera") or l.startswith("def _sky") or l.startswith("def _actors") or l.startswith("def _grade"):
        print(f"{i:4}: {l}")
PY