"""Where the app's own files live on disk.

One module so that nothing else has to guess at relative paths, and so the
PyInstaller spec has a single place to check when it decides what to bundle.
"""

from __future__ import annotations

from pathlib import Path

GUI_DIR = Path(__file__).parent

WEB_DIR = GUI_DIR / "web"
INDEX_HTML = WEB_DIR / "index.html"

ICONS_DIR = GUI_DIR / "resources" / "icons"
APP_ICON_PATH = ICONS_DIR / "app_icon.png"
