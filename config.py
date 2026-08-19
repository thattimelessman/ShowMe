# pylint: disable=all
# ─────────────────────────────────────────
#  ShowMe — config.py
#  Central config. Edit these to tune behaviour.
# ─────────────────────────────────────────

import os

# ── Paths ────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model", "vosk-model-small-en-us-0.15")  # Vosk model folder
APP_CACHE_FILE  = os.path.join(BASE_DIR, "apps", "app_cache.json")
LOG_FILE        = os.path.join(BASE_DIR, "showme.log")
ICON_FILE       = os.path.join(BASE_DIR, "assets", "icon.png")

# ── Audio ────────────────────────────────
SAMPLE_RATE     = 16000   # Vosk needs 16kHz
CHUNK_SIZE = 4000   # was 4000/8000 — halves CPU wake-ups
CHANNELS        = 1       # mono

# ── Trigger ──────────────────────────────
TRIGGER_PHRASE  = "show me"   # what activates ShowMe

# ── Matching ─────────────────────────────
MATCH_THRESHOLD = 60    # 0-100 — lower = more lenient, higher = stricter
MAX_RESULTS     = 1       # how many fuzzy matches to consider

# ── Weather (optional) ───────────────────
WEATHER_API_KEY = ""                   # OpenWeatherMap free key
WEATHER_CITY    = "Lucknow"           # your city
WEATHER_UNITS   = "metric"            # metric = Celsius

# ── App behaviour ────────────────────────
AUTOSTART_NAME  = "ShowMe"            # name in Windows registry autostart
DEBUG_MODE      = False               # prints every transcript if True

# ── Custom overrides ─────────────────────
# we can add manual mappings here if fuzzy match ever gets it wrong
# "alias" : "full exe path or app name in cache"




CUSTOM_MAPPINGS = {
    # VS Code
    "vs code"                       : "visual studio code",
    "vscode"                        : "visual studio code",
    "vsc"                           : "visual studio code",
    "visual studio"                 : "visual studio code",
    "visual studio on"              : "visual studio code",
    "visual studio board"           : "visual studio code",
    "be a seat"                     : "visual studio code",
    "be a c"                        : "visual studio code",
    "be a see"                      : "visual studio code",
    "be i see"                      : "visual studio code",
    "bsc"                           : "visual studio code",
    "really see"                    : "visual studio code",

    # VLC
    "vlc"                           : "vlc media player",
    "be l c"                        : "vlc media player",
    "v l c"                         : "vlc media player",
    "blc"                           : "vlc media player",
    "blc media player"              : "vlc media player",
    "bmc"                           : "vlc media player",
    "bnc"                           : "vlc media player",
    "via see"                       : "vlc media player",
    "we'll see"                     : "vlc media player",

    # WhatsApp
    "whatsapp"                      : "whatsapp",
    "what sub"                      : "whatsapp",
    "what sad"                      : "whatsapp",
    "bought sad"                    : "whatsapp",
    "board sad"                     : "whatsapp",
    "what's"                        : "whatsapp",

    # Xbox
    "xbox"                          : "xboxpcappce",
    "x box"                         : "xboxpcappce",
    "exports"                       : "xboxpcappce",
    "its box"                       : "xboxpcappce",
    "it's box"                      : "xboxpcappce",

    # Explorer
    "explorer"                      : "file explorer",
    "windows explorer"              : "file explorer",
    "files"                         : "file explorer",
    "exploded"                      : "file explorer",
    "miss builders"                 : "file explorer",
    "a bloated"                     : "file explorer",
    "explode of"                    : "file explorer",
    "a lot of"                      : "file explorer",
    "your of"                       : "file explorer",
    "when those exploded"           : "file explorer",

    # Edge
    "edge"                          : "microsoft edge",

    # Chrome
    "chrome"                        : "google chrome",

    # Word — "board" and "what bad" removed, they go to wordpad now
    "word"                          : "word",
    "microsoft word"                : "word",

    # Wordpad — takes all the mishearings
    "wordpad"                       : "wordpad",
    "word pad"                      : "wordpad",
    "what bad"                      : "wordpad",
    "board bad"                     : "wordpad",
    "void bad"                      : "wordpad",
    "board"                         : "wordpad",

    # Excel
    "excel"                         : "excel",
    "microsoft excel"               : "excel",
    "xl"                            : "excel",
    "accent"                        : "excel",
    "x l"                           : "excel",

    # PowerPoint
    "powerpoint"                    : "powerpoint",
    "microsoft powerpoint"          : "powerpoint",
    "valid point"                   : "powerpoint",

    # Outlook
    "outlook"                       : "olk",
    "microsoft outlook"             : "olk",

    # OneNote
    "onenote"                       : "onenote",
    "one note"                      : "onenote",
    "microsoft onenote"             : "onenote",
    "what not"                      : "onenote",
    "but not"                       : "onenote",
    "one more"                      : "onenote",

    # Terminal
    "terminal"                      : "wt",
    "windows terminal"              : "wt",
    "command line"                  : "wt",

    # Paint
    "paint"                         : "mspaint",
    "microsoft paint"               : "mspaint",

    # Sticky Notes
    "sticky notes"                  : "sticky notes (new)",
    "sticky"                        : "sticky notes (new)",

    # OneDrive
    "onedrive"                      : "onedrive",
    "one drive"                     : "onedrive",

    # Apple Music
    "apple music"                   : "applemusic",
    "in music"                      : "applemusic",
    "and music"                     : "applemusic",
    "an music"                      : "applemusic",
    "in michigan"                   : "applemusic",

    # Teams
    "teams"                         : "ms-teams",
    "microsoft teams"               : "ms-teams",

    # Smart Connect
    "smart connect"                 : "smart connect",

    # Snipping Tool
    "snipping tool"                 : "snippingtool",
    "snipping to"                   : "snippingtool",
    "screenshot"                    : "snippingtool",

    # HWMonitor
    "hw monitor"                    : "hwmonitor",
    "hardware monitor"              : "hwmonitor",
    "edged of the monitor"          : "hwmonitor",

    # Need for Speed
    "nfs"                           : "need for speed - most wanted",
    "need for speed"                : "need for speed - most wanted",

    # Forza Horizon 4
    "forza"                         : "forza horizon 4",
    "forza horizon"                 : "forza horizon 4",
    "forza horizon 4"               : "forza horizon 4",
    "for some reason for"           : "forza horizon 4",
    "for no reason for"             : "forza horizon 4",
    "for doubt as important"        : "forza horizon 4",
    "for job i them for"            : "forza horizon 4",
    "for our i spotted"             : "forza horizon 4",
    "for some reason for them"      : "forza horizon 4",
    "for jeopardizing reason for"   : "forza horizon 4",
    "for south will rise and fall"  : "forza horizon 4",
    "for love rise and fall"        : "forza horizon 4",
    "for eyes and for"              : "forza horizon 4",

    # qBittorrent
    "bit torrent"                   : "qbittorrent",
    "bittorrent"                    : "qbittorrent",
    "torrent"                       : "qbittorrent",

    # Store
    "store"                         : "store",
    "microsoft store"               : "store",

    # Windows Security
    "windows security"              : "windowsdefender:",
    "defender"                      : "windowsdefender:",
    "security"                      : "windowsdefender:",
    "because security"              : "windowsdefender:",
    "been to a security"            : "windowsdefender:",
    "when those security"           : "windowsdefender:",
    "with those security"           : "windowsdefender:",
    "been no security"              : "windowsdefender:",
    "no security"                   : "windowsdefender:",
}