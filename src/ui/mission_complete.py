"""Physical KRAP Intelligence Case Dossier for MISSION_COMPLETE.

Intentionally distinct from ui.mission_failed (dark electronic error terminal):
this screen presents an open manila case file resting on a tungsten-lit desk,
with a taped 3D field diorama (ui.mission_complete_3d, rendered live by
engine3d) and paperclipped audio transcript on the left leaf, a typed cream
after-action sheet (FORM KR-47) with dotted-leader records and a tilted rubber
stamp on the right leaf, and a steel command rail along the bottom edge.
"""
import pygame

from core import mission_meta
from core.config import HEIGHT, WIDTH
from engine.text import T as _T
from ui import kit as _kit
from ui.widgets import ModernButton, note_hover

# Warm archive & desk palette (matches tools/sprites/palette.py)
DESK_DARK = (16, 13, 12)
DESK_SEAM = (10, 8, 7)
DESK_MAT = (19, 22, 24)
DESK_MAT_EDGE = (36, 40, 42)
MANILA = (148, 130, 92)
MANILA_SHD = (138, 120, 84)
MANILA_HI = (178, 160, 118)
MANILA_EDGE = (82, 68, 46)
PAPER = (226, 218, 196)
PAPER_RULE = (208, 198, 174)
PAPER_EDGE = (166, 154, 132)
PHOTO_BORDER = (232, 226, 212)
SLIP_BG = (214, 212, 204)
INK_DARK = (28, 24, 22)
INK_MID = (82, 74, 64)
INK_MUTED = (122, 112, 98)
KRAP_BLUE = (48, 82, 142)
STAMP_GREEN = (40, 104, 66)
STAMP_RED = (148, 42, 38)

# key -> (location, exhibit_caption, photo_kind, stamp_accent)
PROFILES = {
    "MISSION0": ("WAREHOUSE DEPOT", "SUPPLY CRATE // MANIFEST 114", "depot", STAMP_GREEN),
    "MISSION1": ("KILEMENO HARBOR", "LOADING ROAD // EXFIL 03:17", "notebook", STAMP_GREEN),
    "MISSION2": ("ROUTE 12", "CONTROL 04 // AUTH CHAIN SENT", "route", STAMP_GREEN),
    "MISSION3": ("STABILIZATION CENTER", "STUDIO BOOTH // 22:00 ADDRESS", "broadcast", STAMP_GREEN),
    "MISSION4": ("THE CAPITAL", "RADIO ROOFTOP // FIRST LIGHT", "tower", STAMP_GREEN),
    "MISSION5": ("THE CAPITAL", "DRAINAGE TUNNEL // RIVER GATE", "tunnel", STAMP_GREEN),
    "MISSION6": ("KIM KIM BORDER", "PLATFORM 01 // FILE: VELICU, B.", "border", STAMP_GREEN),
    "MISSION7": ("VALEA SEACA HILLS", "FIELD RECEIVER // TWO CHANNELS", "farm", STAMP_GREEN),
    "MISSION8": ("ROUTE 12 / KIM KIM", "BORDER CROSSING // 06:00", "crossing", STAMP_RED),
}
_DEFAULT_PROFILE = ("ACARISTAN", "FIELD RECORD // VERIFIED", "depot", STAMP_GREEN)

# Missions with no entry in core.mission_meta resolve to NEUTRAL_OPERATION there.
_TITLE_OVERRIDES = {"MISSION0": "DEPOT SWEEP - MANIFEST 114"}

_DEBRIEF = {
    "MISSION0": (
        "Perimeter swept  ·  Supply manifest 114 logged  ·  Ready for field deployment",
        "FIELD LOG // DEPOT",
        '"Manifest 114 verified. Guard stamp active on medical crates."',
    ),
    "MISSION1": (
        "Target escaped  ·  Notebook recovered  ·  Questions remain",
        "Vasile, over the radio:",
        '"Good. I\'ve got it. Later. You need sleep."',
    ),
    "MISSION2": (
        "KRAP framed  ·  Evidence transmitted  ·  Comms compromised",
        "Vasile, over broken static:",
        '"No. They framed you first."',
    ),
    "MISSION3": (
        "Vostral aired live at 22:00  ·  Balaceanu exposed  ·  Facility breached",
        "Volkov, in the dark booth:",
        '"Six years he spent building it. You read it in one minute."',
    ),
    "MISSION4": (
        "Transmitter held till dawn  ·  Balaceanu arrested live  ·  The capital cheers",
        "Biribel, on the studio roof at dawn:",
        '"Nobody asked us to do this. First time in my life - that\'s how it\'s done right."',
    ),
    "MISSION5": (
        "Print works raided  ·  Maru extracted via river tunnel  ·  Ucilev held fire",
        "Maru, in the radio station:",
        '"Good answer. Tools get pointed at the people too - remember that."',
    ),
    "MISSION6": (
        "Volkov reached the train  ·  Last notebook recovered  ·  Vasile named",
        "Volkov, at the boxcar:",
        '"I just wanted to get out. Funny. You did too."',
    ),
    "MISSION7": (
        "Farm burned in the Guard sweep  ·  Bodi joined you  ·  Channel chosen",
        "Bodi, on the tractor seat:",
        '"They\'ll come back. There\'s nothing left to come back to. I\'m coming with you."',
    ),
}

_NEXT_META_KEYS = {
    "MISSION1": "MISSION2",
    "MISSION2": "MISSION3",
    "MISSION3": "MISSION4",
    "MISSION4": "MISSION5",
    "MISSION5": "MISSION6",
    "MISSION6": "MISSION7",
    "MISSION7": "MISSION8",
}

_buttons = [ModernButton(0, 0, "MAIN MENU"), ModernButton(0, 0, "NEXT")]
_ui = {"focus": 0, "kb_nav": False}
_sheet_cache = {"sig": None, "surf": None}


def _sfx(name, volume):
    try:
        from core.config import audio
        audio.play(name, volume=volume)
    except Exception:
        pass


def _mission_key(state):
    raw = getattr(state, "active_mission", None)
    if raw in PROFILES:
        return raw
    return mission_meta.mission_key(state) or raw


def _mission_num(key):
    if isinstance(key, str) and key.startswith("MISSION") and key[7:].isdigit():
        return int(key[7:])
    return None


def _button_rects(count, w, h):
    y = h - 58
    if count > 1:
        return [pygame.Rect(536, y, 176, 40), pygame.Rect(728, y, 224, 40)]
    return [pygame.Rect(728, y, 224, 40)]


def enter():
    """Reset screen focus, hover states, and cached sheet on state entry."""
    _ui["focus"] = -1  # resolved to rightmost primary action on first event/draw
    _ui["kb_nav"] = False
    _sheet_cache["sig"] = None
    _sheet_cache["surf"] = None
    try:
        from ui import mission_complete_3d as _mc3d
        _mc3d.enter()
    except Exception:
        pass
    for b in _buttons:
        b.is_hovered = False
        b.is_selected = False
        b.press_dip = 0.0
        b.flash_timer = 0.0


def button_specs(state, has_next):
    """Left-to-right (action, label) buttons on the bottom desk rail."""
    key = _mission_key(state)
    num = _mission_num(key)
    if has_next and num is not None and 1 <= num <= 7:
        return [
            ("menu", _T("mc.main_menu")),
            ("continue", _T("mc.next_mission", num=f"{num + 1:02d}")),
        ]
    return [("menu", _T("mc.return_menu"))]


def handle_event(event, mouse_x, mouse_y, state, elapsed_frames, has_next):
    """Handle keyboard/mouse controls; return 'continue', 'menu', or None."""
    specs = button_specs(state, has_next)
    rects = _button_rects(len(specs), WIDTH, HEIGHT)
    for i, (_act, label) in enumerate(specs):
        _buttons[i].text = label
        _buttons[i].rect = rects[i]
    for j in range(len(specs), len(_buttons)):
        _buttons[j].rect = pygame.Rect(-999, -999, 0, 0)

    default_idx = len(specs) - 1
    if not (0 <= _ui["focus"] < len(specs)):
        _ui["focus"] = default_idx

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            _sfx("menu_click", 0.5)
            return "menu"
        if len(specs) > 1 and event.key in (
                pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d, pygame.K_TAB):
            step = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
            _ui["focus"] = (_ui["focus"] + step) % len(specs)
            _ui["kb_nav"] = True
            _sfx("menu_hover", 0.25)
            return None
        if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            return specs[_ui["focus"]][0]

    elif event.type == pygame.MOUSEMOTION:
        for i in range(len(specs)):
            if _buttons[i].rect.collidepoint(mouse_x, mouse_y):
                _ui["kb_nav"] = False
                _ui["focus"] = i
                break

    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and elapsed_frames >= 18:
        for i, (act, _label) in enumerate(specs):
            if _buttons[i].rect.collidepoint(mouse_x, mouse_y):
                _sfx("menu_click", 0.5)
                _buttons[i].press()
                return act

    return None


def _draw_text(surf, label, x, y, size=13, color=INK_DARK, weight="regular", align="left"):
    img = _kit.font(size, weight).render(str(label), True, color)
    if align == "right":
        x -= img.get_width()
    elif align == "center":
        x -= img.get_width() // 2
    surf.blit(img, (x, y))
    return img.get_rect(topleft=(x, y))


def _wrap(text, width, size=13, weight="regular"):
    f = _kit.font(size, weight)
    lines, line = [], ""
    for para in str(text).split("\n"):
        for word in para.split():
            trial = (line + " " + word).strip()
            if line and f.size(trial)[0] > width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
            line = ""
    return lines


def debrief_copy(state, key):
    """Return (outcome, quote_attr, quote, stamp_override) for *key*."""
    if key == "MISSION8":
        route = getattr(state, "m8_route", "revenge")
        if route == "duty":
            return (
                "Ucilev neutralized on the pad  ·  Retardovici dead on the ridge  ·  Interim President Vasile",
                "Biribel, at the inauguration:",
                '"Gabi, Seby, Darius. Volkov. The country\'s free. I wanted to tell you that."',
                _T("mc.case_closed"),
            )
        return (
            "Vasile dead at Route 12  ·  Maru lost at the mansion  ·  Border train departed",
            "Biribel, on the border train:",
            '"Volkov - I caught your train. The coffee\'s terrible."',
            _T("mc.case_closed"),
        )

    default_out, default_attr, default_quote = _DEBRIEF.get(
        key,
        ("Operation concluded  ·  Field record archived", "", ""),
    )
    if key in ("MISSION1", "MISSION2", "MISSION6"):
        outcome = getattr(state, "active_mission_outcome", None) or default_out
    else:
        outcome = default_out

    if key in ("MISSION1", "MISSION2", "MISSION4", "MISSION5", "MISSION6"):
        quote_attr = getattr(state, "active_mission_quote_attr", None) or default_attr
        quote = getattr(state, "active_mission_quote", None) or default_quote
    else:
        quote_attr, quote = default_attr, default_quote

    return outcome, quote_attr, quote, None


def ledger_rows(state, report, key):
    """Four mission-authentic typed ledger entries (no arcade score/rank)."""
    elapsed_str = str(report.get("time_str", "00:00"))
    kills_str = str(report.get("kills", 0))
    acc_str = f"{int(report.get('accuracy', 0))}%"

    if key == "MISSION1":
        fourth = ("LOGBOOK", "RECOVERED" if getattr(state, "notebook_collected", False) else "LOGGED")
    elif key == "MISSION2":
        ev = getattr(state, "mission2_evidence", []) or []
        found = sum(bool(item.get("done")) for item in ev)
        fourth = ("EVIDENCE", f"{found}/3 SENT")
    elif key == "MISSION3":
        fourth = ("VOSTRAL", "ON AIR" if getattr(state, "mission3_evidence_uploaded", False) else "SECURED")
    elif key == "MISSION4":
        tone = getattr(state, "m4_tone", None)
        if tone:
            fourth = ("ALLEGIANCE", "THE STATE" if tone[0] == 0 else "THE PEOPLE")
        else:
            fourth = ("TRANSMISSION", "HELD" if getattr(state, "m4_broadcast_held", False) else "ACTIVE")
    elif key == "MISSION5":
        gk = int(getattr(state, "m5_guard_kills", 0) or 0)
        fourth = ("QUARTER KILLS", "NONE" if gk == 0 else str(gk))
    elif key == "MISSION6":
        fourth = ("GUARD FILE", "VELICU, B.")
    elif key == "MISSION7":
        preps = getattr(state, "m7_preps", ()) or ()
        fourth = ("FARM PREPS", f"{len(preps)}/3 SET")
    elif key == "MISSION8":
        route = getattr(state, "m8_route", "revenge")
        fourth = ("ROUTE", "HEAD OF STATE" if route == "duty" else "OLD FRIENDS")
    else:
        fourth = ("SHOTS FIRED", str(report.get("shots_fired", 0)))

    return [
        ("ELAPSED TIME", elapsed_str),
        ("HOSTILES DOWN", kills_str),
        ("SHOT ACCURACY", acc_str),
        fourth,
    ]


def _draw_tape(surf, cx, cy, angle_deg):
    tape = pygame.Surface((52, 16), pygame.SRCALPHA)
    tape.fill((212, 196, 146, 192))
    pygame.draw.rect(tape, (172, 156, 112, 180), tape.get_rect(), 1)
    rot = pygame.transform.rotate(tape, angle_deg)
    r = rot.get_rect(center=(cx, cy))
    surf.blit(rot, r.topleft)


def _draw_rubber_stamp(surf, x, y, label, color, angle_deg=-7):
    f = _kit.font(16, "bold")
    tw, th = f.size(label)
    sw, sh = tw + 30, th + 18
    stamp = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.rect(stamp, (*color, 210), (0, 0, sw, sh), 3)
    pygame.draw.rect(stamp, (*color, 175), (4, 4, sw - 8, sh - 8), 1)
    txt = f.render(label, True, (*color, 225))
    stamp.blit(txt, (15, 9))
    rot = pygame.transform.rotate(stamp, angle_deg)
    surf.blit(rot, (x, y))


def _draw_dotted_row(surf, label, value, x_left, x_right, y):
    lf = _kit.font(12, "bold")
    vf = _kit.font(13, "bold")
    ls = lf.render(label, True, INK_MID)
    vs = vf.render(value, True, INK_DARK)
    surf.blit(ls, (x_left, y + 1))
    surf.blit(vs, (x_right - vs.get_width(), y))
    dot_start = x_left + ls.get_width() + 8
    dot_end = x_right - vs.get_width() - 8
    if dot_end > dot_start + 8:
        df = _kit.font(11, "regular")
        step = max(5, df.size(".")[0] + 2)
        dx = dot_start
        while dx < dot_end - 3:
            surf.blit(df.render(".", True, INK_MUTED), (dx, y + 1))
            dx += step


def _fit_display_size(label, max_w, start_size=28, min_size=18):
    size = start_size
    while size > min_size and _kit.font(size, "display").size(label)[0] > max_w:
        size -= 2
    return size


def _build_sheet(state, report, key, has_next):
    """Build the 1000x700 desk + open manila dossier surface (cached per mission)."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    location, exhibit_cap, _photo_kind, stamp_col = PROFILES.get(key, _DEFAULT_PROFILE)
    outcome, quote_attr, quote, stamp_override = debrief_copy(state, key)
    rows = ledger_rows(state, report, key)

    # 1. Dark wooden desk + felt mat + upper-left warm lamp pool
    surf.fill(DESK_DARK)
    for y in (78, 172, 266, 360, 454, 548):
        pygame.draw.line(surf, DESK_SEAM, (0, y), (WIDTH, y), 1)
        pygame.draw.line(surf, (24, 19, 17), (0, y + 1), (WIDTH, y + 1), 1)

    mat = pygame.Rect(42, 34, 916, 580)
    pygame.draw.rect(surf, DESK_MAT, mat)
    pygame.draw.rect(surf, DESK_MAT_EDGE, mat, 1)

    lamp = pygame.Surface((WIDTH, 624), pygame.SRCALPHA)
    for r, alpha in ((520, 12), (400, 14), (290, 16), (190, 18), (110, 14)):
        pygame.draw.circle(lamp, (255, 198, 120, alpha), (190, 90), r)
    surf.blit(lamp, (0, 0))

    _draw_text(surf, _T("mc.archive_desk"), 44, 12, 11, (124, 114, 96), "bold")
    _draw_text(surf, "KRAPNET // " + _T("app.mission_complete"), WIDTH - 44, 12, 11, (148, 128, 92), "bold", "right")

    # 2. Open manila folder + index tab + spine fasteners
    num = _mission_num(key)
    case_tag = f"M-{num:02d}" if num is not None else "OPS"
    shd = pygame.Surface((864, 544), pygame.SRCALPHA)
    shd.fill((0, 0, 0, 145))
    surf.blit(shd, (76, 64))

    tab = pygame.Rect(86, 34, 232, 22)
    pygame.draw.rect(surf, MANILA, tab)
    pygame.draw.rect(surf, MANILA_HI, (tab.x, tab.y, tab.w, 1))
    pygame.draw.line(surf, MANILA_EDGE, tab.topleft, tab.bottomleft)
    pygame.draw.line(surf, MANILA_EDGE, tab.topright, tab.bottomright)
    _draw_text(surf, _T("mc.case_file_tag", tag=case_tag), tab.x + 14, tab.y + 3, 11, INK_DARK, "bold")

    left_leaf = pygame.Rect(68, 54, 430, 544)
    right_leaf = pygame.Rect(502, 54, 430, 544)
    pygame.draw.rect(surf, MANILA, left_leaf)
    pygame.draw.rect(surf, MANILA_SHD, right_leaf)
    pygame.draw.line(surf, MANILA_HI, left_leaf.topleft, left_leaf.topright)
    pygame.draw.line(surf, MANILA_HI, left_leaf.topleft, left_leaf.bottomleft)
    pygame.draw.rect(surf, MANILA_EDGE, (68, 54, 864, 544), 1)
    pygame.draw.rect(surf, (94, 80, 56), (496, 55, 8, 542))
    pygame.draw.line(surf, (68, 56, 38), (500, 55), (500, 597), 1)
    for fy in (160, 488):
        pygame.draw.rect(surf, (154, 158, 156), (492, fy, 16, 6))
        pygame.draw.rect(surf, (76, 78, 76), (492, fy, 16, 6), 1)

    # 3. Left leaf: taped field Polaroid + paperclipped audio transcript slip
    photo_shd = pygame.Surface((360, 266), pygame.SRCALPHA)
    photo_shd.fill((0, 0, 0, 75))
    surf.blit(photo_shd, (108, 86))
    photo_card = pygame.Rect(104, 82, 360, 266)
    pygame.draw.rect(surf, PHOTO_BORDER, photo_card)
    pygame.draw.rect(surf, (172, 164, 146), photo_card, 1)

    # Live 3D diorama viewport: the exhibit window is a dark plate in the
    # cached sheet; draw() blits the rendered frame over it and re-lays the
    # masking tape, because the 3D frame animates and the sheet does not.
    pygame.draw.rect(surf, (14, 17, 21), (124, 98, 320, 190))
    pygame.draw.rect(surf, (58, 54, 48), (123, 97, 322, 192), 1)
    _draw_text(surf, _kit.fit(_T("mc.exhibit_loc", loc=location), 11, 320, "bold"),
               124, 299, 11, INK_DARK, "bold")
    _draw_text(surf, _kit.fit(exhibit_cap, 11, 320), 124, 319, 11, INK_MID)

    slip_shd = pygame.Surface((360, 204), pygame.SRCALPHA)
    slip_shd.fill((0, 0, 0, 65))
    surf.blit(slip_shd, (107, 371))
    slip = pygame.Rect(104, 368, 360, 204)
    pygame.draw.rect(surf, SLIP_BG, slip)
    pygame.draw.rect(surf, (154, 150, 140), slip, 1)
    # Paperclip at top-left of transcript slip
    pygame.draw.rect(surf, (152, 158, 162), (122, 358, 10, 24), 2, border_radius=4)
    pygame.draw.rect(surf, (112, 118, 122), (125, 361, 4, 16), 1, border_radius=2)

    _draw_text(surf, _T("mc.audio_transcript"), 142, 378, 11, KRAP_BLUE, "bold")
    _draw_text(surf, mission_meta.radio_channel(state), 448, 378, 11, INK_MUTED, align="right")
    pygame.draw.line(surf, (176, 172, 162), (120, 398), (448, 398), 1)
    qy = 410
    if quote_attr:
        _draw_text(surf, _kit.fit(quote_attr, 12, 328, "bold"), 120, qy, 12, STAMP_RED, "bold")
        qy += 22
    for line in _wrap(quote, 328, 13):
        if qy + 18 > 560:
            break
        _draw_text(surf, line, 120, qy, 13, INK_DARK)
        qy += 21

    # Ruled continuation lines keep a short transcript from looking blank.
    ry = max(qy + 14, 470)
    while ry <= 556:
        pygame.draw.line(surf, (198, 194, 184), (120, ry), (448, ry), 1)
        ry += 22

    # 4. Right leaf: FORM KR-47 cream intelligence debrief document
    doc_shd = pygame.Surface((398, 504), pygame.SRCALPHA)
    doc_shd.fill((0, 0, 0, 65))
    surf.blit(doc_shd, (520, 78))
    doc = pygame.Rect(516, 74, 398, 504)
    pygame.draw.rect(surf, PAPER, doc)
    pygame.draw.rect(surf, PAPER_EDGE, doc, 1)
    for ry in range(196, 566, 26):
        pygame.draw.line(surf, PAPER_RULE, (530, ry), (900, ry), 1)

    _draw_text(surf, _T("mc.krap_intel_division"), 538, 88, 11, KRAP_BLUE, "bold")
    _draw_text(surf, _T("mc.form_code"), 892, 88, 11, INK_MUTED, align="right")
    pygame.draw.line(surf, INK_DARK, (538, 108), (892, 108), 2)
    pygame.draw.line(surf, INK_MUTED, (538, 112), (892, 112), 1)

    op_name = mission_meta.operation_name(state)
    if op_name == mission_meta.NEUTRAL_OPERATION:
        op_name = _TITLE_OVERRIDES.get(key, op_name)
    op_size = _fit_display_size(op_name, 354, start_size=28, min_size=18)
    op_rect = _draw_text(surf, op_name, 538, 118, op_size, INK_DARK, "display")
    m_code = key.replace("MISSION", "MISSION 0") if key else "OPERATION"
    _draw_text(surf, f"{m_code}  //  {location}", 538, max(156, op_rect.bottom + 4), 12, STAMP_RED, "bold")
    pygame.draw.line(surf, PAPER_EDGE, (538, 184), (892, 184), 1)

    # Section I: bulleted operational outcome
    _draw_text(surf, _T("mc.sec_outcome"), 538, 198, 11, KRAP_BLUE, "bold")
    bullets = [part.strip() for part in str(outcome).split("·") if part.strip()] or [str(outcome)]
    by = 220
    for item in bullets[:3]:
        for li, line in enumerate(_wrap(item, 336, 13)):
            if by + 18 > 304:
                break
            prefix = "- " if li == 0 else "  "
            _draw_text(surf, prefix + line, 538, by, 13, INK_DARK)
            by += 20

    # Section II: typed dotted-leader record
    _draw_text(surf, _T("mc.sec_record"), 538, 314, 11, KRAP_BLUE, "bold")
    for i, (label, value) in enumerate(rows):
        _draw_dotted_row(surf, label, value, 538, 892, 342 + i * 30)

    # Bottom clearance & tilted rubber stamp
    pygame.draw.line(surf, PAPER_EDGE, (538, 474), (892, 474), 1)
    _draw_text(surf, _T("app.classified"), 538, 488, 11, STAMP_RED, "bold")
    _draw_text(surf, _T("mc.operative_id"), 538, 508, 11, INK_DARK)
    after_action = _T("app.krap_intel_after_action_report").split(" - ")[-1]
    field_copy = _T("app.krap_intelligence_division_field").split(" - ")[-1]
    _draw_text(surf, after_action, 538, 528, 10, INK_MID)
    _draw_text(surf, field_copy, 538, 544, 10, INK_MUTED)

    stamp_label = stamp_override or _T("mc.filed_stamp")
    _draw_rubber_stamp(surf, 744, 492, stamp_label, stamp_col, angle_deg=-7)

    # 5. Bottom anodized steel command rail
    rail = pygame.Rect(0, 624, WIDTH, HEIGHT - 624)
    pygame.draw.rect(surf, (10, 11, 13), rail)
    pygame.draw.line(surf, (62, 56, 46), (0, 624), (WIDTH, 624), 1)
    pygame.draw.line(surf, (26, 24, 20), (0, 625), (WIDTH, 625), 1)

    nxt_key = _NEXT_META_KEYS.get(key)
    if has_next and nxt_key and nxt_key in mission_meta.MISSION_META:
        nxt_num = _mission_num(nxt_key)
        nxt_op = mission_meta.MISSION_META[nxt_key]["operation"]
        next_line = f"MISSION {nxt_num:02d} - {nxt_op}"
    elif key == "MISSION8":
        next_line = _T("mc.campaign_concluded")
    else:
        next_line = "CALL OF ACARISTAN"

    _draw_text(surf, _T("mc.next_deployment"), 48, 634, 10, _kit.AMBER_DIM, "bold")
    _draw_text(surf, _kit.fit(next_line, 13, 460, "semibold"), 48, 650, 13, _kit.TEXT, "semibold")
    hint_key = "mc.hint_bar" if has_next else "mc.hint_bar_single"
    _draw_text(surf, _T(hint_key), 48, 675, 10, _kit.MUTED)

    return surf


def draw(surface, state, report, elapsed_frames, now_ms, mouse, has_next):
    """Render the Mission Complete dossier screen onto *surface*."""
    key = _mission_key(state)
    route = getattr(state, "m8_route", "revenge")
    outcome, quote_attr, quote, _ = debrief_copy(state, key)
    rows = tuple(ledger_rows(state, report, key))
    sig = (key, route, bool(has_next), outcome, quote_attr, quote, rows)

    if _sheet_cache["sig"] != sig or _sheet_cache["surf"] is None:
        _sheet_cache["sig"] = sig
        _sheet_cache["surf"] = _build_sheet(state, report, key, has_next)
    surface.blit(_sheet_cache["surf"], (0, 0))

    # Live 3D diorama inside the Polaroid window, then the tape corners back
    # on top (they belong to the sheet, but the animating blit covers them).
    exhibit_surf = None
    try:
        from ui import mission_complete_3d as _mc3d
        exhibit_surf = _mc3d.render(
            key, route, elapsed_frames * 16.667,
            reduced_motion=bool(getattr(state, "reduced_motion", False)),
        )
    except Exception:
        exhibit_surf = None
    if exhibit_surf is not None:
        surface.blit(exhibit_surf, (124, 98))
    else:
        _draw_text(surface, "ARCHIVE VISUAL // 3D OFFLINE", 284, 184, 11,
                   _kit.MUTED, "bold", "center")
    pygame.draw.rect(surface, (46, 42, 36), (123, 97, 322, 192), 1)
    _draw_tape(surface, 116, 86, -18)
    _draw_tape(surface, 452, 86, 18)

    specs = button_specs(state, has_next)
    rects = _button_rects(len(specs), WIDTH, HEIGHT)
    ready = elapsed_frames >= 18
    if not (0 <= _ui["focus"] < len(specs)):
        _ui["focus"] = len(specs) - 1

    for i, (act, label) in enumerate(specs):
        btn = _buttons[i]
        btn.text = label
        box = rects[i]
        btn.x, btn.y = box.x, box.y
        btn.rect = box if ready else pygame.Rect(box.x, HEIGHT + 200, box.w, box.h)
        btn.is_selected = False
        if ready:
            btn.check_hover(mouse)
            note_hover(btn.is_hovered)
        else:
            btn.is_hovered = False
        hot = btn.is_hovered or (_ui["kb_nav"] and i == _ui["focus"])
        _kit.button(surface, box, label, hot=hot, primary=(act == "continue" or len(specs) == 1))

    for j in range(len(specs), len(_buttons)):
        _buttons[j].rect = pygame.Rect(-999, -999, 0, 0)
        _buttons[j].is_hovered = False

    if elapsed_frames < 24:
        fade = pygame.Surface((WIDTH, HEIGHT))
        fade.fill((0, 0, 0))
        fade.set_alpha(int(255 * (1.0 - max(0, elapsed_frames) / 24.0)))
        surface.blit(fade, (0, 0))
