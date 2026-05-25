# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — frontend/tray.py  v3
#  Uses Agraj's custom 3D mic icons
# ─────────────────────────────────────────

import os
import logging
from PIL import Image

log = logging.getLogger("showme.tray")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
ICON_GREEN = os.path.join(ASSETS_DIR, "icon_green.png")
ICON_RED   = os.path.join(ASSETS_DIR, "icon_red.png")


def _load_icon(listening: bool) -> Image.Image:
    path = ICON_GREEN if listening else ICON_RED
    try:
        return Image.open(path).convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
    except Exception:
        # fallback — plain colored circle if icons missing
        from PIL import ImageDraw
        img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (86, 156, 18, 255) if listening else (146, 0, 0, 255)
        draw.ellipse([2, 2, 126, 126], fill=color)
        return img


class ShowMeTray:
    def __init__(self, on_quit, on_settings, on_rescan, on_pause_resume):
        self.on_quit         = on_quit
        self.on_settings     = on_settings
        self.on_rescan       = on_rescan
        self.on_pause_resume = on_pause_resume
        self._paused         = False
        self._icon           = None

    def _build_menu(self):
        import pystray
        pause_label = "Resume" if self._paused else "Pause"
        return pystray.Menu(
            pystray.MenuItem("ShowMe  v1.0",  None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_label,     self._toggle_pause),
            pystray.MenuItem("Rescan Apps",   self._rescan),
            pystray.MenuItem("Settings",      self._settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",          self._quit),
        )

    def _toggle_pause(self, icon, item):
        self._paused = not self._paused
        self.on_pause_resume(self._paused)
        if self._icon:
            self._icon.icon = _load_icon(not self._paused)
        icon.menu = self._build_menu()
        log.info("ShowMe %s", "paused" if self._paused else "resumed")

    def _rescan(self, _icon, _item):
        self.on_rescan()

    def _settings(self, _icon, _item):
        self.on_settings()

    def _quit(self, icon, _item):
        icon.stop()
        self.on_quit()

    def run(self):
        import pystray
        self._icon = pystray.Icon(
            name="ShowMe",
            icon=_load_icon(True),
            title="ShowMe — say 'show me [app]'",
            menu=self._build_menu()
        )
        self._icon.run()