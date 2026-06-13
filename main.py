# ─────────────────────────────────────────
#  ShowMe — main.py
#  Entry point. Wires everything together.
#
#  Architecture (fixed):
#    - QApplication lives on the main thread (required by Qt)
#    - pystray runs in a daemon thread (it only needs win32 message pump)
#    - All Qt work from background threads is posted via _ui_queue
#      and drained every 50 ms by a QTimer on the main thread
#
#  On startup:
#    1. Sets up logging
#    2. Scans / loads installed apps
#    3. Starts listener thread
#    4. Creates QApplication + ui dispatch queue
#    5. Starts tray thread
#    6. qt_app.exec() runs on main thread (blocks until quit)
#
#  On quit (from tray):
#    7. Stops listener thread cleanly
#    8. qt_app.quit() signals main thread to exit exec()
#    9. sys.exit(0)
# ─────────────────────────────────────────
import ctypes
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("thattimelessman.showme.1.0")
import sys
import os
os.environ["VOSK_LOG_LEVEL"] = "-1"
import logging
import threading
import queue

# ── make sure project root is on path ────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from config import (
    MODEL_DIR, APP_CACHE_FILE, LOG_FILE,
    SAMPLE_RATE, CHUNK_SIZE, DEBUG_MODE
)


# ─────────────────────────────────────────
#  Logging setup
# ─────────────────────────────────────────
def _setup_logging():
    level = logging.DEBUG if DEBUG_MODE else logging.INFO
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
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
        log.warning(f"Autostart failed: {e}")


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
    log.info(f"Loaded {len(app_dict)} apps.")

    # ── 2. Start listener thread ─────────
    from core import listener
    listener_thread = threading.Thread(
        target=listener.start,
        args=(app_dict, MODEL_DIR, SAMPLE_RATE, CHUNK_SIZE),
        daemon=True,
        name="ShowMe-Listener"
    )
    listener_thread.start()

    # ── 3. Add to autostart (first run) ──
    _add_to_autostart()

    # ── 4. Create QApplication on main thread ──
    # Qt mandates that QApplication exists on the main thread.
    # All subsequent Qt widgets/timers created by _show_window and
    # _show (overlay) will also run here via the drain queue.
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    # ── 5. UI dispatch queue ─────────────
    # Background threads (tray callbacks, listener) post callables here.
    # The drain timer executes them on the main thread every 50 ms.
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

    # ── 6. Tray callbacks ────────────────
    _is_paused = [False]

    def on_quit():
        log.info("Quit requested.")
        listener.stop()
        _ui_queue.put(qt_app.quit)   # tells exec() on the main thread to return

    def on_settings():
        from frontend.settings_window import open_settings
        listener.status_queue.put_nowait("Stopped" if _is_paused[0] else "Listening")
        open_settings(app_dict, on_rescan, listener.status_queue)

    def on_rescan():
        nonlocal app_dict
        log.info("Rescanning apps...")
        from apps.scanner import build_cache
        app_dict = build_cache(APP_CACHE_FILE)
        log.info(f"Rescan complete: {len(app_dict)} apps.")

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

    # ── 7. Run tray in background thread ──
    # pystray only needs a win32 message pump — it works fine off-main-thread.
    from frontend.tray import ShowMeTray
    tray = ShowMeTray(
        on_quit=on_quit,
        on_settings=on_settings,
        on_rescan=on_rescan,
        on_pause_resume=on_pause_resume
    )
    tray_thread = threading.Thread(target=tray.run, daemon=True, name="ShowMe-Tray")
    tray_thread.start()

    # ── 8. Qt event loop on main thread ──
    # Blocks here until qt_app.quit() is called (from on_quit above).
    qt_app.exec()
    sys.exit(0)


if __name__ == "__main__":
    main()