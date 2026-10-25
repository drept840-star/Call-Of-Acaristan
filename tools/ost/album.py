"""Call of Acaristan - Original Soundtrack. Eight tracks, menu to ending film.

Leitmotifs (offsets in semitones from the track root, lengths in beats):
- Biribel: a doina phrase in Romanian minor (raised 4th). CALL, ANSWER, HOME.
- Ucilev: Biribel's CALL inverted - the mirror, like his callsign.
- Vasile: a warm F-major hymn. Played straight as the state anthem; soured at the end.
- Volkov: a falling music-box figure that loses its last notes once the leaf gets wet.
"""
from .synth import (Track, SR, boom, brass, chirp, chord, choir, cimbalom, clack, crowd, drone, epiano,
                    fade, glass, hat, horn, hum, hz, kick, metal, midi, musicbox, organ, pad, pulse, radio,
                    rain, reed, rim, riser, rotor, shot, snare, squelch, static, strings, taiko, timpani,
                    wind, sine, env)

CALL = [(0, 1), (7, 1), (6, .5), (7, .5), (3, 1), (2, .5), (3, .5), (0, 3)]
ANSWER = [(7, 1), (10, 1), (9, .5), (7, .5), (6, 1), (7, 4)]
HOME = [(7, 1), (10, 1), (9, .5), (7, .5), (6, 1), (3, .5), (2, .5), (0, 3)]
DAWN = [(7, 1), (10, 1), (8, .5), (7, .5), (5, 1), (7, 4)]


def mirror(m):
    return [(-o, l) for o, l in m]


UCILEV, UCILEV_ANSWER, UCILEV_HOME = mirror(CALL), mirror(ANSWER), mirror(HOME)
VASILE = [(0, 1), (2, 1), (4, 1), (7, 1), (5, 1), (4, 1), (2, 2), (0, 1), (4, 1), (2, 1), (0, 1), (-1, 1), (0, 1), (2, 2)]
VASILE_CADENCE = VASILE[:7] + [(5, 1), (4, 1), (2, 1), (4, 1), (2, 1), (-1, 1), (0, 2)]
VASILE_TURN = VASILE[:7] + [(5, 1), (4, 1), (2, 1), (0, 1), (-1, 4)]
HYMN_CHORDS = ["F", "Bb", "Dm", "C", "F", "Bb", "C", "F"]
SOUR_CHORDS = ["F", "Bb", "Dm", "C", "F", "Bb", "Gm", "A"]
VOLKOV = [(7, .5), (3, .5), (2, .5), (0, .5), (2, .5), (-2, .5), (0, 1)]

PROG_A = ["Dm", "Dm", "Bb", "A", "Dm", "Gm", "Bb", "A"]
ARP = ("R", "5", "R", "9", "3", "9", "R", "5")


# ---------------------------------------------------------------- score helpers

def motif(T, inst, notes, root, bar, beat=0.0, scale=1.0, gain=1.0, pan=0.0, verb=0.3, legato=1.0,
          human=0.004, **kw):
    b, r = beat, midi(root)
    for off, length in notes:
        if off is not None:
            T.add(inst(hz(r + off), T.dur(length * scale * legato), **kw), T.t(bar, b), gain, pan, verb, human)
        b += length * scale


def pads(T, inst, prog, bar, gain, verb=0.4, base=45, pan=0.0, **kw):
    """One chord per bar; repeated chords are held, not re-struck."""
    i = 0
    while i < len(prog):
        j = i
        while j + 1 < len(prog) and prog[j + 1] == prog[i]:
            j += 1
        notes = chord(prog[i], base)
        for m in notes:
            T.add(inst(hz(m), T.dur((j - i + 1) * T.beats), **kw), T.t(bar + i), gain / len(notes) ** 0.5, pan, verb)
        i = j + 1


def arp(T, inst, prog, bar, gain, pan=0.0, verb=0.3, step=0.5, pattern=ARP, base=45, length=None, **kw):
    for i, sym in enumerate(prog):
        c = chord(sym, base)
        r = c[0]
        tone = {"r": r, "5": r + 7, "R": r + 12, "9": r + 14, "3": c[1] + 12, "5^": r + 19}
        for k in range(int(T.beats / step)):
            m = tone[pattern[k % len(pattern)]]
            T.add(inst(hz(m), T.dur(length or step * 1.6), **kw), T.t(bar + i, k * step), gain, pan, verb, 0.004)


def bassline(T, inst, prog, bar, gain, hits=((0, 4),), shift=-12, base=45, verb=0.08, **kw):
    for i, sym in enumerate(prog):
        r = chord(sym, base)[0] + shift
        for beat, length in hits:
            T.add(inst(hz(r), T.dur(length), **kw), T.t(bar + i, beat), gain, 0, verb, 0.003)


def groove(T, bar, bars, parts, human=0.005):
    """parts: (drum, beats, gain, pan, verb). A beat may be (beat, accent)."""
    for b in range(bar, bar + bars):
        for drum, beats, gain, pan, verb in parts:
            for k, bt in enumerate(beats):
                g = gain
                if isinstance(bt, tuple):
                    bt, g = bt[0], gain * bt[1]
                T.add(drum((b * 7 + k) % 8), T.t(b, bt), g, pan, verb, human)


def radio_take(T, bars, build):
    """Score a passage on a scratch bus and return it as a field-radio signal."""
    sub = Track(bars, 60.0 / T.spb, T.beats, seed=int(T.rng.integers(1 << 30)), tail=1.0)
    build(sub)
    return radio(sub.dry, T.rng)


def hymn(T, bar, melody, chords, melody_inst=brass, march=False, gain=1.0):
    pads(T, organ, chords, bar, 0.35 * gain, verb=0.3, base=48)
    bassline(T, bass_long, chords, bar, 0.3 * gain)
    motif(T, melody_inst, melody, "F4", bar, gain=0.5 * gain, verb=0.3)
    if march:
        groove(T, bar, len(chords), [(snare, [0, (0.75, 0.5), 1, 2, (2.75, 0.5), 3, (3.5, 0.6)], 0.25 * gain, 0, 0.2),
                                    (lambda v: taiko(v, 55.0), [0, 2], 0.4 * gain, 0, 0.2)])


def bass_long(f, dur):
    return pulse(f, dur, 300.0)


def low_taiko(v):
    return taiko(v, 48.0)


def high_taiko(v):
    return taiko(v, 92.0)


def heartbeat(T, bar, bars, gain=0.35, beats=(0, 0.33)):
    for b in range(bar, bar + bars):
        T.add(kick(1), T.t(b, beats[0]), gain, 0, 0.1)
        T.add(kick(2), T.t(b, beats[1]), gain * 0.6, 0, 0.1)


# ---------------------------------------------------------------- 1. Call of Acaristan (main theme)

def t1_call_of_acaristan():
    T = Track(48, 80, seed=11, verb_s=3.4, damp=4200)
    B = ["F", "Bb", "Dm", "C", "F", "Bb", "Gm", "A"]
    T.add(fade(wind(T.n, T.rng, 180, 650), 6, 8), 0, 0.10, verb=0.05)
    T.add(drone(hz("D2"), T.t(48)), 0, 0.22, verb=0.3)
    for bar in range(4):
        for k in range(16):
            T.add(cimbalom(hz("D4" if k % 2 == 0 else "A4"), 0.2), T.t(bar, k * 0.25), 0.05 + 0.05 * bar, 0.35, 0.6, 0.003)
    T.add(low_taiko(1), T.t(2), 0.5, 0, 0.6)
    T.add(low_taiko(2), T.t(3, 2), 0.6, 0, 0.6)

    for bar in (4, 12):
        arp(T, cimbalom, PROG_A, bar, 0.22, pan=-0.2, verb=0.35)
        pads(T, strings, PROG_A, bar, 0.28, a=1.2, r=1.5)
        bassline(T, bass_long, PROG_A, bar, 0.3)
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, reed, m, "D4", 12 + 2 * i, gain=0.5, pan=0.1, verb=0.45)
    groove(T, 16, 4, [(low_taiko, [0, 2.5], 0.4, 0, 0.5)])

    arp(T, cimbalom, PROG_A, 20, 0.2, pan=-0.2)
    pads(T, choir, PROG_A, 20, 0.32, base=50)
    pads(T, strings, PROG_A, 20, 0.2)
    bassline(T, bass_long, PROG_A, 20, 0.32)
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, brass, m, "D3", 20 + 2 * i, gain=0.45, verb=0.4)
    groove(T, 20, 8, [(low_taiko, [0, 1.5, 2, (3, 0.7)], 0.55, 0, 0.45), (high_taiko, [1, 3], 0.25, 0.3, 0.4)])

    motif(T, strings, VASILE, "F4", 28, gain=0.45, verb=0.45, a=0.15)
    motif(T, strings, VASILE_TURN, "F4", 32, gain=0.45, verb=0.45, a=0.15)
    pads(T, choir, B, 28, 0.2, vowel="o")
    arp(T, cimbalom, B, 28, 0.14, pan=-0.3)
    bassline(T, bass_long, B, 28, 0.3)
    groove(T, 28, 7, [(low_taiko, [0, (2.5, 0.6)], 0.45, 0, 0.5)])
    for k in range(16):
        T.add(timpani(hz("A2"), k % 4), T.t(35, k * 0.25), 0.1 + 0.03 * k, 0, 0.4)
    T.add(riser(T.dur(8)), T.t(34), 0.25, 0, 0.3)

    T.add(boom(0), T.t(36), 0.7, 0, 0.5)
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, brass, m, "D3", 36 + 2 * i, gain=0.5, verb=0.35)
        motif(T, reed, m, "D5", 36 + 2 * i, gain=0.35, pan=0.15, verb=0.4)
    pads(T, strings, PROG_A, 36, 0.3, trem=11.0)
    pads(T, choir, PROG_A, 36, 0.3, base=50)
    arp(T, cimbalom, PROG_A, 36, 0.18, pan=-0.25)
    bassline(T, bass_long, PROG_A, 36, 0.34)
    groove(T, 36, 8, [(low_taiko, [0, 0.75, 1.5, 2, 3, (3.5, 0.6)], 0.6, 0, 0.4), (high_taiko, [1, 3], 0.35, 0.3, 0.35),
                      (snare, [1, 3], 0.18, -0.1, 0.3), (hat, [0.5, 1.5, 2.5, 3.5], 0.05, 0.4, 0.1)])

    T.add(low_taiko(3), T.t(44), 0.8, 0, 0.7)
    T.add(boom(1), T.t(44), 0.5, 0, 0.6)
    for b in range(4):
        arp(T, cimbalom, ["Dm"], 44 + b, 0.18 - 0.04 * b, pan=-0.2, verb=0.5)
    for n in ("D3", "A3", "D4"):
        T.add(fade(strings(hz(n), T.dur(14), a=1.0, r=3.0), 0, 5), T.t(44), 0.15, 0, 0.6)
    return T


# ---------------------------------------------------------------- 2. Black Notebook (M1, Day 0)

def t2_black_notebook():
    T = Track(40, 72, seed=22, verb_s=2.2, damp=3800, tail=5.0)
    N = ["Am9", "Fmaj7", "Dm9", "E7b9"] * 10
    T.add(fade(rain(T.n, T.rng), 3, 6), 0, 0.17, verb=0.04)
    T.add(fade(hum(T.n, T.rng), 4, 4), 0, 0.02, verb=0)

    def comp(bar, bars, gain):
        for b in range(bar, bar + bars):
            for beat, g in ((0, 1.0), (2.5, 0.6)):
                for m in chord(N[b], 48):
                    T.add(epiano(hz(m), T.dur(2)), T.t(b, beat), gain * g, -0.15, 0.4, 0.006)

    comp(0, 24, 0.09)
    bassline(T, pulse, N[4:24], 4, 0.3, hits=[(k * 0.5, 0.4) for k in range(8)], cutoff=500.0)
    groove(T, 4, 20, [(rim, [1, 3], 0.12, 0.2, 0.3), (hat, [(k * 0.25, 1.0 if k % 2 == 0 else 0.5) for k in range(16)], 0.035, 0.45, 0.1)])
    for bar in (8, 10, 12, 14):
        motif(T, musicbox, VOLKOV, "A5", bar, gain=0.24, pan=0.4, verb=0.5)

    pads(T, strings, N[16:24], 16, 0.18, trem=10.0)
    groove(T, 16, 8, [(low_taiko, [0, 1.5], 0.35, 0, 0.4)])
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, brass, m, "A2", 16 + 2 * i, gain=0.35, verb=0.35, bright=900.0)

    bassline(T, pulse, N[24:32], 24, 0.32, hits=[(k * 0.25, 0.22) for k in range(16)], cutoff=900.0)
    groove(T, 24, 8, [(kick, [0, 0.75, 2, 2.75], 0.45, 0, 0.1), (snare, [1, 3], 0.3, 0, 0.3),
                      (hat, [k * 0.5 for k in range(8)], 0.07, 0.35, 0.1), (low_taiko, [0, 2], 0.4, 0, 0.4)])
    arp(T, strings, N[24:32], 24, 0.1, step=0.5, length=0.4, base=57, pan=0.2, a=0.02, r=0.15)
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, reed, m, "A4", 24 + 2 * i, gain=0.42, pan=-0.1, verb=0.4)
    T.add(riser(T.dur(8)), T.t(30), 0.2)

    T.add(boom(2), T.t(32), 0.55, 0, 0.6)
    comp(32, 6, 0.08)
    motif(T, musicbox, VOLKOV, "A5", 34, gain=0.22, pan=0.4, verb=0.6, wobble=35.0)
    motif(T, musicbox, VOLKOV[:-2], "A5", 37, gain=0.2, pan=0.4, verb=0.7, wobble=70.0)
    return T


# ---------------------------------------------------------------- 3. Quiet on Route 12 (M2, Day 1)

def t3_quiet_on_route_12():
    T = Track(52, 90, seed=33, verb_s=3.8, damp=5200, tail=5.0)
    T.add(fade(wind(T.n, T.rng, 400, 1400), 5, 8), 0, 0.08, verb=0.1)
    for n, start, bars in (("A5", 0, 20), ("E6", 2, 18), ("A5", 44, 8)):
        T.add(fade(glass(hz(n), T.dur(bars * 4)), 0, 3), T.t(start), 0.05, 0.3 if n == "E6" else -0.3, 0.6)

    def fifths(bar, bars, gain):
        for b in range(bar, bar + bars):
            r = "D4" if b % 4 < 2 else ("Bb3" if b % 4 == 2 else "C4")
            for beat, g in ((0, 1.0), (2.5, 0.55)):
                T.add(cimbalom(hz(r), 2.0, 0.5), T.t(b, beat), gain * g, -0.25, 0.55, 0.008)
                T.add(cimbalom(hz(midi(r) + 7), 2.0, 0.5), T.t(b, beat + 0.02), gain * g * 0.8, 0.25, 0.55)

    fifths(0, 20, 0.16)
    T.add(squelch(0), T.t(6), 0.1, -0.3)
    T.add(squelch(1), T.t(11, 3), 0.1, -0.3)

    T.add(squelch(2), T.t(12), 0.14, -0.3)
    take = radio_take(T, 8, lambda s: hymn(s, 0, VASILE + VASILE_CADENCE, HYMN_CHORDS))
    T.add(take, T.t(12), 0.16, -0.3, 0.2)
    T.add(squelch(3), T.t(20), 0.14, -0.3)

    heartbeat(T, 20, 10, 0.3)
    groove(T, 20, 10, [(rim, [k * 0.5 for k in range(8)], 0.04, 0.3, 0.2)])
    for n in ("D3", "A3"):
        T.add(strings(hz(n), T.dur(40), a=2.0, r=1.0, cutoff=1500.0), T.t(20), 0.13, 0, 0.5)
    T.add(shot(0), T.t(31, 3), 0.7, 0.1, 0.9)

    arp(T, cimbalom, PROG_A, 32, 0.18, pan=-0.2)
    bassline(T, pulse, PROG_A + PROG_A[:4], 32, 0.3, hits=[(0, .4), (0.5, .4), (1.5, .4), (2, .4), (3, .4), (3.5, .4)], cutoff=700.0)
    groove(T, 32, 12, [(low_taiko, [0, 1.5, 2, (2.5, 0.6), 3], 0.5, 0, 0.4), (snare, [1, 3], 0.25, 0, 0.3),
                       (hat, [k * 0.5 for k in range(8)], 0.07, 0.4, 0.1)])
    for i, m in enumerate((CALL, ANSWER, CALL, HOME)):
        motif(T, reed, m, "D4", 32 + 2 * i, gain=0.45, verb=0.4)
    arp(T, cimbalom, PROG_A[:4], 40, 0.18, pan=-0.2)
    pads(T, strings, PROG_A[:4], 40, 0.28)
    motif(T, brass, CALL, "D3", 40, gain=0.45)
    motif(T, reed, CALL, "D4", 40, gain=0.4)
    motif(T, brass, HOME, "D3", 42, gain=0.45)
    motif(T, reed, HOME, "D4", 42, gain=0.4)

    T.add(low_taiko(5), T.t(44), 0.6, 0, 0.6)
    fifths(44, 7, 0.14)
    T.add(squelch(4), T.t(50), 0.12, -0.3)
    return T


# ---------------------------------------------------------------- 4. The Vostral (M3, Day 4)

def t4_the_vostral():
    T = Track(64, 124, seed=44, verb_s=2.4, damp=4500, tail=5.0)
    V = ["Em", "Em", "C", "B"]
    V2 = ["Em", "Am", "C", "B"]
    T.add(fade(static(int(T.t(8) * SR), T.rng), 1, 2), 0, 0.05, verb=0)
    T.add(drone(hz("E2"), T.t(40)), 0, 0.22, verb=0.3)
    for bar, beat, v in ((1, 2, 0), (3, 0.5, 1), (5, 3, 2), (6, 1, 3), (7, 2.5, 4)):
        T.add(metal(v), T.t(bar, beat), 0.3, (v - 2) * 0.3, 0.7)
    bassline(T, pulse, ["Em"] * 4, 4, 0.28, hits=[(k, 0.6) for k in range(4)], cutoff=400.0)

    oct16 = [(k * 0.25, 0.2) for k in range(16)]
    bassline(T, pulse, ["Em"] * 16 + V * 2 + V2 * 2, 8, 0.28, hits=oct16, cutoff=700.0)
    groove(T, 8, 32, [(kick, [0, 2, 2.5], 0.55, 0, 0.1), (snare, [1, 3], 0.35, 0, 0.25),
                      (metal, [1.5, 3.75], 0.14, 0.4, 0.4),
                      (hat, [(k * 0.25, 1.0 if k % 2 == 0 else 0.5) for k in range(16)], 0.05, -0.3, 0.1)])
    for b in range(12, 24):
        tone = "E5" if b % 2 == 0 else "C5"
        T.add(brass(hz(tone), T.dur(4), bright=1400.0), T.t(b), 0.06, 0.5, 0.5)
    for b, sym in enumerate(V * 2):
        for beat in (0, 1.5):
            for m in chord(sym, 52):
                T.add(strings(hz(m), 0.3, a=0.01, r=0.2), T.t(16 + b, beat), 0.08, 0, 0.3)

    for i, m in enumerate((CALL, ANSWER, CALL, HOME) * 2):
        motif(T, brass, m, "E3", 24 + 2 * i, gain=0.45, verb=0.3)
        motif(T, reed, m, "E4", 24 + 2 * i, gain=0.3, pan=0.15, verb=0.35)
    pads(T, choir, V2 * 2, 32, 0.28, base=52)
    groove(T, 24, 16, [(low_taiko, [0, 2], 0.4, 0, 0.4)])

    heartbeat(T, 40, 8, 0.35)
    T.add(fade(static(int(T.t(8) * SR), T.rng), 0.5, 1), T.t(40), 0.05, verb=0)
    take = radio_take(T, 8, lambda s: (pads(s, organ, ["G", "C", "Em", "D", "G", "C", "D", "G"], 0, 0.4, base=50),
                                       motif(s, brass, VASILE + VASILE_CADENCE, "G4", 0, gain=0.5)))
    T.add(take, T.t(40), 0.2, -0.2, 0.3)
    T.add(drone(hz("E1"), T.t(10)), T.t(40), 0.2, verb=0.2)
    T.add(riser(T.dur(8)), T.t(46), 0.3)

    T.add(boom(3), T.t(48), 0.7, 0, 0.5)
    bassline(T, pulse, (V + V2) * 2, 48, 0.3, hits=oct16, cutoff=900.0)
    groove(T, 48, 16, [(kick, [0, 1, 2, 2.5, 3], 0.55, 0, 0.1), (snare, [1, 3], 0.35, 0, 0.25),
                       (low_taiko, [0, 0.75, 1.5, 2.5, 3], 0.4, 0, 0.35),
                       (lambda v: hat(v, True), [0.5, 1.5, 2.5, 3.5], 0.06, 0.4, 0.1)])
    pads(T, choir, (V + V2) * 2, 48, 0.3, base=52)
    pads(T, strings, (V + V2) * 2, 48, 0.22, trem=12.0)
    for i, m in enumerate((CALL, ANSWER, CALL, HOME) * 2):
        motif(T, brass, m, "E3", 48 + 2 * i, gain=0.5, verb=0.3)
        motif(T, reed, m, "E5", 48 + 2 * i, gain=0.35, pan=0.15, verb=0.35)

    T.add(boom(4), T.t(64), 0.8, 0, 0.6)
    T.add(fade(static(int(4 * SR), T.rng), 0, 2), T.t(64), 0.06, verb=0)
    n = int(3.5 * SR)
    T.add(sine(1000.0, n) * env(n, 0.01, 0, 1, 1.5), T.t(64, 1), 0.04, 0, 0)
    return T


# ---------------------------------------------------------------- 5. Curfew Dawn (M4, Day 6 into Day 7)

def t5_curfew_dawn():
    T = Track(44, 76, seed=55, verb_s=3.0, damp=4800, tail=6.0)
    T.add(fade(crowd(int(T.t(14) * SR), T.rng), 3, 5), 0, 0.05, verb=0.3)
    T.add(squelch(0), T.t(1, 3), 0.1, 0.3)
    take = radio_take(T, 8, lambda s: hymn(s, 0, VASILE + VASILE_CADENCE, HYMN_CHORDS, march=True))
    T.add(take, T.t(2), 0.2, 0.3, 0.3)
    T.add(squelch(1), T.t(10), 0.1, 0.3)
    T.add(fade(strings(hz("D2"), T.dur(24), a=3.0), 0, 2), T.t(6), 0.12, 0, 0.3)

    pads(T, strings, PROG_A + PROG_A[:4], 12, 0.25, trem=8.0)
    bassline(T, pulse, PROG_A + PROG_A[:4], 12, 0.3, hits=[(k * 0.5, 0.4) for k in range(8)], cutoff=500.0)
    for b in range(12, 24):
        T.add(timpani(hz(chord(PROG_A[b % 8], 38)[0])), T.t(b), 0.3, 0, 0.4)
    groove(T, 12, 12, [(low_taiko, [0, 2.5], 0.4, 0, 0.5)])
    for b in range(12, 24, 2):
        for m in chord(PROG_A[b % 8], 50):
            T.add(brass(hz(m), T.dur(7), a=1.2, bright=1200.0, r=1.0), T.t(b), 0.1, 0, 0.4)

    for k, n in enumerate(("D4", "Eb4", "E4", "F4", "F#4", "G4", "G#4", "A4")):
        T.add(fade(strings(hz(n), T.dur(16 - 2 * k), a=0.3), 0, 0.05), T.t(24, 2 * k), 0.1, (k - 3.5) * 0.15, 0.4)
    T.add(riser(T.dur(16)), T.t(24), 0.25)
    T.add(boom(5), T.t(28), 0.6, 0, 0.6)

    dawn = ["Dm", "Bb", "F", "C"] * 3 + ["Bb", "C", "Fadd9", "Fadd9"]
    motif(T, cimbalom, CALL, "D5", 28, gain=0.4, verb=0.5)
    motif(T, cimbalom, DAWN, "D5", 30, gain=0.4, verb=0.5)
    pads(T, pad, dawn[:4], 28, 0.18, cutoff=900.0)
    pads(T, strings, dawn[4:], 32, 0.25, a=1.5)
    bassline(T, bass_long, dawn[4:], 32, 0.25)
    for i, m in enumerate((CALL, DAWN, CALL, DAWN)):
        motif(T, reed, m, "D4", 32 + 2 * i, gain=0.42, verb=0.45)
        motif(T, cimbalom, m, "D5", 32 + 2 * i, gain=0.2, pan=-0.3, verb=0.5)
    pads(T, choir, dawn[8:], 36, 0.22, vowel="o", base=50)
    arp(T, cimbalom, dawn[8:], 36, 0.1, pan=0.3, verb=0.5)
    for k in range(10):
        T.add(chirp(k), T.t(36 + k * 0.8, float(T.rng.uniform(0, 4))), 0.04, float(T.rng.uniform(-0.8, 0.8)), 0.5)
    T.add(cimbalom(hz("A5"), 3.0), T.t(42), 0.25, 0.2, 0.7)
    return T


# ---------------------------------------------------------------- 6. Not Tonight (M5, Day 8)

def t6_not_tonight():
    T = Track(56, 108, seed=66, verb_s=2.8, damp=4200, tail=5.0)
    M = ["Gm", "Gm", "Eb", "D"]
    T.add(fade(rotor(int(T.t(56) * SR), T.rng), T.t(8), T.t(4)), 0, 0.2, 0.1, 0.15)
    for n in ("G3", "D4"):
        T.add(fade(glass(hz(n), T.dur(32)), 0, 2), 0, 0.1, 0, 0.5)
    T.add(drone(hz("G1"), T.t(32)), 0, 0.2, verb=0.2)

    groove(T, 8, 16, [(snare, [0, (0.75, 0.5), 1, 2, (2.75, 0.5), 3, (3.25, 0.4), (3.5, 0.6)], 0.25, 0, 0.25),
                      (kick, [0, 2], 0.5, 0, 0.1)])
    bassline(T, pulse, M * 4, 8, 0.28, hits=[(k * 0.5, 0.35) for k in range(8)], cutoff=600.0)
    for bar in (8, 12, 16, 20):
        motif(T, brass, UCILEV, "G3", bar, gain=0.45, verb=0.35)
        for b in (bar + 2, bar + 3):
            for beat in (0, 1.5):
                for m in chord(M[b % 4], 50):
                    T.add(strings(hz(m), 0.35, a=0.01, r=0.25), T.t(b, beat), 0.1, 0, 0.3)

    groove(T, 24, 8, [(low_taiko, [(k * 0.5, 1.0 if k % 2 == 0 else 0.6) for k in range(8)], 0.45, 0, 0.35),
                      (metal, [1.5, 3.5], 0.14, -0.4, 0.4), (snare, [1, 3], 0.3, 0, 0.25),
                      (hat, [k * 0.25 for k in range(16)], 0.04, 0.4, 0.1)])
    bassline(T, pulse, M * 2, 24, 0.3, hits=[(k * 0.25, 0.2) for k in range(16)], cutoff=800.0)
    pads(T, strings, M * 2, 24, 0.25, trem=12.0)
    motif(T, brass, UCILEV, "G3", 24, gain=0.5)
    motif(T, brass, UCILEV_HOME, "G3", 28, gain=0.5)
    T.add(riser(T.dur(8)), T.t(30), 0.25)

    T.add(fade(strings(hz("G2"), T.dur(32), a=2.0), 0, 1), T.t(32), 0.12, 0, 0.4)
    for i, (b, u) in enumerate(((CALL, UCILEV), (ANSWER, UCILEV_ANSWER), (CALL, UCILEV), (HOME, UCILEV_HOME))):
        motif(T, musicbox, b, "G4", 32 + 2 * i, gain=0.25, pan=-0.6, verb=0.6)
        motif(T, musicbox, u, "G4", 32 + 2 * i, gain=0.25, pan=0.6, verb=0.6)

    T.add(boom(6), T.t(40), 0.6, 0, 0.5)
    parts = [(low_taiko, [0, 0.75, 1.5, 2, 3], 0.5, 0, 0.35), (snare, [1, 3], 0.3, 0, 0.25),
             (kick, [0, 2, 2.5], 0.45, 0, 0.1), (hat, [k * 0.5 for k in range(8)], 0.06, 0.4, 0.1)]
    groove(T, 40, 14, parts)
    bassline(T, pulse, M * 4, 40, 0.3, hits=[(k * 0.25, 0.2) for k in range(16)], cutoff=800.0)
    pads(T, strings, M * 4, 40, 0.22)
    pads(T, choir, M * 2, 48, 0.28, base=50)
    for i, (b, u) in enumerate(((CALL, UCILEV), (ANSWER, UCILEV_ANSWER), (CALL, UCILEV), (HOME, UCILEV_HOME)) * 2):
        motif(T, reed, b, "G4", 40 + 2 * i, gain=0.42, pan=-0.15, verb=0.35)
        motif(T, brass, u, "G2", 40 + 2 * i, gain=0.42, pan=0.15, verb=0.3)
    T.add(boom(7), T.t(48), 0.5, 0, 0.5)
    T.add(low_taiko(6), T.t(54), 0.7, 0, 0.7)
    T.add(fade(strings(hz("G3"), T.dur(8), a=0.5, r=2.0), 0, 3), T.t(54), 0.15, 0, 0.6)
    return T


# ---------------------------------------------------------------- 7. Whiteout (M6, Day 10)

def t7_whiteout():
    T = Track(60, 100, seed=77, verb_s=4.0, damp=3800, tail=6.0)
    T.add(fade(wind(T.n, T.rng, 300, 1200), 4, 8), 0, 0.14, verb=0.1)
    for n, pan_ in (("D4", -0.4), ("A4", 0.4), ("F5", 0.0)):
        T.add(fade(glass(hz(n), T.dur(80)), 0, 4), 0, 0.07, pan_, 0.6)
    for bar in (2, 6):
        motif(T, musicbox, VOLKOV, "D5", bar, scale=2.0, gain=0.25, pan=0.3, verb=0.6)

    S = ["Dm", "Dm", "Bb", "A"] * 3
    bassline(T, pulse, S, 8, 0.2, hits=[(k, 0.8) for k in range(4)], cutoff=300.0)
    pads(T, strings, S, 8, 0.16, cutoff=1800.0, a=1.5)
    for b in range(8, 20, 2):
        T.add(clack(b % 8), T.t(b), 0.08, 0.5, 0.7)
        T.add(clack((b + 1) % 8), T.t(b, 0.25), 0.07, 0.5, 0.7)
    for k in range(48):
        T.add(cimbalom(hz("A4"), 0.2), T.t(14, k * 0.25), 0.04, -0.3, 0.6, 0.003)

    H = ["Bb", "F", "C", "Dm"] * 3
    for b in range(20, 32):
        g = 0.1 + 0.3 * (b - 20) / 12
        for beat in (0, 0.25, 2, 2.25):
            T.add(clack((b + int(beat * 4)) % 8), T.t(b, beat), g, 0.2, 0.4)
    motif(T, strings, VOLKOV, "D4", 20, scale=2.0, gain=0.4, verb=0.5, a=0.2)
    motif(T, strings, VOLKOV, "D4", 24, scale=2.0, gain=0.4, verb=0.5, a=0.2)
    motif(T, strings, VOLKOV, "D5", 28, scale=2.0, gain=0.35, verb=0.5, a=0.2)
    pads(T, pad, H, 20, 0.16, cutoff=1100.0)
    pads(T, choir, H[4:], 24, 0.25, base=50)
    bassline(T, bass_long, H, 20, 0.28)
    groove(T, 24, 8, [(low_taiko, [0, 2.5], 0.4, 0, 0.5)])
    T.add(horn(3.0), T.t(28), 0.12, -0.4, 0.8)
    T.add(riser(T.dur(8)), T.t(30), 0.22)

    T.add(shot(1), T.t(32), 0.8, 0.2, 0.9)

    G = ["Dm", "Bb", "Gm", "A"] * 3
    pads(T, choir, G, 33, 0.25, vowel="u", base=50)
    pads(T, strings, G, 33, 0.22, a=2.0, r=2.0)
    bassline(T, bass_long, G, 33, 0.22)
    motif(T, musicbox, VOLKOV, "D5", 36, scale=2.0, gain=0.22, pan=0.3, verb=0.7, wobble=40.0)
    motif(T, musicbox, VOLKOV[:-2], "D5", 40, scale=2.0, gain=0.2, pan=0.3, verb=0.8, wobble=70.0)

    F = PROG_A + PROG_A[:4]
    T.add(boom(8), T.t(45), 0.6, 0, 0.5)
    groove(T, 45, 12, [(clack, [k * 0.5 for k in range(8)], 0.22, 0.2, 0.3),
                       (low_taiko, [0, 0.75, 1.5, 2, 3], 0.5, 0, 0.35), (snare, [1, 3], 0.3, 0, 0.25),
                       (kick, [0, 2], 0.45, 0, 0.1), (hat, [k * 0.5 + 0.25 for k in range(8)], 0.04, 0.4, 0.1)])
    bassline(T, pulse, F, 45, 0.3, hits=[(k * 0.5, 0.35) for k in range(8)], cutoff=700.0)
    pads(T, strings, F, 45, 0.22, trem=10.0)
    motif(T, brass, UCILEV, "D3", 45, gain=0.45)
    motif(T, reed, CALL, "D4", 47, gain=0.45)
    motif(T, brass, UCILEV_HOME, "D3", 49, gain=0.45)
    motif(T, reed, HOME, "D4", 51, gain=0.45)
    pads(T, choir, F[8:], 53, 0.28, base=50)
    motif(T, reed, CALL, "D4", 53, gain=0.45)
    motif(T, brass, UCILEV, "D3", 53, gain=0.4)
    motif(T, reed, HOME, "D4", 55, gain=0.45)
    motif(T, brass, UCILEV_HOME, "D3", 55, gain=0.4)

    T.add(boom(9), T.t(57), 0.7, 0, 0.6)
    T.add(horn(4.0), T.t(57, 2), 0.1, 0.5, 0.9)
    T.add(drone(hz("D2"), T.t(3) + 4), T.t(57), 0.2, verb=0.4)
    return T


# ---------------------------------------------------------------- 8. I Chose the Many (ending film)

def t8_i_chose_the_many():
    T = Track(44, 66, seed=88, verb_s=3.6, damp=4000, tail=7.0)
    T.add(fade(static(int(T.t(4) * SR), T.rng), 1, 1), 0, 0.05, verb=0)
    T.add(squelch(0), T.t(0, 1), 0.12, 0.2)
    T.add(fade(organ(hz("F2"), T.dur(14)), 2, 2), 0, 0.1, 0, 0.4)

    take = radio_take(T, 8, lambda s: (pads(s, organ, HYMN_CHORDS, 0, 0.4, base=48),
                                       motif(s, reed, VASILE + VASILE_CADENCE, "F4", 0, gain=0.5)))
    T.add(take, T.t(4), 0.18, 0.2, 0.3)
    T.add(squelch(1), T.t(12), 0.12, 0.2)

    pads(T, organ, HYMN_CHORDS, 12, 0.28, base=48)
    pads(T, strings, HYMN_CHORDS, 12, 0.18, a=1.5)
    pads(T, choir, HYMN_CHORDS, 12, 0.18, vowel="o", base=48)
    bassline(T, bass_long, HYMN_CHORDS, 12, 0.25)
    motif(T, strings, VASILE + VASILE_CADENCE, "F4", 12, gain=0.45, verb=0.45, a=0.2)

    pads(T, strings, SOUR_CHORDS, 20, 0.22, a=1.5)
    pads(T, organ, SOUR_CHORDS[:4], 20, 0.18, base=48)
    pads(T, choir, SOUR_CHORDS[4:], 24, 0.2, vowel="u", base=48)
    bassline(T, bass_long, SOUR_CHORDS, 20, 0.25)
    motif(T, strings, VASILE + VASILE_TURN, "F4", 20, gain=0.42, verb=0.5, a=0.2)
    motif(T, cimbalom, VASILE_TURN[7:], "F5", 26, gain=0.2, pan=-0.3, verb=0.5)

    D = ["Dm", "Dm", "Bb", "A"] * 3
    pads(T, pad, D, 28, 0.2, cutoff=900.0)
    bassline(T, bass_long, D, 28, 0.25)
    motif(T, cimbalom, CALL, "D4", 28, gain=0.45, verb=0.5)
    motif(T, cimbalom, ANSWER, "D4", 30, gain=0.45, verb=0.5)
    motif(T, reed, CALL, "D4", 32, gain=0.45, verb=0.5)
    motif(T, reed, HOME, "D4", 34, gain=0.45, verb=0.5)
    pads(T, strings, D[4:], 32, 0.22)
    pads(T, choir, D[8:], 36, 0.25, base=50)
    motif(T, brass, CALL, "D3", 36, gain=0.4)
    motif(T, reed, CALL, "D5", 36, gain=0.35, pan=0.15)
    motif(T, brass, HOME, "D3", 38, gain=0.4)
    motif(T, reed, HOME, "D5", 38, gain=0.35, pan=0.15)
    groove(T, 36, 4, [(low_taiko, [0, (2.5, 0.5)], 0.4, 0, 0.5)])

    T.add(fade(wind(int(T.t(9) * SR), T.rng, 200, 700), T.t(3), 4), T.t(38), 0.1, verb=0.1)
    for n in ("D3", "A3"):
        T.add(fade(strings(hz(n), T.dur(16), a=1.0, r=3.0), 0, 6), T.t(40), 0.14, 0, 0.6)
    motif(T, cimbalom, [(0, 1), (7, 1), (6, 2)], "D4", 41, gain=0.4, verb=0.7)
    T.add(fade(reed(hz("G#4"), T.dur(6), a=0.3, r=2.0), 0, 2.5), T.t(41, 2), 0.25, 0.1, 0.7)
    T.add(horn(3.5), T.t(42, 2), 0.08, -0.5, 0.9)
    return T


ALBUM = [
    ("Call of Acaristan", "Main Theme", t1_call_of_acaristan),
    ("Black Notebook", "Mission 1 - Day 0", t2_black_notebook),
    ("Quiet on Route 12", "Mission 2 - Day 1", t3_quiet_on_route_12),
    ("The Vostral", "Mission 3 - Day 4", t4_the_vostral),
    ("Curfew Dawn", "Mission 4 - The Aftermath", t5_curfew_dawn),
    ("Not Tonight", "Mission 5 - Martial Law", t6_not_tonight),
    ("Whiteout", "Mission 6 - Day 10", t7_whiteout),
    ("I Chose the Many", "Ending", t8_i_chose_the_many),
]
