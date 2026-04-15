#!/usr/bin/env python3
"""Sandbox weather CLI harness (pilot backend)."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

LOCATIONS = {
    "staten": {"label": "Staten Island, New York", "lat": 40.5795, "lon": -74.1502},
    "englishtown": {"label": "Englishtown, New Jersey", "lat": 40.2968, "lon": -74.3582},
    "ohio": {"label": "Bellefontaine, Ohio", "lat": 40.3612, "lon": -83.7599},
}

CODE_MAP = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers",
    81: "Heavy showers", 82: "Violent showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Severe thunderstorm + hail",
}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "weather-harness/0.1"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _forecast(lat: float, lon: float) -> dict:
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
    return _get_json(url)


def _condition(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return CODE_MAP.get(int(code), f"Code {code}")


def _warnings(data: dict) -> list[str]:
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
    if any((p or 0) >= 70 and (r or 0) >= 0.5 for p, r in zip(pops, prec)):
        out.append("Heavy rain/storm risk.")
    return out


def build_payload(location: str) -> dict:
    loc = LOCATIONS[location]
    data = _forecast(loc["lat"], loc["lon"])
    cur = data.get("current", {})
    daily = data.get("daily", {})
    warnings = _warnings(data)

    return {
        "location": loc["label"],
        "key": location,
        "current": {
            "condition": _condition(cur.get("weather_code")),
            "temp_f": round(cur.get("temperature_2m", 0)),
            "humidity_pct": round(cur.get("relative_humidity_2m", 0)),
            "wind_mph": round(cur.get("wind_speed_10m", 0)),
        },
        "today": {
            "high_f": round((daily.get("temperature_2m_max") or [0])[0]),
            "low_f": round((daily.get("temperature_2m_min") or [0])[0]),
        },
        "warnings": warnings,
    }


def format_daily_brief(location: str) -> str:
    payload = build_payload(location)
    warns = "None" if not payload["warnings"] else " ".join(payload["warnings"])
    return "\n".join([
        f"🧪 **Weather Pilot (CLI backend)** — {payload['location']}",
        f"Current: {payload['current']['condition']}, {payload['current']['temp_f']}°F, humidity {payload['current']['humidity_pct']}%, wind {payload['current']['wind_mph']} mph",
        f"Today: high {payload['today']['high_f']}°F / low {payload['today']['low_f']}°F",
        f"Warnings: {warns}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(prog="weather-harness", description="Sandbox weather CLI harness")
    parser.add_argument("action", choices=["current", "daily", "alerts"], help="Action to run")
    parser.add_argument("--location", choices=sorted(LOCATIONS.keys()), default="staten")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    payload = build_payload(args.location)

    if args.action == "alerts":
        out = {
            "location": payload["location"],
            "warnings": payload["warnings"],
        }
    elif args.action == "current":
        out = {
            "location": payload["location"],
            "current": payload["current"],
        }
    else:
        out = payload

    if args.as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.action == "alerts":
        warns = "None" if not out["warnings"] else " ".join(out["warnings"])
        print(f"⚠️ Alerts — {out['location']}: {warns}")
        return 0

    if args.action == "current":
        c = out["current"]
        print(f"🌤️ {out['location']}: {c['condition']}, {c['temp_f']}°F, humidity {c['humidity_pct']}%, wind {c['wind_mph']} mph")
        return 0

    print(format_daily_brief(args.location))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
