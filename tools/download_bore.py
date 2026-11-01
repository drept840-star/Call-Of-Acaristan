"""Fetch the pinned official Windows x64 bore release for PyInstaller builds."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from net import tcp_tunnel  # noqa: E402

DEST = ROOT / "assets" / "bin" / "bore.exe"


def main():
    if tcp_tunnel._sha256_file(str(DEST)) == tcp_tunnel.BORE_BINARY_SHA256:
        print("bore v%s already verified" % tcp_tunnel.BORE_VERSION)
        return
    print("Downloading official bore v%s (Windows x64)..." % tcp_tunnel.BORE_VERSION)
    err = tcp_tunnel.download_bore(os.fspath(DEST), timeout=60)
    if err:
        raise RuntimeError(err + "; refusing to bundle")
    print("Saved " + str(DEST))


if __name__ == "__main__":
    main()
