"""PyInstaller entry point for the self-hosted lobby EXE.

Kept as a separate file from mp_host.py so the console (not --windowed) is
used: a host NEEDS to see the address to share it, the connection count, and
any firewall/port-forwarding instructions. A silent GUI host would be worse
than useless.

Build with tools/build_host_exe.bat.
"""

import os
import sys

# mp_host.py lives next to this file and does its own sys.path setup for src/
# and tools/, so importing it is all that is needed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mp_host  # noqa: E402

if __name__ == "__main__":
    # When frozen, argparse must not try to read PyInstaller's own argv.
    argv = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv[1:]
    raise SystemExit(mp_host.main(argv))

