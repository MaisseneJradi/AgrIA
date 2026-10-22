"""Context data for the agent: Tunisian governorates, their climate, soil and crop water needs.

  governorates  the 24 governorates, coordinates of the chief town (Open-Meteo geocoding, GeoNames data)
  climate       daily weather 2015-2024 at the chief town (Open-Meteo archive = ERA5 reanalysis, free, no key):
                Tmin/Tmax, rain, relative humidity, reference evapotranspiration ET0 (FAO-56). Summarised into
                monthly normals per governorate, with the climatic water balance rain - ET0.
  soil          SoilGrids 250 m (ISRIC, CC BY 4.0), topsoil 0-30 cm: pH water, clay, sand, silt, organic carbon,
                total nitrogen, CEC. Town centres are masked (urban), so 8 points on a 10-20 km ring around the
                chief town are queried and their median kept.
  crop water    FAO-56 crop coefficients (Kc ini / mid / end, Allen et al. 1998, Table 12) for the crops of the
                project: crop water need ETc = Kc x ET0 for each governorate and month.
The app gets live forecasts from the same Open-Meteo API (see forecast_url()).

Usage: python src/preparation/fetch_context_tn.py
Output: data/processed/context/gouvernorats.csv, climat_journalier.csv, climat_mensuel.csv, sols.csv,
        kc_fao56.csv, besoins_eau_mensuels.csv   (raw API answers cached in data/raw/context/)
"""
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

RAW = os.path.join("data", "raw", "context")
OUT = os.path.join("data", "processed", "context")
UA = "AgrIA-research/1.0 (student project)"
START, END = "2015-01-01", "2024-12-31"
# governorate -> chief town as GeoNames writes it
GOVERNORATES = {
    "Tunis": "Tunis", "Ariana": "Ariana", "Ben Arous": "Ben Arous", "Manouba": "Manouba", "Nabeul": "Nabeul",
    "Zaghouan": "Zaghouan", "Bizerte": "Bizerte", "Béja": "Béja", "Jendouba": "Jendouba", "Le Kef": "El Kef",
    "Siliana": "Siliana", "Sousse": "Sousse", "Monastir": "Monastir", "Mahdia": "Mahdia", "Sfax": "Sfax",
    "Kairouan": "Kairouan", "Kasserine": "Kasserine", "Sidi Bouzid": "Sidi Bouzid", "Gabès": "Gabès",
    "Médenine": "Médenine", "Tataouine": "Tataouine", "Gafsa": "Gafsa", "Tozeur": "Tozeur", "Kébili": "Kebili",
}
DAILY = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", "precipitation_sum",
         "relative_humidity_2m_mean", "et0_fao_evapotranspiration", "wind_speed_10m_max", "shortwave_radiation_sum"]
SOIL = {"phh2o": 10, "clay": 10, "sand": 10, "silt": 10, "soc": 10, "nitrogen": 100, "cec": 10}  # d_factor
SOIL_UNITS = {"phh2o": "pH", "clay": "%", "sand": "%", "silt": "%", "soc": "g/kg", "nitrogen": "g/kg",
              "cec": "cmol(+)/kg"}
# FAO-56 Table 12 (Kc ini, Kc mid, Kc end) and the months of each stage for the usual Tunisian calendar
KC = [
    ("tomato", "Tomate (saison)", 0.60, 1.15, 0.80, [3, 4], [5, 6, 7], [8]),
    ("pepper", "Piment / Poivron", 0.60, 1.05, 0.90, [3, 4], [5, 6, 7], [8, 9]),
    ("potato", "Pomme de terre (saison)", 0.50, 1.15, 0.75, [1, 2], [3, 4], [5]),
    ("melon", "Melon / Pastèque", 0.50, 1.00, 0.75, [4], [5, 6], [7]),
    ("squash", "Courgette", 0.50, 0.95, 0.75, [3], [4, 5], [6]),
    ("wheat", "Blé", 0.40, 1.15, 0.30, [11, 12], [1, 2, 3, 4], [5]),
    ("barley", "Orge", 0.30, 1.15, 0.25, [11, 12], [1, 2, 3], [4, 5]),
    ("olive", "Olivier", 0.65, 0.70, 0.70, [1, 2, 3], [4, 5, 6, 7, 8, 9, 10], [11, 12]),
    ("citrus", "Agrumes", 0.70, 0.65, 0.70, [1, 2, 3], [4, 5, 6, 7, 8, 9, 10], [11, 12]),
    ("grape", "Vigne (table)", 0.30, 0.85, 0.45, [3, 4], [5, 6, 7, 8], [9, 10]),
    ("apple", "Pommier", 0.60, 0.95, 0.75, [3, 4], [5, 6, 7, 8], [9, 10]),
    ("peach", "Pêcher / Abricotier", 0.55, 0.90, 0.65, [3, 4], [5, 6, 7], [8, 9, 10]),
    ("datepalm", "Palmier dattier", 0.90, 0.95, 0.95, [1, 2, 3], [4, 5, 6, 7, 8, 9, 10], [11, 12]),
    ("pomegranate", "Grenadier", 0.50, 0.80, 0.65, [3, 4], [5, 6, 7, 8, 9], [10]),
    ("strawberry", "Fraisier", 0.40, 0.85, 0.75, [10, 11], [12, 1, 2, 3, 4], [5]),
]
_last = [0.0]


def get(url, cache, gap=1.0):
    path = os.path.join(RAW, cache)
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    for k in range(5):
        time.sleep(max(0.0, _last[0] + gap - time.time()))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or k == 4:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 20 * (k + 1)))
        finally:
            _last[0] = time.time()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data


def forecast_url(lat, lon, days=7):
    """Live forecast for the app (same variables as the archive)."""
    return ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {"latitude": lat, "longitude": lon, "daily": ",".join(DAILY), "forecast_days": days,
         "timezone": "Africa/Tunis"}))


def governorates():
    rows = []
    for gov, town in GOVERNORATES.items():
        q = urllib.parse.urlencode({"name": town, "count": 10, "language": "fr", "countryCode": "TN"})
        res = get(f"https://geocoding-api.open-meteo.com/v1/search?{q}", f"geo_{town}.json").get("results", [])
        # the chief town is a populated place (PPLA / PPLC); else the most populated hit
        res = sorted(res, key=lambda r: (r.get("feature_code") not in ("PPLA", "PPLC"), -(r.get("population") or 0)))
        r = res[0]
        rows.append({"gouvernorat": gov, "chef_lieu": r["name"], "lat": r["latitude"], "lon": r["longitude"],
                     "altitude_m": r.get("elevation"), "population_chef_lieu": r.get("population")})
    return pd.DataFrame(rows)


def climate(gov):
    frames = []
    for g in gov.itertuples():
        q = urllib.parse.urlencode({"latitude": g.lat, "longitude": g.lon, "start_date": START, "end_date": END,
                                    "daily": ",".join(DAILY), "timezone": "Africa/Tunis"})
        d = get(f"https://archive-api.open-meteo.com/v1/archive?{q}", f"climat_{g.gouvernorat}.json", gap=2.0)
        df = pd.DataFrame(d["daily"]).rename(columns={"time": "date"})
        frames.append(df.assign(gouvernorat=g.gouvernorat))
    daily = pd.concat(frames, ignore_index=True)
    daily["date"] = pd.to_datetime(daily["date"])
    return daily


def monthly_normals(daily):
    d = daily.assign(annee=daily["date"].dt.year, mois=daily["date"].dt.month)
    per_year = d.groupby(["gouvernorat", "annee", "mois"]).agg(
        pluie_mm=("precipitation_sum", "sum"), et0_mm=("et0_fao_evapotranspiration", "sum"),
        tmax_c=("temperature_2m_max", "mean"), tmin_c=("temperature_2m_min", "mean"),
        tmoy_c=("temperature_2m_mean", "mean"), hr_pct=("relative_humidity_2m_mean", "mean"),
        jours_pluie=("precipitation_sum", lambda s: int((s >= 1).sum())),
        jours_chaleur_35=("temperature_2m_max", lambda s: int((s >= 35).sum())),
        jours_gel=("temperature_2m_min", lambda s: int((s <= 0).sum()))).reset_index()
    norm = per_year.groupby(["gouvernorat", "mois"]).mean(numeric_only=True).drop(columns="annee").round(1)
    norm["bilan_hydrique_mm"] = (norm["pluie_mm"] - norm["et0_mm"]).round(1)
    norm["indice_aridite"] = (norm["pluie_mm"] / norm["et0_mm"]).round(2)  # P/ET0 < 0.2 arid, < 0.5 semi-arid
    return norm.reset_index()


def ring(lat, lon, km, n=8):
    for k in range(n):
        a = 2 * math.pi * k / n
        yield lat + km / 111 * math.cos(a), lon + km / (111 * math.cos(math.radians(lat))) * math.sin(a)


def soils(gov):
    rows = []
    for g in gov.itertuples():
        vals = {p: [] for p in SOIL}
        for k, (la, lo) in enumerate(list(ring(g.lat, g.lon, 10)) + list(ring(g.lat, g.lon, 20))):
            q = "&".join([f"lon={lo:.4f}", f"lat={la:.4f}", "value=mean"] + [f"property={p}" for p in SOIL]
                         + [f"depth={d}" for d in ("0-5cm", "5-15cm", "15-30cm")])
            d = get(f"https://rest.isric.org/soilgrids/v2.0/properties/query?{q}", f"sol_{g.gouvernorat}_{k}.json",
                    gap=12.0)  # SoilGrids fair use: 5 calls per minute
            for layer in d.get("properties", {}).get("layers", []):
                means = [x["values"]["mean"] for x in layer["depths"] if x["values"]["mean"] is not None]
                if means:  # 0-30 cm = mean of the three layers (5, 10, 15 cm thick -> weights 5/30, 10/30, 15/30)
                    w = [5, 10, 15][:len(means)]
                    vals[layer["name"]].append(sum(m * x for m, x in zip(means, w)) / sum(w) / SOIL[layer["name"]])
            if all(len(v) >= 3 for v in vals.values()):
                break  # three agricultural points are enough
        rows.append({"gouvernorat": g.gouvernorat, "n_points": max(len(v) for v in vals.values()),
                     **{f"{p}_{SOIL_UNITS[p]}": round(pd.Series(v).median(), 2) if v else None
                        for p, v in vals.items()}})
    df = pd.DataFrame(rows)
    ph = df["phh2o_pH"]
    df["risque_chlorose_ferrique"] = ph.ge(7.8)  # calcareous, alkaline soils block iron uptake
    df["texture"] = df.apply(lambda r: "argileuse" if (r["clay_%"] or 0) >= 35 else "sableuse"
                             if (r["sand_%"] or 0) >= 65 else "limoneuse / équilibrée", axis=1)
    return df


def crop_water(norm):
    kc_rows, need = [], []
    for code, nom, ini, mid, end, m_ini, m_mid, m_end in KC:
        kc_rows.append({"crop": code, "culture": nom, "kc_ini": ini, "kc_mid": mid, "kc_end": end,
                        "mois_ini": m_ini, "mois_mi_saison": m_mid, "mois_fin": m_end})
        kc_month = {**{m: ini for m in m_ini}, **{m: mid for m in m_mid}, **{m: end for m in m_end}}
        for r in norm.itertuples():
            if r.mois in kc_month:
                etc = kc_month[r.mois] * r.et0_mm
                need.append({"gouvernorat": r.gouvernorat, "crop": code, "culture": nom, "mois": r.mois,
                             "kc": kc_month[r.mois], "et0_mm": r.et0_mm, "etc_mm": round(etc, 1),
                             "pluie_mm": r.pluie_mm, "deficit_mm": round(max(0.0, etc - 0.8 * r.pluie_mm), 1)})
    return pd.DataFrame(kc_rows), pd.DataFrame(need)


def main():
    os.makedirs(OUT, exist_ok=True)
    gov = governorates()
    gov.to_csv(os.path.join(OUT, "gouvernorats.csv"), index=False, encoding="utf-8")
    print(gov.to_string(index=False))
    daily = climate(gov)
    daily.to_csv(os.path.join(OUT, "climat_journalier.csv"), index=False, encoding="utf-8")
    norm = monthly_normals(daily)
    norm.to_csv(os.path.join(OUT, "climat_mensuel.csv"), index=False, encoding="utf-8")
    year = norm.groupby("gouvernorat")[["pluie_mm", "et0_mm"]].sum().round(0)
    year["P/ET0"] = (year["pluie_mm"] / year["et0_mm"]).round(2)
    print(f"\nclimate {START} -> {END}: {len(daily)} daily rows; yearly totals:\n{year.sort_values('pluie_mm').to_string()}")
    kc, need = crop_water(norm)
    kc.to_csv(os.path.join(OUT, "kc_fao56.csv"), index=False, encoding="utf-8")
    need.to_csv(os.path.join(OUT, "besoins_eau_mensuels.csv"), index=False, encoding="utf-8")
    print(f"crop water needs: {len(need)} rows (governorate x crop x month)")
    soil = soils(gov)
    soil.to_csv(os.path.join(OUT, "sols.csv"), index=False, encoding="utf-8")
    print(soil.to_string(index=False))


if __name__ == "__main__":
    main()
