"""
build_code_pdf.py
High-Density Archival Monolith GUI & CLI.
Bundles all .py files into a combined PDF and individual per-file PDFs.

Usage:
python build_code_pdf.py            (Launches GUI Window)
python build_code_pdf.py full       (CLI: single combined PDF)
python build_code_pdf.py split 2    (CLI: split into 2 PDFs)
"""
from pathlib import Path
from fpdf import FPDF
import sys
import os
import subprocess
import io
import json
from datetime import date

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ─── CONFIG ────────────────────────────────────────────────
FONT_SIZE = 0.35
LINE_HEIGHT = 0.50
INDIVIDUAL_FONT_SIZE = 0.4
INDIVIDUAL_LINE_HEIGHT = 0.6
HEADER_SIZE = 0.3
MARGIN = 5

TEXT_COLOR = (10, 35, 64)       # Blueprint Blue
BG_COLOR = (252, 250, 245)      # Archival Cream
HEADER_BG = (220, 230, 245)     # Light Blueprint Blue
HEADER_TEXT = (10, 35, 64)

COLLAPSE_BLANK_LINES = True
PROJECT_ROOT = Path(__file__).resolve().parent
PDF_OUTPUT_DIR = PROJECT_ROOT / "PDFs"
TXT_OUTPUT_DIR = PROJECT_ROOT / "TXTs"
SETTINGS_FILE = PROJECT_ROOT / ".build_settings.json"

PREFERRED_ORDER = [
    "acaristan.py", "camera.py", "config.py", "state.py", "game_core.py",
    "player.py", "weapons.py", "mission.py", "cutscenes.py", "walking_sim.py",
    "effects.py", "ui_hud.py", "interactions.py", "enemy_ai.py", "menu.py",
    "audio.py", "mission2.py", "save_system.py", "settings_store.py",
    "user_settings.py", "smoke_test.py",
]

SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env",
    "build", "dist", ".pytest_cache", ".mypy_cache", "PDFs", "TXTs",
}
SKIP_FILES = {Path(__file__).name.lower()}
INCLUDE_LINE_NUMBERS = False

UNICODE_MONO_FONT_CANDIDATES = [
    PROJECT_ROOT / "DejaVuSansMono.ttf",
    PROJECT_ROOT / "assets" / "DejaVuSansMono.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/usr/local/share/fonts/DejaVuSansMono.ttf"),
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
    Path("/Library/Fonts/Menlo.ttf"),
]
# ───────────────────────────────────────────────────────────

def find_py_files(root: Path):
    found = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts): continue
        if path.name.lower() in SKIP_FILES: continue
        found.append(rel)

    def sort_key(path: Path):
        name = path.name
        rel_str = str(path).replace("\\", "/")
        if name in PREFERRED_ORDER:
            return (0, PREFERRED_ORDER.index(name), rel_str.lower())
        return (1, 9999, rel_str.lower())
    return sorted(found, key=sort_key)

def find_unicode_mono_font():
    for candidate in UNICODE_MONO_FONT_CANDIDATES:
        if candidate.exists(): return candidate
    return None

class CodePDF(FPDF):
    _has_cover = False

    def add_page(self, *args, **kwargs):
        super().add_page(*args, **kwargs)
        self.set_fill_color(*BG_COLOR)
        self.rect(0, 0, self.w, self.h, "F")
        if self.page_no() % 2 != 0:
            self.set_left_margin(12); self.set_right_margin(5)
        else:
            self.set_left_margin(5); self.set_right_margin(12)
        self.set_x(self.l_margin)

    def header(self):
        if self.page_no() == 1 and self._has_cover: return
        l_mar, r_mar = (12, 5) if self.page_no() % 2 != 0 else (5, 12)
        self.set_font("Courier", size=2.5)
        self.set_text_color(100, 100, 100)
        self.set_x(l_mar)
        self.cell(self.w - l_mar - r_mar, 3, "CALL OF ACARISTAN - SOURCE CODE", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 190, 200)
        self.line(l_mar, self.get_y(), self.w - r_mar, self.get_y())
        self.ln(2)

    def footer(self):
        self.set_y(-6)
        self.set_font("Courier", size=3)
        self.set_text_color(100, 100, 100)
        self.cell(0, 3, f"- {self.page_no()} -", align="C")

# Characters commonly missing from monospace fonts like Consolas
GLYPH_REPLACEMENTS = {
    "\u25c6": "#",     # ◆ black diamond
    "\u25ef": "O",     # ◯ large circle
    "\u21c4": "<->",   # ⇄ arrow
    "\u2318": "[Cmd]", # ⌘ command key
    "\u21b5": "[Ret]", # ↵ return
    "\U0001f4c2": "[F]",# 📂 folder
    "\U0001f4c4": "[D]",# 📄 document
    "\u26a0": "[!]",   # ⚠ warning
    "\ufe0f": "",      # variation selector-16
    "\u2713": "v",     # ✓ check
    "\u274c": "X",     # ❌ cross
}

def safe_text(text: str, unicode_font_available: bool) -> str:
    text = text.replace("\ufeff", "")
    for char, replacement in GLYPH_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text if unicode_font_available else text.encode("latin-1", "replace").decode("latin-1")

def get_git_meta():
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], stderr=subprocess.DEVNULL).decode().strip()
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        return f"BRANCH: {branch} | COMMIT: {commit}"
    except Exception: return "GIT METADATA UNAVAILABLE"

def generate_codebase_chart(files):
    if not HAS_MATPLOTLIB: return None
    lengths = []
    for f in files:
        try:
            code = (PROJECT_ROOT / f).read_text(encoding="utf-8")
            lengths.append((f.name, len(code.splitlines())))
        except Exception: pass
    if not lengths: return None
    lengths.sort(key=lambda x: x[1], reverse=True)
    top_files = lengths[:15][::-1]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.barh([x[0] for x in top_files], [x[1] for x in top_files], color='#0A2340')
    ax.set_facecolor('#FCFAF5'); fig.patch.set_facecolor('#FCFAF5')
    for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']: ax.spines[spine].set_color('#0A2340')
    ax.tick_params(colors='#0A2340', labelsize=6)
    ax.set_xlabel('LINES OF CODE', color='#0A2340', fontsize=8, family='monospace')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor())
    plt.close(); buf.seek(0)
    return buf

def write_files_to_txt(files, txt_path):
    lines = []
    for filepath in files:
        abs_path = PROJECT_ROOT / filepath
        try: code = abs_path.read_text(encoding="utf-8")
        except Exception: continue
        lines.extend([f"# {'-'*60}", f"# {filepath}", f"# {'-'*60}", "", code.rstrip(), ""])
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {txt_path}")

def get_file_line_count(filepath):
    abs_path = PROJECT_ROOT / filepath
    code = abs_path.read_text(encoding="utf-8")
    count, prev_blank = 0, False
    for line in code.splitlines():
        is_blank = line.strip() == ""
        if COLLAPSE_BLANK_LINES and is_blank and prev_blank: continue
        count += 1; prev_blank = is_blank
    return count

def split_file_list(files, num_parts, font_size, line_height, header_size):
    page_height = 297 - 2 * MARGIN
    estimates = []
    for f in files:
        count = get_file_line_count(f)
        height = header_size + (count * line_height) + 2
        estimates.append(height)
        
    num_parts = min(num_parts, len(files))
    total = sum(estimates)
    cum = [0]
    for est in estimates: cum.append(cum[-1] + est)
    
    splits = [0]
    for p in range(1, num_parts):
        ideal = total * p / num_parts
        lo, hi = splits[-1] + 1, len(files) - (num_parts - p)
        best, best_diff = lo, abs(cum[lo] - ideal)
        for i in range(lo, hi + 1):
            d = abs(cum[i] - ideal)
            if d < best_diff: best_diff, best = d, i
        splits.append(best)
    splits.append(len(files))
    
    chunks = [files[splits[i]:splits[i + 1]] for i in range(num_parts)]
    est_pages = [(cum[splits[i + 1]] - cum[splits[i]]) / page_height for i in range(num_parts)]
    return chunks, est_pages

def setup_font(pdf: FPDF):
    font_path = find_unicode_mono_font()
    if font_path:
        try:
            pdf.add_font("CodeFont", "", str(font_path))
            pdf.add_font("CodeFont", "B", str(font_path))
            print(f"Using Unicode font: {font_path.name}")
            return "CodeFont", True
        except Exception: pass
    print("Using built-in Courier font.")
    return "Courier", False

def ensure_room_for_header(pdf: FPDF):
    if pdf.get_y() > pdf.h - MARGIN - 8: pdf.add_page()

def add_cover_page(pdf: CodePDF, total_file_count, total_lines, files):
    pdf._has_cover = True; pdf.add_page()
    pdf.set_left_margin(5); pdf.set_right_margin(5); pdf.set_x(pdf.l_margin)
    pdf.ln(20)
    pdf.set_font("Courier", style="B", size=12); pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(0, 10, "CALL OF ACARISTAN", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", size=6)
    pdf.cell(0, 7, "SOURCE CODE ARCHIVAL MONOLITH", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    chart_buf = generate_codebase_chart(files)
    if chart_buf:
        img_w = 80; x = (pdf.w - img_w) / 2
        pdf.image(chart_buf, x=x, y=pdf.get_y(), w=img_w); pdf.ln(40)
    pdf.set_font("Courier", size=4); pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4, get_git_meta(), align="C", new_x="LMARGIN", new_y="NEXT"); pdf.ln(5)
    pdf.set_text_color(*TEXT_COLOR)
    for label, value in [("DATE", date.today().strftime("%Y-%m-%d")), ("FILES", str(total_file_count)), 
                         ("TOTAL LINES", f"{total_lines:,}"), ("DENSITY", "EXTREME")]:
        pdf.cell(0, 4, f"{label}: {value}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10); pdf.set_font("Courier", size=3); pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, "GENERATED BY BUILD_CODE_PDF.PY", align="C", new_x="LMARGIN", new_y="NEXT")

def write_code_line(pdf: FPDF, line: str, line_no: int, unicode_font_available: bool, line_height: float):
    line = line.replace("\t", "    ")
    line = safe_text(line, unicode_font_available)
    first_prefix = f"{line_no:5d} | " if INCLUDE_LINE_NUMBERS else ""
    cont_prefix = "      | " if INCLUDE_LINE_NUMBERS else ""
    if line == "":
        if INCLUDE_LINE_NUMBERS: pdf.cell(0, line_height, first_prefix, new_x="LMARGIN", new_y="NEXT")
        else: pdf.ln(line_height)
        return
    char_w = pdf.get_string_width("M") or 0.001
    start, first = 0, True
    while start < len(line):
        prefix = first_prefix if first else cont_prefix
        prefix_w = pdf.get_string_width(prefix)
        usable_width = pdf.w - pdf.l_margin - pdf.r_margin
        available_for_code = max(1.0, usable_width - prefix_w)
        max_chars = max(1, int(available_for_code / char_w))
        chunk = line[start : start + max_chars]
        pdf.cell(0, line_height, prefix + chunk, new_x="LMARGIN", new_y="NEXT")
        start += max_chars; first = False

def write_files_to_pdf(files, pdf_path, font_size=None, line_height=None, header_size=None, *, add_cover=False, total_file_count=0, total_lines=0):
    if font_size is None: font_size = FONT_SIZE
    if line_height is None: line_height = LINE_HEIGHT
    if header_size is None: header_size = HEADER_SIZE
    
    pdf = CodePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    font_family, unicode_font_available = setup_font(pdf)
    if add_cover: add_cover_page(pdf, total_file_count, total_lines, files)
    pdf.add_page()
    for filepath in files:
        abs_path = PROJECT_ROOT / filepath
        try: code = abs_path.read_text(encoding="utf-8")
        except Exception: continue
        ensure_room_for_header(pdf)
        pdf.start_section(str(filepath), level=0)
        header_text = safe_text(f"  {str(filepath).replace(chr(92), '/').upper()}  ", unicode_font_available)
        pdf.set_fill_color(*HEADER_BG); pdf.set_font(font_family, style="B", size=header_size)
        pdf.set_text_color(*HEADER_TEXT)
        pdf.cell(0, header_size + 1.5, header_text, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT_COLOR); pdf.ln(0.8)
        pdf.set_font(font_family, size=font_size)
        prev_blank = False
        for line_no, raw_line in enumerate(code.splitlines(), start=1):
            is_blank = raw_line.strip() == ""
            if COLLAPSE_BLANK_LINES and is_blank and prev_blank: continue
            write_code_line(pdf, raw_line, line_no, unicode_font_available, line_height)
            prev_blank = is_blank
        pdf.set_draw_color(180, 190, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1)
        print(f"  Added: {filepath}")
    pdf.output(str(pdf_path))
    print(f"Written: {pdf_path}")

# ─── CLI FALLBACK LOGIC ────────────────────────────────────
def choose_mode_cli():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "full": return "full", 0
        if arg == "split" and len(sys.argv) > 2:
            try: return "split", int(sys.argv[2])
            except ValueError: pass
        if arg.startswith("split") and len(arg) > 5:
            try: return "split", int(arg[5:])
            except ValueError: pass
    print("\nCombined PDF mode:")
    print("  1 - Full single PDF (all code in one file)")
    print("  2 - Split into multiple PDFs (no truncated files)")
    while True:
        try:
            choice = input("Choice [1/2]: ").strip()
            if choice == "1": return "full", 0
            if choice == "2":
                parts = input("How many parts? [2/4]: ").strip()
                if parts in ("2", "4"): return "split", int(parts)
        except (EOFError, KeyboardInterrupt): return "full", 0

def build_pdf_cli():
    PDF_OUTPUT_DIR.mkdir(exist_ok=True); TXT_OUTPUT_DIR.mkdir(exist_ok=True)
    files = find_py_files(PROJECT_ROOT)
    if not files: print("No .py files found."); return
    total_lines = sum(len((PROJECT_ROOT / f).read_text(encoding="utf-8").splitlines()) for f in files if (PROJECT_ROOT / f).exists())
    mode, num_parts = choose_mode_cli()
    if mode == "split":
        chunks, est_pages = split_file_list(files, num_parts, FONT_SIZE, LINE_HEIGHT, HEADER_SIZE)
        print(f"\nEstimated pages: {', '.join(f'part {i+1} ~{p:.0f}p' for i, p in enumerate(est_pages))}")
        for i, chunk in enumerate(chunks):
            write_files_to_pdf(chunk, PDF_OUTPUT_DIR / f"game_source_part{i+1}.pdf", add_cover=(i == 0), total_file_count=len(files), total_lines=total_lines)
    else:
        write_files_to_pdf(files, PDF_OUTPUT_DIR / "game_source.pdf", add_cover=True, total_file_count=len(files), total_lines=total_lines)
        write_files_to_txt(files, TXT_OUTPUT_DIR / "game_source.txt")
    print("\n-- Building individual files --")
    for filepath in files:
        name = str(filepath).replace("\\", "/").replace("/", "_")
        write_files_to_pdf([filepath], PDF_OUTPUT_DIR / f"{name}.pdf", font_size=INDIVIDUAL_FONT_SIZE, line_height=INDIVIDUAL_LINE_HEIGHT, header_size=HEADER_SIZE)
        write_files_to_txt([filepath], TXT_OUTPUT_DIR / f"{name}.txt")

# ─── GUI LOGIC (PySide6) ───────────────────────────────────
DARK_THEME_QSS = """
    QWidget {
        background-color: #1A1A1A;
        color: #E0E0E0;
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
        font-size: 14px;
    }
    QMainWindow { background-color: #121212; }

    QFrame#GroupBox {
        background-color: #222222;
        border: 1px solid #2A4B7C;
        border-radius: 10px;
    }

    QComboBox, QDoubleSpinBox, QSpinBox, QAbstractSpinBox {
        background-color: #2B2B2B;
        border: 1px solid #3A5F8C;
        border-radius: 8px;
        padding: 8px 12px;
        color: #FFFFFF;
        min-height: 28px;
        font-size: 14px;
        font-family: "Segoe UI", sans-serif;
    }
    QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {
        border: 1px solid #4DA6FF;
    }
    QAbstractSpinBox QLineEdit {
        color: #FFFFFF;
        background-color: transparent;
        selection-color: #0A0A0A;
    }
    QComboBox {
        padding-right: 35px;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        color: #FFFFFF;
        background-color: #2B2B2B;
        border: 1px solid #3A5F8C;
        selection-background-color: #4DA6FF;
        padding: 6px;
    }

    QPushButton {
        background-color: #222222;
        border: 1px solid #3A5F8C;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
        color: #8AB4F8;
        padding: 12px 24px;
        min-height: 28px;
        font-family: "Segoe UI", sans-serif;
    }
    QPushButton:hover {
        background-color: #2A4B7C;
        color: #FFFFFF;
        border: 1px solid #4DA6FF;
    }
    QPushButton:pressed { background-color: #1E3A5F; }
    QPushButton:disabled {
        color: #666666;
        border: 1px solid #333333;
        background-color: #1A1A1A;
    }

    QTextBrowser {
        background-color: #181818;
        border: 1px solid #3A5F8C;
        border-radius: 8px;
        color: #E0E0E0;
        font-family: "Consolas", "Courier New", monospace;
        padding: 14px;
        font-size: 13px;
    }

    QListWidget {
        background-color: #181818;
        border: 1px solid #3A5F8C;
        border-radius: 8px;
        color: #E0E0E0;
        font-family: "Consolas", monospace;
        padding: 8px;
        font-size: 13px;
    }
    QListWidget::item { padding: 5px 8px; }

    QLabel {
        color: #CCCCCC;
        font-size: 13px;
        background-color: transparent;
        font-family: "Segoe UI", sans-serif;
    }
    QLabel#SectionLabel {
        color: #8AB4F8;
        font-weight: bold;
        font-size: 12px;
        letter-spacing: 1px;
    }

    QProgressBar {
        border: 1px solid #3A5F8C;
        border-radius: 8px;
        text-align: center;
        color: #FFFFFF;
        background-color: #181818;
        min-height: 30px;
        font-weight: bold;
        font-size: 13px;
        font-family: "Segoe UI", sans-serif;
    }
    QProgressBar::chunk { background-color: #4DA6FF; border-radius: 7px; }

    QScrollBar:vertical {
        background: #1A1A1A;
        width: 12px;
        border-radius: 6px;
    }
    QScrollBar:handle:vertical {
        background: #3A5F8C;
        border-radius: 6px;
        min-height: 30px;
    }
    QScrollBar:handle:vertical:hover { background: #4DA6FF; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

DARK_THEME_QSS += """
/* ─── READABILITY / CLIPPING FIXES ───────────────────────── */

QComboBox {
    background-color: #151515;
    border: 1px solid #2E5C93;
    border-radius: 8px;
    color: #EAF2FF;
    padding: 0px 34px 0px 12px;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}

QComboBox:hover {
    border: 1px solid #4DA6FF;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QComboBox QAbstractItemView {
    background-color: #151515;
    color: #EAF2FF;
    border: 1px solid #2E5C93;
    selection-background-color: #1E3A5F;
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 7px 10px;
    color: #EAF2FF;
    background-color: #151515;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #1E3A5F;
    color: #FFFFFF;
}

QDoubleSpinBox, QSpinBox {
    background-color: #151515;
    border: 1px solid #2E5C93;
    border-radius: 8px;
    color: #EAF2FF;
    padding: 0px 30px 0px 10px;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}

QDoubleSpinBox:hover, QSpinBox:hover {
    border: 1px solid #4DA6FF;
}

QDoubleSpinBox QLineEdit, QSpinBox QLineEdit {
    background-color: transparent;
    color: #EAF2FF;
    border: none;
    padding: 0px;
    margin: 0px;
}

QProgressBar {
    border: 1px solid #2E5C93;
    border-radius: 8px;
    text-align: center;
    color: #FFFFFF;
    background-color: #080808;
    min-height: 32px;
    max-height: 32px;
    font-weight: bold;
    font-size: 12px;
}

QProgressBar::chunk {
    background-color: #4DA6FF;
    border-radius: 7px;
}
"""

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QTextBrowser, QProgressBar,
        QLabel, QListWidget, QListWidgetItem, QListView,
        QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy,
        QDoubleSpinBox, QFrame
    )
    from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QPropertyAnimation
    from PySide6.QtGui import QColor, QPalette

    def make_field(label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setObjectName("SectionLabel")
        lbl.setStyleSheet("")
        lbl.setMinimumHeight(14)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(lbl)
        v.addWidget(widget)
        return container

    def make_section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        lbl.setStyleSheet("")
        lbl.setMinimumHeight(16)
        return lbl

    def make_group(title: str):
        """Creates a custom QFrame container to bypass QGroupBox layout bugs."""
        frame = QFrame()
        frame.setObjectName("GroupBox")
        v = QVBoxLayout(frame)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)
        
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #4DA6FF; font-weight: bold; font-size: 11px; letter-spacing: 2px; background-color: transparent;")
        v.addWidget(lbl)
        
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #1E3A5F; border: none;")
        v.addWidget(line)
        v.addSpacing(6)
        
        return frame, v

    def fix_combo_popup(combo: QComboBox):
        view = QListView(combo)
        view.setObjectName("ComboPopup")
        view.setUniformItemSizes(True)
        view.setStyleSheet("""
            QListView#ComboPopup {
                background-color: #151515;
                color: #EAF2FF;
                border: 1px solid #2E5C93;
                outline: none;
                padding: 4px;
            }

            QListView#ComboPopup::item {
                background-color: #151515;
                color: #EAF2FF;
                min-height: 30px;
                padding: 7px 10px;
            }

            QListView#ComboPopup::item:selected {
                background-color: #1E3A5F;
                color: #FFFFFF;
            }

            QListView#ComboPopup::item:hover {
                background-color: #244B78;
                color: #FFFFFF;
            }
        """)
        view.viewport().setStyleSheet("background-color: #151515;")
        combo.setView(view)
        combo.setFixedHeight(36)

    class RadarWorker(QThread):
        finished = Signal(list, int, list)
        def run(self):
            files = find_py_files(PROJECT_ROOT)
            total_lines = 0
            for f in files:
                try: total_lines += len((PROJECT_ROOT / f).read_text(encoding="utf-8").splitlines())
                except: pass
            found_names = {f.name for f in files}
            missing = [name.strip() for name in PREFERRED_ORDER if name.strip() not in found_names]
            self.finished.emit(files, total_lines, missing)

    class BuildWorker(QThread):
        log_signal = Signal(str)
        finished_signal = Signal(str)

        def __init__(self, mode, num_parts, font_size, line_height, header_size):
            super().__init__()
            self.mode = mode
            self.num_parts = num_parts
            self.font_size = font_size
            self.line_height = line_height
            self.header_size = header_size

        def run(self):
            class SignalStream:
                def __init__(self, signal):
                    self.signal = signal
                    self.buffer = ""
                def write(self, text):
                    self.buffer += text
                    while "\n" in self.buffer:
                        line, self.buffer = self.buffer.split("\n", 1)
                        if line.strip(): self.signal.emit(line)
                def flush(self): pass
            
            old_stdout = sys.stdout
            sys.stdout = SignalStream(self.log_signal)
            try:
                PDF_OUTPUT_DIR.mkdir(exist_ok=True); TXT_OUTPUT_DIR.mkdir(exist_ok=True)
                files = find_py_files(PROJECT_ROOT)
                if not files: print("No .py files found."); return
                total_lines = sum(len((PROJECT_ROOT / f).read_text(encoding="utf-8").splitlines()) for f in files if (PROJECT_ROOT / f).exists())
                
                if self.mode == "split":
                    chunks, est_pages = split_file_list(files, self.num_parts, self.font_size, self.line_height, self.header_size)
                    print(f"Estimated pages: {', '.join(f'part {i+1} ~{p:.0f}p' for i, p in enumerate(est_pages))}")
                    for i, chunk in enumerate(chunks):
                        write_files_to_pdf(chunk, PDF_OUTPUT_DIR / f"game_source_part{i+1}.pdf", 
                                           font_size=self.font_size, line_height=self.line_height, header_size=self.header_size,
                                           add_cover=(i == 0), total_file_count=len(files), total_lines=total_lines)
                else:
                    print("Building combined PDF/TXT...")
                    write_files_to_pdf(files, PDF_OUTPUT_DIR / "game_source.pdf", 
                                       font_size=self.font_size, line_height=self.line_height, header_size=self.header_size,
                                       add_cover=True, total_file_count=len(files), total_lines=total_lines)
                    write_files_to_txt(files, TXT_OUTPUT_DIR / "game_source.txt")
                    
                print("\n-- Building individual files --")
                for filepath in files:
                    name = str(filepath).replace("\\", "/").replace("/", "_")
                    write_files_to_pdf([filepath], PDF_OUTPUT_DIR / f"{name}.pdf", 
                                       font_size=self.font_size, line_height=self.line_height, header_size=self.header_size)
                    write_files_to_txt([filepath], TXT_OUTPUT_DIR / f"{name}.txt")
                    
                print(f"\nPDF output: {PDF_OUTPUT_DIR}/")
                self.finished_signal.emit("ARCHIVAL SEQUENCE COMPLETE.")
            except Exception as e:
                self.log_signal.emit(f"ERROR: {str(e)}")
                self.finished_signal.emit("SEQUENCE FAILED.")
            finally:
                sys.stdout = old_stdout

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CALL OF ACARISTAN // ARCHIVAL MONOLITH")
            self.resize(1080, 820)                          
            self.setMinimumSize(920, 720)

            central = QWidget()
            self.setCentralWidget(central)

            outer = QHBoxLayout(central)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.addStretch(1)

            card = QWidget()
            card.setMaximumWidth(1000)
            card.setMinimumWidth(860)
            layout = QVBoxLayout(card)
            layout.setSpacing(22)
            layout.setContentsMargins(36, 28, 36, 28)

            outer.addWidget(card, stretch=0)
            outer.addStretch(1)

            # ── Title Block ──
            title_block = QVBoxLayout()
            title_block.setSpacing(6)
            title = QLabel("CALL OF ACARISTAN")
            title.setStyleSheet("font-size: 26px; font-weight: bold; color: #4DA6FF; letter-spacing: 3px; background-color: transparent;")
            title.setAlignment(Qt.AlignCenter)
            subtitle = QLabel("HIGH-DENSITY SOURCE ARCHIVAL TOOL")
            subtitle.setStyleSheet("font-size: 11px; color: #666; letter-spacing: 2px; background-color: transparent;")
            subtitle.setAlignment(Qt.AlignCenter)
            title_block.addWidget(title)
            title_block.addWidget(subtitle)
            layout.addLayout(title_block)

            # ── Two-column content row ──
            content_row = QHBoxLayout()
            content_row.setSpacing(20)

            # LEFT: Radar
            radar_group, radar_layout = make_group("PROJECT RADAR")
            self.radar_label = QLabel("Scanning project files...")
            self.radar_label.setStyleSheet("font-weight: bold; color: #4DA6FF; font-size: 14px; padding: 4px 0; background-color: transparent;")
            self.radar_list = QListWidget()
            self.radar_list.setMinimumHeight(220)
            radar_layout.addWidget(self.radar_label)
            radar_layout.addWidget(self.radar_list, stretch=1)
            content_row.addWidget(radar_group, stretch=5)

            # RIGHT: Config
            config_group, config_layout = make_group("CONFIGURATION")

            self.mode_combo = QComboBox()
            self.mode_combo.addItems([
                "Single combined PDF",
                "Split into volumes"
            ])
            self.mode_combo.currentIndexChanged.connect(self.toggle_split)
            self.mode_combo.currentIndexChanged.connect(self.update_estimate)
            fix_combo_popup(self.mode_combo)
            config_layout.addWidget(make_field("OUTPUT FORMAT", self.mode_combo))

            self.parts_combo = QComboBox()
            self.parts_combo.addItems(["2", "3", "4", "5", "6", "8"])
            self.parts_combo.currentIndexChanged.connect(self.update_estimate)
            fix_combo_popup(self.parts_combo)
            self.parts_field = make_field("NUMBER OF VOLUMES", self.parts_combo)
            self.parts_field.setVisible(False)
            config_layout.addWidget(self.parts_field)

            # --- Live Density Controllers ---
            density_row1 = QHBoxLayout()
            density_row1.setSpacing(10)
            
            self.font_spin = QDoubleSpinBox()
            self.font_spin.setRange(0.15, 1.5)
            self.font_spin.setSingleStep(0.05)
            self.font_spin.setSuffix(" mm")
            self.font_spin.setFixedHeight(36)
            self.font_spin.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.font_spin.valueChanged.connect(self.update_estimate)
            density_row1.addWidget(make_field("FONT SIZE", self.font_spin))

            self.line_spin = QDoubleSpinBox()
            self.line_spin.setRange(0.15, 2.0)
            self.line_spin.setSingleStep(0.05)
            self.line_spin.setSuffix(" mm")
            self.line_spin.setFixedHeight(36)
            self.line_spin.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.line_spin.valueChanged.connect(self.update_estimate)
            density_row1.addWidget(make_field("LINE HEIGHT", self.line_spin))
            
            config_layout.addLayout(density_row1)

            self.header_spin = QDoubleSpinBox()
            self.header_spin.setRange(0.15, 1.5)
            self.header_spin.setSingleStep(0.05)
            self.header_spin.setSuffix(" mm")
            self.header_spin.setFixedHeight(36)
            self.header_spin.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.header_spin.valueChanged.connect(self.update_estimate)
            config_layout.addWidget(make_field("HEADER SIZE", self.header_spin))

            self.page_bar = QProgressBar()
            self.page_bar.setRange(0, 150)
            self.page_bar.setValue(0)
            self.page_bar.setTextVisible(True)
            self.page_bar.setFormat("~0 Pages (Target: 90)")
            self.page_bar.setMinimumHeight(34)
            config_layout.addWidget(make_field("90-PAGE BUDGET VISUALIZER", self.page_bar))

            config_layout.addStretch(1)
            content_row.addWidget(config_group, stretch=4)

            layout.addLayout(content_row, stretch=0)

            # ── Build button + progress ──
            self.build_btn = QPushButton("  INITIATE ARCHIVAL SEQUENCE   [⌘ ↵]  ")
            self.build_btn.setMinimumHeight(54)
            self.build_btn.setStyleSheet("font-size: 15px; font-weight: bold; letter-spacing: 1px;")
            self.build_btn.clicked.connect(self.start_build)
            layout.addWidget(self.build_btn)

            self.progress = QProgressBar()
            self.progress.setRange(0, 0)
            self.progress.setMaximumHeight(6)
            self.progress.setTextVisible(False)
            self.progress.setVisible(False)
            layout.addWidget(self.progress)

            # ── Log console ──
            layout.addWidget(make_section_label("BUILD LOG"))
            self.log_text = QTextBrowser()
            self.log_text.setReadOnly(True)
            self.log_text.setMinimumHeight(140)
            self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.log_text.anchorClicked.connect(self.open_link)
            self.log_text.document().setDefaultStyleSheet("p { line-height: 1.5; }")
            layout.addWidget(self.log_text, stretch=1)

            # ── Bottom buttons ──
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(14)
            self.open_btn = QPushButton("📂  Reveal Generated PDFs")
            self.open_btn.setMinimumHeight(46)
            self.open_btn.setEnabled(False)
            self.open_btn.clicked.connect(self.open_output_folder)

            self.open_ind_btn = QPushButton("📄  Last File")
            self.open_ind_btn.setMinimumHeight(46)
            self.open_ind_btn.setFixedWidth(170)
            self.open_ind_btn.setEnabled(False)
            self.open_ind_btn.clicked.connect(self.open_last_file)

            btn_layout.addWidget(self.open_btn, stretch=2)
            btn_layout.addWidget(self.open_ind_btn, stretch=0)
            layout.addLayout(btn_layout)

            # ── State ──
            self.worker = None
            self.files = []
            self.last_generated_file = None

            # Start async radar scan
            self.radar_worker = RadarWorker()
            self.radar_worker.finished.connect(self.on_radar_finished)
            self.radar_worker.start()

            # Load settings
            self.load_settings()

        def toggle_split(self, index):
            is_split = (index == 1)
            self.parts_field.setVisible(is_split)
            self.update_estimate()

        def update_estimate(self):
            if not self.files: return
            
            font_size = self.font_spin.value()
            line_height = self.line_spin.value()
            header_size = self.header_spin.value()

            if line_height < font_size:
                self.page_bar.setRange(0, 1)
                self.page_bar.setValue(1)
                self.page_bar.setFormat("LINE HEIGHT < FONT SIZE - TEXT OVERLAP")
                self.page_bar.setStyleSheet("""
                    QProgressBar { border: 1px solid #F44336; border-radius: 8px; text-align: center; color: #FFFFFF; background-color: #050505; min-height: 30px; font-weight: bold; }
                    QProgressBar::chunk { background-color: #F44336; border-radius: 7px; }
                """)
                return

            self.page_bar.setRange(0, 150)
            
            page_height = 297 - 2 * MARGIN
            mode_idx = self.mode_combo.currentIndex()
            mode = "split" if mode_idx == 1 else "full"
            parts_idx = self.parts_combo.currentIndex()
            parts = int(self.parts_combo.itemText(parts_idx)) if mode == "split" else 1
            
            if mode == "split":
                chunks, est_pages = split_file_list(self.files, parts, font_size, line_height, header_size)
                total_est = sum(est_pages)
            else:
                total_height = 0
                for f in self.files:
                    count = get_file_line_count(f)
                    total_height += header_size + (count * line_height) + 2
                total_est = total_height / page_height

            self.page_bar.setValue(int(total_est))
            
            if total_est < 80: 
                color = "#00C853"
                status = "OPTIMAL"
            elif total_est <= 95: 
                color = "#FFD740"
                status = "TIGHT"
            else: 
                color = "#F44336"
                status = "EXCEEDS BUDGET"
                
            self.page_bar.setStyleSheet(f"""
                QProgressBar {{ border: 1px solid #2A4B7C; border-radius: 8px; text-align: center; color: #FFFFFF; background-color: #050505; min-height: 30px; font-weight: bold; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 7px; }}
            """)
            
            self.page_bar.setFormat(f"{status}  |  ~{int(total_est)} pages  |  target 90")

        def on_radar_finished(self, files, total_lines, missing):
            self.files = files
            self.radar_label.setText(f"{len(files)} FILES DETECTED   |   {total_lines:,} LINES")
            self.radar_list.clear()
            
            for name in PREFERRED_ORDER:
                name_clean = name.strip()
                item = QListWidgetItem(name_clean)
                if name_clean in missing:
                    item.setForeground(QColor("#FF6B6B"))
                    item.setText(f"{name_clean}  (MISSING)")
                else:
                    item.setForeground(QColor("#4CAF50"))
                self.radar_list.addItem(item)
                
            self.update_estimate()

        def load_settings(self):
            self.font_spin.setValue(FONT_SIZE)
            self.line_spin.setValue(LINE_HEIGHT)
            self.header_spin.setValue(HEADER_SIZE)
            
            if SETTINGS_FILE.exists():
                try:
                    data = json.loads(SETTINGS_FILE.read_text())
                    self.mode_combo.setCurrentIndex(data.get("mode", 0))
                    self.parts_combo.setCurrentIndex(data.get("parts", 0))
                    self.font_spin.setValue(data.get("font", FONT_SIZE))
                    self.line_spin.setValue(data.get("line", LINE_HEIGHT))
                    self.header_spin.setValue(data.get("header", HEADER_SIZE))
                    self.apply_startup_glow()
                except Exception: pass

        def apply_startup_glow(self):
            effect = QGraphicsDropShadowEffect()
            effect.setColor(QColor(77, 166, 255))
            effect.setBlurRadius(15)
            effect.setOffset(0)
            
            self.mode_combo.setGraphicsEffect(effect)
            self.parts_combo.setGraphicsEffect(effect)
            
            QTimer.singleShot(1500, lambda: self.mode_combo.setGraphicsEffect(None))
            QTimer.singleShot(1500, lambda: self.parts_combo.setGraphicsEffect(None))

        def save_settings(self):
            data = {
                "mode": self.mode_combo.currentIndex(),
                "parts": self.parts_combo.currentIndex(),
                "font": self.font_spin.value(),
                "line": self.line_spin.value(),
                "header": self.header_spin.value()
            }
            SETTINGS_FILE.write_text(json.dumps(data))
            self.show_toast("✓ Configuration saved for next session")

        def show_toast(self, msg):
            if not hasattr(self, 'toast'):
                self.toast = QLabel(msg, self)
                self.toast.setStyleSheet("background-color: #4DA6FF; color: #0A0A0A; padding: 8px 16px; border-radius: 4px; font-weight: bold; font-size: 14px;")
                self.toast.hide()
            
            self.toast.setText(msg)
            self.toast.adjustSize()
            x = (self.width() - self.toast.width()) // 2
            y = self.height() - 150
            self.toast.move(x, y)
            self.toast.show()
            self.toast.raise_()
            
            effect = QGraphicsOpacityEffect()
            self.toast.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(2500)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(self.toast.hide)
            anim.start()
            self.toast_anim = anim

        def start_build(self):
            self.save_settings()
            self.log_text.clear(); self.build_btn.setEnabled(False); self.progress.setVisible(True)
            self.open_btn.setEnabled(False); self.open_ind_btn.setEnabled(False)
            if hasattr(self, 'pulse_timer'): self.pulse_timer.stop()
            
            mode = "split" if self.mode_combo.currentIndex() == 1 else "full"
            parts = int(self.parts_combo.currentText())
            
            font_size = self.font_spin.value()
            line_height = self.line_spin.value()
            header_size = self.header_spin.value()
            
            self.worker = BuildWorker(mode, parts, font_size, line_height, header_size)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.build_finished)
            self.worker.start()

        def append_log(self, text):
            if "Added: " in text:
                filename = text.split("Added: ")[-1].strip()
                filepath = next((f for f in self.files if str(f).replace("\\", "/") == filename or f.name == filename), None)
                if filepath:
                    abs_path = str((PROJECT_ROOT / filepath).resolve())
                    url = QUrl.fromLocalFile(abs_path).toString()
                    html = f'&gt; <a href="{url}" style="color:#00FF41; text-decoration:none; font-weight:bold;">{text}</a>'
                    self.log_text.append(html)
                    self.last_generated_file = abs_path
                    return
                    
            self.log_text.append(f"&gt; {text}")
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        def open_link(self, url):
            path = url.toLocalFile()
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': subprocess.run(['open', path])
            else: subprocess.run(['xdg-open', path])

        def open_output_folder(self):
            path = str(PDF_OUTPUT_DIR.resolve())
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': subprocess.run(['open', path])
            else: subprocess.run(['xdg-open', path])

        def open_last_file(self):
            if self.last_generated_file:
                path = self.last_generated_file
                if sys.platform == 'win32': os.startfile(path)
                elif sys.platform == 'darwin': subprocess.run(['open', path])
                else: subprocess.run(['xdg-open', path])

        def start_pulse(self):
            if hasattr(self, 'pulse_timer') and self.pulse_timer.isActive(): return
            self.pulse_timer = QTimer()
            self.pulse_timer.timeout.connect(self.toggle_pulse)
            self.pulse_state = False
            self.pulse_timer.start(600)

        def toggle_pulse(self):
            if not self.open_btn.isEnabled():
                self.pulse_timer.stop(); return
            if self.pulse_state:
                self.open_btn.setStyleSheet("QPushButton { background-color: #2A4B7C; color: #FFFFFF; border: 2px solid #4DA6FF; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px; }")
            else:
                self.open_btn.setStyleSheet("QPushButton { background-color: #1E1E1E; color: #4DA6FF; border: 2px solid #2A4B7C; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 6px; }")
            self.pulse_state = not self.pulse_state

        def build_finished(self, msg):
            self.append_log(msg); self.progress.setVisible(False); self.build_btn.setEnabled(True)
            if "COMPLETE" in msg:
                self.open_btn.setEnabled(True)
                self.open_ind_btn.setEnabled(True)
                self.start_pulse()

    def run_gui():
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(DARK_THEME_QSS)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

except ImportError:
    def run_gui():
        print("="*50)
        print("GUI MODE REQUIRES PySide6.")
        print("Install it via: pip install PySide6")
        print("Falling back to CLI mode...")
        print("="*50)
        build_pdf_cli()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        build_pdf_cli()
    else:
        run_gui()