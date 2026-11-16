# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — core/executor.py
#
#  Changes:
#   [1] "show me last" — re-launches the last opened app
#   [2] Volume commands — up / down / mute via Win32 key events
#   [3] Track _last_launched after every successful execute()
# ─────────────────────────────────────────

import os
import subprocess
import logging

log = logging.getLogger("showme.executor")

# [1] Track last launched app so "show me last" can replay it
_last_launched = {"name": None, "path": None}


# ── Built-in special commands ─────────────
# These bypass app matching entirely.
BUILTIN_COMMANDS = {
    # Existing
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

    # [1] Replay last launched app
    "last"          : "builtin:last",

    # [2] Volume controls
    "volume up"     : "builtin:volume_up",
    "volume down"   : "builtin:volume_down",
    "volume mute"   : "builtin:volume_mute",
    "mute"          : "builtin:volume_mute",
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
        log.error("Failed to launch '%s': %s", path, e)
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

    # [1] Re-launch last opened app
    if command == "builtin:last":
        if _last_launched["path"]:
            log.info("Replaying last: '%s'", _last_launched["name"])
            return _launch_path(_last_launched["path"])
        log.warning("No app launched yet — 'show me last' has nothing to replay")
        return False

    # [2] Volume controls via Win32 virtual key events
    if command == "builtin:volume_up":
        import ctypes
        ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)   # VK_VOLUME_UP press
        ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)   # VK_VOLUME_UP release
        log.info("Volume up")
        return True

    if command == "builtin:volume_down":
        import ctypes
        ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)   # VK_VOLUME_DOWN press
        ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)   # VK_VOLUME_DOWN release
        log.info("Volume down")
        return True

    if command == "builtin:volume_mute":
        import ctypes
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)   # VK_VOLUME_MUTE press
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)   # VK_VOLUME_MUTE release
        log.info("Volume mute toggled")
        return True

    return False


def execute(name: str, path: str) -> bool:
    """
    Main execution entry point.
    name = matched app name (for logging)
    path = exe path, lnk path, URI, or builtin: prefix
    Returns True if launched successfully.
    """
    log.info("Executing: '%s' → %s", name, path)
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
            # [3] Track last launched
            _last_launched["name"] = name
            _last_launched["path"] = path
            return True
        except Exception as e:
            log.error("URI launch failed: %s", e)
            return False

    ok = _launch_path(path)
    if ok:
        # [3] Track last launched
        _last_launched["name"] = name
        _last_launched["path"] = path
    return ok


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
        log.warning("No app matched for: '%s'", query)
        return False

    name, path = result
    return execute(name, path)