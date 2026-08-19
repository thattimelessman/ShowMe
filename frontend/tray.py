# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — frontend/tray.py  v6
#
#  Changes vs v5:
#   [1] Left-click / touchpad tap now opens the context menu
#       (default=True item now calls icon._show_menu() instead of None)
#   All other behaviour identical to v5.
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
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
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

    # [1] Called by left-click — shows the same menu as right-click
    def _open_menu(self, icon, item):
        try:
            icon._show_menu()
        except Exception:
            pass

    def _build_menu(self):
        import pystray
        pause_label = "Resume" if self._paused else "Pause"
        return pystray.Menu(
            pystray.MenuItem(
                "ShowMe  v1.0",
                self._open_menu,   # [1] was: None
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
        self._paused = not self._paused
        if self._icon:
            self._icon.icon = _load_icon(not self._paused)
        self._icon.menu = self._build_menu()
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

        _set_dpi_aware()

        self._icon = pystray.Icon(
            name  = "ShowMe",
            icon  = _load_icon(True),
            title = "ShowMe — say 'show me [app]'",
            menu  = self._build_menu(),
        )
        self._icon.run()