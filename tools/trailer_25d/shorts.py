"""Four vertical shorts (1080x1920, 30 fps) cut from the 2.5D announcement.

    python tools/trailer_25d/shorts.py [1 2 3 4] [--stills]

Each short reframes trailer frames (render.compose + render.grade with the 16:9
overlays off) into a TV window with its own header, subtitles and footer, and
cuts the matching audio from trailers/announce_25d/_mix.wav (render the
trailer first). Every short ends on the "one dimension" hook card.

Optional lines, picked up when they exist in assets/voice/Trailer/announce_25d:
S01 "Before." and S02 "After." (short 3), S03 the hook line (every short),
S04 "Depth for everyone! ...Except the opposition." (short 1).
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R  # noqa: E402
import pygame  # noqa: E402
import cv2  # noqa: E402

VW, VH, FPS, SR = 1080, 1920, R.FPS, R.SR
DIR = os.path.join(R.OUT, "shorts")
MIX = os.path.join(R.OUT, "_mix.wav")
TV = pygame.Rect(40, 500, 1000, 750)
HOOK = "Citizens who scroll past this video will be given one dimension."
GOLD, RED, WHITE = R.GOLD, R.RED, (255, 255, 255)


def vo_opt(vid):
    """Optional short-only line, silence-trimmed, or None."""
    p = os.path.join(R.VO_DIR, vid + ".wav")
    if not os.path.exists(p):
        return None
    x, sr = R.read_wav(p)
    x = R.resample(x, sr)
    on = np.nonzero(np.abs(x) > 0.02)[0]
    if len(on):
        x = x[max(0, on[0] - int(0.05 * SR)):on[-1] + int(0.15 * SR)]
    return x


# ── shorts: lists of pieces ──────────────────────────────────────────────
def rule_of(t):
    for n, (a, b) in enumerate(((25.0, 31.9), (31.9, 40.1), (40.1, 50.0), (50.0, 58.6)), 1):
        if a <= t < b:
            return n
    return 4


def head_lever(t):
    if t < R.SWITCH:
        return "LIVE FROM THE PALACE", "The President will now switch on depth."
    return "DEPTH HAS ARRIVED", "Decree No. 2.5 is in effect."


def head_rules(t):
    n = rule_of(t)
    return "VIEWER RULE No. %d" % n, R.RULES[n][0]


def head_montage(t):
    if 95.9 <= t < 97.8:
        return "ARCHIVE FOOTAGE", "This is what you had before."
    return "AFTER", "Same Republic. Extra half."


def head_press(t):
    return "PRESS CONFERENCE", "Gen. Balaceanu, inventor of depth."


SHORTS = {
    1: ("01_the_lever", [("trailer", 58.6, 80.0, head_lever)]),
    2: ("02_citizen_instructions", [("trailer", 25.0, 58.6, head_rules)]),
    3: ("03_before_after", [("ba", "m2_2d", 3.0, "m2_3d", 3.0, 4.5),
                           ("ba", "m3_2d", 3.0, "m3_3d", 2.0, 4.5),
                           ("trailer", 80.0, 101.8, head_montage)]),
    4: ("04_balaceanu", [("trailer", 127.0, 141.0, head_press)]),
}
HOOK_DUR = 3.5
BA_AFTER = 1.9          # AFTER screen switches on this far into each pair


# ── drawing ──────────────────────────────────────────────────────────────
def background():
    s = pygame.Surface((VW, VH))
    for y in range(VH):
        k = y / VH
        c = (int(22 - 12 * k), int(24 - 13 * k), int(34 - 18 * k))
        pygame.draw.line(s, c, (0, y), (VW, y))
    for y in range(0, VH, 4):
        pygame.draw.line(s, (0, 0, 0), (0, y), (VW, y))
    s.set_alpha(None)
    bars = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
    bw = VW / len(bars)
    for i, c in enumerate(bars):          # thin colour-bar strip under the header
        pygame.draw.rect(s, c, (int(i * bw), 470, int(bw) + 1, 8))
    return s


BG = None


def bezel(s, r):
    pygame.draw.rect(s, (52, 50, 48), r.inflate(40, 40), border_radius=34)
    pygame.draw.rect(s, (24, 23, 22), r.inflate(40, 40), 4, border_radius=34)
    pygame.draw.rect(s, (8, 8, 8), r.inflate(8, 8), border_radius=14)


def header(s, t, title, sub, live=True):
    b = R.text("TVA 1", "oswald", 58, GOLD, outline=3)
    s.blit(b, (60, 150))
    p = R.text("PROGRAMUL NATIONAL", "mono", 28, (210, 210, 210), outline=2)
    s.blit(p, (64 + b.get_width() + 22, 176))
    if live:
        on = (t * 1.2) % 2 < 1.4
        lv = R.text("LIVE", "oswald", 40, WHITE)
        r = lv.get_rect(topright=(VW - 60, 160)).inflate(22, 4)
        pygame.draw.rect(s, RED, r)
        s.blit(lv, lv.get_rect(center=r.center))
        if on:
            pygame.draw.circle(s, (240, 40, 40), (r.left - 22, r.centery), 11)
    y = 250
    for ln in R.wrap(title, "oswald", 78, 980)[:2]:
        img = R.text(ln, "oswald", 78, WHITE, outline=4)
        s.blit(img, img.get_rect(midtop=(VW // 2, y)))
        y += 92
    if sub:
        img = R.text(sub, "oswald", 40, GOLD, outline=3)
        s.blit(img, img.get_rect(midtop=(VW // 2, y + 6)))


def footer(s):
    a = R.text("CALL OF ACARISTAN", "oswald", 64, GOLD, outline=4)
    s.blit(a, a.get_rect(midtop=(VW // 2, 1560)))
    b = R.text("NOW IN 2.5D  -  RELEASE: SOON (MAYBE)", "oswald", 38, WHITE, outline=3)
    s.blit(b, b.get_rect(midtop=(VW // 2, 1645)))


def subs(s, lines, col=WHITE, y=1290):
    for ln in lines:
        img = R.text(ln, "oswald", 58, col, outline=3)
        s.blit(img, img.get_rect(midtop=(VW // 2, y)))
        y += 72


def sub_at(t):
    for a, b, txt in R.SUBS:
        if a - 0.05 <= t < b + 0.25:
            return R.wrap(txt, "oswald", 58, 980)[:3]
    return []


def to_surf(arr):
    return pygame.image.frombytes(np.ascontiguousarray(arr).tobytes(), (arr.shape[1], arr.shape[0]), "RGB")


def screen43(arr, size):
    """Centre 4:3 crop of a graded 1920x1080 frame, scaled to size."""
    x0 = (R.OW - R.OH * 4 // 3) // 2
    return to_surf(cv2.resize(arr[:, x0:R.OW - x0], size, interpolation=cv2.INTER_AREA))


def flat_bw(surf):
    a = np.frombuffer(pygame.image.tobytes(surf, "RGB"), np.uint8).reshape(surf.get_height(), surf.get_width(), 3)
    y = 255.0 * (np.maximum(a.astype(np.float32) @ R.LUMA, 0) / 255.0) ** 0.72
    y = np.clip((y - 128.0) * 1.1 + 128.0 + np.random.normal(0, 7, y.shape), 0, 255)
    y[::3] *= 0.84
    return to_surf(np.stack([y] * 3, -1).astype(np.uint8))


def frame_trailer(t, head):
    s = BG.copy()
    title, sub = head(t)
    header(s, t, title, sub)
    bezel(s, TV)
    s.blit(screen43(R.grade(R.compose(t), t), TV.size), TV.topleft)
    subs(s, sub_at(t))
    footer(s)
    return s


BA_TOP = pygame.Rect(80, 400, 920, 518)
BA_BOT = pygame.Rect(80, 1015, 920, 518)


def frame_ba(lt, piece):
    _, n2, o2, n3, o3, _dur = piece
    s = BG.copy()
    b = R.text("TVA 1", "oswald", 58, GOLD, outline=3)
    s.blit(b, (60, 150))
    for r in (BA_TOP, BA_BOT):
        bezel(s, r)
    lab = R.text("BEFORE", "oswald", 60, (200, 200, 200), outline=4)
    s.blit(lab, lab.get_rect(bottomleft=(BA_TOP.left, BA_TOP.top - 24)))
    s.blit(flat_bw(R.clip(n2).frame(o2 + lt, size=BA_TOP.size, zoom=1.12)), BA_TOP.topleft)
    if lt < BA_AFTER:
        bot = pygame.transform.smoothscale(R.CARD43, (BA_BOT.h * 4 // 3, BA_BOT.h))
        s.fill((0, 0, 0), BA_BOT)
        s.blit(flat_bw(bot), bot.get_rect(center=BA_BOT.center))
        w = R.text("PLEASE STAND BY", "oswald", 60, WHITE, outline=4)
        s.blit(w, w.get_rect(center=BA_BOT.center))
    else:
        k = R.C.smooth(R.C.clamp((lt - BA_AFTER) / 0.35))
        img = R.clip(n3).frame(o3 + lt - BA_AFTER, size=BA_BOT.size, zoom=1.12 + 0.06 * (lt - BA_AFTER) / 3, pop=True)
        h = max(4, int(BA_BOT.h * k))
        s.blit(pygame.transform.scale(img, (BA_BOT.w, h)), (BA_BOT.left, BA_BOT.centery - h // 2))
        lab = R.text("AFTER", "oswald", 60, GOLD, outline=4)
        s.blit(lab, lab.get_rect(bottomleft=(BA_BOT.left, BA_BOT.top - 24)))
        st = pygame.Surface((VW, VH), pygame.SRCALPHA)
        R.stamp(st, lt - BA_AFTER, ["+0.5D"], (BA_BOT.right - 150, BA_BOT.top + 90), angle=10, scale=0.9)
        s.blit(st, (0, 0))
    footer(s)
    return s


def frame_hook(lt):
    s = BG.copy()
    header(s, lt, "OFFICIAL WARNING", "From the Ministry of Dimensions.", live=False)
    bezel(s, TV)
    card = flat_bw(pygame.transform.smoothscale(R.CARD43, TV.size))
    k = R.C.clamp((lt - (HOOK_DUR - 0.9)) / 0.55)       # the picture loses a dimension
    s.fill((0, 0, 0), TV)
    if k < 1.0:
        h = max(3, int(TV.h * (1 - R.C.smooth(k))))
        s.blit(pygame.transform.scale(card, (TV.w, h)), (TV.left, TV.centery - h // 2))
    else:
        pygame.draw.line(s, (235, 235, 235), (TV.left + 30, TV.centery), (TV.right - 30, TV.centery), 3)
    subs(s, R.wrap(HOOK, "oswald", 58, 980), GOLD)
    footer(s)
    if lt > HOOK_DUR - 0.35:
        f = pygame.Surface((VW, VH))
        f.set_alpha(int(255 * R.C.clamp((lt - (HOOK_DUR - 0.35)) / 0.35)))
        s.blit(f, (0, 0))
    return s


# ── audio ────────────────────────────────────────────────────────────────
def fade_ends(x, d=0.04):
    k = min(len(x) // 2, int(d * SR))
    r = np.linspace(0, 1, k, dtype=np.float32)[:, None]
    x[:k] *= r
    x[len(x) - k:] *= r[::-1]
    return x


def audio(pieces, path, add_s04):
    total = sum(piece_dur(p) for p in pieces) + HOOK_DUR
    buf = np.zeros((int(total * SR) + SR, 2), np.float32)
    t = 0.0
    for p in pieces:
        d = piece_dur(p)
        if p[0] == "trailer":
            R.put(buf, fade_ends(R.mp3(MIX, p[1], d)), t)
            if add_s04 and p[2] >= 80.0:
                s04 = vo_opt("S04")
                if s04 is not None:
                    R.put(buf, s04, t + (77.0 - p[1]), 1.0)
        else:
            mus = R.mp3(os.path.join(R.OST, "01_call_of_acaristan.mp3"), 2.0 if t == 0 else 2.0 + t, d)
            mus *= R.gain_curve([(0, -30), (0.3, -12), (BA_AFTER - 0.1, -12), (BA_AFTER, -4), (d, -4)], len(mus))
            R.put(buf, fade_ends(mus), t)
            R.put(buf, R.sfx("crt_thunk"), t + 0.05, -8)
            R.put(buf, R.sfx("rig_low_boom"), t + BA_AFTER, -6)
            for vid, at in (("S01", 0.25), ("S02", BA_AFTER + 0.1)):
                x = vo_opt(vid)
                if x is not None:
                    R.put(buf, x, t + at, 1.0)
        t += d
    x = vo_opt("S03")
    if x is not None:
        R.put(buf, x, t + 0.15, 1.0)
    else:
        n = int(2.4 * SR)
        tt = np.arange(n) / SR
        R.put(buf, (0.25 * np.sin(2 * np.pi * 1000 * tt) * np.clip(tt / 0.05, 0, 1)).astype(np.float32), t + 0.05, -16)
    R.put(buf, R.sfx("crt_thunk"), t + HOOK_DUR - 0.75, -4)
    buf = buf[:int(total * SR)]
    pk = np.abs(buf).max()
    buf = np.tanh(buf / max(pk, 1e-6) * 1.3) / np.tanh(1.3) * R.db(-1.0)
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32767).astype("<i2").tobytes())
    return total


def piece_dur(p):
    return p[2] - p[1] if p[0] == "trailer" else p[5]


def frames(pieces, want=lambda i: True):
    k = 0
    for p in pieces:
        n = int(round(piece_dur(p) * FPS))
        for i in range(n):
            if want(k):
                yield k, (frame_trailer(p[1] + i / FPS, p[3]) if p[0] == "trailer" else frame_ba(i / FPS, p))
            k += 1
    for i in range(int(HOOK_DUR * FPS)):
        if want(k):
            yield k, frame_hook(i / FPS)
        k += 1


def render(num, stills=False):
    name, pieces = SHORTS[num]
    if stills:
        d = os.path.join(DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for i, s in frames(pieces, lambda i: i % 120 == 40):
            pygame.image.save(s, os.path.join(d, "%s_%04d.jpg" % (name, i)))
        return
    wav = os.path.join(DIR, "_%s.wav" % name)
    vid = os.path.join(DIR, "_%s.mp4" % name)
    audio(pieces, wav, num == 1)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", "%dx%d" % (VW, VH), "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    for _i, s in frames(pieces):
        ff.stdin.write(pygame.image.tobytes(s, "RGB"))
    ff.stdin.close()
    ff.wait()
    out = os.path.join(DIR, "short_%s.mp4" % name)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(vid)
    os.remove(wav)
    print("wrote", out, flush=True)


def main():
    global BG
    args = sys.argv[1:]
    pygame.init()
    pygame.display.set_mode((64, 64))
    R.OVERLAYS["on"] = False
    R.TEST = R.test_card()
    R.CARD43 = R.test_card(480, 360)
    BG = background()
    os.makedirs(DIR, exist_ok=True)
    nums = [int(a) for a in args if a.isdigit()] or sorted(SHORTS)
    for n in nums:
        render(n, stills="--stills" in args)


if __name__ == "__main__":
    main()
