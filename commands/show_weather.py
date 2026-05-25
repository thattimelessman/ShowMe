# ─────────────────────────────────────────
#  ShowMe — commands/show_weather.py
#  Fetches weather and shows a brief overlay.
#  Requires WEATHER_API_KEY in config.py
# ─────────────────────────────────────────

import logging
import requests

log = logging.getLogger("showme.cmd.weather")


def show_weather():
    """Fetch current weather and display it."""
    from config import WEATHER_API_KEY, WEATHER_CITY, WEATHER_UNITS

    if not WEATHER_API_KEY:
        log.warning("No weather API key set in config.py")
        return

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units={WEATHER_UNITS}"
        )
        resp = requests.get(url, timeout=5)
        data = resp.json()

        temp    = data["main"]["temp"]
        feels   = data["main"]["feels_like"]
        desc    = data["weather"][0]["description"].capitalize()
        city    = data["name"]

        summary = f"{city}: {desc}, {temp}°C (feels like {feels}°C)"
        log.info(f"Weather: {summary}")

        # show in overlay
        from frontend.overlay import show_overlay
        show_overlay(summary, duration=5)

    except Exception as e:
        log.error(f"Weather fetch failed: {e}")
