"""Fetch the pinned official playit.gg agent (playitd) for PyInstaller builds."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from net import playit_agent, tcp_tunnel  # noqa: E402

DEST = ROOT / "assets" / "bin" / "playitd.exe"


def main():
    if tcp_tunnel._sha256_file(str(DEST)) == playit_agent.PLAYITD_SHA256:
        print("playitd v%s already verified" % playit_agent.PLAYITD_VERSION)
        return
    print("Downloading official playitd v%s (Windows x64)..." % playit_agent.PLAYITD_VERSION)
    err = playit_agent.download_playitd(os.fspath(DEST), timeout=60)
    if err:
        raise RuntimeError(err + "; refusing to bundle")
    print("Saved " + str(DEST))


if __name__ == "__main__":
    main()
