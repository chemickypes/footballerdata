#!/usr/bin/env python3
"""
footballerdata — Player Data & Statistics Explorer (Serie A)
Web UI: player list (listone) with filters/sort, Player Detail Drawer, AI copilot Q&A.
Derived from an upstream fantacalcio analytics framework; the fantasy auction/league/team engine has been removed.

Thin entrypoint: Flask app assembly + blueprint registration.
Logic lives in: config.py, data.py, pricing.py, players_api.py, ai_api.py.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # web/ — templates/ and static/ live here
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # repo root — used for data/config/env paths
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template

from web.ai_api import ai_bp
from web.config import (
    BOT_NAME, BOT_SUBTITLE, BOT_AVATAR_TEXT, BOT_AVATAR_IMAGE, BOT_BADGE,
    BOT_GREETING, IS_PERSONAL,
)
from web.players_api import players_bp

app = Flask(__name__)


@app.after_request
def add_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template(
        "index.html",
        bot_name=BOT_NAME,
        bot_subtitle=BOT_SUBTITLE,
        bot_avatar_text=BOT_AVATAR_TEXT,
        bot_avatar_image=BOT_AVATAR_IMAGE,
        bot_badge=BOT_BADGE,
        bot_greeting=BOT_GREETING,
        is_personal=IS_PERSONAL
    )


app.register_blueprint(players_bp)
app.register_blueprint(ai_bp)


def main():
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    print("\n" + "=" * 70)
    print("  footballerdata — Player Data & Statistics Explorer (Serie A)")
    print("=" * 70)
    print(f"\n  Accesso Desktop: http://localhost:5050")
    print(f"  Accesso Mobile:  http://{local_ip}:5050 (stessa rete Wi-Fi)\n")

    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
