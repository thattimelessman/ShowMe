# ─────────────────────────────────────────
#  ShowMe — main.py
#  Entry point. Wires everything together.
#
#  On startup:
#    1. Sets up logging
#    2. Scans / loads installed apps
#    3. Starts listener thread
#    4. Starts system tray (blocking)
#
#  On quit (from tray):
#    5. Stops listener thread cleanly
#    6. Exits
# ─────────────────────────────────────────
import ctypes
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("thattimelessman.showme.1.0")
import sys
import os
os.environ["VOSK_LOG_LEVEL"] = "-1" # silence Vosk logs (set to "0" to enable)
import logging
import threading

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
    #i added this line 54 log= logging.getLogger("showme") 
    log = logging.getLogger("showme")
    try:
        import winreg
        # find pythonw.exe — runs without terminal
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

    # ── 4. Tray callbacks ────────────────
    _is_paused = [False]   # mutable flag — shared across closures

    def on_quit():
        log.info("Quit requested.")
        listener.stop()
        sys.exit(0)

    def on_settings():
        from frontend.settings_window import open_settings
        # Prime the queue with current state so the settings window
        # opens showing the correct icon immediately, even if already paused.
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
            # for restarting listener thread 
            t = threading.Thread(
                target=listener.start,
                args=(app_dict, MODEL_DIR, SAMPLE_RATE, CHUNK_SIZE),
                daemon=True,
                name="ShowMe-Listener"
            )
            listener._running.set()
            t.start()

    # ── 5. Run tray (blocks until quit) ──
    from frontend.tray import ShowMeTray
    tray = ShowMeTray(
        on_quit=on_quit,
        on_settings=on_settings,
        on_rescan=on_rescan,
        on_pause_resume=on_pause_resume
    )
    tray.run()


if __name__ == "__main__":
    main()