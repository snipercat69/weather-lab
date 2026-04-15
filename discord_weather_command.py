#!/usr/bin/env python3
"""Discord weather command helper for location triggers and daily summaries."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

try:
    from weather_harness import format_daily_brief as pilot_daily_brief
except Exception:
    pilot_daily_brief = None

LOCATIONS = {
    "staten": {
        "label": "Staten Island, New York",
        "lat": 40.5795,
        "lon": -74.1502,
    },
    "englishtown": {
        "label": "Englishtown, New Jersey",
        "lat": 40.2968,
        "lon": -74.3582,
    },
    "ohio": {
        "label": "Bellefontaine, Ohio",
        "lat": 40.3612,
        "lon": -83.7599,
    },
}

CODE_MAP = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm + hail",
    99: "Severe thunderstorm + hail",
}


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "weather-lab/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def forecast(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "America/New_York",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
        "forecast_days": 7,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    return get_json(url)


def condition(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return CODE_MAP.get(int(code), f"Code {code}")


def warning_lines(data: dict) -> list[str]:
    d = data.get("daily", {})
    highs = d.get("temperature_2m_max", []) or []
    lows = d.get("temperature_2m_min", []) or []
    winds = d.get("wind_speed_10m_max", []) or []
    pops = d.get("precipitation_probability_max", []) or []
    prec = d.get("precipitation_sum", []) or []

    out: list[str] = []
    if highs and max(highs) >= 95:
        out.append("Heat wave risk (95°F+).")
    if lows and min(lows) <= 20:
        out.append("Extreme cold risk (20°F or lower).")
    if winds and max(winds) >= 35:
        out.append("High wind risk (35 mph+).")
    heavy_rain = any((p or 0) >= 70 and (r or 0) >= 0.5 for p, r in zip(pops, prec))
    if heavy_rain:
        out.append("Heavy rain/storm risk.")
    return out


def seven_day_summary(data: dict) -> str:
    d = data.get("daily", {})
    dates = d.get("time", []) or []
    highs = d.get("temperature_2m_max", []) or []
    lows = d.get("temperature_2m_min", []) or []
    codes = d.get("weather_code", []) or []

    parts: list[str] = []
    for i in range(min(7, len(dates))):
        day = dates[i][5:] if len(dates[i]) >= 10 else dates[i]
        parts.append(f"{day}: {condition(codes[i] if i < len(codes) else None)}, {round(highs[i])}°/{round(lows[i])}°")
    return " | ".join(parts)


def brief_for_location(key: str) -> str:
    loc = LOCATIONS[key]
    data = forecast(loc["lat"], loc["lon"])
    cur = data.get("current", {})
    d = data.get("daily", {})

    current_line = (
        f"Current: {condition(cur.get('weather_code'))}, {round(cur.get('temperature_2m', 0))}°F, "
        f"humidity {round(cur.get('relative_humidity_2m', 0))}%, wind {round(cur.get('wind_speed_10m', 0))} mph"
    )
    today_line = f"Today: high {round((d.get('temperature_2m_max') or [0])[0])}°F / low {round((d.get('temperature_2m_min') or [0])[0])}°F"
    week_line = f"7-day: {seven_day_summary(data)}"
    warns = warning_lines(data)
    warn_line = "Warnings: " + ("None" if not warns else " ".join(warns))

    return "\n".join([f"🌤️ **{loc['label']}**", current_line, today_line, week_line, warn_line])


def full_daily_report() -> str:
    a = brief_for_location("staten")
    return "\n\n".join(["📅 **Daily Weather Brief (7:00 AM ET)**", a])


def help_text() -> str:
    return (
        "Weather triggers:\n"
        "- `!staten`\n"
        "- `!englishtown`\n"
        "- `!ohio`\n"
        "- `!weather daily` (Staten Island only)\n"
        "- `!weather pilot [staten|englishtown|ohio]` (sandbox CLI backend demo)"
    )


def handle(msg: str) -> str:
    raw = msg.strip().lower()
    if raw in {"!staten", "!statenisland", "!staten-island"}:
        return brief_for_location("staten")
    if raw == "!englishtown":
        return brief_for_location("englishtown")
    if raw == "!ohio":
        return brief_for_location("ohio")
    if raw in {"!weather daily", "!weather", "!weather full"}:
        return full_daily_report()
    if raw.startswith("!weather pilot"):
        if pilot_daily_brief is None:
            return "Pilot backend unavailable right now."
        parts = raw.split()
        location = "staten"
        if len(parts) >= 3 and parts[2] in LOCATIONS:
            location = parts[2]
        return pilot_daily_brief(location)
    return help_text()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: discord_weather_command.py '!englishtown'")
        return 2
    msg = " ".join(sys.argv[1:])
    try:
        print(handle(msg))
        return 0
    except Exception as e:
        print(f"Weather command error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
