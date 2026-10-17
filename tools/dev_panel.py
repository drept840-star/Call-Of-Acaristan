"""dev_panel.py - clickable dev control panel for jumping into missions.

Run from the repo root::

    python tools/dev_panel.py

Opens a dark, terminal-styled window with one button per dev jump target -
the same registry as ``acaristan.py --jump NAME`` (see
``src/core/dev_jumps.py``). Click a target to launch the game at that
mission; its description sits next to the button so nothing needs hovering.
Anything typed in the "extra args" field (e.g. ``--continue`` for slot-select)
is forwarded to the game. Trailer-bot takes additionally get
``--trailer-bot --trailer-act <act>`` appended automatically.

Layout, top to bottom::

    header   title + live "visible/total targets · running" counts
    filter   type to narrow the list (matches target name or description)
    body     scrollable, grouped target list in mission order
    footer   extra args, Copy command, Stop all games, status line

Keyboard: ↑/↓ walk the visible targets, Enter launches the selected one,
Ctrl+F jumps to the filter, and Esc clears the filter plus the selection.
Handy: right-click any target to copy its command without launching.

Structure notes:
    * ``GROUPS`` defines the display order. The panel self-checks that every
      ``DEV_JUMPS`` entry is filed under exactly one group and reports any
      drift in the status line, so the registry and the panel cannot silently
      fall out of sync as new jumps are added.
    * ``grouped_targets`` / ``build_launch_cmd`` / ``parse_extra_args`` are
      pure and import-safe, so they can be exercised without a Tk root.
"""
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.dev_jumps import DEV_JUMPS

# ── Display groups: (section label, [target names]) ──
# Order here is the panel's order. Keep in sync with DEV_JUMPS - the panel
# warns (in the status line) about any entry that is missing or duplicated.
GROUPS = [
    ("Mission 1", ["m1", "m1-safe"]),
    ("Walking sim", ["walk"]),
    ("Mission 2", ["m2", "m2-game", "m2-sniper", "m2-after-sniper",
                   "m2-flank", "m2-truck", "m2-evidence"]),
    ("Mission 3", ["m3", "m3-game", "m3-comms", "m3-archives",
                   "m3-kill-order", "m3-ledger", "m3-vostral",
                   "m3-archives-cutscene", "m3-broadcast-transition",
                   "m3-broadcast", "m3-upload"]),
    ("Mission 4", ["m4", "m4-game", "m4-station", "m4-tower"]),
    ("Mission 5", ["m5", "m5-hq", "m5-game", "m5-printworks",
                   "m5-tunnel", "m5-ending"]),
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
THEME = {
    "app":        "#1a1815",
    "header":     "#232019",
    "panel":      "#272319",
    "button":     "#2f2a20",
    "button_hover": "#3d3628",
    "border":     "#3d372e",
    "text":       "#e8e2d8",
    "muted":      "#9a9186",
    "accent":     "#32ff96",
    "accent_hover": "#6dffb4",
    "on_accent":  "#0b1a12",
    "danger":     "#ff6b5e",
    "danger_hover": "#ff8d82",
    "amber":      "#ffbe4d",
    "warn":       "#ffc266",
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


# ─────────────────────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────────────────────
class DevPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Acaristan - Dev Panel")
        self.minsize(720, 460)
        self.geometry("880x680")

        self._procs = []          # launched game processes (for Stop all games)
        self._entries = []        # one dict per target row (for filtering)
        self._group_widgets = {}  # group key -> header/frame/label widgets
        self._last_target = None  # last hovered/launched target (for Copy)
        self._selected = None     # keyboard-selected target name (↑/↓ + Enter)

        self.font_title = ("Consolas", 13, "bold")
        self.font_group = ("Consolas", 10, "bold")
        self.font_mono = ("Consolas", 10)
        self.font_ui = ("Segoe UI", 9)

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
        style = ttk.Style(self)
        try:
            style.theme_use("clam")  # clam honours explicit scrollbar colours
        except tk.TclError:
            pass
        style.configure(
            "Dev.Vertical.TScrollbar",
            gripcount=0,
            background=THEME["border"], troughcolor=THEME["app"],
            bordercolor=THEME["app"], arrowcolor=THEME["muted"],
            darkcolor=THEME["border"], lightcolor=THEME["border"],
            relief="flat",
        )
        style.map("Dev.Vertical.TScrollbar",
                  background=[("active", THEME["button_hover"])])
        # Arrowless track+thumb - cleaner than clam's default stepper arrows.
        style.layout("Dev.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [("Vertical.Scrollbar.thumb",
                              {"expand": "1", "sticky": "nswe"})],
            }),
        ])

    def _flat_button(self, parent, text, command, fg=None, bg=None,
                     hover=None, width=None):
        """A consistently styled flat button (classic tk = reliably themable)."""
        fg = fg or THEME["text"]
        bg = bg or THEME["button"]
        hover = hover or THEME["button_hover"]
        btn = tk.Button(
            parent, text=text, command=command, font=self.font_mono,
            width=width, bd=0, relief="flat", highlightthickness=0,
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            padx=10, pady=4, cursor="hand2", anchor="center",
        )
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    # ── sections ───────────────────────────────────────────────────────────
    def _build_header(self):
        head = tk.Frame(self, bg=THEME["header"])
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)

        tk.Label(head, text="ACARISTAN - DEV PANEL", bg=THEME["header"],
                 fg=THEME["accent"], font=self.font_title).grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        tk.Label(
            head,
            text="Click a target to launch it. Right-click copies the command. "
                 "↑/↓ then Enter to pick.",
            bg=THEME["header"], fg=THEME["muted"], font=self.font_ui,
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        self.counts = tk.Label(head, text="", bg=THEME["header"],
                               fg=THEME["muted"], font=self.font_ui)
        self.counts.grid(row=0, column=1, rowspan=2, sticky="e", padx=14)

        tk.Frame(self, bg=THEME["border"], height=1).grid(
            row=0, column=0, sticky="sew")

    def _build_filter(self):
        bar = tk.Frame(self, bg=THEME["app"])
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 6))
        bar.columnconfigure(1, weight=1)

        tk.Label(bar, text="Filter", bg=THEME["app"], fg=THEME["muted"],
                 font=self.font_ui).grid(row=0, column=0, sticky="w")

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        self.filter_entry = tk.Entry(
            bar, textvariable=self.filter_var, font=self.font_mono,
            bg=THEME["button"], fg=THEME["text"], relief="flat",
            insertbackground=THEME["accent"], highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
        )
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=8, ipady=4)
        self.filter_entry.bind("<Return>", self._launch_first_visible)
        self.filter_entry.bind("<Escape>", self._on_escape)

        self._flat_button(bar, "Clear", lambda: self.filter_var.set(""),
                          width=6).grid(row=0, column=2, sticky="e")

    def _build_body(self):
        wrap = tk.Frame(self, bg=THEME["app"])
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

        inner = tk.Frame(self.canvas, bg=THEME["app"])
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

    def _add_group(self, label, targets):
        key = label
        header = tk.Label(
            self._inner, text=f"{label.upper()}   ·   {len(targets)}",
            bg=THEME["app"], fg=THEME["amber"], font=self.font_group,
            anchor="w",
        )
        header.grid(row=self._body_row, column=0, sticky="ew", pady=(10, 3))
        self._body_row += 1

        frame = tk.Frame(self._inner, bg=THEME["panel"])
        frame.grid(row=self._body_row, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self._body_row += 1

        for index, (name, desc) in enumerate(targets):
            self._add_target_row(frame, index, key, name, desc)

        self._group_widgets[key] = {
            "header": header, "frame": frame, "label": label,
            "total": len(targets),
        }

    def _add_target_row(self, parent, index, group_key, name, desc):
        row = tk.Frame(parent, bg=THEME["panel"])
        row.grid(row=index, column=0, sticky="ew", pady=0, padx=1)
        row.columnconfigure(1, weight=1)

        button = tk.Button(
            row, text=name, width=21, anchor="w", font=self.font_mono,
            bd=0, relief="flat", highlightthickness=0, cursor="hand2",
            bg=THEME["button"], fg=THEME["accent"],
            activebackground=THEME["accent"],
            activeforeground=THEME["on_accent"],
            padx=10, pady=3, command=lambda n=name: self.launch(n),
        )
        button.grid(row=0, column=0, sticky="w", padx=(6, 0), pady=2)

        label = tk.Label(row, text=desc, bg=THEME["panel"], fg=THEME["muted"],
                         font=self.font_ui, anchor="w", justify="left")
        label.grid(row=0, column=1, sticky="ew", padx=(12, 10))

        entry = {"name": name, "desc": desc, "row": row, "button": button,
                 "label": label, "group": group_key, "visible": True,
                 "hovered": False}
        for widget in (row, button, label):
            widget.bind("<Enter>", lambda _e, en=entry: self._hover(en, True))
            widget.bind("<Leave>", lambda _e, en=entry: self._hover(en, False))
            widget.bind("<Button-3>", lambda _e, n=name: self._copy_cmd(n))
        self._entries.append(entry)

    def _build_footer(self):
        foot = tk.Frame(self, bg=THEME["header"])
        foot.grid(row=3, column=0, sticky="ew")
        foot.columnconfigure(1, weight=1)

        tk.Label(foot, text="extra args", bg=THEME["header"],
                 fg=THEME["muted"], font=self.font_ui).grid(
            row=0, column=0, sticky="w", padx=(14, 8), pady=(10, 4))

        self.extra = tk.Entry(
            foot, font=self.font_mono, bg=THEME["button"], fg=THEME["text"],
            relief="flat", insertbackground=THEME["accent"],
            highlightthickness=1, highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
        )
        self.extra.grid(row=0, column=1, sticky="ew", pady=(10, 4), ipady=4)
        self.extra.bind("<Return>", self._on_extra_return)

        self._flat_button(foot, "Copy command", self._copy_last).grid(
            row=0, column=2, padx=(8, 4), pady=(10, 4))
        self._flat_button(foot, "Stop all games", self.stop_all,
                          fg=THEME["danger"], hover=THEME["danger_hover"]).grid(
            row=0, column=3, padx=(4, 14), pady=(10, 4))

        self.status = tk.Label(foot, text="", bg=THEME["header"],
                               fg=THEME["muted"], font=self.font_ui, anchor="w")
        self.status.grid(row=1, column=0, columnspan=4, sticky="ew",
                         padx=14, pady=(0, 10))

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
        """Repaint one target row for its current hover/selection state.

        Selection outranks hover, so a keyboard-picked row stays visibly
        marked while the pointer wanders across the rest of the list.
        """
        selected = entry["name"] == self._selected
        hovered = entry.get("hovered", False)
        if selected:
            row_bg, btn_bg, btn_fg = (THEME["button_hover"], THEME["accent"],
                                      THEME["on_accent"])
        elif hovered:
            row_bg, btn_bg, btn_fg = (THEME["button"], THEME["button_hover"],
                                      THEME["accent"])
        else:
            row_bg, btn_bg, btn_fg = (THEME["panel"], THEME["button"],
                                      THEME["accent"])
        for widget in (entry["row"], entry["label"]):
            widget.configure(bg=row_bg)
        entry["button"].configure(
            bg=btn_bg, fg=btn_fg,
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
        colours = {"info": THEME["muted"], "ok": THEME["accent"],
                   "warn": THEME["warn"], "err": THEME["danger"]}
        self.status.configure(text=text, fg=colours.get(kind, THEME["muted"]))

    def _default_status(self):
        running = self._running()
        if running:
            return f"Pick a mission to jump into. ({running} game instance(s) running)"
        return "Pick a mission to jump into."

    def _running(self):
        return sum(1 for p in self._procs if p.poll() is None)

    def _update_counts(self):
        visible = sum(1 for e in self._entries if e["visible"])
        self.counts.configure(
            text=f"{visible}/{len(self._entries)} targets   ·   {self._running()} running")

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
                text=f"{label.upper()}   ·   {shown}/{total}" if query
                else f"{label.upper()}   ·   {total}")
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
        try:
            proc = subprocess.Popen(build_launch_cmd(target, self._extra_args()),
                                    cwd=str(ROOT))
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

