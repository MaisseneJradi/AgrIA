"""Spraying conditions in the next hours for a governorate, from the Open-Meteo forecast (phyto plan, step 6).

  spray_conditions("Nabeul") -> {"pluie_mm": 3.2, "pluie_proba": 80, "vent_max_kmh": 22.0, "pluie": True, "vent": True,
                                 "heure": "2026-11-23T14:00", "source": "Open-Meteo"}
  spray_conditions("Nabeul") -> None   when the API cannot be reached (no warning then: the answer is still given)

Rain warning: at least RAIN_MM of rain in the next 24 hours, or an hourly probability of at least RAIN_PROB %.
Wind warning: wind above WIND_KMH km/h at 10 m in the next 12 hours (drift towards neighbours, hives and water).
Point: the chief town of the governorate (context/gouvernorats.csv). One request per governorate and per hour
(in-memory cache, a failure is kept 5 minutes), TIMEOUT seconds at most. AGRIA_METEO=0 turns it off (tests,
evaluation: the answer must not depend on the day it is computed).
"""
import json
import os
import time
import urllib.parse
import urllib.request

from common import governorate as gov_name
from common import query

RAIN_MM, RAIN_PROB, WIND_KMH = 1.0, 60, 15.0
RAIN_HOURS, WIND_HOURS = 24, 12
TIMEOUT, TTL, TTL_FAIL = 3, 3600, 300
_CACHE = {}


def enabled():
    return os.environ.get("AGRIA_METEO", "1") != "0"


def _fetch(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {"latitude": lat, "longitude": lon, "hourly": "precipitation,precipitation_probability,wind_speed_10m",
         "wind_speed_unit": "kmh", "forecast_days": 2, "timezone": "Africa/Tunis"})
    req = urllib.request.Request(url, headers={"User-Agent": "AgrIA/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def conditions(forecast, now):
    """Open-Meteo hourly answer + the current local hour ("2026-11-23T14:00") -> the spraying conditions."""
    h = forecast["hourly"]
    start = next((i for i, t in enumerate(h["time"]) if t >= now), None)
    if start is None:
        return None
    rain = [x or 0 for x in h["precipitation"][start:start + RAIN_HOURS]]
    proba = [x or 0 for x in (h.get("precipitation_probability") or [])[start:start + RAIN_HOURS]]
    wind = [x or 0 for x in h["wind_speed_10m"][start:start + WIND_HOURS]]
    if not rain or not wind:
        return None
    out = {"pluie_mm": round(sum(rain), 1), "pluie_proba": max(proba) if proba else None,
           "vent_max_kmh": round(max(wind), 1), "heure": h["time"][start], "source": "Open-Meteo"}
    out["pluie"] = out["pluie_mm"] >= RAIN_MM or (out["pluie_proba"] or 0) >= RAIN_PROB
    out["vent"] = out["vent_max_kmh"] > WIND_KMH
    return out


def spray_conditions(governorate, fetch=_fetch, now=None):
    if not enabled() or not governorate:
        return None
    try:
        gov = gov_name(governorate)
    except ValueError:
        return None
    hit = _CACHE.get(gov)
    if hit and time.time() - hit[0] < (TTL if hit[1] else TTL_FAIL):
        return hit[1]
    try:
        row = query("SELECT lat, lon FROM gouvernorats WHERE gouvernorat = ?", (gov,))[0]
        now = now or time.strftime("%Y-%m-%dT%H:00")
        out = conditions(fetch(row["lat"], row["lon"]), now)
    except Exception:  # no network, timeout, unexpected answer: no warning, the answer is still given
        out = None
    _CACHE[gov] = (time.time(), out)
    return out
