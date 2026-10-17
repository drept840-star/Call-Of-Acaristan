
"""M5 rebuilt finale: immutable script/timing shared by renderer and player.
No pygame, game state, or renderer imports here; safe during meta loading.
"""
SCENE = 'm5_shadow_finale'
DURATION_MS = 42000
# onset, offset, speaker, text. Same clock as cameras, motion, and foley.
LINES = (
    (9800, 13700, 'UCILEV', 'Biribel. Y-3. Same intake. Same training.'),
    (14100, 17600, 'BIRIBEL', 'Then you know why I let Maru go.'),
    (18000, 22900, 'UCILEV', "I know. You stopped following orders. I didn't."),
    (23400, 26400, 'BIRIBEL', 'So why am I still standing?'),
    (27000, 31100, 'UCILEV', "Not tonight. They haven't told me to yet."),
    (35400, 40000, 'VASILE', "Biribel, report. ...Never mind. I didn't hear anything. Neither did you."),
)
CUTS = (0, 6200, 9600, 11800, 13900, 17700, 23000, 26700, 31600, 34900)
# Foley follows the authored actor clock; radio is a connection, not a
# static burst on every conversational cut. No gunshot: he never fires.
# Thunder trails its lightning by ~0.75 s (BOLTS in cutscenes/m5shadow3d):
# the flash is seen first, the rumble arrives late, like a far storm.
CUES = (
    (600, 'm5_wet_step', .42), (1200, 'm5_wet_step', .39),
    (1850, 'm5_wet_step', .37), (2500, 'm5_wet_step', .34),
    (3200, 'm5_wet_step', .30), (3746, 'm5_door_open', .20),
    (3900, 'm5_wet_step', .25), (4600, 'm5_wet_step', .20),
    (5050, 'm5_thunder', .45),
    (5800, 'm5_wet_step', .15), (6200, 'm5_sling', .28),
    (6300, 'm5_wet_step', .12), (6416, 'm5_door', .23),
    (9600, 'm5_radio_open', .28),
    (27600, 'm5_thunder', .48),
    (28600, 'm5_sling', .30), (29600, 'm5_laser_switch', .24),
    (31200, 'm5_radio_close', .24), (31600, 'm5_sling', .18),
    (33100, 'm5_roof_step', .32), (33700, 'm5_roof_step', .26),
    (34300, 'm5_roof_step', .19), (34550, 'm5_thunder', .45),
    (35150, 'm5_radio_open', .32), (40200, 'm5_radio_close', .19),
)

FINAL_SHOT = {
    'scene': SCENE, 'speaker': '', 'text': '', 'lighting': (10, 15, 21),
    'hide_caption': True, 'quiet_ui': True, 'auto_advance': True,
    'hard_cut': True, 'self_graded': True, 'cinematic_controls': True,
    'min_ms': DURATION_MS, 'cues': CUES,
    'dialogue_events': tuple((on, who, text, True) for on,off,who,text in LINES),
}

