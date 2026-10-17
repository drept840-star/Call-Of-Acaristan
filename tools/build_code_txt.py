"""
build_code_txt.py
Selective TXT code bundle: pick files, pick folder, get TXT only (no PDF).

Usage:
  python tools/build_code_txt.py                  (tkinter picker GUI)
  python tools/build_code_txt.py --all [--out DIR]
  python tools/build_code_txt.py [--out DIR] src/core/config.py src/app.py ...
"""
from pathlib import Path
import sys
import os
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = PROJECT_ROOT / "archive" / "TXTs"
SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env",
    "build", "dist", ".pytest_cache", ".mypy_cache", "PDFs", "TXTs",
    "archive",
}
SKIP_FILES = {"build_code_pdf.py", "build_code_txt.py"}


def find_py_files(root: Path):
    found = []
    for path in root.rglob("*.py"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name.lower() in {s.lower() for s in SKIP_FILES}:
            continue
        found.append(rel)
    return sorted(found, key=lambda p: str(p).replace("\\", "/").lower())


def write_files_to_txt(files, txt_path: Path):
    lines = []
    for filepath in files:
        abs_path = PROJECT_ROOT / filepath
        try:
            code = abs_path.read_text(encoding="utf-8")
        except Exception as e:
            lines.extend([f"# {'-' * 60}", f"# {filepath} (UNREADABLE: {e})", "", ""])
            continue
        lines.extend([
            f"# {'-' * 60}",
            f"# {filepath}",
            f"# {'-' * 60}",
            "",
            code.rstrip(),
            "",
        ])
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {txt_path}")
    return txt_path


def write_individual_txts(files, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for filepath in files:
        name = str(filepath).replace("\\", "/").replace("/", "_")
        if not name.endswith(".txt"):
            name = name + ".txt" if name.endswith(".py") else name + ".txt"
            # src_core_config.py.py -> keep as is? strip one .py:
            if name.endswith(".py.txt"):
                name = name[:-7] + ".txt"
        write_files_to_txt([filepath], out_dir / name)


def resolve_cli_files(args):
    """Return (files, out_dir). Files are project-relative Paths."""
    out_dir = DEFAULT_OUT_DIR
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "--out" and i + 1 < len(args):
            out_dir = Path(args[i + 1])
            if not out_dir.is_absolute():
                out_dir = (PROJECT_ROOT / out_dir).resolve()
            i += 2
        elif args[i] == "--all":
            rest.append("--all")
            i += 1
        else:
            rest.append(args[i])
            i += 1
    if "--all" in rest or not [r for r in rest if r != "--all"]:
        if "--all" in rest and len([r for r in rest if r != "--all"]) == 0:
            return find_py_files(PROJECT_ROOT), out_dir
        if not [r for r in rest if r != "--all"]:
            return None, out_dir  # signal: nothing picked
    files = []
    for r in rest:
        if r == "--all":
            continue
        p = Path(r)
        abs_p = (PROJECT_ROOT / p).resolve() if not p.is_absolute() else p
        try:
            rel = abs_p.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            print(f"Skip (outside project): {r}")
            continue
        if not (PROJECT_ROOT / rel).exists():
            print(f"Skip (not found): {r}")
            continue
        files.append(rel)
    return files, out_dir


def build_selection(files, out_dir: Path, combined_name="selected_source.txt"):
    if not files:
        print("No files selected.")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    write_files_to_txt(files, out_dir / combined_name)
    write_individual_txts(files, out_dir / "individual")
    print(f"DONE: {len(files)} file(s) -> {out_dir}")


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    files = find_py_files(PROJECT_ROOT)
    display = [str(f).replace("\\", "/") for f in files]

    root = tk.Tk()
    root.title("Code TXT Bundle - pick files, pick folder")
    root.geometry("760x600")

    # Filter row
    top = tk.Frame(root)
    top.pack(fill=tk.X, padx=10, pady=(10, 4))
    tk.Label(top, text="Filter:").pack(side=tk.LEFT)
    filter_var = tk.StringVar()
    filter_entry = tk.Entry(top, textvariable=filter_var, width=40)
    filter_entry.pack(side=tk.LEFT, padx=6)

    # File list (multi-select)
    list_frame = tk.Frame(root)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED,
                         yscrollcommand=scrollbar.set,
                         font=("Consolas", 10))
    listbox.pack(fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    for d in display:
        listbox.insert(tk.END, d)

    def apply_filter(*_):
        q = filter_var.get().lower()
        sel = set(listbox.curselection())
        # remember selected names before refilter
        selected_names = {listbox.get(i) for i in sel}
        listbox.delete(0, tk.END)
        for d in display:
            if q in d.lower():
                listbox.insert(tk.END, d)
        # restore selection for visible items
        for i in range(listbox.size()):
            if listbox.get(i) in selected_names:
                listbox.select_set(i)

    filter_var.trace_add("write", apply_filter)

    # Selection buttons
    btn_row = tk.Frame(root)
    btn_row.pack(fill=tk.X, padx=10, pady=4)
    tk.Button(btn_row, text="Select all",
              command=lambda: listbox.select_set(0, tk.END)).pack(side=tk.LEFT, padx=2)
    tk.Button(btn_row, text="Clear",
              command=lambda: listbox.selection_clear(0, tk.END)).pack(side=tk.LEFT, padx=2)
    tk.Button(btn_row, text="Invert",
              command=lambda: [listbox.select_set(i) if not listbox.selection_includes(i)
                               else listbox.selection_clear(i) for i in range(listbox.size())]
              ).pack(side=tk.LEFT, padx=2)
    count_var = tk.StringVar(value="0 selected")
    tk.Label(btn_row, textvariable=count_var).pack(side=tk.RIGHT)

    def update_count(*_):
        count_var.set(f"{len(listbox.curselection())} selected")
    root.bind_class("Listbox", "<<ListboxSelect>>", update_count)

    # Output folder row
    out_row = tk.Frame(root)
    out_row.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(out_row, text="Output folder:").pack(side=tk.LEFT)
    out_var = tk.StringVar(value=str(DEFAULT_OUT_DIR))
    out_entry = tk.Entry(out_row, textvariable=out_var, width=55)
    out_entry.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)

    def browse():
        d = filedialog.askdirectory(initialdir=out_var.get() or str(PROJECT_ROOT))
        if d:
            out_var.set(d)
    tk.Button(out_row, text="Browse...", command=browse).pack(side=tk.LEFT)

    # Combined filename row
    name_row = tk.Frame(root)
    name_row.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(name_row, text="Combined file:").pack(side=tk.LEFT)
    name_var = tk.StringVar(value="selected_source.txt")
    tk.Entry(name_row, textvariable=name_var, width=30).pack(side=tk.LEFT, padx=6)

    status_var = tk.StringVar(value=f"{len(files)} .py files found")
    tk.Label(root, textvariable=status_var).pack(padx=10, pady=2)

    def do_build():
        idx = listbox.curselection()
        if not idx:
            messagebox.showwarning("Nothing selected", "Select at least one file.")
            return
        chosen = [Path(listbox.get(i)) for i in idx]
        out_dir = Path(out_var.get())
        cname = name_var.get().strip() or "selected_source.txt"
        if not cname.endswith(".txt"):
            cname += ".txt"
        try:
            build_selection(chosen, out_dir, cname)
            status_var.set(f"DONE: {len(chosen)} file(s) -> {out_dir}")
            if messagebox.askyesno("Done", f"Wrote {len(chosen)} file(s) to:\n{out_dir}\n\nOpen folder?"):
                open_folder(str(out_dir))
        except Exception as e:
            messagebox.showerror("Build failed", str(e))

    def open_folder(path):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    bot = tk.Frame(root)
    bot.pack(fill=tk.X, padx=10, pady=(4, 10))
    tk.Button(bot, text="BUILD TXT", command=do_build,
              font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Button(bot, text="Open folder",
              command=lambda: open_folder(out_var.get())).pack(side=tk.LEFT, padx=6)

    root.mainloop()


def open_folder_cli(path):
    print(f"Output: {path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        try:
            run_gui()
        except ImportError:
            print("tkinter not available. Use CLI:")
            print("  python tools/build_code_txt.py --all [--out DIR]")
            print("  python tools/build_code_txt.py [--out DIR] <file> ...")
    else:
        files, out_dir = resolve_cli_files(args)
        if files is None:
            print("No files given. Use --all or pass file paths, or run with no args for the GUI.")
            print(__doc__)
        else:
            build_selection(files, out_dir)
