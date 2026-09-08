"""
footballerdata — web app configuration
Paths, environment (.env), pricing defaults, bot persona, injuries cache.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # web/ — templates/ and static/ live here
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # repo root — used for data/config/env paths

DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_finale.csv")
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(PROJECT_ROOT, "dataset_finale.csv")
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(PROJECT_ROOT, "examples", "dataset_sample.csv")

# ──────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ──────────────────────────────────────────────────────────────────────
APP_ENV = os.environ.get("APP_ENV", "community").strip().lower()

# Load Transfermarkt injuries cache for Clinical Audit Window
INJURIES_CACHE = {}
_inj_path = os.path.join(PROJECT_ROOT, "data", "tm_injuries_cache.json")
if not os.path.exists(_inj_path):
    _inj_path = os.path.join(PROJECT_ROOT, "tm_injuries_cache.json")
if os.path.exists(_inj_path):
    try:
        with open(_inj_path, "r", encoding="utf-8") as f:
            INJURIES_CACHE = json.load(f)
    except Exception:
        pass

# Load local .env if present
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_PATH):
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# FIXED PRICING DEFAULTS
# Used only to calibrate VORP baselines / fair-price quality scores.
# ──────────────────────────────────────────────────────────────────────

DEFAULT_BUDGET = 1000
DEFAULT_ROSTER_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}
DEFAULT_N_TEAMS = 10

_personal_config_path = os.path.join(PROJECT_ROOT, "core", "config.personal.py")
IS_PERSONAL = (APP_ENV == "personal")

# ──────────────────────────────────────────────────────────────────────
# BOT IDENTITY & PERSONA
# ──────────────────────────────────────────────────────────────────────
BOT_NAME = "Il Maestro"
BOT_SUBTITLE = "Assistente Tattico Quantitativo"
BOT_AVATAR_TEXT = "AI"
BOT_BADGE = "PRO DECISION"
BOT_GREETING = (
    "Ciao! Sono l'assistente quantitativo de **La FantaOfficina**. Chiedimi confronti (es. *Malen vs Lautaro*), "
    "analisi di reparto o raccomandazioni basate su VORP e proiezioni ML."
)
BOT_AVATAR_IMAGE = ""

if IS_PERSONAL and os.path.exists(_personal_config_path):
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("config_personal", _personal_config_path)
        _personal = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_personal)
        BOT_NAME = getattr(_personal, "BOT_NAME", BOT_NAME)
        BOT_SUBTITLE = getattr(_personal, "BOT_SUBTITLE", BOT_SUBTITLE)
        BOT_AVATAR_TEXT = getattr(_personal, "BOT_AVATAR_TEXT", BOT_AVATAR_TEXT)
        BOT_BADGE = getattr(_personal, "BOT_BADGE", BOT_BADGE)
        BOT_GREETING = getattr(_personal, "BOT_GREETING", BOT_GREETING)
    except Exception:
        pass

if IS_PERSONAL:
    _local_avatar_path = os.path.join(BASE_DIR, "static", "personal_avatar.jpg")
    if os.path.exists(_local_avatar_path):
        try:
            import base64
            with open(_local_avatar_path, "rb") as f:
                BOT_AVATAR_IMAGE = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass

BOT_NAME = os.environ.get("BOT_NAME", BOT_NAME)
BOT_SUBTITLE = os.environ.get("BOT_SUBTITLE", BOT_SUBTITLE)
BOT_AVATAR_TEXT = os.environ.get("BOT_AVATAR_TEXT", BOT_AVATAR_TEXT)
BOT_BADGE = os.environ.get("BOT_BADGE", BOT_BADGE)
BOT_GREETING = os.environ.get("BOT_GREETING", BOT_GREETING)
BOT_AVATAR_IMAGE = os.environ.get("BOT_AVATAR_URL", BOT_AVATAR_IMAGE)
