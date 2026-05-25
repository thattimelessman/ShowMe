# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — core/executor.py
#  Receives a matched (name, path) and launches it.
#  Handles .exe paths, .lnk shortcuts, and
#  special built-in commands.
# ─────────────────────────────────────────

import os
import subprocess
import logging

log = logging.getLogger("showme.executor")

# ── Built-in special commands ─────────────
# These bypass app matching entirely
BUILTIN_COMMANDS = {
    "weather"       : "builtin:weather",
    "my day"        : "builtin:day",
    "my schedule"   : "builtin:day",
    "desktop"       : "builtin:desktop",
    "task manager"  : "taskmgr.exe",
    "settings"      : "ms-settings:",
    "camera"        : "microsoft.windows.camera:",
    "calculator"    : "calc.exe",
    "notepad"       : "notepad.exe",
    "paint"         : "mspaint.exe",
}


def _launch_path(path: str) -> bool:
    """
    Launch a file path — works for .exe and .lnk.
    Returns True on success, False on failure.
    """
    try:
        if path.endswith(".lnk") or not path.endswith(".exe"):
            os.startfile(path)
        else:
            subprocess.Popen(
                [path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        return True
    except Exception as e:
        log.error(f"Failed to launch '{path}': {e}")
        return False


def _handle_builtin(command: str) -> bool:
    """Handle special built-in ShowMe commands."""
    if command == "builtin:weather":
        from commands.show_weather import show_weather
        show_weather()
        return True

    if command == "builtin:day":
        log.info("My day command — calendar feature coming soon")
        return True

    if command == "builtin:desktop":
        import ctypes
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
        return True

    return False


def execute(name: str, path: str) -> bool:
    """
    Main execution entry point.
    name = matched app name (for logging)
    path = exe path, lnk path, URI, or builtin: prefix

    Returns True if launched successfully.
    """
    log.info(f"Executing: '{name}' → {path}")
    try:
        from frontend.settings_window import record_command
        record_command(name)
    except Exception:
        pass

    # handle builtin commands
    if path.startswith("builtin:"):
        return _handle_builtin(path)

    # handle ms-settings: and other URI schemes
    if ":" in path and not os.path.isabs(path):
        try:
            if path.startswith("shell:"):
                subprocess.Popen(["explorer.exe", path])
            else:
                os.startfile(path)
            return True
        except Exception as e:
            log.error(f"URI launch failed: {e}")
            return False

    return _launch_path(path)


def execute_query(query: str, app_dict: dict) -> bool:
    """
    Convenience: check builtins first, then fuzzy match, then execute.
    Used by listener so it only needs one import.
    """
    from apps.matcher import find_app

    q = query.lower().strip()

    # check builtins first (exact)
    if q in BUILTIN_COMMANDS:
        path = BUILTIN_COMMANDS[q]
        return execute(q, path)

    # fuzzy match installed apps
    result = find_app(query, app_dict)
    if result is None:
        log.warning(f"No app matched for: '{query}'")
        return False

    name, path = result
    return execute(name, path)