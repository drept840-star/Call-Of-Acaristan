
"""Split from menu.py - see menu.py (shim) for the map."""
import pygame
from core.config import (C_ORANGE, C_TERMINAL, C_WHITE, HEIGHT, WIDTH, audio, font_btn, font_speaker, font_terminal, font_terminal_small, get_scaled_mouse, screen)
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

from core import profile_store
from core.state import STATE

from ui.main import draw_menu_background
from ui.system import server_back_btn, _server_title_font
from ui.widgets import clipboard_text
from ui import multiplayer_style as _mp_style
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

server_list = [

    ("Micul Fuego's FUEGOTECH K1 Launch Party!!", 3, 6, 45),

    ("Dekro Palace [MODDED] [NO RULES]", 1, 50, 120),

    ("Sebi's Parlament [RP] [SERIOUS ONLY]", 50, 49, 30),

    ("KGB Archives // LEAKED", 0, 12, 89),

    ("Putin's Summer House [VIP ONLY]", 2, 8, 202),

    ("█████████ [REDACTED]", 7, 7, 999),

    ("Vasile's Cigarette Break", 1, 4, 12),

    ("Biribel's Safe House (PASS: 742)", 0, 2, 67),

    ("MAG Recruitment Center", 24, 32, 88),

    ("Krapistan #1 Official", 0, 64, 350),

    ("noobs only pls", 3, 10, 156),

    ("[24/7] OIL RIG EXPLOSION SIM", 12, 16, 78),

    ("MR.BEAST GIVING AWAY CIGARETTES", 99, 100, 45),

    ("yo mama's basement", 1, 2, 4),

    ("FREE V-BUCKS REAL NOT FAKE", 6, 6, 230),

]

# Server rules - shown on hover

SERVER_RULES = {

    "Micul Fuego's FUEGOTECH K1 Launch Party!!": [

        "GAMEMODE:  Launch Party Deathmatch",

        "MAP:       FuegoTech HQ Rooftop",

        "RULES:     1. Bring your own fireworks.",

        "           2. No actual fuego allowed.",

        "           3. Micul Fuego always wins.",

    ],

    "Dekro Palace [MODDED] [NO RULES]": [

        "GAMEMODE:  Free For All",

        "MAP:       The Palace",

        "RULES:     Literally none. We tried.",

        "           Last admin resigned in tears.",

    ],

    "Sebi's Parlament [RP] [SERIOUS ONLY]": [

        "GAMEMODE:  Parliamentary Procedure RP",

        "MAP:       Parlament Chamber",

        "RULES:     1. Address the chair properly.",

        "           2. No filibustering past 3am.",

        "           3. Bring snacks for the recess.",

    ],

    "KGB Archives // LEAKED": [

        "GAMEMODE:  ???",

        "MAP:       ???",

        "RULES:     Do not discuss what you see here.",

        "           Это всё, что вам нужно знать.",

    ],

    "Putin's Summer House [VIP ONLY]": [

        "GAMEMODE:  Bear Wrestling",

        "MAP:       Dacha + Sauna",

        "RULES:     1. No shirts allowed.",

        "           2. Stay away from the windows.",

        "           3. Compliment the host's judo.",

    ],

    "█████████ [REDACTED]": [

        "GAMEMODE:  █████████",

        "MAP:       █████████",

        "RULES:     ████ ██ ████████ ██ ████.",

        "           ████████ ████ ██ █████.",

    ],

    "Vasile's Cigarette Break": [

        "GAMEMODE:  Standing Around",

        "MAP:       Behind the Warehouse",

        "RULES:     1. No talking shop.",

        "           2. Share the lighter.",

        "           3. Back to work in 5 minutes.",

    ],

    "Biribel's Safe House (PASS: 742)": [

        "GAMEMODE:  Cooperative Stealth",

        "MAP:       Safe House Interior",

        "RULES:     1. Keep your voice down.",

        "           2. Do not turn on the lights.",

        "           3. The code is in the desk.",

    ],

    "MAG Recruitment Center": [

        "GAMEMODE:  Capture the Flag",

        "MAP:       Slum District",

        "RULES:     1. Free graffiti supplies provided.",

        "           2. No KRAP affiliates.",

        "           3. MARU SEES YOU.",

    ],

    "Krapistan #1 Official": [

        "GAMEMODE:  Peacekeeping Simulator",

        "MAP:       Acaristan-wide",

        "RULES:     1. Follow protocol at all times.",

        "           2. Paperwork must be in triplicate.",

        "           3. Do not ask about the oil.",

    ],

    "noobs only pls": [

        "GAMEMODE:  Training Grounds",

        "MAP:       Tutorial Map",

        "RULES:     1. No tryhards.",

        "           2. Be nice to new players.",

        "           3. We were all noobs once.",

    ],

    "[24/7] OIL RIG EXPLOSION SIM": [

        "GAMEMODE:  Demolition Derby",

        "MAP:       Kilemeno Ocean Platform",

        "RULES:     1. Everything must explode.",

        "           2. Survive 5 minutes for VIP.",

        "           3. No fishing during gameplay.",

    ],

    "MR.BEAST GIVING AWAY CIGARETTES": [

        "GAMEMODE:  Subscribe Battle Royale",

        "MAP:       Mystery Warehouse",

        "RULES:     1. Must subscribe to enter.",

        "           2. Last sub wins cigarettes.",

        "           3. Not actually MrBeast.",

    ],

    "yo mama's basement": [

        "GAMEMODE:  LAN Party",

        "MAP:       The Basement",

        "RULES:     1. Bring your own Mountain Dew.",

        "           2. Mom said pizza at 8.",

        "           3. No yelling, she's sleeping.",

    ],

    "FREE V-BUCKS REAL NOT FAKE": [

        "GAMEMODE:   TROJAN.WIN32.SUSPICIOUS",

        "MAP:       N/A",

        "RULES:     Just enter your card details.",

        "           100% legit. We promise.",

    ],

}

# Region rotation for flavor

SERVER_REGIONS = [

    "ACARISTAN-EAST relay",

    "KILEMENO-NORTH relay",

    "KRAPISTAN-CENTRAL relay",

    "SLUM-DISTRICT mesh",

    "[UNKNOWN ORIGIN]",

]

# Server-specific kick messages - falls back to global pool

KICK_MESSAGES_BY_SERVER = {

    "Sebi's Parlament [RP] [SERIOUS ONLY]": [

        "Kicked: lacked sufficient bureaucratic forms",

        "Disconnected: your parliamentary immunity has expired",

        "Kicked: failed to address the chair properly",

    ],

    "KGB Archives // LEAKED": [

        "Connection severed by external party",

        "Кикнут. Не задавайте больше вопросов.",

        "You were never here.",

    ],

    "Putin's Summer House [VIP ONLY]": [

        "Kicked: insufficient loyalty score",

        "Disconnected: a man fell out of a window",

        "Kicked: refused to take shirt off",

    ],

    "█████████ [REDACTED]": [

        "███████ ███████████ ████.",

        "████ ████ ███ ███████████ ████.",

    ],

    "MR.BEAST GIVING AWAY CIGARETTES": [

        "Kicked: did not subscribe",

        "Connection failed: insufficient ad revenue",

    ],

    "FREE V-BUCKS REAL NOT FAKE": [

        "Antivirus prevented connection",

        "Connection rejected: you actually have a brain",

    ],

    "yo mama's basement": [

        "Kicked: mom said it's bedtime",

        "Disconnected: pizza arrived",

    ],

}

KICK_MESSAGES = [

    "Connection rejected: your chair lacks RGB",

    "Kicked: skill issue detected",

    "Connection lost: packet of crisps required",

    "Server full: try again in 1984",

    "Kicked: you were born in the wrong decade",

    "Authentication failed: no admin mod installed",

    "Disconnected: your aura is misaligned",

]

# ── Live chat ticker ──

CHAT_POOL = [

    # ── Recurring regulars ──

    ("VasileFan2007", "ez clap", (180, 180, 180)),

    ("VasileFan2007", "lol", (180, 180, 180)),

    ("VasileFan2007", "vasile carried", (180, 180, 180)),

    ("VasileFan2007", "report this guy", (180, 180, 180)),

    ("VasileFan2007", "im not toxic ur just bad", (180, 180, 180)),

    ("xX_KRAP_Xx", "anyone got the notebook code?", (180, 180, 180)),

    ("xX_KRAP_Xx", "fine", (180, 180, 180)),

    ("xX_KRAP_Xx", "ok ok i wont ask again", (180, 180, 180)),

    ("xX_KRAP_Xx", "is it 742", (180, 180, 180)),

    ("xX_KRAP_Xx", "guys??", (180, 180, 180)),

    ("BiribelMain", "skill issue", (180, 180, 180)),

    ("BiribelMain", "down bad", (180, 180, 180)),

    ("BiribelMain", "no scope only", (180, 180, 180)),

    ("BiribelMain", "ur mom", (180, 180, 180)),

    ("Volkov_Real", "i am literally him", (255, 100, 60)),

    ("Volkov_Real", "the IPA doesnt control me", (255, 100, 60)),

    ("Volkov_Real", "stop dming me", (255, 100, 60)),

    ("Volkov_Real", "im not selling secrets", (255, 100, 60)),

    ("Volkov_Real", "ok maybe a few secrets", (255, 100, 60)),

    # ── Admin / moderation drama ──

    ("admin", "do not discuss the notebook code in chat", (255, 120, 0)),

    ("admin", "KICKED: CommanderActual (impersonating officer)", (255, 120, 0)),

    ("admin", "server restart in 2 hours", (255, 120, 0)),

    ("admin", "stop spamming", (255, 120, 0)),

    ("admin", "MUTED: VasileFan2007 (10min)", (255, 120, 0)),

    ("admin", "please report bugs in the appropriate channel", (255, 120, 0)),

    ("admin", "no, we will not add a battle pass", (255, 120, 0)),

    ("admin", "the duplication glitch is patched", (255, 120, 0)),

    ("admin", "stop asking about the duplication glitch", (255, 120, 0)),

    ("admin", "MUTED: BiribelMain (toxicity)", (255, 120, 0)),

    ("MOD_Krapov", "guys keep it civil", (255, 150, 60)),

    ("MOD_Krapov", "first warning", (255, 150, 60)),

    ("MOD_Krapov", "i am NOT a bot", (255, 150, 60)),

    ("MOD_Krapov", "this is your final warning", (255, 150, 60)),

    # ── Faction roleplayers ──

    ("CommanderActual", "hello soldiers", (200, 200, 200)),

    ("CommanderActual_2", "i am the REAL commander", (200, 200, 200)),

    ("CommanderActual_3", "no I am", (200, 200, 200)),

    ("CommanderActual_4", "stop impersonating me", (200, 200, 200)),

    ("MaruWatches", "MARU SEES YOU", (140, 30, 30)),

    ("MaruWatches", "MARU IS DISPLEASED", (140, 30, 30)),

    ("MaruWatches", "the eye does not blink", (140, 30, 30)),

    ("MaruWatches", "MARU SEES YOU SPECIFICALLY", (140, 30, 30)),

    ("MAGRecruiter", "join us. the slums need you.", (140, 30, 30)),

    ("MAGRecruiter", "down with KRAP", (140, 30, 30)),

    ("MAGRecruiter", "free graffiti supplies for new members", (140, 30, 30)),

    ("MAGRecruiter", "the revolution will be uploaded to youtube", (140, 30, 30)),

    ("IPA_OFFICIAL", "stability through prosperity", (180, 100, 100)),

    ("IPA_OFFICIAL", "your oil. our future.", (180, 100, 100)),

    ("IPA_OFFICIAL", "MAG is a terrorist organization", (180, 100, 100)),

    ("IPA_OFFICIAL", "please vote yes on the new pipeline", (180, 100, 100)),

    ("Sebi_PM", "vote yes on bill 7742", (100, 160, 220)),

    ("Sebi_PM", "or else", (100, 160, 220)),

    ("Sebi_PM", "my approval rating is fine actually", (100, 160, 220)),

    ("Sebi_PM", "the polls are rigged", (100, 160, 220)),

    ("Sebi_PM", "i was elected fair and square", (100, 160, 220)),

    ("KGB_Watching", "you have been added to the list", (180, 180, 180)),

    ("KGB_Watching", "we know where you live", (180, 180, 180)),

    ("KGB_Watching", "пожалуйста подтвердите свою личность", (180, 180, 180)),

    ("KGB_Watching", "your cat is also on the list", (180, 180, 180)),

    # ── Cigarette guy saga ──

    ("Cigarette_Enjoyer", "got a light?", (180, 180, 180)),

    ("Cigarette_Enjoyer", "anyone??", (180, 180, 180)),

    ("Cigarette_Enjoyer", "ill trade ammo for a smoke", (180, 180, 180)),

    ("Cigarette_Enjoyer", "two clips for one cigarette", (180, 180, 180)),

    ("Cigarette_Enjoyer", "please", (180, 180, 180)),

    ("Cigarette_Enjoyer", "you guys are heartless", (180, 180, 180)),

    ("Cigarette_Enjoyer", "found one. nvm", (180, 180, 180)),

    # ── Old Fisherman ──

    ("OldFisherman", "third time this month...", (140, 140, 120)),

    ("OldFisherman", "you'll learn", (140, 140, 120)),

    ("OldFisherman", "the ocean was different before", (140, 140, 120)),

    ("OldFisherman", "back in my day we had two fish", (140, 140, 120)),

    ("OldFisherman", "now there's just the one", (140, 140, 120)),

    # ── Noob ──

    ("noob123", "how do i shoot", (180, 180, 180)),

    ("noob123", "nvm", (180, 180, 180)),

    ("noob123", "how do i reload", (180, 180, 180)),

    ("noob123", "WHAT IS THIS GAME", (180, 180, 180)),

    ("noob123", "where are the controls", (180, 180, 180)),

    ("noob123", "i pressed a button and now im dead", (180, 180, 180)),

    ("noob123", "wait its WASD?", (180, 180, 180)),

    ("noob123", "ohhhh", (180, 180, 180)),

    ("noob123", "this game is hard", (180, 180, 180)),

    ("noob123", "why is everyone shooting me", (180, 180, 180)),

    # ── FuegoTech fanboy ──

    ("FuegoTechFan", "K1 is the best gun in the game change my mind", (180, 180, 180)),

    ("FuegoTechFan", "FUEGO FUEGO FUEGO", (180, 180, 180)),

    ("FuegoTechFan", "micul fuego is god", (180, 180, 180)),

    ("FuegoTechFan", "FT > all other brands", (180, 180, 180)),

    ("FuegoTechFan", "K2 leak when???", (180, 180, 180)),

    # ── Toxic teen squad ──

    ("KGB_Hater_69", "this game is rigged", (180, 180, 180)),

    ("KGB_Hater_69", "modded lobby", (180, 180, 180)),

    ("KGB_Hater_69", "everyone is cheating", (180, 180, 180)),

    ("KGB_Hater_69", "uninstalling", (180, 180, 180)),

    ("KGB_Hater_69", "im back", (180, 180, 180)),

    ("Putin_Stan_88", "russia stronk", (180, 180, 180)),

    ("Putin_Stan_88", "in soviet acaristan...", (180, 180, 180)),

    # ── Lore / atmosphere ──

    ("???", "...", (90, 90, 90)),

    ("???", "is anyone still here", (90, 90, 90)),

    ("???", "the lights flicker again", (90, 90, 90)),

    ("???", "i can hear them through the wall", (90, 90, 90)),

    ("BANNED_USER", "[message redacted]", (90, 90, 90)),

    ("BANNED_USER", "[user banned]", (90, 90, 90)),

    ("BANNED_USER", "[evading ban detected]", (90, 90, 90)),

    ("DELETED_ACCOUNT", "[this user no longer exists]", (90, 90, 90)),

    # ── Salesmen / spam ──

    ("CHEAP_BOOSTING", "RANK UP FAST! DM FOR PRICES", (110, 110, 110)),

    ("CHEAP_BOOSTING", "RANK 1 GUARANTEED $20", (110, 110, 110)),

    ("CHEAP_BOOSTING", "VAC PROOF (probably)", (110, 110, 110)),

    ("admin", "KICKED: CHEAP_BOOSTING (advertising)", (255, 120, 0)),

    ("WTF_IS_OIL", "what is oil", (180, 180, 180)),

    ("WTF_IS_OIL", "no like seriously", (180, 180, 180)),

    ("WTF_IS_OIL", "why are we fighting over it", (180, 180, 180)),

    # ── Random one-liners ──

    ("Cmdr_VodkaTime", "anyone wanna duo?", (180, 180, 180)),

    ("Cmdr_VodkaTime", "im drunk", (180, 180, 180)),

    ("Cmdr_VodkaTime", "lets go", (180, 180, 180)),

    ("StealthMain_42", "if you shoot you lose", (180, 180, 180)),

    ("StealthMain_42", "throw bottles. always.", (180, 180, 180)),

    ("StealthMain_42", "i havent fired a shot in 200 hours", (180, 180, 180)),

    ("RushB_Acaristan", "RUSH B", (180, 180, 180)),

    ("RushB_Acaristan", "RUSH B CYKA", (180, 180, 180)),

    ("RushB_Acaristan", "WHY NOBODY RUSH B", (180, 180, 180)),

    ("MicrowaveChef", "im cooking dinner brb", (180, 180, 180)),

    ("MicrowaveChef", "back. it was hot pockets", (180, 180, 180)),

    ("ServerRegular", "another day in acaristan", (160, 160, 165)),

    ("ServerRegular", "same as yesterday", (160, 160, 165)),

    ("ServerRegular", "and the day before", (160, 160, 165)),

    ("ConspiracyGuy", "the oil rigs were an inside job", (180, 180, 180)),

    ("ConspiracyGuy", "wake up sheeple", (180, 180, 180)),

    ("ConspiracyGuy", "MARU is just a CIA op", (180, 180, 180)),

    ("LonelyHeart", "anyone wanna be my friend?", (180, 180, 180)),

    ("LonelyHeart", "no?", (180, 180, 180)),

    ("LonelyHeart", "ok", (180, 180, 180)),

    ("SystemBot_v3", "REMINDER: Drink water.", (80, 140, 100)),

    ("SystemBot_v3", "REMINDER: Take a break.", (80, 140, 100)),

    ("SystemBot_v3", "REMINDER: Your posture is bad.", (80, 140, 100)),

    ("EX_KRAP_OPERATOR", "i shouldnt be here", (180, 100, 100)),

    ("EX_KRAP_OPERATOR", "they think im dead", (180, 100, 100)),

    ("EX_KRAP_OPERATOR", "if anyone sees this, run", (180, 100, 100)),

    # ── Meme / quote spam ──

    ("MemeLord_AC", "the notebook was inside us all along", (180, 180, 180)),

    ("MemeLord_AC", "what if acaristan was a game", (180, 180, 180)),

    ("MemeLord_AC", "it's just a flesh wound", (180, 180, 180)),

    ("CapsLock_Stuck", "WHY IS MY CAPS LOCK STUCK", (180, 180, 180)),

    ("CapsLock_Stuck", "PLEASE HELP", (180, 180, 180)),

    ("CapsLock_Stuck", "I CANT TYPE NORMAL", (180, 180, 180)),

    ("CapsLock_Stuck", "OH WAIT NVM", (180, 180, 180)),

    # ── The Returning Joke ──

    ("xX_KRAP_Xx", "wait the code IS 742??", (180, 180, 180)),

    ("admin", "MUTED: xX_KRAP_Xx (permanent)", (255, 120, 0)),

]

# ── Connections / DM system ──

CONNECTIONS = [

    {

        "name": "Vasile",

        "status": "Online",

        "last_seen": "now",

        "color": (100, 160, 220),

        "replies": [

            "Biribel. Get to the point.",

            "I'm in a meeting. Make it quick.",

            "Did you check the safe code? It's in the desk.",

            "Stop messaging me on KRAPNET. Use the encrypted line.",

            "I hate paperwork. This is paperwork.",

            "Don't die. I hate the funeral forms even more.",

        ],

    },

    {

        "name": "Volkov",

        "status": "Away",

        "last_seen": "3m ago",

        "color": (255, 100, 60),

        "replies": [

            "Who is this?",

            "How did you get this number.",

            "I'm not Volkov. You have the wrong person.",

            "Stop. Messaging. Me.",

            "If you tell anyone, you'll regret it.",

            "Fine. What do you want.",

        ],

    },

    {

        "name": "Old Fisherman",

        "status": "Online",

        "last_seen": "now",

        "color": (140, 140, 120),

        "replies": [

            "The ocean was different before.",

            "Third time this month.",

            "You'll learn.",

            "Back in my day we had two fish. Now there's just the one.",

            "The rigs burn brighter every year.",

            "Don't trust the men in blue.",

        ],

    },

    {

        "name": "Sebi (PM)",

        "status": "In Meeting",

        "last_seen": "1h ago",

        "color": (100, 160, 220),

        "replies": [

            "I do not have time for citizens right now.",

            "Vote yes on bill 7742.",

            "My approval rating is fine, actually.",

            "The polls are rigged.",

            "I was elected fair and square.",

            "Please direct all complaints to /dev/null.",

        ],

    },

    {

        "name": "MaruWatches",

        "status": "Online",

        "last_seen": "always",

        "color": (140, 30, 30),

        "replies": [

            "MARU SEES YOU.",

            "THE EYE DOES NOT BLINK.",

            "WHY ARE YOU MESSAGING ME.",

            "MARU IS DISPLEASED.",

            "MARU SAW THAT.",

            "MARU SEES YOU SPECIFICALLY.",

        ],

    },

    {

        "name": "Micul Fuego",

        "status": "Online - LAUNCH PARTY!",

        "last_seen": "now",

        "color": (255, 180, 60),

        "replies": [

            "YO BIRIBEL!! u coming to the K1 launch?!?!",

            "bro the new gun goes HARD",

            "FUEGO FUEGO FUEGO !!!",

            "i got u a free K1. dm me your address",

            "wait dont dm me your address. the IPA is watching",

            "actually do. its fine. probably.",

        ],

    },

    {

        "name": "noob123",

        "status": "Online",

        "last_seen": "now",

        "color": (180, 180, 180),

        "replies": [

            "how do i play",

            "is this discord",

            "where am i",

            "are u the admin",

            "i pressed a button",

            "ok",

        ],

    },

    {

        "name": "Cigarette_Enjoyer",

        "status": "Online",

        "last_seen": "now",

        "color": (180, 180, 180),

        "replies": [

            "got a light?",

            "please",

            "ill trade ammo for a smoke",

            "two clips for one cigarette. final offer",

            "you guys are heartless",

            "fine ill ask someone else",

        ],

    },

    {

        "name": "KGB_Watching",

        "status": "Online",

        "last_seen": "always",

        "color": (180, 180, 180),

        "replies": [

            "We know who you are.",

            "You have been added to the list.",

            "Your cat is also on the list.",

            "Please confirm your identity.",

            "\u0414\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e.",

            "We are inside your walls.",

        ],

    },

    {

        "name": "MAGRecruiter",

        "status": "Online",

        "last_seen": "now",

        "color": (140, 30, 30),

        "replies": [

            "Join us. The slums need you.",

            "Down with KRAP.",

            "Free graffiti supplies for new members.",

            "The revolution will be uploaded to youtube.",

            "Are you really one of them?",

            "It's not too late to switch sides.",

        ],

    },

    {

        "name": "EX_KRAP_OPERATOR",

        "status": "Away",

        "last_seen": "unknown",

        "color": (180, 100, 100),

        "replies": [

            "I shouldn't be here.",

            "They think I'm dead.",

            "If anyone sees this, run.",

            "Do not trust the Commander.",

            "I left a notebook. Find it.",

            "Don't reply to this message.",

        ],

    },

    {

        "name": "Mom",

        "status": "Offline",

        "last_seen": "2 days ago",

        "color": (200, 180, 180),

        "replies": [

            "honey when are you coming home",

            "i made your favorite soup",

            "did you eat today",

            "your father says hello",

            "please call me",

            "i love you",

        ],

    },

    {

        "name": "[REDACTED]",

        "status": "\u2588\u2588\u2588\u2588\u2588\u2588\u2588",

        "last_seen": "\u2588\u2588\u2588\u2588\u2588\u2588\u2588",

        "color": (110, 110, 110),

        "replies": [

            "\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588 \u2588\u2588\u2588 \u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588.",

            "\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588.",

            "\u2588\u2588 \u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588.",

            "\u2588\u2588\u2588\u2588\u2588 \u2588\u2588\u2588 \u2588\u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588\u2588.",

        ],

    },

    {

        "name": "DELETED_USER",

        "status": "Account Deleted",

        "last_seen": "never",

        "color": (90, 90, 90),

        "replies": [

            "[this user no longer exists]",

            "[message could not be delivered]",

            "[recipient is gone]",

        ],

    },

    {

        "name": "Captain Krapov",

        "status": "In Game",

        "last_seen": "now",

        "color": (180, 150, 100),

        "replies": [

            "Operator. Report status.",

            "Negative. Stay on mission.",

            "I don't have time for this. Out.",

            "Watch your tone, soldier.",

            "Affirmative.",

            "Out.",

        ],

    },

]

# DM state

_dm_open_user = None

_dm_history = {}

_dm_input = ""

_dm_response_delay = 0

_dm_pending_reply = None

_dm_scroll_offset = 0

# Tab state

_mp_tab = "SERVERS"

# Button rects

servers_tab_rect = pygame.Rect(0, 0, 130, 28)

connections_tab_rect = pygame.Rect(0, 0, 164, 28)

# The Outfitter, reachable from here because this is the screen that earns the
# currency it spends. Positioned at draw time like the tabs, since the panel
# geometry it sits inside is defined below.
outfitter_btn_rect = pygame.Rect(0, 0, 124, 28)

# ── Panel geometry ──────────────────────────────────────────────
# The panel is split into three horizontal bands, all derived from
# these two numbers so nothing can drift out of alignment:
#
#   header : panel top .. SERVER_LIST_TOP
#   body   : SERVER_LIST_TOP .. SERVER_LIST_LIMIT  (list / chat)
#   footer : SERVER_FOOTER_TOP .. panel bottom     (actions)
#
# The old layout had one 184px header and no footer band at all, so
# the last visible server row was drawn underneath the BACK button
# and the scroll hint landed past the panel's own content area.

SERVER_PANEL_W = 940

SERVER_PANEL_H = 620

SERVER_PANEL_X = (WIDTH - SERVER_PANEL_W) // 2

SERVER_PANEL_Y = (HEIGHT - SERVER_PANEL_H) // 2

SERVER_HEADER_Y = SERVER_PANEL_Y + 22

# The subtitle hangs off the *measured* title height, not a magic
# offset - a font fallback (no Impact) must not re-collide them.

SERVER_SUBTITLE_Y = SERVER_PANEL_Y + 80

SERVER_CONNECT_Y = max(
    SERVER_PANEL_Y + 105,
    SERVER_SUBTITLE_Y + font_terminal_small.get_height() + 8,
)

SERVER_TAB_Y = SERVER_CONNECT_Y + 35

SERVER_DIVIDER_Y = SERVER_TAB_Y + 38

# Server list lives on the LEFT side of the panel

SERVER_ROW_X = SERVER_PANEL_X + 34

SERVER_ROW_W = 580

SERVER_LIST_TOP = max(SERVER_PANEL_Y + 210, SERVER_DIVIDER_Y + 36)

# Footer band: divider, BACK button and the ESC hint live here.

SERVER_FOOTER_TOP = SERVER_PANEL_Y + SERVER_PANEL_H - 76

SERVER_BACK_Y = SERVER_FOOTER_TOP + 12

# Hard ceiling for list content - no row is ever drawn past this,
# whatever the font metrics turn out to be.

SERVER_LIST_LIMIT = SERVER_FOOTER_TOP - 26

# font_terminal renders a 28px tall glyph box, so a 2-line name needs
# 28px of leading to stop the boxes touching (the old 20px leading
# overlapped them by 8px).  6 + 28 + 28 = 62, which is what a 70px row
# can carry with 4px to spare.

SERVER_ROW_LEAD = 28

SERVER_ROW_H_SINGLE = 46

SERVER_ROW_H_DOUBLE = 70

SERVER_ROW_GAP = 6

# A 2-line name plus its region line never fitted in 64px, so the
# region moved into the hover tooltip. These heights always fit
# between SERVER_LIST_TOP and SERVER_LIST_LIMIT.

SERVER_VISIBLE_ROWS = 4

SERVER_NAME_MAX_W = 322 - 24

SERVER_BADGE_W = 78

# Right-hand columns. 580px of row minus the widest possible values
# ("99/100" = 78px, "400ms" = 65px) leaves >=12px between each.

SERVER_STATUS_X = SERVER_ROW_X + 322

SERVER_PLAYERS_X = SERVER_ROW_X + 414

SERVER_PING_X = SERVER_ROW_X + 504

# Chat panel lives on the RIGHT side, sharing the body's bottom edge

CHAT_PANEL_X = SERVER_PANEL_X + SERVER_PANEL_W - 270

CHAT_PANEL_Y = SERVER_LIST_TOP

CHAT_PANEL_W = 240

CHAT_PANEL_H = SERVER_LIST_LIMIT - CHAT_PANEL_Y

# Contacts list (CONNECTIONS tab)

CONTACTS_X = SERVER_PANEL_X + 28

CONTACTS_Y = SERVER_LIST_TOP - 4

CONTACTS_W = 400

CONNECTIONS_ROW_H = 40

_chat_messages = []

_chat_next_spawn = 0

_server_animation_timer = 0

_refresh_active = False

_refresh_progress = 0.0

_scroll_offset = 0

refresh_btn_rect = pygame.Rect(SERVER_PANEL_X + SERVER_PANEL_W - 110, SERVER_CONNECT_Y, 82, 26)

kick_dismiss_btn_rect = pygame.Rect(0, 0, 160, 30)

def _server_status(cur, max_p, ping):

    if cur >= max_p:

        return "FULL", (220, 120, 45)

    if ping >= 180:

        return "UNSTABLE", (220, 80, 70)

    return "OPEN", C_TERMINAL

def _draw_server_badge(text, color, x, y, w=78):

    badge = pygame.Surface((w, 22), pygame.SRCALPHA)

    badge.fill((8, 12, 16, 210))

    pygame.draw.rect(badge, color, badge.get_rect(), 1)

    screen.blit(badge, (x, y))

    label = font_terminal_small.render(text, True, color)

    screen.blit(label, (x + w // 2 - label.get_width() // 2, y + 4))

def _fit_text(text, font, max_width):

    if font.size(text)[0] <= max_width:

        return text

    ellipsis = "..."

    while text and font.size(text + ellipsis)[0] > max_width:

        text = text[:-1]

    return text + ellipsis

def update_server_browser_animation():

    """Called once per frame while on multiplayer screen."""

    global _server_animation_timer, _chat_next_spawn, _chat_messages

    global _refresh_active, _refresh_progress

    # Pull the latest relay snapshot FIRST, so the ping jitter and chat
    # spawner below operate on current data rather than last frame's.

    _sync_relay_into_server_list()

    _server_animation_timer += 1

    # Animate pings + player counts every ~90 frames (1.5s).
    # Skipped when a live relay is driving the list: those numbers are
    # authoritative, and jittering them would be a lie.

    if relay_is_live():

        pass

    elif _server_animation_timer % 90 == 0 and not _refresh_active:

        for i, (name, cur, max_p, ping) in enumerate(server_list):

            delta = _rng_legacy.choice([-1, 0, 0, 0, 0, 1])

            new_cur = max(0, min(max_p, cur + delta))

            new_ping = max(8, min(400, ping + _rng_legacy.randint(-6, 6)))

            server_list[i] = (name, new_cur, max_p, new_ping)

    # Refresh progress

    if _refresh_active:

        _refresh_progress += 0.025

        if _refresh_progress >= 1.0:

            _refresh_active = False

            _refresh_progress = 0.0

            for i, (name, cur, max_p, ping) in enumerate(server_list):

                new_cur = max(0, min(max_p, cur + _rng_legacy.randint(-3, 3)))

                new_ping = max(8, min(400, ping + _rng_legacy.randint(-25, 25)))

                server_list[i] = (name, new_cur, max_p, new_ping)

    # Spawn chat messages.
    # Suppressed while a live relay is connected: real players' lines are
    # arriving over the socket, and mixing in CHAT_POOL fiction would make
    # it impossible to tell who is actually in the lobby.

    if not relay_is_live():

        _chat_next_spawn -= 1

    if not relay_is_live() and _chat_next_spawn <= 0:

        msg = _rng_legacy.choice(CHAT_POOL)

        _chat_messages.append({

            "user": msg[0],

            "text": msg[1],

            "color": msg[2],

            "age": 0,

            # Marks this line as invented, so the handover to a live relay
            # can drop fiction without touching real players' messages.

            "fict": True,

        })

        _chat_next_spawn = _rng_legacy.randint(60, 130)

        if _rng_legacy.random() < 0.18:

            msg2 = _rng_legacy.choice(CHAT_POOL)

            _chat_messages.append({

                "user": msg2[0],

                "text": msg2[1],

                "color": msg2[2],

                "age": 0,

                "fict": True,

            })

        if len(_chat_messages) > 50:

            _chat_messages.pop(0)

    # Age messages

    for m in _chat_messages:

        m["age"] += 1

def switch_mp_tab(tab):

    global _mp_tab

    _mp_tab = tab

    audio.play("menu_click", volume=0.3)

def open_dm(user_idx):

    global _dm_open_user, _dm_input

    _dm_open_user = user_idx

    _dm_input = ""

    if user_idx not in _dm_history:

        _dm_history[user_idx] = []

    audio.play("menu_click", volume=0.3)

def close_dm():

    global _dm_open_user, _dm_input

    _dm_open_user = None

    _dm_input = ""

def send_dm_message():

    global _dm_input, _dm_response_delay, _dm_pending_reply

    if _dm_open_user is None or not _dm_input.strip():

        return

    _dm_history[_dm_open_user].append({

        "from": "you",

        "text": _dm_input.strip(),

        "age": 0,

    })

    _dm_input = ""

    _dm_response_delay = _rng_legacy.randint(45, 110)

    _dm_pending_reply = _dm_open_user

    audio.play("menu_click", volume=0.2)

def update_dm_state():

    global _dm_response_delay, _dm_pending_reply

    if _dm_open_user is not None and _dm_open_user in _dm_history:

        for m in _dm_history[_dm_open_user]:

            m["age"] += 1

    if _dm_response_delay > 0:

        _dm_response_delay -= 1

        if _dm_response_delay == 0 and _dm_pending_reply is not None:

            reply = _rng_legacy.choice(CONNECTIONS[_dm_pending_reply]["replies"])

            _dm_history[_dm_pending_reply].append({

                "from": "them",

                "text": reply,

                "age": 0,

            })

            _dm_pending_reply = None

            audio.play("menu_hover", volume=0.3)

def _status_color(status):

    if "Online" in status or status == "always":

        return (80, 220, 100)

    if "Away" in status or "Meeting" in status:

        return (220, 180, 60)

    if "Game" in status:

        return (100, 160, 220)

    if "Offline" in status or "Deleted" in status or "never" in status:

        return (110, 110, 110)

    if "\u2588" in status:

        return (140, 60, 60)

    return (180, 180, 180)

def draw_connections_panel():

    """Draws the friends list + active DM window."""

    mouse_pos = get_scaled_mouse()

    list_x = CONTACTS_X

    list_y = CONTACTS_Y

    list_w = CONTACTS_W

    row_h = CONNECTIONS_ROW_H

    list_header = font_terminal_small.render(_T("mp.contacts"), True, (80, 130, 160))

    screen.blit(list_header, (list_x + 6, list_y - 20))

    online_count = sum(1 for c in CONNECTIONS if "Online" in c["status"])

    online_lbl = font_terminal_small.render(

        _T("mp.online_total", online=online_count, total=len(CONNECTIONS)),

        True, (90, 130, 100),

    )

    screen.blit(online_lbl, (list_x + list_w - online_lbl.get_width() - 6, list_y - 20))

    list_bottom_limit = SERVER_LIST_LIMIT

    visible_friends = (list_bottom_limit - list_y) // row_h

    visible_friends = min(visible_friends, len(CONNECTIONS))

    for vi in range(visible_friends):

        i = vi + _dm_scroll_offset

        if i >= len(CONNECTIONS):

            break

        conn = CONNECTIONS[i]

        ry = list_y + vi * row_h

        row_rect = pygame.Rect(list_x, ry, list_w, row_h - 4)

        hover = row_rect.collidepoint(mouse_pos)

        is_open = _dm_open_user == i

        row_surf = pygame.Surface((list_w, row_h - 4), pygame.SRCALPHA)

        if is_open:

            row_surf.fill((28, 36, 42, 235))

            pygame.draw.rect(row_surf, C_ORANGE, row_surf.get_rect(), 1)

            pygame.draw.rect(row_surf, (255, 120, 0, 130), (0, 0, 3, row_h - 4))

        elif hover:

            row_surf.fill((18, 28, 34, 225))

            pygame.draw.rect(row_surf, (80, 120, 140), row_surf.get_rect(), 1)

        else:

            row_surf.fill((9, 14, 18, 210))

            pygame.draw.rect(row_surf, (28, 44, 56), row_surf.get_rect(), 1)

        screen.blit(row_surf, row_rect)

        s_col = _status_color(conn["status"])

        pygame.draw.circle(screen, s_col, (list_x + 14, ry + row_h // 2 - 2), 4)

        name_col = C_WHITE if (hover or is_open) else conn["color"]

        name_surf = font_terminal.render(conn["name"], True, name_col)

        screen.blit(name_surf, (list_x + 28, ry + 4))

        # One line per contact: name left, status right-aligned. It used to
        # be a second line under a 34px-tall row, so it spilled out of the
        # row and into the contact below. The name is the identity here, so
        # the status is the half that gets the ellipsis.
        status_text = f"{conn['status']}  \u00b7  {conn['last_seen']}"

        status_w = list_w - 28 - 8 - name_surf.get_width() - 16

        status_surf = font_terminal_small.render(_fit_text(status_text, font_terminal_small, max(48, status_w)), True, (120, 130, 140))

        screen.blit(status_surf, (list_x + list_w - 8 - status_surf.get_width(), ry + 8))

    # ── Scroll indicators ──

    remaining_below = len(CONNECTIONS) - (_dm_scroll_offset + visible_friends)

    remaining_above = _dm_scroll_offset

    more_y = list_y + visible_friends * row_h + 4

    if remaining_below > 0 and remaining_above > 0:

        more_lbl = font_terminal_small.render(

            _T("mp.remaining_above_above_remaining", remaining_above=remaining_above, remaining_below=remaining_below),

            True, (90, 110, 130),

        )

        screen.blit(more_lbl, (list_x + 6, more_y))

    elif remaining_below > 0:

        more_lbl = font_terminal_small.render(

            _T("mp.remaining_below_more_contacts_sc", remaining_below=remaining_below),

            True, (90, 110, 130),

        )

        screen.blit(more_lbl, (list_x + 6, more_y))

    elif remaining_above > 0:

        more_lbl = font_terminal_small.render(

            _T("mp.remaining_above_above_scroll_whe", remaining_above=remaining_above),

            True, (90, 110, 130),

        )

        screen.blit(more_lbl, (list_x + 6, more_y))

    # ── Scrollbar for contacts ──

    if len(CONNECTIONS) > visible_friends:

        sb_x = list_x + list_w + 4

        sb_y = list_y

        sb_h = visible_friends * row_h - 4

        sb_w = 5

        pygame.draw.rect(screen, (15, 22, 28), (sb_x, sb_y, sb_w, sb_h))

        pygame.draw.rect(screen, (28, 44, 56), (sb_x, sb_y, sb_w, sb_h), 1)

        thumb_ratio = visible_friends / len(CONNECTIONS)

        thumb_h = max(20, int(sb_h * thumb_ratio))

        max_scroll = max(1, len(CONNECTIONS) - visible_friends)

        thumb_y = sb_y + int((sb_h - thumb_h) * (_dm_scroll_offset / max_scroll))

        pygame.draw.rect(screen, C_ORANGE, (sb_x, thumb_y, sb_w, thumb_h))

    # DM window (right column)

    dm_x = list_x + list_w + 16

    dm_y = list_y - 4

    dm_w = SERVER_PANEL_X + SERVER_PANEL_W - dm_x - 28

    # Stopped above the footer divider, which used to clip the send hint.

    dm_h = SERVER_LIST_LIMIT - 8 - dm_y

    dm_bg = pygame.Surface((dm_w, dm_h), pygame.SRCALPHA)

    dm_bg.fill((6, 11, 16, 230))

    pygame.draw.rect(dm_bg, (30, 50, 60), dm_bg.get_rect(), 1)

    pygame.draw.rect(dm_bg, (40, 60, 70, 100), dm_bg.get_rect(), 1)

    screen.blit(dm_bg, (dm_x, dm_y))

    if _dm_open_user is None:

        empty_lbl = font_terminal.render(_T("mp.select_a_contact"), True, (60, 90, 110))

        screen.blit(

            empty_lbl,

            (dm_x + dm_w // 2 - empty_lbl.get_width() // 2,

             dm_y + dm_h // 2 - 20),

        )

        hint = font_terminal_small.render(

            _T("mp.click_a_name_on_the_left_to_star"),

            True, (50, 70, 85),

        )

        screen.blit(

            hint,

            (dm_x + dm_w // 2 - hint.get_width() // 2,

             dm_y + dm_h // 2 + 8),

        )

    else:

        conn = CONNECTIONS[_dm_open_user]

        s_col = _status_color(conn["status"])

        pygame.draw.circle(screen, s_col, (dm_x + 14, dm_y + 14), 4)

        hdr = font_terminal.render(conn["name"], True, conn["color"])

        screen.blit(hdr, (dm_x + 26, dm_y + 4))

        st = font_terminal_small.render(

            conn["status"], True, _status_color(conn["status"]),

        )

        screen.blit(st, (dm_x + 26, dm_y + 22))

        pygame.draw.line(

            screen, (30, 50, 60),

            (dm_x + 8, dm_y + 40),

            (dm_x + dm_w - 8, dm_y + 40), 1,

        )

        msg_x = dm_x + 12

        msg_y = dm_y + 48

        msg_w = dm_w - 24

        msg_area_h = dm_h - 116

        history = _dm_history.get(_dm_open_user, [])

        rendered = []

        for m in history:

            text = m["text"]

            is_you = m["from"] == "you"

            col = (220, 220, 220) if is_you else conn["color"]

            words = text.split(" ")

            line = ""

            wrapped = []

            for w in words:

                test = (line + " " + w).strip() if line else w

                if font_terminal_small.size(test)[0] <= msg_w - 60:

                    line = test

                else:

                    if line:

                        wrapped.append(line)

                    line = w

            if line:

                wrapped.append(line)

            for li, ln in enumerate(wrapped):

                prefix = ""

                if li == 0:

                    prefix = "you: " if is_you else f"{conn['name']}: "

                rendered.append((prefix, ln, col, is_you, m["age"]))

        line_h = 16

        max_lines = msg_area_h // line_h

        visible = rendered[-max_lines:]

        for li, (prefix, ln, col, is_you, age) in enumerate(visible):

            ly = msg_y + li * line_h

            alpha = min(255, age * 15)

            if prefix:

                p_col = (140, 140, 145) if is_you else col

                ps = font_terminal_small.render(prefix, True, p_col)

                ps.set_alpha(alpha)

                screen.blit(ps, (msg_x, ly))

                ts = font_terminal_small.render(ln, True, (220, 220, 220) if is_you else (210, 210, 215))

                ts.set_alpha(alpha)

                screen.blit(ts, (msg_x + ps.get_width(), ly))

            else:

                ts = font_terminal_small.render("  " + ln, True, (210, 210, 215))

                ts.set_alpha(alpha)

                screen.blit(ts, (msg_x, ly))

        if _dm_response_delay > 0 and _dm_pending_reply == _dm_open_user:

            dots = "." * (((_now_ms() // 300) % 3) + 1)

            typing = font_terminal_small.render(

                _T("mp.typing", name=conn["name"], dots=dots), True, (100, 130, 150),

            )

            screen.blit(typing, (msg_x, dm_y + dm_h - 64))

        input_box_y = dm_y + dm_h - 42

        pygame.draw.rect(screen, (15, 22, 28), (dm_x + 8, input_box_y, dm_w - 16, 32))

        pygame.draw.rect(screen, (50, 80, 100), (dm_x + 8, input_box_y, dm_w - 16, 32), 1)

        cursor = "_" if (_now_ms() // 500) % 2 == 0 else " "

        input_display = _dm_input + cursor

        if not _dm_input:

            input_display = "Type a message..."

            in_col = (90, 100, 110)

        else:

            in_col = C_WHITE

        ins = font_terminal_small.render(input_display, True, in_col)

        screen.blit(ins, (dm_x + 16, input_box_y + 10))

        send_hint = font_terminal_small.render(

            _T("mp.enter_send_esc_close_dm"),

            True, (90, 110, 120),

        )

        screen.blit(send_hint, (dm_x + 12, dm_y + dm_h + 4))

def scroll_server_list(direction):

    """direction: +1 scrolls down, -1 scrolls up."""

    global _scroll_offset

    # Scroll by a whole window: stopping at len-1 used to leave a single
    # row stranded on screen.

    max_offset = max(0, len(server_list) - SERVER_VISIBLE_ROWS)

    _scroll_offset = max(0, min(max_offset, _scroll_offset + direction))

def scroll_dm_list(direction):

    global _dm_scroll_offset

    list_bottom_limit = SERVER_LIST_LIMIT

    list_y = CONTACTS_Y

    row_h = CONNECTIONS_ROW_H

    visible_friends = (list_bottom_limit - list_y) // row_h

    max_offset = max(0, len(CONNECTIONS) - visible_friends)

    _dm_scroll_offset = max(0, min(max_offset, _dm_scroll_offset + direction))

# ── KRAPNET relay (real backend) ──────────────────────────────────
# The fictional server_list above is the offline fallback. When a relay
# client is running, its rows replace server_list in-place (same 4-tuple
# shape) so every existing render and hit-test site keeps working with no
# changes. _relay_rules mirrors the master's rules side-table and takes
# priority over SERVER_RULES in the hover tooltip.
#
# Mutable-state discipline: _relay_client / _relay_status / _relay_error
# are owned by THIS module. Anything else that needs them must use
# `import ui.mp as _o` and read `_o.name` -- never `from ui.mp import ...`,
# which would snapshot a stale value.
_relay_client = None
_relay_status = "offline"
_relay_error = ""
_relay_rules = {}
_relay_host = "127.0.0.1"
_relay_port = 27015
_relay_nick = "operator"
# Chat input line. While a live relay is up this is real text the player
# types; it is never populated while offline.
_chat_input = ""
_CHAT_MAX_INPUT = 180
# Default port used when a pasted address omits ":port". Defined here (not
# at the use site) because relay_connect_to() below reads it.
_P_DEFAULT_PORT = 27015

# ── Direct connect ("join by address") ───────────────────────────
# A friend running tools/mp_host.py (or the hosted EXE) gives you an
# address like 1.2.3.4:27015. This is the box you paste it into.
_connect_input = ""
_CONNECT_MAX_INPUT = 60
_connect_rect = pygame.Rect(0, 0, 300, 26)
_connect_btn_rect = pygame.Rect(0, 0, 92, 26)
_connect_focused = False
_connect_msg = ""
_connect_msg_age = 0


def connect_bar_take_focus():
    """Called on click so typing goes to the address box, not the game."""
    global _connect_focused
    _connect_focused = True


def connect_bar_click(mouse_pos):
    """Handle a click in the direct-connect row. Returns True if consumed."""
    global _connect_focused
    if _connect_btn_rect.collidepoint(mouse_pos):
        return do_direct_connect()
    if _connect_rect.collidepoint(mouse_pos):
        _connect_focused = True
        return True
    _connect_focused = False
    return False


def do_direct_connect():
    """Connect to whatever is in the address box. Returns True if we tried."""
    global _connect_msg, _connect_msg_age
    _connect_focused = False
    ok, message = relay_connect_to(_connect_input)
    if ok:
        _connect_msg = "connecting to %s" % message
        audio.play("menu_click", volume=0.3)
    else:
        _connect_msg = message
    _connect_msg_age = 0
    return ok


def direct_connect_key(event):
    """Handle one KEYDOWN for the address box. True if consumed."""
    global _connect_input, _connect_focused
    if not _connect_focused:
        return False
    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
        return do_direct_connect()
    if event.key == pygame.K_BACKSPACE:
        _connect_input = _connect_input[:-1]
        return True
    if event.key == pygame.K_ESCAPE:
        _connect_focused = False
        return True
    # A paste is a TEXTINPUT event, not a keypress; grab the clipboard.
    if event.key == pygame.K_v and (
            event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
        paste = clipboard_text(_CONNECT_MAX_INPUT - len(_connect_input))
        if paste:
            _connect_input += paste
        return True
    if getattr(event, "unicode", "") and event.unicode.isprintable():
        if len(_connect_input) < _CONNECT_MAX_INPUT:
            _connect_input += event.unicode
        return True
    return False


def direct_connect_tick():
    """Age the status message so it fades like the chat lines do."""
    global _connect_msg_age
    _connect_msg_age += 1

# Set True to fall back to the fictional list if the relay is unreachable.
_relay_optional = True


def relay_host():
    """Current master host/port, read from the environment if present.

    Env vars let a player point the game at someone else's master without
    editing code, and let the smoke test spin up a throwaway instance.
    """
    import os
    host = os.environ.get("ACA_MP_HOST", _relay_host)
    try:
        port = int(os.environ.get("ACA_MP_PORT", _relay_port))
    except ValueError:
        port = _relay_port
    return host, port


def relay_start(nick=None, host=None, port=None, discover=True):
    """Start (or restart) the relay client. Safe to call every frame.

    Returns True if a client is running. Never blocks *for long*: start()
    only spawns a daemon thread, and all socket work happens on that
    thread. The optional LAN discovery probe is the one exception -- it is
    a single UDP broadcast with a short timeout, and only runs when no
    explicit host was passed.
    """
    global _relay_client, _relay_nick, _relay_host, _relay_port
    from net.client import MPRelayClient, register_chat_sink

    if nick:
        _relay_nick = nick
    h, p = relay_host()
    if host is not None:
        h = host
    if port is not None:
        p = port
    # Only auto-discover when the caller did not name a host explicitly.
    # An explicit host is a deliberate choice and must not be overridden.
    if discover and host is None:
        try:
            from net.discovery import discover_master
            found = discover_master(timeout=1.0)
            if found:
                h, p = found
        except Exception:
            pass  # discovery is a convenience, never a requirement
    _relay_host, _relay_port = h, p

    if _relay_client is not None:
        _relay_client.host = h
        _relay_client.port = p
        return True

    # Register the sink before starting so no early chat line is dropped.
    register_chat_sink(_on_relay_chat)
    _relay_client = MPRelayClient(host=h, port=p, nickname=_relay_nick,
                                 chat_enabled=True)
    _relay_client.start()
    _relay_client.request_connect()
    return True


def relay_send_chat_line():

    """Send whatever is in the chat input box, then clear it.

    Returns True if a line was actually sent. Echo is handled by the master,
    so we do not append locally -- that would double every message.
    """
    global _chat_input

    text = _chat_input.strip()

    if not text:
        return False

    if not relay_send_chat(text):
        return False

    _chat_input = ""

    return True


def relay_chat_key(event):

    """Handle one KEYDOWN for the chat input. Returns True if consumed.

    Only ENTER and BACKSPACE are claimed here; ordinary character keys are
    consumed too, but only while a live relay is connected. Returning
    True tells the caller to swallow the event so it does not also reach
    the DM composer or the mission input layer.
    """
    global _chat_input

    if not relay_is_live():
        return False

    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
        relay_send_chat_line()
        return True

    if event.key == pygame.K_BACKSPACE:
        _chat_input = _chat_input[:-1]
        return True

    # A paste is a TEXTINPUT event, not a keypress; grab the clipboard.
    if event.key == pygame.K_v and (
            event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
        paste = clipboard_text(_CHAT_MAX_INPUT - len(_chat_input))
        if paste:
            _chat_input += paste
        return True

    # Printable characters only. Without the isprintable() guard, control
    # codes and dead keys would land in the input box.
    if getattr(event, "unicode", "") and event.unicode.isprintable():
        if len(_chat_input) < _CHAT_MAX_INPUT:
            _chat_input += event.unicode
        return True

    return False


def relay_connect_to(address, nick=None, timeout_note=True):
    """Point the relay at an explicit address and start connecting.

    ``address`` is "host" or "host:port" (IPv4). This is the path a player
    takes when a friend hands them an address, so it must never raise on
    bad input -- it returns (ok, message) instead.

    Passing a host explicitly also disables LAN discovery for this
    connection: an address a friend gave us is a deliberate choice and
    must not be silently replaced by whatever beacon answers.
    """
    if not isinstance(address, str):
        return (False, "bad address")
    text = address.strip()
    if not text:
        return (False, "enter an address")
    # Accept "host:port" and bare "host" (default port).
    if ":" in text:
        host, _sep, port_text = text.rpartition(":")
        try:
            port = int(port_text)
        except ValueError:
            return (False, "port must be a number")
        if not (1 <= port <= 65535):
            return (False, "port out of range")
    else:
        host, port = text, _P_DEFAULT_PORT
    host = host.strip()
    if not host:
        return (False, "missing host")
    # Disallow whitespace and slashes: they cannot appear in a hostname or
    # IPv4 literal, so their presence means a paste accident.
    if any(c.isspace() or c in "/\\?#" for c in host):
        return (False, "address looks malformed")
    relay_start(nick=nick, host=host, port=port, discover=False)
    return (True, "%s:%d" % (host, port))


def relay_stop():
    """Shut the relay client down. Safe when it was never started."""
    global _relay_client, _relay_status, _relay_error
    if _relay_client is not None:
        _relay_client.stop()
        _relay_client = None
    _relay_status = "offline"
    _relay_error = ""
    _set_fixedstep(False)


def _set_fixedstep(on):
    """Turn the multiplayer fixed-timestep accumulator on or off.

    The host simulates the authoritative world, so its simulation rate must
    not depend on its hardware -- otherwise a host that renders slowly hands
    out measurably different fire rates and enemy reactions to every client.
    Advancing the sim in fixed 1/60 ticks removes that dependency.

    Single-player is deliberately untouched: this stays off unless a relay
    session is live, and is forced off on disconnect so a lobby can never
    leave the campaign running on the multiplayer timing path.
    """
    try:
        from core import fixedstep
        fixedstep.set_enabled(bool(on))
    except Exception:
        # A missing/broken fixedstep module must never take the lobby or the
        # game down; multiplayer just runs on legacy timing instead.
        pass


def relay_send_chat(text):
    """Send a chat line to the master. False if offline or rejected."""
    if _relay_client is None:
        return False
    return _relay_client.send_chat(text)


def relay_refresh():
    if _relay_client is None:
        return False
    _relay_client.refresh()
    return True


def _on_relay_chat(msg):
    """Inbound chat sink. Runs on the NETWORK thread, not the render thread.

    Appending to _chat_messages is atomic under the GIL and the list is
    only appended to here, so the renderer iterating it cannot see a
    half-written dict.
    """
    text = msg.get("text")
    user = msg.get("user")
    if not isinstance(text, str) or not isinstance(user, str):
        return
    color = msg.get("color")
    if not (isinstance(color, (list, tuple)) and len(color) == 3):
        color = (180, 180, 180)
    try:
        color = tuple(max(0, min(255, int(c))) for c in color)
    except (TypeError, ValueError):
        color = (180, 180, 180)
    _chat_messages.append({
        "user": user[:32],
        "text": text[:200],
        "color": color,
        "age": 0,
    })
    if len(_chat_messages) > 50:
        del _chat_messages[:-50]


def relay_status():
    """(status, error) for the UI to display."""
    return _relay_status, _relay_error


def relay_is_live():
    """True when the master answered and we are showing real rows."""
    return _relay_status == "online" and bool(_relay_client)


def _sync_relay_into_server_list():
    """Copy the relay snapshot into the module-level server_list.

    Done in place (slice assignment) so that `import ui.mp as _o; _o.server_list`
    observers see the update -- rebinding the name would leave those
    references pointing at the stale fictional list.
    """
    global _relay_status, _relay_error, _relay_rules
    if _relay_client is None:
        _relay_status = "offline"
        return

    status, error, servers, _nick = _relay_client.state()
    _was_live = _relay_status == "online"
    _relay_status = status
    _relay_error = error

    # Soft notes from the master ("sending too fast", "registering too often")
    # go into the chat panel as system lines. They are not faults and not
    # chat, but the chat panel is where a person looking at this screen would
    # look for an explanation of why their line did not appear.
    for note in _relay_client.take_notes():
        if not note:
            continue
        _chat_messages.append({
            "user": "SYSTEM", "text": note, "color": (240, 200, 110),
            "age": 0,
        })
        if len(_chat_messages) > 50:
            del _chat_messages[:-50]

    # Keep the fixed-timestep switch in step with the session. It goes on
    # only on the offline->online edge (so it is not re-set every frame) and
    # off as soon as we lose the session, which is what stops a lobby from
    # ever leaving the campaign running on multiplayer timing.
    if status == "online" and not _was_live:
        _set_fixedstep(True)
    elif status != "online" and _was_live:
        _set_fixedstep(False)

    if status != "online":
        # Do not clobber the last good list on a blip; the UI keeps showing
        # the fictional rows and the status line explains why.
        return

    if not servers:
        # Connected, but the master is genuinely empty -- show that rather
        # than silently falling back to the fiction.
        server_list[:] = []
        return

    server_list[:] = [(name, cur, mx, ping) for (name, cur, mx, ping, _r) in servers]
    _relay_rules = dict(
        (name, list(lines)) for (name, _c, _m, _p, lines) in servers if lines
    )

    # The fictional chat pool runs until the relay first comes online, so
    # its lines can be sitting in the panel. Drop exactly those the moment
    # we go live -- but ONLY those. The master backfills recent chat to
    # every joiner, and that backfill typically lands in the same breath as
    # the server list, so a blanket clear() would wipe real messages the
    # instant they arrived. Fiction entries are tagged "fict": True at
    # creation precisely so this can tell them apart.
    if not _was_live:
        _chat_messages[:] = [m for m in _chat_messages if not m.get("fict")]


def server_rules_for(name):
    """Rules for a server: relay-provided first, then the local fiction."""
    rules = _relay_rules.get(name)
    if rules:
        return rules
    return SERVER_RULES.get(name)


def trigger_server_refresh():

    global _refresh_active, _refresh_progress

    # With a live relay, ask the master for a fresh list instead of faking
    # one. The client re-queries and _sync_relay_into_server_list picks the
    # answer up on the next frame.

    if relay_refresh():

        audio.play("menu_click", volume=0.4)

        return

    if not _refresh_active:

        _refresh_active = True

        _refresh_progress = 0.0

        audio.play("menu_click", volume=0.4)

def get_kick_message_for_server(server_name):

    if server_name in KICK_MESSAGES_BY_SERVER:

        return _rng_legacy.choice(KICK_MESSAGES_BY_SERVER[server_name])

    return _rng_legacy.choice(KICK_MESSAGES)

_server_shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

_server_shade.fill((0, 0, 0, 115))

_server_panel = pygame.Surface((SERVER_PANEL_W, SERVER_PANEL_H), pygame.SRCALPHA)

_server_panel.fill((7, 10, 13, 236))

pygame.draw.rect(_server_panel, (38, 58, 70, 170), _server_panel.get_rect(), 1)

pygame.draw.rect(_server_panel, (255, 120, 0, 90), (0, 0, SERVER_PANEL_W, 3))

def _wrap_server_name(name, font, max_width, max_lines=2):

    """Wrap a server name into up to max_lines lines.

    Returns a list of rendered strings (1 or 2 elements)."""

    if font.size(name)[0] <= max_width:

        return [name]

    words = name.split(" ")

    if len(words) > 1:

        best_split = 1

        for i in range(1, len(words)):

            first = " ".join(words[:i])

            if font.size(first)[0] <= max_width:

                best_split = i

            else:

                break

        line1 = " ".join(words[:best_split])

        line2 = " ".join(words[best_split:])

        if font.size(line2)[0] > max_width:

            ellipsis = "..."

            while line2 and font.size(line2 + ellipsis)[0] > max_width:

                line2 = line2[:-1]

            line2 = line2 + ellipsis

        return [line1, line2]

    mid = len(name) // 2

    while mid > 1 and font.size(name[:mid])[0] > max_width:

        mid -= 1

    line1 = name[:mid]

    line2 = name[mid:]

    if font.size(line2)[0] > max_width:

        ellipsis = "..."

        while line2 and font.size(line2 + ellipsis)[0] > max_width:

            line2 = line2[:-1]

        line2 = line2 + ellipsis

    return [line1, line2]

def server_row_layouts(scroll_offset=None):

    """Row geometry for the server list - the single source of truth.

    Returns [(index, name_lines, row_h, y), ...] for the rows that
    actually fit between SERVER_LIST_TOP and SERVER_LIST_LIMIT.

    The clip is what stops the list from running into the footer
    again whatever the font metrics happen to be.  Both
    draw_server_browser() and the click handler in app.py consume
    this, so the hit boxes can never drift from what is drawn."""

    if scroll_offset is None:

        scroll_offset = _scroll_offset

    layouts = []

    cur_y = SERVER_LIST_TOP

    for vi in range(SERVER_VISIBLE_ROWS):

        i = vi + scroll_offset

        if i >= len(server_list):

            break

        name = server_list[i][0]

        name_lines = _wrap_server_name(name, font_terminal, SERVER_NAME_MAX_W)

        row_h = SERVER_ROW_H_DOUBLE if len(name_lines) > 1 else SERVER_ROW_H_SINGLE

        if cur_y + row_h > SERVER_LIST_LIMIT:

            break

        layouts.append((i, name_lines, row_h, cur_y))

        cur_y += row_h + SERVER_ROW_GAP

    return layouts

def server_region(idx):

    """Stable fake relay region for a server (shown in the tooltip)."""

    name = server_list[idx][0]

    return SERVER_REGIONS[(sum(ord(c) for c in name) + idx) % len(SERVER_REGIONS)]

def enter_arena_hit(mouse_pos):
    """True if the mouse is on the ARENA MATCH button on the browser.

    Lives here rather than in match_screen so the button sits with the rest
    of the browser chrome. The rect is computed rather than cached because
    the panel moves with the window and a stale rect is a button that
    silently does nothing. draw_server_browser() draws the button at these
    exact coordinates -- keep the two in step.
    """
    return enter_arena_rect().collidepoint(mouse_pos)


def enter_arena_rect():
    return pygame.Rect(SERVER_PANEL_X + SERVER_PANEL_W - 286, SERVER_PANEL_Y + 30, 258, 48)


def enter_arena_click(mouse_pos):
    return enter_arena_hit(mouse_pos)


_ARENA_FONT = None


def _arena_font():
    """Cached button font.

    Building a pygame Font every frame is a real cost, and this draws on
    the multiplayer screen where frame time is visible to the player.
    """
    global _ARENA_FONT
    if _ARENA_FONT is None:
        try:
            _ARENA_FONT = pygame.font.Font(None, 16)
        except Exception:
            _ARENA_FONT = pygame.font.Font(pygame.font.get_default_font(), 12)
    return _ARENA_FONT


def draw_server_browser(selected_idx, connecting, kicked_msg, connect_progress=0.0):

    # Operations shell; list/chat/relay presentation below retains its live data.
    _mp_style.background(screen)
    _mp_style.browser_shell(screen, pygame.Rect(SERVER_PANEL_X, SERVER_PANEL_Y,
                                               SERVER_PANEL_W, SERVER_PANEL_H))

    # Give the relay state its own line; keep address entry, connect and
    # refresh together on the row below so the browser header does not read as
    # one cramped run of title, status and controls.
    _bar_y = SERVER_CONNECT_Y
    _connect_btn_rect.w = 92
    _connect_btn_rect.h = 26
    _connect_btn_rect.x = refresh_btn_rect.x - 12 - _connect_btn_rect.w
    _connect_btn_rect.y = _bar_y
    _connect_rect.x = SERVER_PANEL_X + 28
    _connect_rect.w = _connect_btn_rect.x - 10 - _connect_rect.x
    _connect_rect.h = 26
    _connect_rect.y = _bar_y
    refresh_btn_rect.y = _bar_y

    # The subtitle doubles as the connection indicator. When a relay is
    # running it reports the real state (and the real error, e.g. "no master
    # on that host") instead of implying a live KRAPNET that isn't there.

    _rel_st, _rel_err = relay_status()

    # Cached once per frame: the chat panel below branches on it.

    _relay_live = (_rel_st == "online")

    if _rel_st == "online":

        _sub_text = f"KRAPNET  ·  {_relay_host}:{_relay_port}  ·  {len(server_list)} servers online"

        _sub_col = (95, 125, 145)

    elif _rel_st in ("connecting", "error"):

        _sub_text = f"KRAPNET  ·  {_rel_st.upper()}  ·  {_rel_err or 'no master'}"

        _sub_col = (220, 150, 60) if _rel_st == "connecting" else (220, 90, 75)

    else:

        _sub_text = f"KRAPNET regional lobbies  ·  {len(server_list)} servers online (offline)"

        _sub_col = (95, 125, 145)

    subtitle = font_terminal_small.render(_sub_text, True, _sub_col)

    # The status line has a full row to itself now; clip only to the panel's
    # inner width in case a long custom master address is configured.
    _sub_max_w = SERVER_PANEL_W - 62

    if subtitle.get_width() > _sub_max_w:

        while _sub_text and font_terminal_small.size(_sub_text)[0] > _sub_max_w - 12:

            _sub_text = _sub_text[:-1]

        subtitle = font_terminal_small.render(_sub_text + "...", True, _sub_col)

    screen.blit(subtitle, (SERVER_PANEL_X + 31, SERVER_SUBTITLE_Y))

    # ── Direct connect bar (join by address) ──
    # Rects are positioned earlier in this function; this block only draws.
    # A friend who self-hosts gives you an address. Putting the box in the
    # header keeps it reachable without scrolling and mirrors the REFRESH
    # button on the same row, so "find servers" and "join a known one"
    # read as the two ways in.
    _box_col = _mp_style.ACCENT if _connect_focused else (60, 90, 110)
    pygame.draw.rect(screen, (8, 14, 20), _connect_rect)
    pygame.draw.rect(screen, _box_col, _connect_rect, 1)
    _hint = "paste host:port" if not _connect_input else _connect_input
    _hint_col = (90, 110, 130) if not _connect_input else (200, 220, 230)
    _fit = _fit_text(_hint, font_terminal_small, _connect_rect.w - 16)
    _caret = "_" if (_connect_focused and (_now_ms() // 400) % 2) else " "
    screen.blit(
        font_terminal_small.render(_fit + _caret, True, _hint_col),
        (_connect_rect.x + 8, _connect_rect.y + 6),
    )

    _btn_hover = _connect_btn_rect.collidepoint(get_scaled_mouse())
    pygame.draw.rect(screen, (28, 38, 48) if _btn_hover else (12, 20, 28),
                     _connect_btn_rect)
    pygame.draw.rect(screen, _mp_style.ACCENT if _btn_hover else (70, 100, 120),
                     _connect_btn_rect, 1)
    _btn_lbl = font_terminal_small.render(_T("mp.connect"), True, _mp_style.ACCENT)
    screen.blit(_btn_lbl, (
        _connect_btn_rect.x + _connect_btn_rect.w // 2 - _btn_lbl.get_width() // 2,
        _connect_btn_rect.y + 7,
    ))

    # Status/error line under the box, fading out like chat does.
    if _connect_msg and _connect_msg_age < 240:
        _ma = max(0, min(255, (240 - _connect_msg_age) * 4))
        _mcol = (120, 200, 140) if _connect_msg.startswith("connecting") else (220, 120, 90)
        _msurf = font_terminal_small.render(_connect_msg, True, _mcol)
        _msurf.set_alpha(_ma)
        screen.blit(_msurf, (_connect_rect.x, _connect_rect.bottom + 4))

    # ── Tabs (SERVERS / CONNECTIONS) ──

    tab_y = SERVER_TAB_Y

    servers_tab_rect.x = SERVER_PANEL_X + 28

    servers_tab_rect.y = tab_y

    connections_tab_rect.x = SERVER_PANEL_X + 28 + servers_tab_rect.w + 4

    connections_tab_rect.y = tab_y

    for tab_name, tab_rect in [("SERVERS", servers_tab_rect), ("CONNECTIONS", connections_tab_rect)]:

        is_active = _mp_tab == tab_name

        hover = tab_rect.collidepoint(get_scaled_mouse())

        if is_active:

            pygame.draw.rect(screen, (28, 38, 48), tab_rect)

            pygame.draw.rect(screen, _mp_style.ACCENT, tab_rect, 1)

            pygame.draw.rect(screen, _mp_style.ACCENT, (tab_rect.x, tab_rect.bottom - 2, tab_rect.w, 2))

        else:

            pygame.draw.rect(screen, _mp_style.PLATE, tab_rect)

            pygame.draw.rect(screen, (50, 70, 85) if hover else _mp_style.EDGE, tab_rect, 1)

        label_text = tab_name

        if tab_name == "CONNECTIONS":

            online = sum(1 for c in CONNECTIONS if "Online" in c["status"])

            label_text = f"CONNECTIONS  ({online})"

        ts = font_terminal_small.render(label_text, True, C_WHITE if (is_active or hover) else _mp_style.DIM)

        screen.blit(ts, (tab_rect.centerx - ts.get_width() // 2, tab_rect.centery - ts.get_height() // 2))

    # ── OUTFITTER + wallet ──────────────────────────────────────────────
    # On the tab row's right edge, deliberately NOT a third tab: the two on the
    # left are views of the lobby, this opens a different screen, and a tab that
    # leaves the panel reads as a bug the first time it happens.

    outfitter_btn_rect.x = SERVER_PANEL_X + SERVER_PANEL_W - 28 - outfitter_btn_rect.w

    outfitter_btn_rect.y = SERVER_TAB_Y

    _out_hover = outfitter_btn_rect.collidepoint(get_scaled_mouse())

    pygame.draw.rect(screen, (16, 30, 22) if _out_hover else _mp_style.PLATE, outfitter_btn_rect)

    pygame.draw.rect(screen, (80, 220, 120) if _out_hover else (40, 70, 55), outfitter_btn_rect, 1)

    _olabel = font_terminal_small.render(_T("mp.outfitter"), True, C_WHITE if _out_hover else (150, 170, 160))

    screen.blit(_olabel, (outfitter_btn_rect.centerx - _olabel.get_width() // 2, outfitter_btn_rect.centery - _olabel.get_height() // 2))

    # The balance belongs on the screen where you decide to play, not only on
    # the one where you spend: it is the answer to "can I afford another round
    # of this". Zero is shown rather than hidden, so the first match has a
    # before-and-after.
    _balance = profile_store.balance()

    _bt = font_terminal_small.render("%s ACARIBUCKS" % "{:,}".format(_balance), True,
                                     _mp_style.ACCENT if _balance else (120, 95, 45))

    screen.blit(_bt, (outfitter_btn_rect.x - _bt.get_width() - 14,
                      outfitter_btn_rect.centery - _bt.get_height() // 2))

    # ── Refresh button ──

    refresh_hover = refresh_btn_rect.collidepoint(get_scaled_mouse())

    refresh_bg = (40, 50, 60, 220) if refresh_hover else (20, 30, 40, 200)

    btn_surf = pygame.Surface((refresh_btn_rect.w, refresh_btn_rect.h), pygame.SRCALPHA)

    btn_surf.fill(refresh_bg)

    pygame.draw.rect(btn_surf, _mp_style.ACCENT if refresh_hover else _mp_style.EDGE, btn_surf.get_rect(), 1)

    screen.blit(btn_surf, refresh_btn_rect)

    if _refresh_active:

        fw = int(refresh_btn_rect.w * _refresh_progress)

        pygame.draw.rect(screen, (255, 120, 0, 100), (refresh_btn_rect.x, refresh_btn_rect.y, fw, refresh_btn_rect.h))

        rt = font_terminal_small.render(_T("mp.scanning"), True, _mp_style.ACCENT)

    else:

        rt = font_terminal_small.render(_T("mp.refresh"), True, _mp_style.ACCENT if refresh_hover else (180, 180, 190))

    screen.blit(rt, (refresh_btn_rect.centerx - rt.get_width() // 2, refresh_btn_rect.centery - rt.get_height() // 2))

    mouse_pos = get_scaled_mouse()

    # ── Divider under header (drawn for both tabs - same header band) ──

    pygame.draw.line(

        screen, _mp_style.ACCENT,

        (SERVER_PANEL_X + 28, SERVER_DIVIDER_Y),

        (SERVER_PANEL_X + SERVER_PANEL_W - 28, SERVER_DIVIDER_Y), 1,

    )

    if _mp_tab == "SERVERS":

        # ── Column headers (above list) ──

        header_y = SERVER_LIST_TOP - 26

        status_x = SERVER_STATUS_X

        players_x = SERVER_PLAYERS_X

        ping_x = SERVER_PING_X

        headers = [

            ("SERVER", SERVER_ROW_X + 14),

            ("STATUS", status_x + 5),

            ("PLAYERS", players_x),

            ("PING", ping_x),

        ]

        for label, hx in headers:

            screen.blit(font_terminal_small.render(label, True, _mp_style.DIM), (hx, header_y))

        # ── Server list (left side) - rows can be 1 or 2 lines tall ──

        hovered_server_idx = -1

        list_top = SERVER_LIST_TOP

        ROW_GAP = SERVER_ROW_GAP

        name_max_width = SERVER_NAME_MAX_W

        row_layouts = server_row_layouts()

        visible_count = len(row_layouts)

        list_bottom = list_top + sum(rh + ROW_GAP for _, _, rh, _ in row_layouts)

        for i, name_lines, row_h, ry in row_layouts:

            name, cur, max_p, ping = server_list[i]

            row_rect = pygame.Rect(SERVER_ROW_X, ry, SERVER_ROW_W, row_h - 4)

            hover = row_rect.collidepoint(mouse_pos) and not _refresh_active and not connecting and not kicked_msg

            if hover:

                hovered_server_idx = i

            status, status_color = _server_status(cur, max_p, ping)

            row_surf = pygame.Surface((SERVER_ROW_W, row_h - 4), pygame.SRCALPHA)

            if i == selected_idx:

                row_surf.fill((28, 36, 42, 235))

                pygame.draw.rect(row_surf, _mp_style.ACCENT, row_surf.get_rect(), 1)

                pygame.draw.rect(row_surf, (255, 120, 0, 130), (0, 0, 4, row_h - 4))

            elif hover:

                row_surf.fill((18, 28, 34, 225))

                pygame.draw.rect(row_surf, (80, 120, 140), row_surf.get_rect(), 1)

            else:

                row_surf.fill((9, 14, 18, 210))

                pygame.draw.rect(row_surf, _mp_style.EDGE, row_surf.get_rect(), 1)

            if _refresh_active:

                fade = pygame.Surface((SERVER_ROW_W, row_h - 4), pygame.SRCALPHA)

                fade.fill((0, 0, 0, 140))

                row_surf.blit(fade, (0, 0))

            screen.blit(row_surf, row_rect)

            name_color = C_WHITE if (hover or i == selected_idx) and not _refresh_active else _mp_style.TEXT

            # Centre the name block on the row instead of pinning it to
            # the top, so 1-line and 2-line names share a baseline with
            # the badge/players/ping columns.

            name_top = ry + (row_h - 4 - len(name_lines) * SERVER_ROW_LEAD) // 2

            for li, line in enumerate(name_lines):

                line_surf = font_terminal.render(line, True, name_color)

                screen.blit(line_surf, (SERVER_ROW_X + 12, name_top + li * SERVER_ROW_LEAD))

            # The relay region used to sit on a third line under the name,
            # which is what forced the 64px row to overflow.  It now lives
            # in the hover tooltip (see server_region()).

            badge_y = ry + (row_h - 4 - 22) // 2

            value_y = ry + (row_h - 4 - 28) // 2

            _draw_server_badge(status, status_color, status_x, badge_y, SERVER_BADGE_W)

            pc = font_terminal.render(_T("mp.cur_02d_max_p_02d", cur=cur, max_p=max_p), True, _mp_style.ACCENT if cur >= max_p else C_TERMINAL)

            ping_c = (100, 200, 100) if ping < 60 else ((200, 200, 100) if ping < 150 else (200, 100, 100))

            ping_t = font_terminal.render(_T("mp.ping_ms", ping=ping), True, ping_c)

            screen.blit(pc, (players_x, value_y))

            screen.blit(ping_t, (ping_x, value_y))

            bar_x = ping_x

            bar_y = value_y + 30

            pygame.draw.rect(screen, (25, 28, 30), (bar_x, bar_y, 42, 4))

            fill_w = max(6, min(42, int(42 * (1 - min(ping, 240) / 240))))

            pygame.draw.rect(screen, ping_c, (bar_x, bar_y, fill_w, 4))

        if len(server_list) > visible_count:

            sb_x = SERVER_ROW_X + SERVER_ROW_W + 8

            sb_y = list_top

            sb_h = list_bottom - list_top - ROW_GAP

            sb_w = 5

            pygame.draw.rect(screen, (15, 22, 28), (sb_x, sb_y, sb_w, sb_h))

            pygame.draw.rect(screen, _mp_style.EDGE, (sb_x, sb_y, sb_w, sb_h), 1)

            thumb_ratio = visible_count / len(server_list)

            thumb_h = max(20, int(sb_h * thumb_ratio))

            max_scroll = max(1, len(server_list) - visible_count)

            thumb_y = sb_y + int((sb_h - thumb_h) * (_scroll_offset / max_scroll))

            pygame.draw.rect(screen, _mp_style.ACCENT, (sb_x, thumb_y, sb_w, thumb_h))

        # ── Scroll indicators (bottom of list, right-aligned to avoid BACK button) ──

        rendered_count = len(row_layouts)

        remaining_below = len(server_list) - (_scroll_offset + rendered_count)

        remaining_above = _scroll_offset

        if remaining_below > 0 or remaining_above > 0:

            if remaining_below > 0 and remaining_above > 0:

                hint_text = f"\u2191 {remaining_above} above  \u00b7  \u2193 {remaining_below} below  \u00b7  scroll wheel"

            elif remaining_below > 0:

                hint_text = f"\u2193 {remaining_below} more servers  \u00b7  scroll wheel"

            else:

                hint_text = f"\u2191 {remaining_above} above  \u00b7  scroll wheel"

            more_hint = font_terminal_small.render(hint_text, True, (90, 110, 130))

            screen.blit(

                more_hint,

                (

                    SERVER_ROW_X + SERVER_ROW_W - more_hint.get_width() - 4,

                    list_bottom + 4,

                ),

            )

        # ── Vertical Chat Panel (right side) ──

        chat_bg = pygame.Surface((CHAT_PANEL_W, CHAT_PANEL_H), pygame.SRCALPHA)

        chat_bg.fill((4, 8, 12, 215))

        pygame.draw.rect(chat_bg, _mp_style.EDGE, chat_bg.get_rect(), 1)

        pygame.draw.rect(chat_bg, (80, 130, 160, 90), (0, 0, CHAT_PANEL_W, 2))

        screen.blit(chat_bg, (CHAT_PANEL_X, CHAT_PANEL_Y))

        chat_lbl = font_terminal_small.render("COMMS / GLOBAL" if _relay_live else "COMMS / OFFLINE", True, _mp_style.DIM)

        screen.blit(chat_lbl, (CHAT_PANEL_X + 10, CHAT_PANEL_Y + 10))

        online_dot_pulse = (_now_ms() // 500) % 2

        dot_col = _mp_style.GREEN if _relay_live else _mp_style.DIM

        pygame.draw.circle(screen, dot_col, (CHAT_PANEL_X + CHAT_PANEL_W - 22, CHAT_PANEL_Y + 16), 3)

        online_lbl = font_terminal_small.render("LIVE" if _relay_live else "DEMO", True, _mp_style.GREEN if _relay_live else _mp_style.DIM)

        screen.blit(online_lbl, (CHAT_PANEL_X + CHAT_PANEL_W - 60, CHAT_PANEL_Y + 10))

        pygame.draw.line(

            screen, _mp_style.EDGE,

            (CHAT_PANEL_X + 8, CHAT_PANEL_Y + 30),

            (CHAT_PANEL_X + CHAT_PANEL_W - 8, CHAT_PANEL_Y + 30), 1,

        )

        msg_area_x = CHAT_PANEL_X + 10

        msg_area_y = CHAT_PANEL_Y + 42

        msg_area_w = CHAT_PANEL_W - 20

        msg_area_h = CHAT_PANEL_H - 70

        rendered_lines = []

        for msg in _chat_messages:

            alpha = min(255, msg["age"] * 13)

            user_text = f"[{msg['user']}]"

            body_text = msg["text"]

            user_surf = font_terminal_small.render(user_text, True, msg["color"])

            user_surf.set_alpha(alpha)

            rendered_lines.append([(user_surf, msg_area_x, alpha)])

            words = body_text.split(" ")

            line = ""

            for w in words:

                test = (line + " " + w).strip() if line else w

                if font_terminal_small.size(test)[0] <= msg_area_w - 12:

                    line = test

                else:

                    if line:

                        s = font_terminal_small.render(line, True, _mp_style.TEXT)

                        s.set_alpha(alpha)

                        rendered_lines.append([(s, msg_area_x + 12, alpha)])

                    line = w

            if line:

                s = font_terminal_small.render(line, True, _mp_style.TEXT)

                s.set_alpha(alpha)

                rendered_lines.append([(s, msg_area_x + 12, alpha)])

            rendered_lines.append([])

        line_h = 16

        max_lines = msg_area_h // line_h

        visible_lines = rendered_lines[-max_lines:]

        for li, line_entries in enumerate(visible_lines):

            ly = msg_area_y + li * line_h

            for surf, x, _ in line_entries:

                screen.blit(surf, (x, ly))

        typing_y = CHAT_PANEL_Y + CHAT_PANEL_H - 18

        pygame.draw.line(

            screen, _mp_style.EDGE,

            (CHAT_PANEL_X + 8, typing_y - 4),

            (CHAT_PANEL_X + CHAT_PANEL_W - 8, typing_y - 4), 1,

        )

        typing_dots = "." * ((_now_ms() // 400) % 4)

        typing_users = [

            "Volkov_Real", "admin", "noob123", "MaruWatches", "Sebi_PM",

            "VasileFan2007", "xX_KRAP_Xx", "Cigarette_Enjoyer", "MOD_Krapov",

            "OldFisherman", "ConspiracyGuy", "MAGRecruiter", "Cmdr_VodkaTime",

            "RushB_Acaristan", "EX_KRAP_OPERATOR", "CapsLock_Stuck",

        ]

        # Live relay: show the real input line instead of the fictional
        # "someone is typing" ticker. The fiction is only honest when no
        # master is connected.

        if _relay_live:

            _caret = "|" if (_now_ms() // 500) % 2 else " "

            _inp = _fit_text(_chat_input, font_terminal_small, CHAT_PANEL_W - 30)

            _inp_surf = font_terminal_small.render("> " + _inp + _caret, True, (170, 200, 210))

            screen.blit(_inp_surf, (CHAT_PANEL_X + 10, typing_y))

        else:

            typing_user = typing_users[(_now_ms() // 4000) % len(typing_users)]

            typing_lbl = font_terminal_small.render(

                _T("mp.typing_user_is_typing_typing_dot", typing_dots=typing_dots, typing_user=typing_user), True, _mp_style.DIM,

            )

            screen.blit(typing_lbl, (CHAT_PANEL_X + 10, typing_y))

        if hovered_server_idx >= 0 and not _refresh_active and not connecting and not kicked_msg:

            name = server_list[hovered_server_idx][0]

            rules = server_rules_for(name)

            if rules:

                tip_w = 360

                tip_lines = [f"REGION:  {server_region(hovered_server_idx)}"] + list(rules)

                tip_h = 22 + len(tip_lines) * 16 + 12

                tip_x = min(mouse_pos[0] + 16, WIDTH - tip_w - 10)

                tip_y = min(mouse_pos[1] + 16, HEIGHT - tip_h - 10)

                tip_surf = pygame.Surface((tip_w, tip_h), pygame.SRCALPHA)

                tip_surf.fill((6, 10, 14, 245))

                pygame.draw.rect(tip_surf, _mp_style.ACCENT, tip_surf.get_rect(), 1)

                pygame.draw.rect(tip_surf, (255, 120, 0, 100), (0, 0, tip_w, 3))

                screen.blit(tip_surf, (tip_x, tip_y))

                tlbl = font_terminal_small.render(_T("mp.server_info"), True, _mp_style.ACCENT)

                screen.blit(tlbl, (tip_x + 10, tip_y + 6))

                for li, line in enumerate(tip_lines):

                    col = (200, 200, 210) if not line.startswith(" ") else (140, 140, 150)

                    ls = font_terminal_small.render(line, True, col)

                    screen.blit(ls, (tip_x + 10, tip_y + 24 + li * 16))

    else:

        draw_connections_panel()

    # ── Footer band: divider, back button, hint ──

    pygame.draw.line(

        screen, _mp_style.EDGE,

        (SERVER_PANEL_X + 28, SERVER_FOOTER_TOP),

        (SERVER_PANEL_X + SERVER_PANEL_W - 28, SERVER_FOOTER_TOP), 1,

    )

    # ── ARENA MATCH entry point ──
    # Positioned from enter_arena_rect() so the drawn button and the hit
    # test can never drift apart -- a button that looks clickable and does
    # nothing is the worst possible bug for a UI.
    _arena_rect = enter_arena_rect()
    _arena_hover = _arena_rect.collidepoint(get_scaled_mouse())
    pygame.draw.rect(screen, (250, 189, 107) if _arena_hover else _mp_style.ACCENT,
                     _arena_rect)
    pygame.draw.rect(screen, _mp_style.ACCENT, _arena_rect, 1)
    screen.blit(
        _mp_style.browser_font(18, True).render(_T("mp.arena_host_join"), True,
                             _mp_style.BG if _arena_hover else _mp_style.BG),
        (_arena_rect.x + 12, _arena_rect.y + 16))

    server_back_btn.x = SERVER_PANEL_X + 28

    server_back_btn.y = SERVER_BACK_Y

    server_back_btn.width = 150

    server_back_btn.rect.x = server_back_btn.x

    server_back_btn.rect.y = server_back_btn.y

    server_back_btn.rect.width = server_back_btn.width

    server_back_btn.check_hover(get_scaled_mouse())

    pygame.draw.rect(screen, _mp_style.PLATE, server_back_btn.rect)
    pygame.draw.rect(screen, _mp_style.ACCENT if server_back_btn.rect.collidepoint(get_scaled_mouse()) else _mp_style.EDGE, server_back_btn.rect, 1)
    _back_text = _mp_style.browser_font(13, True).render(_T("mp.back_main_menu"), True, _mp_style.TEXT)
    screen.blit(_back_text, _back_text.get_rect(center=server_back_btn.rect.center))

    hint = font_terminal_small.render(_T("mp.esc_menu_arena_match_private_roo"), True, _mp_style.DIM)

    screen.blit(hint, (SERVER_PANEL_X + SERVER_PANEL_W - hint.get_width() - 28, SERVER_BACK_Y + 10))

    # ── Connecting popup ──

    if connecting:

        popup = pygame.Surface((460, 220), pygame.SRCALPHA)

        popup.fill((8, 11, 16, 248))

        popup_rect = popup.get_rect(center=(WIDTH // 2, HEIGHT // 2))

        pygame.draw.rect(popup, _mp_style.ACCENT, popup.get_rect(), 1)

        pygame.draw.rect(popup, (255, 120, 0, 120), (0, 0, 460, 3))

        screen.blit(popup, popup_rect)

        progress = max(0.0, min(1.0, float(connect_progress or 0.0)))

        dots = "." * ((_now_ms() // 300) % 4)

        t = font_speaker.render(_T("mp.connecting_dots", dots=dots), True, _mp_style.ACCENT)

        screen.blit(t, (popup_rect.x + 28, popup_rect.y + 18))

        pct = font_terminal_small.render(_T("mp.progress_pct", pct="{:02d}".format(int(progress * 100))), True, (120, 160, 175))

        screen.blit(pct, (popup_rect.right - pct.get_width() - 30, popup_rect.y + 28))

        log_lines = [

            (0.00, "Resolving krapnet.acaristan.gov..."),

            (0.16, "Handshake established"),

            (0.32, "Verifying loyalty token..."),

            (0.50, "Bypassing IPA firewall..."),

            (0.68, "Downloading server modpack (4.7 GB)..."),

            (0.88, "Almost there..."),

        ]

        ly = popup_rect.y + 60

        for threshold, line in log_lines:

            active = progress >= threshold

            col = (140, 200, 140) if active else (55, 75, 75)

            prefix = ">" if active else "·"

            ls = font_terminal_small.render(_T("mp.prefix_line", line=line, prefix=prefix), True, col)

            screen.blit(ls, (popup_rect.x + 30, ly))

            ly += 18

        pygame.draw.rect(screen, (24, 28, 32), (popup_rect.x + 30, popup_rect.y + 180, 400, 10))

        fill_w = int(400 * progress)

        pygame.draw.rect(screen, _mp_style.ACCENT, (popup_rect.x + 30, popup_rect.y + 180, fill_w, 10))

        # Small moving scan highlight inside the filled portion; does not affect progress.

        if fill_w > 12:

            scan_x = popup_rect.x + 30 + int((_now_ms() * 0.12) % max(1, fill_w))

            pygame.draw.rect(screen, (255, 190, 80), (scan_x, popup_rect.y + 180, min(18, fill_w), 10))

        pygame.draw.rect(screen, (80, 70, 55), (popup_rect.x + 30, popup_rect.y + 180, 400, 10), 1)

    elif kicked_msg:

        popup_w, popup_h = 460, 220

        popup = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)

        popup.fill((15, 10, 10, 245))

        popup_rect = popup.get_rect(center=(WIDTH // 2, HEIGHT // 2))

        pygame.draw.rect(popup, (200, 50, 50), popup.get_rect(), 1)

        pygame.draw.rect(popup, (220, 60, 60, 120), (0, 0, popup_w, 3))

        screen.blit(popup, popup_rect)

        t = font_speaker.render(_T("mp.kicked"), True, (220, 60, 60))

        screen.blit(t, (popup_rect.x + 28, popup_rect.y + 18))

        pygame.draw.line(

            screen, (90, 30, 30),

            (popup_rect.x + 20, popup_rect.y + 52),

            (popup_rect.right - 20, popup_rect.y + 52), 1,

        )

        reason_lbl = font_terminal_small.render(_T("mp.reason"), True, (140, 90, 90))

        screen.blit(reason_lbl, (popup_rect.x + 28, popup_rect.y + 64))

        words = kicked_msg.split(" ")

        wrap_w = popup_w - 60

        lines = []

        line = ""

        for w in words:

            test = (line + " " + w).strip() if line else w

            if font_terminal.size(test)[0] <= wrap_w:

                line = test

            else:

                if line:

                    lines.append(line)

                line = w

        if line:

            lines.append(line)

        for j, ln in enumerate(lines):

            lt = font_terminal.render(ln, True, (220, 200, 200))

            screen.blit(lt, (popup_rect.x + 30, popup_rect.y + 88 + j * 24))

        kick_dismiss_btn_rect.x = popup_rect.centerx - kick_dismiss_btn_rect.w // 2

        kick_dismiss_btn_rect.y = popup_rect.bottom - 46

        btn_hover = kick_dismiss_btn_rect.collidepoint(mouse_pos)

        bg_col = (60, 25, 25) if btn_hover else (40, 18, 18)

        outline_col = (220, 80, 80) if btn_hover else (140, 50, 50)

        pygame.draw.rect(screen, bg_col, kick_dismiss_btn_rect, border_radius=3)

        pygame.draw.rect(screen, outline_col, kick_dismiss_btn_rect, 1, border_radius=3)

        ok = font_btn.render(_T("mp.dismiss"), True, C_WHITE if btn_hover else (200, 180, 180))

        screen.blit(

            ok,

            (

                kick_dismiss_btn_rect.centerx - ok.get_width() // 2,

                kick_dismiss_btn_rect.centery - ok.get_height() // 2,

            ),

        )

        hint2 = font_terminal_small.render(_T("mp.esc_also_dismisses"), True, (110, 70, 70))

        screen.blit(

            hint2,

            (

                popup_rect.centerx - hint2.get_width() // 2,

                kick_dismiss_btn_rect.bottom + 4,

            ),

        )
