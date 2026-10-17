"""Read-only KRAPNET presentation. No sockets, timers or session mutations.

The arena schematic is derived from the existing authoritative tile strings;
this module never changes maps, teams, capacity or protocol data.
"""
import pygame
from missions import arena as AR
from engine.text import T as _T  # RPE6 Phase 4 text table

BG = (7, 12, 15)
PLATE = (14, 21, 24)
EDGE = (48, 64, 66)
ACCENT = (232, 166, 82)
TEXT = (225, 229, 216)
DIM = (148, 162, 157)
GREEN = (155, 194, 134)


def text(ui, surface, x, y, label, size=12, color=DIM, bold=False):
    ui._blit(surface, x, label, y, size, color, mono=True, bold=bold)


def fitted(ui, surface, rect, label, size=12, color=DIM, bold=False):
    label = ui._clip(label, ui._font(size, bold, True), rect.w)
    text(ui, surface, rect.x, rect.y, label, size, color, bold)


def background(surface):
    surface.fill(BG)
    w, h = surface.get_size()
    for x in range(0, w, 40):
        pygame.draw.line(surface, (12, 21, 24), (x, 0), (x, h))
    for y in range(0, h, 40):
        pygame.draw.line(surface, (12, 21, 24), (0, y), (w, y))


def frame(ui, surface, panel, title, subtitle, state):
    pygame.draw.rect(surface, (2, 5, 7), panel.move(5, 6))
    pygame.draw.rect(surface, PLATE, panel)
    pygame.draw.rect(surface, EDGE, panel, 1)
    pygame.draw.rect(surface, ACCENT, (panel.x, panel.y, 5, 88))
    x = panel.x + 24
    text(ui, surface, x, panel.y + 17, 'KRAPNET / OPERATIONS TERMINAL', 11, ACCENT, True)
    text(ui, surface, x, panel.y + 38, title, 30, TEXT, True)
    text(ui, surface, x, panel.y + 78, subtitle, 12)
    r = pygame.Rect(panel.right - 194, panel.y + 22, 170, 30)
    pygame.draw.rect(surface, (24, 34, 30), r)
    pygame.draw.rect(surface, EDGE, r, 1)
    pygame.draw.circle(surface, GREEN, (r.x + 14, r.centery), 3)
    text(ui, surface, r.x + 26, r.y + 8, state, 11, GREEN, True)
    pygame.draw.line(surface, EDGE, (x, panel.y + 104), (panel.right - 24, panel.y + 104))
    # Registration marks, not decoration over content.
    for cx, cy, dx, dy in ((panel.x, panel.y, 1, 1), (panel.right - 1, panel.y, -1, 1),
                           (panel.x, panel.bottom - 1, 1, -1), (panel.right - 1, panel.bottom - 1, -1, -1)):
        pygame.draw.line(surface, ACCENT, (cx, cy), (cx + dx * 10, cy))
        pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + dy * 10))


def section(ui, surface, x, y, label, width):
    text(ui, surface, x, y, label, 11, DIM, True)
    tw = ui._font(11, True, True).size(label)[0]
    pygame.draw.line(surface, EDGE, (x + tw + 12, y + 6), (x + width, y + 6))


def card(surface, rect):
    pygame.draw.rect(surface, (9, 16, 19), rect)
    pygame.draw.rect(surface, EDGE, rect, 1)


def preview(ui, surface, rect, name):
    """A cached, accurate, north-up arena survey with real spawn/pickup tiles."""
    key = (name, rect.size)
    cache = getattr(ui, '_survey_cache', None)
    if cache is None or cache[0] != key:
        image = pygame.Surface(rect.size)
        image.fill((9, 18, 21))
        for gx in range(0, rect.w, 20):
            pygame.draw.line(image, (18, 32, 35), (gx, 0), (gx, rect.h))
        for gy in range(0, rect.h, 20):
            pygame.draw.line(image, (18, 32, 35), (0, gy), (rect.w, gy))
        rows = AR.ARENAS.get(name, AR.ARENAS['yard'])
        cols = max(map(len, rows))
        cell = max(1, min((rect.w - 140) // cols, (rect.h - 44) // len(rows)))
        ox, oy = (rect.w - cols * cell) // 2, (rect.h - len(rows) * cell) // 2
        for row, line in enumerate(rows):
            for col, tile in enumerate(line):
                r = pygame.Rect(ox + col * cell, oy + row * cell, cell, cell)
                if tile == '#':
                    pygame.draw.rect(image, (67, 88, 84), r.inflate(-1, -1))
                    pygame.draw.line(image, (113, 134, 120), r.topleft, (r.right - 2, r.top))
                elif tile == '+':
                    pygame.draw.rect(image, ACCENT, r.inflate(-2, -2), 1)
                else:
                    pygame.draw.rect(image, (22, 39, 40), r.inflate(-1, -1))
                    if tile in '12345678':
                        pygame.draw.circle(image, GREEN, r.center, max(2, cell // 3), 1)
                    elif tile in 'RBWM':
                        pygame.draw.rect(image, ACCENT, pygame.Rect(r.centerx - 1, r.centery - 1, 3, 3))
        # Survey ticks and a north indicator.
        for xx in range(16, rect.w - 16, 20):
            pygame.draw.line(image, EDGE, (xx, 0), (xx, 4))
            pygame.draw.line(image, EDGE, (xx, rect.h - 5), (xx, rect.h - 1))
        ui._survey_cache = (key, image)
    surface.blit(ui._survey_cache[1], rect)
    pygame.draw.rect(surface, EDGE, rect, 1)
    text(ui, surface, rect.x + 12, rect.y + 12, 'SURVEY / ' + name.upper(), 11, ACCENT, True)
    text(ui, surface, rect.right - 30, rect.y + 12, 'N', 12, TEXT, True)
    pygame.draw.line(surface, DIM, (rect.right - 26, rect.y + 34), (rect.right - 26, rect.y + 50))
    pygame.draw.lines(surface, DIM, False, [(rect.right - 30, rect.y + 40), (rect.right - 26, rect.y + 34), (rect.right - 22, rect.y + 40)])
    text(ui, surface, rect.x + 12, rect.bottom - 20, 'O SPAWN   /   + SUPPLY', 10)
    text(ui, surface, rect.right - 117, rect.bottom - 20, '%02d x %02d TILES' % (len(AR.ARENAS[name][0]), len(AR.ARENAS[name])), 10)


def draw_entry(ui, surface, panel):
    background(surface)
    frame(ui, surface, panel, 'MULTIPLAYER', 'ARENA OPERATIONS  /  HOST OR JOIN A PRIVATE MATCH', 'SESSION SETUP')
    ui._map_rects, ui._pl_rects, ui._mode_rects, ui._btn_rects = {}, {}, {}, {}
    x, y, left = panel.x + 24, panel.y + 122, 540
    rx, rw = x + left + 24, 328
    section(ui, surface, x, y, '01 / SELECT THEATRE', left)
    preview(ui, surface, pygame.Rect(x, y + 24, left, 210), ui.map_name)
    for i, name in enumerate(ui.maps()):
        r = pygame.Rect(x + i * 184, y + 246, 172, 36)
        ui._row(surface, r, '%s / %dP' % (name.upper(), AR.max_players(name)), name == ui.map_name)
        ui._map_rects[i] = r
    section(ui, surface, x, y + 300, '02 / RULES OF ENGAGEMENT', left)
    for i, (mode, label) in enumerate(((AR.MODE_TDM, 'TEAM DEATHMATCH'), (AR.MODE_FFA, 'FREE-FOR-ALL'))):
        r = pygame.Rect(x + i * 276, y + 324, 264, 40)
        ui._row(surface, r, label, ui.mode_name == mode)
        ui._mode_rects[i] = r
    section(ui, surface, x, y + 388, '03 / ROOM CAPACITY', left)
    cap = ui.max_players()
    cw = (left - (cap - 2) * 8) // (cap - 1)
    for i in range(2, cap + 1):
        r = pygame.Rect(x + (i - 2) * (cw + 8), y + 412, cw, 36)
        ui._row(surface, r, str(i), i == ui.players)
        ui._pl_rects[i] = r

    section(ui, surface, rx, y, 'OPERATOR / CALLSIGN', rw)
    ui._draw_name_box(surface, pygame.Rect(rx, y + 24, rw, 42))
    host_card = pygame.Rect(rx, y + 90, rw, 132)
    card(surface, host_card)
    text(ui, surface, rx + 14, y + 104, 'CREATE A ROOM', 18, TEXT, True)
    text(ui, surface, rx + 14, y + 134, 'Host. Share the code. Start when ready.', 12)
    hr = pygame.Rect(rx + 14, y + 164, rw - 28, 44)
    ui._action(surface, hr, 'HOST MATCH', True)
    ui._btn_rects[1] = hr
    join_card = pygame.Rect(rx, y + 246, rw, 194)
    card(surface, join_card)
    text(ui, surface, rx + 14, y + 260, 'JOIN AN OPERATION', 18, TEXT, True)
    text(ui, surface, rx + 14, y + 290, 'Paste the entire code, including @TOKEN.', 12)
    ui._draw_addr_box(surface, pygame.Rect(rx + 14, y + 316, rw - 28, 42))
    jr = pygame.Rect(rx + 14, y + 382, rw - 28, 44)
    ui._action(surface, jr, 'JOIN MATCH', False)
    ui._btn_rects[2] = jr
    text(ui, surface, rx, y + 452, 'HOST SETTINGS APPLY TO NEW ROOMS ONLY', 10)
    fy = panel.bottom - 52
    pygame.draw.line(surface, EDGE, (x, fy), (panel.right - 24, fy))
    br = pygame.Rect(x, fy + 10, 150, 32)
    ui._back(surface, br)
    ui._btn_rects[3] = br
    if ui.status:
        label, color = ui.status, ACCENT
        if any(word in label.lower() for word in ('could not', 'closed', 'invalid', 'failed')):
            color = (247, 130, 110)
    else:
        label, color = 'TAB / SWITCH FIELD    ENTER / JOIN    ESC / BACK', DIM
    fitted(ui, surface, pygame.Rect(br.right + 24, fy + 20, panel.right - br.right - 48, 18), label, 12, color)


def draw_lobby(ui, surface, panel):
    background(surface)
    host = ui.mode == 'hosting'
    roster = ui._lobby_roster() if host else (ui._match_state or {}).get('roster', [])
    roster = list(roster or [])[:8]
    cap = ui.players if host else (ui._match_state or {}).get('room_capacity', 8)
    cap = max(2, min(8, int(cap or 8)))
    count = len(roster)
    frame(ui, surface, panel, 'MATCH LOBBY', '%s  /  %s  /  FIRST TO 15' % (ui.map_name.upper(), 'TEAM DEATHMATCH' if ui._team_play() else 'FREE-FOR-ALL'), 'HOST CONTROL' if host else 'WAITING FOR HOST')
    # These are presentation-only click targets; event dispatch stays in the owner.
    ui._wait_rects, ui._lobby_rects = {}, {}
    x, y, lw = panel.x + 24, panel.y + 122, 540
    rx, rw = x + lw + 24, 328
    section(ui, surface, x, y, 'THEATRE / ' + ui.map_name.upper(), lw)
    preview(ui, surface, pygame.Rect(x, y + 24, lw, 194), ui.map_name)
    box = pygame.Rect(x, y + 236, lw, 104)
    card(surface, box)
    text(ui, surface, x + 16, box.y + 14, 'INVITE / ROOM CODE' if host else 'ROOM / CONNECTION STATUS', 11, ACCENT, True)
    if host:
        ready = ui.room_code_ready()
        label = ui.share_code() if ready else 'ESTABLISHING CONNECTION...'
        fitted(ui, surface, pygame.Rect(x + 16, box.y + 37, lw - 32, 26), label, 21 if ready else 15, TEXT if ready else DIM, True)
        text(ui, surface, x + 16, box.y + 78, 'Share the full code. Friends paste it into JOIN MATCH.', 12)
    else:
        text(ui, surface, x + 16, box.y + 38, 'CONNECTED / AWAITING HOST', 21, GREEN, True)
        text(ui, surface, x + 16, box.y + 78, 'Choose a side. The host controls match deployment.', 12)
    if host:
        ready = ui.room_code_ready()
        copy = pygame.Rect(x, y + 358, 190, 44)
        ui._action(surface, copy, 'COPY CODE' if ready else 'CHECKING...', ready)
        if ready:
            ui._wait_rects['copy'] = copy
        reason = ui._unstartable_reason()
        can_start = count >= 2 and reason is None
        start = pygame.Rect(x + 206, y + 358, 334, 44)
        label = 'NEED 2+ PLAYERS' if count < 2 else (reason or 'START MATCH')
        ui._action(surface, start, label, can_start)
        if can_start:
            ui._lobby_rects['start'] = start
        note, color = ui._forward_status()
        # Two measured lines, not an unbounded status string.
        font = ui._font(12, False, True)
        words, line, lines = note.split(), '', []
        for word in words:
            candidate = (line + ' ' + word).strip()
            if font.size(candidate)[0] > lw and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        for i, line in enumerate(lines[:2]):
            fitted(ui, surface, pygame.Rect(x, y + 418 + i * 18, lw, 18), line, 12, color)
    else:
        card(surface, pygame.Rect(x, y + 358, lw, 44))
        text(ui, surface, x + 16, y + 374, 'STANDBY / THE HOST WILL START WHEN EVERYONE IS IN', 12, DIM, True)
    section(ui, surface, rx, y, 'OPERATORS / %02d OF %02d' % (count, cap), rw)
    board = pygame.Rect(rx, y + 24, rw, 392)
    if ui._team_play():
        ui._draw_team_board(surface, board, roster, ui._teams_table(), ui._local_slot(), host)
    else:
        card(surface, board)
        text(ui, surface, board.x + 12, board.y + 14, 'FREE-FOR-ALL / NO ALLIANCES', 11, ACCENT, True)
        for slot in range(cap):
            r = pygame.Rect(board.x + 12, board.y + 46 + slot * 40, board.w - 24, 34)
            card(surface, r)
            if slot < count:
                try:
                    pid, name = int(roster[slot][0]), str(roster[slot][1])
                except (ValueError, TypeError, IndexError):
                    pid, name = slot, 'OPERATOR'
                mine = pid == ui._local_slot()
                label = ('YOU / ' if mine else '') + name
                color = TEXT if mine else GREEN
            else:
                label, color = 'OPEN SLOT / AWAITING OPERATOR', DIM
            fitted(ui, surface, pygame.Rect(r.x + 10, r.y + 10, r.w - 20, 18), label, 12, color)
    text(ui, surface, rx, y + 440, 'SIMULATION HELD UNTIL HOST STARTS', 11)
    fy = panel.bottom - 52
    pygame.draw.line(surface, EDGE, (x, fy), (panel.right - 24, fy))
    text(ui, surface, x, fy + 21, 'ESC / MATCH OPTIONS', 12, TEXT, True)
    fitted(ui, surface, pygame.Rect(x + 230, fy + 21, panel.w - 278, 18), ui.status or ('HOST / INVITE YOUR SQUAD' if host else 'CONNECTED / WAITING FOR DEPLOYMENT'), 12)


def draw_teams(ui, surface, board, roster, teams, my_slot, host):
    names = {}
    for row in roster:
        try:
            names[int(row[0])] = str(row[1])
        except (TypeError, ValueError, IndexError):
            continue
    # Balance gets its own row, never laid over a team header.
    header_h = 42 if host else 8
    if host:
        b = pygame.Rect(board.x, board.y, board.w, 32)
        ui._row(surface, b, 'AUTO-BALANCE TEAMS', False)
        ui._lobby_rects['balance'] = b
    col_w = (board.w - 8) // 2
    for index, team in enumerate((AR.TEAM_IPA, AR.TEAM_KRAP)):
        col = pygame.Rect(board.x + index * (col_w + 8), board.y + header_h, col_w, board.h - header_h)
        tint = (232, 166, 82) if team == AR.TEAM_IPA else (131, 191, 200)
        here = teams.get(my_slot) == team
        members = sorted(pid for pid in teams if teams[pid] == team)
        card(surface, col)
        pygame.draw.rect(surface, tint if here else EDGE, col, 2 if here else 1)
        pygame.draw.rect(surface, tint, (col.x, col.y, col.w, 3))
        text(ui, surface, col.x + 10, col.y + 14, '%s / %02d' % (AR.TEAM_NAMES[team], len(members)), 13, tint, True)
        # All eight members fit even for a deliberately unbalanced team.
        capacity = ui.players if host else (ui._match_state or {}).get('room_capacity', 8)
        empty_slots = min(4, (max(2, min(8, int(capacity or 8))) + 1) // 2)
        for i in range(max(len(members), empty_slots)):
            yy = col.y + 44 + i * 32
            if yy + 30 > col.bottom - 32:
                break
            if i < len(members):
                pid = members[i]
                mine = pid == my_slot
                available = col.w - 20 - (44 if host and not mine else 0)
                label = ('> ' if mine else '') + names.get(pid, 'OPERATOR')
                fitted(ui, surface, pygame.Rect(col.x + 10, yy + 4, available, 18), label, 12, TEXT if mine else tint, mine)
                if host and not mine:
                    move = pygame.Rect(col.right - 48, yy, 40, 24)
                    pygame.draw.rect(surface, (27, 40, 43), move)
                    pygame.draw.rect(surface, EDGE, move, 1)
                    text(ui, surface, move.x + 5, move.y + 7, 'MOVE', 10, TEXT)
                    ui._lobby_rects['swap_%d' % pid] = move
            else:
                text(ui, surface, col.x + 10, yy + 4, '-- OPEN --', 11, DIM)
            pygame.draw.line(surface, (25, 39, 41), (col.x + 8, yy + 29), (col.right - 8, yy + 29))
        text(ui, surface, col.x + 10, col.bottom - 23, 'YOUR SIDE' if here else 'CLICK TO JOIN', 11, tint, True)
        ui._lobby_rects['team_%d' % team] = col

_BROWSER_FONTS = {}


def browser_font(size, bold=False):
    key = (size, bold)
    if key not in _BROWSER_FONTS:
        _BROWSER_FONTS[key] = pygame.font.SysFont('Consolas', size, bold=bold)
    return _BROWSER_FONTS[key]


def browser_shell(surface, panel):
    """Browser chrome only. All existing list, relay and DM logic stays owned by mp."""
    pygame.draw.rect(surface, (2, 5, 7), panel.move(5, 6))
    pygame.draw.rect(surface, PLATE, panel)
    pygame.draw.rect(surface, EDGE, panel, 1)
    pygame.draw.rect(surface, ACCENT, (panel.x, panel.y, 5, 88))
    surface.blit(browser_font(11, True).render(_T("multiplayer_style.krapnet_operations_terminal"), True, ACCENT), (panel.x + 28, panel.y + 16))
    surface.blit(browser_font(30, True).render(_T("multiplayer_style.multiplayer"), True, TEXT), (panel.x + 28, panel.y + 38))
