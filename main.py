# ─────────────────────────────────────────
#  ShowMe — main.py
#  Entry point. Wires everything together.
#
#  Architecture:
#    - QApplication lives on the main thread (required by Qt)
#    - pystray runs in a daemon thread (it only needs win32 message pump)
#    - All Qt work from background threads is posted via _ui_queue
#      and drained every 50 ms by a QTimer on the main thread
#
#  On startup:
#    1. Sets up logging (rotating, max 1MB × 3 files)
#    2. Scans / loads installed apps
#    3. Starts silent background rescan (8s delay, auto-refreshes cache)
#    4. Starts listener thread
#    5. Creates QApplication + ui dispatch queue
#    6. Starts tray thread
#    7. qt_app.exec() runs on main thread (blocks until quit)
#
#  On quit (from tray):
#    8. Stops listener thread cleanly
#    9. qt_app.quit() signals main thread to exit exec()
#   10. sys.exit(0)
# ─────────────────────────────────────────
import ctypes
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("thattimelessman.showme.1.0")
import sys
import os
os.environ["VOSK_LOG_LEVEL"] = "-1"
import logging
import threading
import queue
from logging.handlers import RotatingFileHandler

# ── make sure project root is on path ────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from config import (
    MODEL_DIR, APP_CACHE_FILE, LOG_FILE,
    SAMPLE_RATE, CHUNK_SIZE, DEBUG_MODE
)


# ─────────────────────────────────────────
#  Logging setup — rotating file handler
#  Max 1 MB per file, keeps last 3 files.
#  showme.log never grows unbounded again.
# ─────────────────────────────────────────
def _setup_logging():
    level = logging.DEBUG if DEBUG_MODE else logging.INFO
    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,   # 1 MB
            backupCount=3,
            encoding="utf-8"
        ),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s  [%(name)s]  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


# ─────────────────────────────────────────
#  Autostart helpers (Windows only)
# ─────────────────────────────────────────
def _add_to_autostart():
    log = logging.getLogger("showme")
    try:
        import winreg
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        script  = os.path.join(BASE_DIR, "showme.pyw")
        value   = f'"{pythonw}" "{script}"'
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ShowMe", 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        log.info("Autostart set.")
    except Exception as e:
        log.warning("Autostart failed: %s", e)


# ─────────────────────────────────────────
#  Background rescan
#  Waits 8s after startup then silently
#  rebuilds app cache in-place so the
#  listener picks up newly installed apps
#  without needing a manual Rescan.
# ─────────────────────────────────────────
def _silent_rescan(app_dict: dict):
    import time
    time.sleep(8)
    log = logging.getLogger("showme.rescan")
    log.info("Background rescan starting...")
    try:
        from apps.scanner import build_cache, HARDCODED_APPS
        new_apps = build_cache(APP_CACHE_FILE)
        new_apps.update(HARDCODED_APPS)
        app_dict.clear()
        app_dict.update(new_apps)
        log.info("Background rescan done: %d apps", len(app_dict))
    except Exception as e:
        log.warning("Background rescan failed: %s", e)


# ─────────────────────────────────────────
#  Main
# ─────────────────────────────────────────
def main():
    _setup_logging()
    log = logging.getLogger("showme")
    log.info("ShowMe starting...")

    # ── 1. Load app cache ────────────────
    from apps.scanner import get_apps
    app_dict = get_apps(APP_CACHE_FILE)
    log.info("Loaded %d apps.", len(app_dict))

    # ── 2. Background rescan (auto-refresh) ──
    threading.Thread(
        target=_silent_rescan,
        args=(app_dict,),
        daemon=True,
        name="ShowMe-AutoRescan"
    ).start()

    # ── 3. Start listener thread ─────────
    from core import listener
    listener_thread = threading.Thread(
        target=listener.start,
        args=(app_dict, MODEL_DIR, SAMPLE_RATE, CHUNK_SIZE),
        daemon=True,
        name="ShowMe-Listener"
    )
    listener_thread.start()

    # ── 4. Add to autostart (first run) ──
    _add_to_autostart()

    # ── 5. Create QApplication on main thread ──
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    # ── 6. UI dispatch queue ─────────────
    _ui_queue = queue.Queue()

    from frontend import overlay as _overlay_mod
    from frontend import settings_window as _settings_mod
    _overlay_mod.init(_ui_queue)
    _settings_mod.init(_ui_queue)

    def _drain_ui_queue():
        try:
            while True:
                fn = _ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass

    drain_timer = QTimer()
    drain_timer.timeout.connect(_drain_ui_queue)
    drain_timer.start(50)

    # ── 7. Tray callbacks ────────────────
    _is_paused = [False]

    def on_quit():
        log.info("Quit requested.")
        listener.stop()
        _ui_queue.put(qt_app.quit)

    def on_settings():
        from frontend.settings_window import open_settings
        listener.status_queue.put_nowait("Stopped" if _is_paused[0] else "Listening")
        open_settings(app_dict, on_rescan, listener.status_queue)

    def on_rescan():
        nonlocal app_dict
        log.info("Manual rescan...")
        from apps.scanner import build_cache, HARDCODED_APPS
        new_apps = build_cache(APP_CACHE_FILE)
        new_apps.update(HARDCODED_APPS)
        app_dict.clear()
        app_dict.update(new_apps)
        log.info("Rescan complete: %d apps.", len(app_dict))

    def on_pause_resume(paused: bool):
        _is_paused[0] = paused
        if paused:
            listener.stop()
        else:
            t = threading.Thread(
                target=listener.start,
                args=(app_dict, MODEL_DIR, SAMPLE_RATE, CHUNK_SIZE),
                daemon=True,
                name="ShowMe-Listener"
            )
            listener._running.set()
            t.start()

    # ── 8. Run tray in background thread ──
    from frontend.tray import ShowMeTray
    tray = ShowMeTray(
        on_quit=on_quit,
        on_settings=on_settings,
        on_rescan=on_rescan,
        on_pause_resume=on_pause_resume
    )
    tray_thread = threading.Thread(target=tray.run, daemon=True, name="ShowMe-Tray")
    tray_thread.start()

    # ── 9. Qt event loop on main thread ──
    qt_app.exec()
    sys.exit(0)


if __name__ == "__main__":
    main()