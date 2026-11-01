"""dev_panel.py - clickable dev control panel for jumping into missions.

Run from the repo root::

    python tools/dev_panel.py

Opens a dark, terminal-styled window with one button per dev jump target -
the same registry as ``acaristan.py --jump NAME`` (see
``src/core/dev_jumps.py``). Click a target to launch the game at that
mission; its description sits next to the button so nothing needs hovering.
Anything typed in the "extra args" field (e.g. ``--continue`` for slot-select,
``--no-upload`` / ``--with-tests`` for the packaging zips) is forwarded to
whichever target launches. Trailer-bot takes additionally get
``--trailer-bot --trailer-act <act>`` appended automatically.

Layout, top to bottom::

    header   title + live "visible/total targets · running" counts
    filter   type to narrow the list (matches target name or description)
    body     scrollable, grouped target list in mission order, plus a
             "Packaging" group (full / slim / handoff zip via tools/zip_project.py)
             and a "Source" group (build all source .py -> TXT via
             tools/build_code_txt.py --all, plus a directory-tree TXT listing
             every project file, any type (source_dir.txt)
     footer   extra args, Copy command, Stop all games, status line

Keyboard: ↑/↓ walk the visible targets, Enter launches the selected one,
Ctrl+F jumps to the filter, and Esc clears the filter plus the selection.
Handy: right-click any target to copy its command without launching.

Structure notes:
    * ``GROUPS`` defines the display order. The panel self-checks that every
      ``DEV_JUMPS`` entry is filed under exactly one group and reports any
      drift in the status line, so the registry and the panel cannot silently
      fall out of sync as new jumps are added.
    * ``TOOL_TARGETS`` (the "Packaging" group) are not dev jumps: they run
      ``tools/zip_project.py`` with a fixed base argv instead of
      ``acaristan.py --jump``. Extra args from the footer still append, so
      ``--no-upload`` / ``--with-tests`` can be passed from the panel.
    * ``grouped_targets`` / ``build_launch_cmd`` / ``build_tool_cmd`` /
      ``parse_extra_args`` are pure and import-safe, so they can be exercised
      without a Tk root.
"""
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from textwrap import wrap
from tkinter import ttk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.dev_jumps import DEV_JUMPS

# ── Display groups: (section label, [target names]) ──
# Order here is the panel's order. Keep in sync with DEV_JUMPS - the panel
# warns (in the status line) about any entry that is missing or duplicated.
GROUPS = [
    ("Mission 0", ["m0"]),
    ("Mission 1", ["m1", "m1-safe"]),
    ("Walking sim", ["walk", "walk-after"]),
    ("Mission 2", ["m2", "m2-game", "m2-sniper", "m2-after-sniper",
                   "m2-flank", "m2-truck", "m2-evidence"]),
    ("Mission 3", ["m3", "m3-game", "m3-comms", "m3-archives",
                   "m3-kill-order", "m3-ledger", "m3-vostral",
                   "m3-archives-cutscene", "m3-broadcast-transition",
                   "m3-broadcast", "m3-upload"]),
    ("Mission 4", ["m4", "m4-game", "m4-station", "m4-tower"]),
    ("Mission 5", ["m5", "m5-hq", "m5-game", "m5-printworks",
                   "m5-tunnel", "m5-ending"]),
    ("Mission 6", ["m6", "m6-game", "m6-crossing", "m6-rail", "m6-boxcar",
                   "m6-train", "m6-3d", "m6-shootout", "m6-yard",
                   "m6-heli", "m6-ending"]),
    ("Mission 7", ["m7", "m7-arrival", "m7-chores", "m7-runner", "m7-prep",
                   "m7-raid", "m7-raid-prepped", "m7-raid-w2", "m7-raid-w3",
                   "m7-finale", "m7-choice", "m7-outro"]),
    ("Trailer bot", ["trailer-m1", "trailer-m2-killbox", "trailer-m2-evidence",
                     "trailer-m3-breakout", "trailer-m3-comms"]),
    ("Misc", ["slot-select", "audio-parade"]),
    ("Multiplayer", ["mp-host", "mp-join"]),
]

# ── Palette: warm dark ground + terminal green, matching the in-game HUD ──
# (C_BG_GAME = 45,42,38 and C_TERMINAL = 50,255,150 in core/config.py.)
# Trailer takes need the bot driver + act, not just the mission start flag.
# ``build_launch_cmd`` appends these automatically (unless the user already
# typed ``--trailer-bot`` in extra args). Act names from tools/trailer_bot.
TRAILER_ACTS = {
    "trailer-m1": "act1",
    "trailer-m2-killbox": "act2_killbox",
    "trailer-m2-evidence": "act2_evidence",
    "trailer-m3-breakout": "act3_breakout",
    "trailer-m3-comms": "act3_relay",
}

# ── Packager targets: full / slim zip via tools/zip_project.py ──
# Rendered as their own "Packaging" group. Not DEV_JUMPS entries (they are
# not missions), so they stay out of ``GROUPS`` and the drift check; the
# base argv lives here and ``build_tool_cmd`` turns it into a launch line.
ZIP_TOOL = "tools/zip_project.py"
TOOL_TARGETS = {
    "zip": ("Full project snapshot zip + Pixeldrain upload", []),
    "zip-slim": ("Slim playable bundle (--slim): runtime essentials only",
                 ["--slim"]),
    "zip-handoff": ("Handoff zip (--handoff): tests + .wolf + plan, for review",
                    ["--handoff"]),
}

# ── Source-code bundle actions: all source .py -> one TXT, plus directory tree ──
SOURCE_TXT_TOOL = "tools/build_code_txt.py"
SOURCE_TXT_TARGET = "source-txt"
SOURCE_TXT_DESC = (
    "Build all source code files into a TXT "
    "(tools/build_code_txt.py --all), plus the full directory tree")
SOURCE_DIR_TXT_TARGET = "source-dir-txt"
SOURCE_DIR_TXT_DESC = "Write a TXT tree of every project file (any type, with sizes)"
SOURCE_DIR_TXT_OUT = ROOT / "archive" / "TXTs" / "source_dir.txt"
SOURCE_DIR_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".venv", "venv", "env",
    "build", "dist", ".pytest_cache", ".mypy_cache", "PDFs", "TXTs", "archive",
    "graphify-out",  # gitignored 32 MB code-graph cache, not project content
})
# Machine-local trackers, not part of the project's file set.
SOURCE_DIR_SKIP_FILES = frozenset({
    ".pixeldrain_last_id", ".pixeldrain_last_id_slim", ".pixeldrain_last_id_handoff",
})
THEME = {
    "app":          "#090d0b",
    "header":       "#0d1410",
    "panel":        "#111914",
    "panel_alt":    "#141e18",
    "panel_hover":  "#19271f",
    "button":       "#17231b",
    "button_hover": "#22352a",
    "border":       "#24342a",
    "border_hot":   "#3f7053",
    "text":         "#e7f4eb",
    "muted":        "#83948a",
    "dim":          "#4d5e54",
    "accent":       "#44ff9a",
    "accent_soft":  "#a0ffc8",
    "accent_dark":  "#123523",
    "accent_hover": "#1d4c32",
    "cyan":         "#6ec8ff",
    "on_accent":    "#06110a",
    "danger":       "#ff6b66",
    "danger_hover": "#3a2020",
    "amber":        "#ffc45c",
    "warn":         "#ffc45c",
}


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (import-safe, no Tk required)
# ─────────────────────────────────────────────────────────────────────────────
def grouped_targets():
    """Yield (group_label, [(name, description), ...]) for the panel.

    Targets missing from ``DEV_JUMPS`` are skipped rather than crashing, so a
    stale name in ``GROUPS`` degrades to a reported drift instead of a
    traceback (see :func:`group_issues`).
    """
    for label, names in GROUPS:
        yield label, [(n, DEV_JUMPS[n][1]) for n in names if n in DEV_JUMPS]


def build_launch_cmd(target, extra_args=()):
    """Pure helper (headless-testable): argv to launch the game at target.

    Trailer takes also get ``--trailer-bot --trailer-act <act>`` appended
    (unless the user already passed ``--trailer-bot``), otherwise the button
    would boot a plain mission start instead of the described bot take.
    """
    cmd = [sys.executable, str(ROOT / "acaristan.py"), "--jump", target]
    cmd.extend(a for a in extra_args if a != "--")
    act = TRAILER_ACTS.get(target)
    if act is not None and "--trailer-bot" not in cmd:
        cmd.extend(["--trailer-bot", "--trailer-act", act])
    return cmd


def build_tool_cmd(target, extra_args=()):
    """Pure helper (headless-testable): argv to run a packaging tool target.

    Same contract as :func:`build_launch_cmd` but for ``TOOL_TARGETS``:
    the base argv from the table plus any extra args (``--no-upload``,
    ``--with-tests``, ...) typed in the footer.
    """
    _desc, base_args = TOOL_TARGETS[target]
    cmd = [sys.executable, str(ROOT / ZIP_TOOL)]
    cmd.extend(base_args)
    cmd.extend(a for a in extra_args if a != "--")
    return cmd


def parse_extra_args(text):
    """Split the footer's extra-args field into argv tokens (drop bare ``--``)."""
    return [tok for tok in text.split() if tok != "--"]


def group_issues():
    """Report drift between ``GROUPS`` and ``DEV_JUMPS``.

    Returns ``(missing, duplicated, unknown)`` - sorted name lists for
    registry entries filed nowhere, names filed under two groups, and group
    entries that no longer exist in the registry.
    """
    filed = [name for _label, names in GROUPS for name in names]
    duplicated = sorted({n for n in filed if filed.count(n) > 1})
    missing = sorted(n for n in DEV_JUMPS if n not in filed)
    unknown = sorted(n for n in filed if n not in DEV_JUMPS)
    return missing, duplicated, unknown


# ── Source-code bundle: all source .py -> one TXT, plus full directory tree ──
def build_source_txt_cmd(extra_args=()):
    """Pure helper (headless-testable): argv that builds all source .py -> one TXT.

    Runs ``tools/build_code_txt.py --all``: every source file the builder finds
    gets bundled into the combined TXT (plus per-file TXTs) under
    ``archive/TXTs/``.
    """
    cmd = [sys.executable, str(ROOT / SOURCE_TXT_TOOL), "--all"]
    cmd.extend(a for a in extra_args if a != "--" and not a.startswith("-"))
    return cmd


def source_dir_files(root=ROOT):
    """Sorted project-relative paths of every project file (junk pruned).

    Unlike the code bundle (``.py`` only) this keeps every file type - audio,
    video, art, maps, docs - so the tree shows what else lives in the repo.
    Dotted *directories* (.git, .venv, .wolf, ...) are always skipped; dotted
    files such as ``.gitignore`` or ``assets/baked/*/.bakeinfo.json`` are kept.
    """
    found = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SOURCE_DIR_SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        if not path.is_file() or path.name in SOURCE_DIR_SKIP_FILES:
            continue
        found.append(rel)
    return sorted(found, key=lambda p: str(p).replace("\\", "/").lower())


def _format_size(size):
    """Human-readable file size (1.2 MiB, 940 KiB, 12 B)."""
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KiB", "MiB", "GiB"):
        value /= 1024
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
    return f"{value:.1f} GiB"


def _count_files(node):
    return sum(1 if children is None else _count_files(children)
               for children in node.values())


def _walk_tree(node, rel, prefix, sizes, lines):
    """Append (label, info) tree rows depth-first: directories before files."""
    entries = sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))
    for index, (name, children) in enumerate(entries):
        last = index == len(entries) - 1
        connector = "└── " if last else "├── "
        child_rel = f"{rel}/{name}" if rel else name
        if children is None:
            info = _format_size(sizes.get(child_rel, 0))
            lines.append((f"{prefix}{connector}{name}", info))
        else:
            count = _count_files(children)
            info = f"{count:,} file" if count == 1 else f"{count:,} files"
            lines.append((f"{prefix}{connector}{name}/", info))
            _walk_tree(children, child_rel, prefix + ("    " if last else "│   "),
                       sizes, lines)


def render_dir_listing(paths, root=ROOT):
    """Render relative paths as a header + aligned directory tree (text)."""
    tree = {}
    sizes = {}
    for rel in paths:
        parts = Path(rel).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None
        try:
            sizes[Path(rel).as_posix()] = (root / rel).stat().st_size
        except OSError:
            pass

    rows = []
    _walk_tree(tree, "", "", sizes, rows)
    # Cap the name column: a handful of very deep paths would otherwise push
    # every other row's size info half a screen to the right.
    width = min(max((len(label) for label, _info in rows), default=0), 72)

    total_files = len(paths)
    total_size = _format_size(sum(sizes.values()))
    # Dotted dirs are covered by the note below, so list only the named ones.
    pruned = " ".join(sorted((d for d in SOURCE_DIR_SKIP_DIRS
                              if not d.startswith(".")), key=str.lower))
    rule = "# " + "=" * 74
    header = [
        rule,
        "# PROJECT DIRECTORY LISTING - every project file, any type",
        f"# Root   : {Path(root).as_posix()}",
        f"# Files  : {total_files:,}   Total: {total_size}   "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "# Legend : directory/ -> files inside | file -> size on disk",
    ]
    for index, chunk in enumerate(wrap(
            f"Pruned : {pruned} (plus every dotted directory: .git, .venv, .wolf, ...)",
            width=71, subsequent_indent="         ")):
        header.append("# " + chunk)
    header.extend([rule, "", f"{Path(root).name}/"])
    body = [f"{label.ljust(width)}  {info}" for label, info in rows]
    return "\n".join(header + body) + "\n"


def write_source_dir_txt(txt_path=SOURCE_DIR_TXT_OUT, files=None, root=ROOT):
    """Write a TXT directory tree of every project file, every type."""
    paths = source_dir_files(root) if files is None else files
    txt_path = Path(txt_path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(render_dir_listing(paths, root), encoding="utf-8")
    print(f"Written: {txt_path}")
    return txt_path


def source_txt_action(extra_args=()):
    """Dev-panel action: build all source code files into a single TXT,
    plus the full project directory tree (source-dir-txt content) appended at
    the end."""
    cmd = build_source_txt_cmd(extra_args)
    subprocess.Popen(cmd, cwd=str(ROOT)).wait()
    combined = ROOT / "archive" / "TXTs" / "selected_source.txt"
    listing = write_source_dir_txt()
    with combined.open("a", encoding="utf-8") as fh:
        fh.write("\n\n")
        fh.write(listing.read_text(encoding="utf-8"))
    return ("Built source code txt: all source files + full directory tree -> "
            "archive/TXTs/selected_source.txt")


def source_dir_action(extra_args=()):
    """Dev-panel action: write a TXT that is just the directory listing."""
    return f"Directory listing written: {write_source_dir_txt(SOURCE_DIR_TXT_OUT)}"


SOURCE_ACTIONS = {
    SOURCE_TXT_TARGET: (SOURCE_TXT_DESC, source_txt_action),
    SOURCE_DIR_TXT_TARGET: (SOURCE_DIR_TXT_DESC, source_dir_action),
}


# ─────────────────────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────────────────────
class DevPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Acaristan // Mission Control")
        self.minsize(760, 520)
        self.geometry("960x740")

        self._procs = []
        self._entries = []
        self._group_widgets = {}
        self._last_target = None
        self._selected = None
        self._pulse_phase = False

        mono = {
            "win32": "Cascadia Mono",
            "darwin": "SF Mono",
        }.get(sys.platform, "DejaVu Sans Mono")
        ui = {
            "win32": "Segoe UI",
            "darwin": "SF Pro Display",
        }.get(sys.platform, "DejaVu Sans")

        self.font_title = (mono, 20, "bold")
        self.font_group = (mono, 10, "bold")
        self.font_mono = (mono, 10)
        self.font_button = (mono, 9, "bold")
        self.font_metric = (mono, 10, "bold")
        self.font_ui = (ui, 9)
        self.font_small = (ui, 8)

        self._apply_theme()
        self._build_header()
        self._build_filter()
        self._build_body()
        self._build_footer()

        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._apply_filter()
        self._set_status(self._default_status())
        self._bind_keys()
        self.after(10, self._enable_dark_titlebar)
        self.after(650, self._pulse_live)
        self.after(1000, self._reap)

    def _enable_dark_titlebar(self):
        """Ask Windows to paint a dark caption (no-op off Windows / on failure).

        Tk owns only the client area - the title bar is OS chrome, so it stays
        light by default and breaks the dark theme. Windows 10 20H1+ exposes
        ``DWMWA_USE_IMMERSIVE_DARK_MODE`` (attribute 20); older builds used 19.
        If neither is supported we simply keep the light caption.
        """
        if sys.platform != "win32":
            return
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            enabled = ctypes.c_int(1)
            for attribute in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attribute, ctypes.byref(enabled),
                        ctypes.sizeof(enabled)) == 0:
                    break
        except Exception:
            pass  # cosmetic only - never let theming break the panel

    # ── theme ──────────────────────────────────────────────────────────────
    def _apply_theme(self):
        self.configure(bg=THEME["app"])
        self.option_add("*selectBackground", THEME["accent"])
        self.option_add("*selectForeground", THEME["on_accent"])

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Dev.Vertical.TScrollbar",
            gripcount=0,
            background=THEME["border"],
            troughcolor=THEME["panel"],
            bordercolor=THEME["app"],
            arrowcolor=THEME["muted"],
            darkcolor=THEME["border"],
            lightcolor=THEME["border"],
            relief="flat",
        )
        style.map(
            "Dev.Vertical.TScrollbar",
            background=[("active", THEME["border_hot"])],
        )
        style.layout("Dev.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [
                    ("Vertical.Scrollbar.thumb",
                     {"expand": "1", "sticky": "nswe"})
                ],
            }),
        ])

    def _flat_button(self, parent, text, command, fg=None, bg=None,
                     hover=None, width=None):
        fg = fg or THEME["text"]
        bg = bg or THEME["button"]
        hover = hover or THEME["button_hover"]

        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font_button,
            width=width,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            padx=10,
            pady=5,
            cursor="hand2",
            anchor="center",
            takefocus=0,
        )

        def enter(_event):
            btn.configure(
                bg=hover,
                highlightbackground=THEME["border_hot"],
            )

        def leave(_event):
            btn.configure(
                bg=bg,
                highlightbackground=THEME["border"],
            )

        btn.bind("<Enter>", enter)
        btn.bind("<Leave>", leave)
        return btn

    def _keycap(self, parent, text):
        return tk.Label(
            parent,
            text=text,
            font=self.font_small,
            bg=THEME["button"],
            fg=THEME["muted"],
            padx=6,
            pady=2,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )

    # ── sections ───────────────────────────────────────────────────────────
    def _build_header(self):
        head = tk.Frame(self, bg=THEME["header"])
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)

        tk.Frame(head, bg=THEME["accent"], height=3).grid(
            row=0, column=0, sticky="ew"
        )

        content = tk.Frame(head, bg=THEME["header"])
        content.grid(row=1, column=0, sticky="ew", padx=16, pady=(13, 12))
        content.columnconfigure(0, weight=1)

        tk.Label(
            content,
            text="ACARISTAN SYSTEMS  /  INTERNAL OPERATIONS",
            bg=THEME["header"],
            fg=THEME["cyan"],
            font=self.font_small,
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            content,
            text="MISSION CONTROL",
            bg=THEME["header"],
            fg=THEME["text"],
            font=self.font_title,
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))

        tk.Label(
            content,
            text="Select a jump target, tool operation, or source export.",
            bg=THEME["header"],
            fg=THEME["muted"],
            font=self.font_ui,
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))

        shortcuts = tk.Frame(content, bg=THEME["header"])
        shortcuts.grid(row=3, column=0, sticky="w")

        tk.Label(
            shortcuts,
            text="NAV",
            bg=THEME["header"],
            fg=THEME["dim"],
            font=self.font_small,
        ).pack(side="left", padx=(0, 7))

        for key in ("↑ ↓", "ENTER", "CTRL F", "ESC"):
            self._keycap(shortcuts, key).pack(side="left", padx=(0, 5))

        metrics = tk.Frame(
            content,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        metrics.grid(
            row=0, column=1, rowspan=4,
            sticky="nse", padx=(24, 0)
        )

        state = tk.Frame(metrics, bg=THEME["panel"])
        state.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 7))

        self.live_dot = tk.Label(
            state,
            text="●",
            bg=THEME["panel"],
            fg=THEME["dim"],
            font=self.font_mono,
        )
        self.live_dot.pack(side="left")

        self.live_state = tk.Label(
            state,
            text="SYSTEM READY",
            bg=THEME["panel"],
            fg=THEME["muted"],
            font=self.font_small,
        )
        self.live_state.pack(side="left", padx=(6, 0))

        tk.Frame(metrics, bg=THEME["border"], height=1).grid(
            row=1, column=0, sticky="ew"
        )

        self.counts = tk.Label(
            metrics,
            text="",
            bg=THEME["panel"],
            fg=THEME["accent"],
            font=self.font_metric,
            justify="right",
            anchor="e",
        )
        self.counts.grid(
            row=2, column=0, sticky="ew",
            padx=14, pady=(9, 10)
        )

        tk.Frame(head, bg=THEME["border"], height=1).grid(
            row=2, column=0, sticky="ew"
        )

    def _build_filter(self):
        bar = tk.Frame(self, bg=THEME["app"])
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 7))
        bar.columnconfigure(0, weight=1)

        shell = tk.Frame(bar, bg=THEME["border"], padx=1, pady=1)
        shell.grid(row=0, column=0, sticky="ew")
        shell.columnconfigure(0, weight=1)

        inner = tk.Frame(shell, bg=THEME["panel"])
        inner.grid(row=0, column=0, sticky="ew")
        inner.columnconfigure(1, weight=1)

        tk.Label(
            inner,
            text="⌕  FILTER TARGETS",
            bg=THEME["panel"],
            fg=THEME["cyan"],
            font=self.font_button,
        ).grid(row=0, column=0, sticky="w", padx=(11, 8), pady=8)

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())

        self.filter_entry = tk.Entry(
            inner,
            textvariable=self.filter_var,
            font=self.font_mono,
            bg=THEME["button"],
            fg=THEME["text"],
            relief="flat",
            insertbackground=THEME["accent"],
            selectbackground=THEME["accent"],
            selectforeground=THEME["on_accent"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
        )
        self.filter_entry.grid(
            row=0, column=1, sticky="ew",
            padx=(0, 8), pady=7, ipady=4
        )
        self.filter_entry.bind("<Return>", self._launch_first_visible)
        self.filter_entry.bind("<Escape>", self._on_escape)

        self._keycap(inner, "CTRL F").grid(
            row=0, column=2, padx=(0, 8)
        )

        self._flat_button(
            inner,
            "CLEAR ×",
            lambda: self.filter_var.set(""),
            width=7,
        ).grid(row=0, column=3, padx=(0, 7), pady=6)

    def _build_body(self):
        wrap = tk.Frame(
            self,
            bg=THEME["border"],
            padx=1,
            pady=1,
        )
        wrap.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(wrap, bg=THEME["app"], bd=0,
                                highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.canvas.yview,
                            style="Dev.Vertical.TScrollbar")
        bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=bar.set)

        inner = tk.Frame(
            self.canvas,
            bg=THEME["app"],
            padx=10,
            pady=6,
        )
        inner.columnconfigure(0, weight=1)
        self._inner = inner
        self._body_row = 0
        window = self.canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(window,
                                                             width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        for label, targets in grouped_targets():
            self._add_group(label, targets)
        # Packaging rows are not dev jumps, but they ride the same row /
        # filter / keyboard machinery; ``launch`` dispatches them separately.
        self._add_group("Packaging",
                        [(name, desc) for name, (desc, _args) in
                         TOOL_TARGETS.items()])
        self._add_group("Source", [
            (SOURCE_TXT_TARGET, SOURCE_TXT_DESC),
            (SOURCE_DIR_TXT_TARGET, SOURCE_DIR_TXT_DESC),
        ])

    def _group_heading(self, index, label, shown, total, filtered=False):
        count = f"{shown:02}/{total:02}" if filtered else f"{total:02}"
        return f"◆  {index:02} // {label.upper()}    [{count}]"

    def _add_group(self, label, targets):
        key = label
        index = len(self._group_widgets) + 1

        header = tk.Label(
            self._inner,
            text=self._group_heading(
                index, label, len(targets), len(targets)
            ),
            bg=THEME["app"],
            fg=THEME["cyan"],
            font=self.font_group,
            anchor="w",
        )
        header.grid(
            row=self._body_row,
            column=0,
            sticky="ew",
            pady=(12, 4),
        )
        self._body_row += 1

        frame = tk.Frame(
            self._inner,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        frame.grid(row=self._body_row, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self._body_row += 1

        for row_index, (name, desc) in enumerate(targets):
            self._add_target_row(frame, row_index, key, name, desc)

        self._group_widgets[key] = {
            "header": header,
            "frame": frame,
            "label": label,
            "total": len(targets),
            "index": index,
        }

    def _add_target_row(self, parent, index, group_key, name, desc):
        base_bg = THEME["panel_alt"] if index % 2 else THEME["panel"]

        row = tk.Frame(parent, bg=base_bg, cursor="hand2")
        row.grid(row=index, column=0, sticky="ew")
        row.columnconfigure(2, weight=1)

        marker = tk.Frame(row, bg=THEME["border"], width=3)
        marker.grid(row=0, column=0, sticky="ns")

        button = tk.Button(
            row,
            text=name,
            width=21,
            anchor="w",
            font=self.font_mono,
            bd=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            bg=THEME["button"],
            fg=THEME["accent"],
            activebackground=THEME["accent"],
            activeforeground=THEME["on_accent"],
            padx=10,
            pady=5,
            command=lambda n=name: self.launch(n),
        )
        button.grid(
            row=0, column=1,
            sticky="w",
            padx=(7, 0),
            pady=4,
        )

        label = tk.Label(
            row,
            text=desc,
            bg=base_bg,
            fg=THEME["muted"],
            font=self.font_ui,
            anchor="w",
            justify="left",
            cursor="hand2",
        )
        label.grid(
            row=0, column=2,
            sticky="ew",
            padx=(13, 10),
        )

        action = tk.Label(
            row,
            text="RUN   ▶",
            width=10,
            bg=base_bg,
            fg=THEME["dim"],
            font=self.font_button,
            anchor="e",
            cursor="hand2",
        )
        action.grid(row=0, column=3, sticky="e", padx=(4, 12))

        separator = tk.Frame(row, bg=THEME["border"], height=1)
        separator.grid(
            row=1, column=1, columnspan=3,
            sticky="ew",
            padx=(7, 0),
        )

        entry = {
            "name": name,
            "desc": desc,
            "row": row,
            "button": button,
            "label": label,
            "action": action,
            "marker": marker,
            "separator": separator,
            "base_bg": base_bg,
            "group": group_key,
            "visible": True,
            "hovered": False,
        }

        widgets = (row, button, label, action, marker, separator)
        for widget in widgets:
            widget.bind(
                "<Enter>",
                lambda _e, en=entry: self._hover(en, True),
            )
            widget.bind(
                "<Leave>",
                lambda _e, en=entry: self._hover(en, False),
            )
            widget.bind(
                "<Button-3>",
                lambda _e, n=name: self._copy_cmd(n),
            )

        for widget in (row, label, action, marker, separator):
            widget.bind(
                "<Button-1>",
                lambda _e, n=name: self.launch(n),
            )

        self._entries.append(entry)

    def _build_footer(self):
        foot = tk.Frame(self, bg=THEME["header"])
        foot.grid(row=3, column=0, sticky="ew")
        foot.columnconfigure(1, weight=1)

        tk.Frame(foot, bg=THEME["border"], height=1).grid(
            row=0, column=0, columnspan=4, sticky="ew"
        )

        tk.Label(
            foot,
            text=">_  EXTRA ARGS",
            bg=THEME["header"],
            fg=THEME["cyan"],
            font=self.font_button,
        ).grid(
            row=1, column=0, sticky="w",
            padx=(14, 9), pady=(10, 6)
        )

        self.extra = tk.Entry(
            foot,
            font=self.font_mono,
            bg=THEME["button"],
            fg=THEME["text"],
            relief="flat",
            insertbackground=THEME["accent"],
            selectbackground=THEME["accent"],
            selectforeground=THEME["on_accent"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
        )
        self.extra.grid(
            row=1, column=1, sticky="ew",
            pady=(10, 6), ipady=4
        )
        self.extra.bind("<Return>", self._on_extra_return)

        self._flat_button(
            foot,
            "COPY CMD",
            self._copy_last,
            fg=THEME["cyan"],
        ).grid(
            row=1, column=2,
            padx=(8, 4), pady=(10, 6)
        )

        self._flat_button(
            foot,
            "■ STOP ALL",
            self.stop_all,
            fg=THEME["danger"],
            hover=THEME["danger_hover"],
        ).grid(
            row=1, column=3,
            padx=(4, 14), pady=(10, 6)
        )

        status_shell = tk.Frame(
            foot,
            bg=THEME["app"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        status_shell.grid(
            row=2, column=0, columnspan=4,
            sticky="ew",
            padx=14, pady=(0, 11)
        )
        status_shell.columnconfigure(1, weight=1)

        self.status_mark = tk.Label(
            status_shell,
            text="●",
            bg=THEME["app"],
            fg=THEME["dim"],
            font=self.font_mono,
        )
        self.status_mark.grid(
            row=0, column=0,
            padx=(9, 7), pady=6
        )

        self.status = tk.Label(
            status_shell,
            text="",
            bg=THEME["app"],
            fg=THEME["muted"],
            font=self.font_ui,
            anchor="w",
        )
        self.status.grid(
            row=0, column=1,
            sticky="ew",
            pady=6,
        )

        tk.Label(
            status_shell,
            text="RIGHT-CLICK  COPY",
            bg=THEME["app"],
            fg=THEME["dim"],
            font=self.font_small,
        ).grid(
            row=0, column=2,
            padx=(10, 9),
        )

    # ── behaviour ──────────────────────────────────────────────────────────
    def _on_wheel(self, event):
        """Scroll the body, but only while the pointer is over it."""
        widget = self.winfo_containing(*self.winfo_pointerxy())
        while widget is not None:
            if widget is self.canvas:
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
                return
            widget = getattr(widget, "master", None)

    def _paint_row(self, entry):
        selected = entry["name"] == self._selected
        hovered = entry.get("hovered", False)

        if selected:
            row_bg = THEME["accent_dark"]
            button_bg = THEME["accent"]
            button_fg = THEME["on_accent"]
            label_fg = THEME["text"]
            marker_bg = THEME["accent"]
            action_fg = THEME["accent_soft"]
            action_text = "ACTIVE ▶"
        elif hovered:
            row_bg = THEME["panel_hover"]
            button_bg = THEME["button_hover"]
            button_fg = THEME["accent"]
            label_fg = THEME["text"]
            marker_bg = THEME["cyan"]
            action_fg = THEME["cyan"]
            action_text = "LAUNCH ▶"
        else:
            row_bg = entry["base_bg"]
            button_bg = THEME["button"]
            button_fg = THEME["accent"]
            label_fg = THEME["muted"]
            marker_bg = THEME["border"]
            action_fg = THEME["dim"]
            action_text = "RUN   ▶"

        entry["row"].configure(bg=row_bg)
        entry["label"].configure(bg=row_bg, fg=label_fg)
        entry["action"].configure(
            bg=row_bg,
            fg=action_fg,
            text=action_text,
        )
        entry["marker"].configure(bg=marker_bg)
        entry["separator"].configure(
            bg=THEME["border_hot"] if selected else THEME["border"]
        )
        entry["button"].configure(
            bg=button_bg,
            fg=button_fg,
            activebackground=THEME["accent"],
            activeforeground=THEME["on_accent"],
        )

    def _hover(self, entry, on):
        entry["hovered"] = on
        self._paint_row(entry)
        if on:
            self._last_target = entry["name"]
            self._set_status(f"{entry['name']}   -   {entry['desc']}")
        elif entry["name"] != self._selected:
            self._set_status(self._default_status())

    # ── keyboard navigation ────────────────────────────────────────────────
    def _bind_keys(self):
        """Panel-wide shortcuts; the header line advertises the main ones."""
        self.bind("<Control-f>", self._focus_filter)
        self.bind("<Escape>", self._on_escape)
        self.bind("<Up>", lambda _e: self._arrow(-1))
        self.bind("<Down>", lambda _e: self._arrow(1))
        self.bind("<Return>", self._on_return)

    def _typing_in_entry(self):
        """True when a text field owns focus, so keys should reach it first."""
        return isinstance(self.focus_get(), tk.Entry)

    def _visible_entries(self):
        return [e for e in self._entries if e["visible"]]

    def _entry_for(self, name):
        for entry in self._entries:
            if entry["name"] == name:
                return entry
        return None

    def _focus_filter(self, _event=None):
        self.filter_entry.focus_set()
        self.filter_entry.select_range(0, "end")
        return "break"

    def _arrow(self, delta):
        if self._typing_in_entry():
            return None      # let the Entry move its own caret
        self._move_selection(delta)
        return "break"

    def _move_selection(self, delta):
        entries = self._visible_entries()
        if not entries:
            return
        names = [e["name"] for e in entries]
        if self._selected in names:
            index = (names.index(self._selected) + delta) % len(names)
        else:
            index = 0 if delta > 0 else len(names) - 1
        self._select(names[index])

    def _select(self, name):
        previous = self._entry_for(self._selected)
        self._selected = name
        current = self._entry_for(name)
        for entry in (previous, current):
            if entry is not None:
                self._paint_row(entry)
        if current is not None:
            self._last_target = name
            self._ensure_visible(current)
            self._set_status(
                f"{name}   -   {current['desc']}   ·   Enter launches")

    def _clear_selection(self):
        entry = self._entry_for(self._selected)
        self._selected = None
        if entry is not None:
            self._paint_row(entry)

    def _ensure_visible(self, entry):
        """Scroll the body just enough to bring a selected row into view."""
        self.canvas.update_idletasks()
        row = entry["row"]
        top = row.winfo_rooty() - self._inner.winfo_rooty()
        bottom = top + row.winfo_height()
        view_top = self.canvas.canvasy(0)
        view_height = self.canvas.winfo_height()
        total = max(1, self._inner.winfo_height())
        if top < view_top:
            self.canvas.yview_moveto(top / total)
        elif bottom > view_top + view_height:
            self.canvas.yview_moveto(max(0.0, (bottom - view_height) / total))

    def _on_return(self, _event=None):
        if self._typing_in_entry():
            return None      # the focused Entry handles its own Return
        self._launch_selected()
        return "break"

    def _on_escape(self, _event=None):
        if self.filter_var.get():
            self.filter_var.set("")
        self._clear_selection()
        return "break"

    def _on_extra_return(self, _event=None):
        self._launch_last()
        return "break"

    def _launch_selected(self):
        if self._selected:
            self.launch(self._selected)
        else:
            self._launch_first_visible()

    def _set_status(self, text, kind="info"):
        colours = {
            "info": THEME["muted"],
            "ok": THEME["accent"],
            "warn": THEME["warn"],
            "err": THEME["danger"],
        }
        marks = {
            "info": "●",
            "ok": "◆",
            "warn": "▲",
            "err": "×",
        }

        colour = colours.get(kind, THEME["muted"])
        self.status.configure(text=text, fg=colour)

        if hasattr(self, "status_mark"):
            self.status_mark.configure(
                text=marks.get(kind, "●"),
                fg=colour,
            )

    def _default_status(self):
        running = self._running()
        if running:
            return (
                f"Session active. {running} child process(es) currently running."
            )
        return "System ready. Select a target to begin."

    def _running(self):
        return sum(1 for p in self._procs if p.poll() is None)

    def _update_counts(self):
        visible = sum(1 for e in self._entries if e["visible"])
        running = self._running()

        self.counts.configure(
            text=(
                f"{visible:02} / {len(self._entries):02}  VISIBLE\n"
                f"{running:02}  RUNNING"
            )
        )

        self.live_state.configure(
            text="SESSION ACTIVE" if running else "SYSTEM READY",
            fg=THEME["accent"] if running else THEME["muted"],
        )

        if not running:
            self.live_dot.configure(fg=THEME["dim"])

    def _pulse_live(self):
        self._pulse_phase = not self._pulse_phase
        running = self._running()

        if running:
            colour = (
                THEME["accent_soft"]
                if self._pulse_phase
                else THEME["accent"]
            )
        else:
            colour = THEME["dim"]

        try:
            self.live_dot.configure(fg=colour)
            self.after(650, self._pulse_live)
        except tk.TclError:
            pass

    def _extra_args(self):
        return parse_extra_args(self.extra.get())

    def _apply_filter(self):
        query = self.filter_var.get().strip().lower()
        per_group = {}
        for entry in self._entries:
            match = (not query
                     or query in entry["name"].lower()
                     or query in entry["desc"].lower())
            entry["visible"] = match
            if match:
                entry["row"].grid()
                per_group[entry["group"]] = per_group.get(entry["group"], 0) + 1
            else:
                entry["row"].grid_remove()

        for key, widgets in self._group_widgets.items():
            shown = per_group.get(key, 0)
            label, total = widgets["label"], widgets["total"]
            widgets["header"].configure(
                text=self._group_heading(
                    widgets["index"],
                    label,
                    shown,
                    total,
                    filtered=bool(query),
                )
            )
            for widget in (widgets["header"], widgets["frame"]):
                if shown:
                    widget.grid()
                else:
                    widget.grid_remove()

        # Drop a keyboard selection the filter just hid, so Enter can't fire a
        # target the user can no longer see.
        selected = self._entry_for(self._selected)
        if selected is not None and not selected["visible"]:
            self._selected = None
            self._paint_row(selected)

        self._update_counts()
        self.canvas.yview_moveto(0.0)

    def _launch_first_visible(self, _event=None):
        for entry in self._entries:
            if entry["visible"]:
                self.launch(entry["name"])
                return "break"

    def _launch_last(self):
        target = self._last_target or next(iter(DEV_JUMPS), None)
        if target:
            self.launch(target)

    def _copy_cmd(self, name):
        if name in SOURCE_ACTIONS:
            _desc, action = SOURCE_ACTIONS[name]
            text = action(self._extra_args())
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status(f"Copied: {text}", "ok")
            return
        if name in TOOL_TARGETS:
            cmd = " ".join(build_tool_cmd(name, self._extra_args()))
        else:
            cmd = " ".join(build_launch_cmd(name, self._extra_args()))
        self.clipboard_clear()
        self.clipboard_append(cmd)
        self._set_status(f"Copied: {cmd}", "ok")

    def _copy_last(self):
        target = self._last_target or next(iter(DEV_JUMPS), None)
        if target:
            self._copy_cmd(target)

    def launch(self, target):
        self._last_target = target

        entry = self._entry_for(target)
        if entry is not None and entry["visible"]:
            self._select(target)

        if target in SOURCE_ACTIONS:
            _desc, action = SOURCE_ACTIONS[target]
            result = action(self._extra_args())
            self._set_status(result, "ok")
            self._update_counts()
            return
        if target in TOOL_TARGETS:
            cmd = build_tool_cmd(target, self._extra_args())
        else:
            cmd = build_launch_cmd(target, self._extra_args())
        try:
            proc = subprocess.Popen(cmd, cwd=str(ROOT))
        except Exception as exc:  # e.g. python not on PATH for the child
            self._set_status(f"Launch failed: {exc}", "err")
            return
        self._procs.append(proc)
        self._set_status(f"Launched {target}   (pid {proc.pid})", "ok")
        self._update_counts()

    def stop_all(self):
        killed = 0
        for proc in self._procs:
            if proc.poll() is None:
                proc.terminate()
                killed += 1
        self._procs = [p for p in self._procs if p.poll() is None]
        if killed:
            self._set_status(f"Stopped {killed} game instance(s).", "warn")
        else:
            self._set_status("No running game instances.")    
        self._update_counts()

    def _reap(self):
        self._procs = [p for p in self._procs if p.poll() is None]
        self._update_counts()
        self.after(1000, self._reap)


def main():
    panel = DevPanel()
    missing, duplicated, unknown = group_issues()
    if missing or duplicated or unknown:
        parts = []
        if missing:
            parts.append("not in any group: " + ", ".join(missing))
        if duplicated:
            parts.append("in two groups: " + ", ".join(duplicated))
        if unknown:
            parts.append("unknown to registry: " + ", ".join(unknown))
        panel._set_status("DEV_JUMPS drift - " + " | ".join(parts), "warn")
    panel.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
