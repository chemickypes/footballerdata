"""
footballerdata web package.
Importing `web.*` puts the repo root on sys.path so that `core.*` and the
sibling modules resolve both when imported as a package (Vercel/gunicorn)
and when web/app.py is run as a script.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
