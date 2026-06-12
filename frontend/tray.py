# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — frontend/tray.py  v4
#
#  Fixes vs v3:
#   [1] Icon correctly goes RED on pause, GREEN on resume
#       (v3 had inverted logic — self._paused already flipped
#        before _load_icon was called, so result was always wrong)
#   [2] DPI awareness declared before tray creation so the
#       right-click menu isn't blurry on 125 %/150 % displays
#   [3] "ShowMe v1.0" title renders bold+black (default=True)
#       instead of greyed-out disabled text
# ─────────────────────────────────────────

import os
import ctypes
import logging
from PIL import Image

log = logging.getLogger("showme.tray")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
ICON_GREEN = os.path.join(ASSETS_DIR, "icon_green.png")
ICON_RED   = os.path.join(ASSETS_DIR, "icon_red.png")


def _set_dpi_aware():
    """
    Declare DPI awareness so Win32 renders the pystray context
    menu at native resolution instead of bitmap-scaling it up.
    Must be called before the Icon object is created.
    Idempotent — safe to call more than once.
    """
    try:
        # Per-monitor v2 (Windows 10 1703+) — sharpest result
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # System DPI fallback (Windows Vista+)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _load_icon(listening: bool) -> Image.Image:
    """
    listening=True  → green icon  (mic active)
    listening=False → red icon    (paused)
    """
    path = ICON_GREEN if listening else ICON_RED
    try:
        return Image.open(path).convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
    except Exception:
        from PIL import ImageDraw
        img  = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
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
            # default=True  → Windows renders this bold + black
            # enabled=False → not clickable
            # Together: visible title, not a button, not greyed out
            pystray.MenuItem(
                "ShowMe  v1.0",
                None,
                enabled=False,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_label,   self._toggle_pause),
            pystray.MenuItem("Rescan Apps", self._rescan),
            pystray.MenuItem("Settings",    self._settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",        self._quit),
        )

    def _toggle_pause(self, icon, item):
        # Flip state first
        self._paused = not self._paused

        # NOW update icon: paused=True → listening=False → RED
        #                  paused=False → listening=True → GREEN
        if self._icon:
            self._icon.icon = _load_icon(not self._paused)

        # Swap Pause ↔ Resume label
        self._icon.menu = self._build_menu()

        # Notify main.py
        self.on_pause_resume(self._paused)
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
            name  = "ShowMe",
            icon  = _load_icon(True),   # green on startup
            title = "ShowMe — say 'show me [app]'",
            menu  = self._build_menu(),
        )
        self._icon.run()