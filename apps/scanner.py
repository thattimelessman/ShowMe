# ─────────────────────────────────────────
#  ShowMe — apps/scanner.py
#  Scans Windows Registry + Start Menu to build
#  a complete dictionary of installed apps.
#  Runs once on startup, saves to app_cache.json.
# ─────────────────────────────────────────

import os
import json
import logging
import glob

log = logging.getLogger("showme.scanner")

# ── where Windows keeps installed app paths ──
REGISTRY_PATHS = []
START_MENU_DIRS = []

# Only import winreg on Windows
try:
    import winreg
    REGISTRY_PATHS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    START_MENU_DIRS = [
        os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""),     r"Microsoft\Windows\Start Menu\Programs"),
    ]
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False
    log.warning("winreg not available — running outside Windows. Scanner will return empty cache.")


def _scan_registry() -> dict:
    """Read HKLM + HKCU App Paths registry keys."""
    apps = {}
    if not WINREG_AVAILABLE:
        return apps

    for hive, path in REGISTRY_PATHS:
        try:
            with winreg.OpenKey(hive, path) as root:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root, i)
                        i += 1
                        with winreg.OpenKey(root, subkey_name) as subkey:
                            try:
                                exe_path, _ = winreg.QueryValueEx(subkey, "")
                                if exe_path and os.path.isfile(exe_path):
                                    # strip .exe, lowercase for matching
                                    clean = subkey_name.lower().replace(".exe", "").strip()
                                    apps[clean] = exe_path
                            except FileNotFoundError:
                                pass
                    except OSError:
                        break
        except Exception as e:
            log.debug(f"Registry scan error on {path}: {e}")

    log.info(f"Registry scan: {len(apps)} apps found")
    return apps


def _scan_start_menu() -> dict:
    """Walk Start Menu folders and collect .lnk shortcuts."""
    apps = {}

    for base_dir in START_MENU_DIRS:
        if not os.path.isdir(base_dir):
            continue
        # grab every .lnk recursively
        pattern = os.path.join(base_dir, "**", "*.lnk")
        for lnk_path in glob.glob(pattern, recursive=True):
            name = os.path.splitext(os.path.basename(lnk_path))[0].lower().strip()
            if name:
                apps[name] = lnk_path   # store .lnk path; executor uses os.startfile

    log.info(f"Start Menu scan: {len(apps)} shortcuts found")
    return apps


def _merge(reg: dict, start: dict) -> dict:
    """
    Merge registry and start menu results.
    Registry paths take priority (more reliable).
    """
    merged = {}
    merged.update(start)   # start menu first (lower priority)
    merged.update(reg)     # registry overwrites where both exist
    return merged


def build_cache(cache_file: str) -> dict:
    """
    Full scan → merge → save to JSON.
    Returns the final app dict.
    """
    log.info("Building app cache...")

    reg_apps   = _scan_registry()
    start_apps = _scan_start_menu()
    all_apps   = _merge(reg_apps, start_apps)

    # ensure directory exists
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(all_apps, f, indent=2)

    log.info(f"App cache saved: {len(all_apps)} total apps → {cache_file}")
    return all_apps


def load_cache(cache_file: str) -> dict:
    """Load existing cache from JSON. Returns empty dict if missing."""
    if not os.path.isfile(cache_file):
        return {}
    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_apps(cache_file: str, force_rescan: bool = False) -> dict:
    """
    Main entry point.
    Loads from cache if it exists, otherwise scans fresh.
    Pass force_rescan=True to always rebuild.
    """
    if force_rescan or not os.path.isfile(cache_file):
        apps = build_cache(cache_file)
        apps.update(HARDCODED_APPS)
        return apps
    apps = load_cache(cache_file)
    log.info(f"Loaded {len(apps)} apps from cache")
    apps.update(HARDCODED_APPS)
    return apps


HARDCODED_APPS = {
    # Explorer
    "file explorer"         : "explorer.exe",
    "explorer"              : "explorer.exe",

    # WhatsApp
    "whatsapp"              : "whatsapp:",

    # Clock
    "clock"                 : "ms-clock:",
    "windows clock"         : "ms-clock:",
    "alarm"                 : "ms-clock:",

    # Photos
    "photos"                : "ms-photos:",
    "microsoft photos"      : "ms-photos:",

    # To Do
    "to do"                 : "ms-todo:",
    "microsoft to do"       : "ms-todo:",

    # Family
    "family"                : "ms-family:",

    # Windows Security — URI
    "windowsdefender:"      : "windowsdefender:",
    "windows security"      : "windowsdefender:",
    "defender"              : "windowsdefender:",
    "security"              : "windowsdefender:",

    # Windows Tools
    "windows tools"         : "control admintools",

    # Whiteboard — direct exe
    "whiteboard"            : r"C:\Program Files\WindowsApps\Microsoft.Whiteboard_53.20111.128.0_x64__8wekyb3d8bbwe\MicrosoftWhiteboard\MicrosoftWhiteboard.exe",
    "microsoft whiteboard"  : r"C:\Program Files\WindowsApps\Microsoft.Whiteboard_53.20111.128.0_x64__8wekyb3d8bbwe\MicrosoftWhiteboard\MicrosoftWhiteboard.exe",

    # Dolby — direct exe
    "dolby"                 : r"C:\Program Files\WindowsApps\DolbyLaboratories.DolbyAccess_3.27.9430.0_x64__rz1tebttyb220\DolbyAccess.exe",
    "dolby access"          : r"C:\Program Files\WindowsApps\DolbyLaboratories.DolbyAccess_3.27.9430.0_x64__rz1tebttyb220\DolbyAccess.exe",

   # Sound Recorder
   "sound recorder"        : "shell:appsFolder\\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App",
   "voice recorder"        : "shell:appsFolder\\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App",

   # Journal
   "journal"               : "shell:appsFolder\\Microsoft.MicrosoftJournal_8wekyb3d8bbwe!App",
   "microsoft journal"     : "shell:appsFolder\\Microsoft.MicrosoftJournal_8wekyb3d8bbwe!App",
   "smart note"            : "shell:appsFolder\\Microsoft.MicrosoftJournal_8wekyb3d8bbwe!App",

   # Quick Share
   "quick share"           : "shell:appsFolder\\MicrosoftWindows.Client.CBS_cw5n1h2txyewy!QuickShare",

    # Quick Assist
    "quick assist"          : r"C:\Program Files\WindowsApps\MicrosoftCorporationII.QuickAssist_2.0.29.0_x64__8wekyb3d8bbwe\QuickAssist.exe",

    # Forza Horizon 4
    "forza horizon 4"       : r"D:\Games\Forza Horizon 4\ForzaHorizon4.exe",

    # Settings
    "settings"              : "ms-settings:",

    # Calculator
    "calculator"            : "calc.exe",
    "calc"                  : "calc.exe",

    # Camera
    "camera"                : "microsoft.windows.camera:",

    # Notepad
    "notepad"               : "notepad.exe",

    # Task Manager
    "task manager"          : "taskmgr.exe",
}