"""Irrigation need of a crop in a governorate and a month (FAO-56 method), and optionally the 7-day forecast.

  get_water_need("Kairouan", "olivier", 7)
  -> {"gouvernorat": "Kairouan", "crop": "olive", "mois": 7, "en_saison": True, "et0_mm": ..., "kc": ...,
      "besoin_mm": ETc = ET0 x Kc, "pluie_mm": ..., "deficit_mm": ETc - pluie, "deficit_m3_ha": ...,
      "deficit_mm_jour": ..., "source": ...}

Climate: monthly means 2015-2024 (Open-Meteo archive, context/climat_mensuel.csv); Kc: FAO-56 table
(context/kc_fao56.csv); 1 mm on 1 ha = 10 m3. Outside the growing season of the crop the table has no row:
en_saison is False and no need is given. forecast=True adds the next 7 days from the Open-Meteo API (needs the
internet; on failure "prevision" holds the error, the monthly answer is still given). The forecast uses the Kc of
the current month, not of the month asked.
"""
import calendar
import datetime
import json
import urllib.request

from common import governorate as gov_name
from common import query
from lexicon import crop_code

SOURCE = "climat 2015-2024 (Open-Meteo), coefficients Kc FAO-56 ; besoin = ET0 x Kc, déficit = besoin - pluie"


def _forecast(gov, kc, days=7):
    g = query("SELECT lat, lon FROM gouvernorats WHERE gouvernorat = ?", (gov,))[0]
    url = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&daily=precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max&forecast_days={d}"
           "&timezone=Africa%2FTunis").format(lat=g["lat"], lon=g["lon"], d=days)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            daily = json.load(r)["daily"]
    except Exception as e:  # no network, API down: the monthly answer stays valid
        return {"erreur": f"prévision indisponible ({type(e).__name__})"}
    et0, rain = sum(daily["et0_fao_evapotranspiration"]), sum(daily["precipitation_sum"])
    need = et0 * kc if kc is not None else None
    return {"jours": days, "du": daily["time"][0], "au": daily["time"][-1], "et0_mm": round(et0, 1),
            "pluie_mm": round(rain, 1), "tmax_c": max(daily["temperature_2m_max"]),
            "besoin_mm": round(need, 1) if need is not None else None,
            "deficit_mm": round(max(need - rain, 0), 1) if need is not None else None, "source": "api.open-meteo.com"}


def get_water_need(governorate, crop, month, forecast=False):
    gov = gov_name(governorate)
    code = crop_code(crop)
    crops = [r["crop"] for r in query("SELECT crop FROM kc ORDER BY crop")]
    if code not in crops:
        raise ValueError(f"culture sans coefficient Kc : {crop!r} (disponibles : {', '.join(crops)})")
    month = int(month)
    if not 1 <= month <= 12:
        raise ValueError(f"mois invalide : {month}")
    rows = query("SELECT * FROM besoins_eau WHERE gouvernorat = ? AND crop = ? AND mois = ?", (gov, code, month))
    out = {"gouvernorat": gov, "crop": code, "mois": month, "en_saison": bool(rows), "source": SOURCE}
    if rows:
        r = rows[0]
        deficit = max(r["deficit_mm"], 0.0)
        out.update({"culture": r["culture"], "et0_mm": r["et0_mm"], "kc": r["kc"], "besoin_mm": r["etc_mm"],
                    "pluie_mm": r["pluie_mm"], "deficit_mm": round(deficit, 1),
                    "deficit_m3_ha": round(deficit * 10), "deficit_mm_jour": round(deficit / calendar.monthrange(2023, month)[1], 2)})
    else:
        season = sorted(x["mois"] for x in query("SELECT DISTINCT mois FROM besoins_eau WHERE crop = ?", (code,)))
        out["message"] = f"hors saison de culture dans la table (mois couverts : {season})"
    if forecast:
        now = query("SELECT kc FROM besoins_eau WHERE gouvernorat = ? AND crop = ? AND mois = ?",
                    (gov, code, datetime.date.today().month))
        out["prevision"] = _forecast(gov, now[0]["kc"] if now else None)
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(get_water_need(sys.argv[1], sys.argv[2], sys.argv[3], forecast="--forecast" in sys.argv),
                     ensure_ascii=False, indent=1))
