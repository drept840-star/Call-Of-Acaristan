"""Fetch the pinned official Windows x64 bore release for PyInstaller builds."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

VERSION = "0.6.0"
URL = "https://github.com/ekzhang/bore/releases/download/v0.6.0/bore-v0.6.0-x86_64-pc-windows-msvc.zip"
ARCHIVE_SHA256 = "01709c64fe2787cdc9a21d7030b0f08ad72dff0c36b7ecb72f4f667a55a34b4f"
# Filled from the verified archive. Prevent reuse of an altered local binary.
BINARY_SHA256 = "e8c1096ea01460ba9dbf30017b5eccf2100f63ef2c701930e56fcaca239b48cc"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "bin" / "bore.exe"


def main():
    if DEST.is_file() and hashlib.sha256(DEST.read_bytes()).hexdigest() == BINARY_SHA256:
        print("bore v%s already verified" % VERSION)
        return
    print("Downloading official bore v%s (Windows x64)..." % VERSION)
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("bore archive checksum mismatch; refusing to bundle")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if Path(n).name == "bore.exe"]
        if len(names) != 1:
            raise RuntimeError("release must contain exactly one bore.exe")
        binary = archive.read(names[0])
    if hashlib.sha256(binary).hexdigest() != BINARY_SHA256:
        raise RuntimeError("bore executable checksum mismatch")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(".exe.tmp")
    temp.write_bytes(binary)
    temp.replace(DEST)
    print("Saved " + str(DEST))


if __name__ == "__main__":
    main()
