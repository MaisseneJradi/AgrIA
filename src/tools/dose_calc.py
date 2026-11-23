"""Practical dose: the registered dose of the official list converted for a 16 L backpack sprayer and for the farmer's
area, with explicit units (phyto plan, step 5). Arithmetic only: nothing is estimated.

  practical_dose("3 kg/ha (300 g/hl)", area_ha=0.5)
  -> {"officielle": "3 kg/ha (300 g/hl)",
      "pulverisateur": {"min": 48.0, "max": 48.0, "base": "g", "texte": "48 g", "source": "300 g/hl"},
      "surface": {"min": 1500.0, "max": 1500.0, "base": "g", "texte": "1,5 kg", "source": "3 kg/ha", "ha": 0.5},
      "pulverisateur_absent": None, "surface_absente": None}
  practical_dose("1 L/300 à") -> None    (no unit that can be read: the official dose is shown alone)

Read parts: a number (or a range "30-50", "30 à 50"), a unit of mass (g, gr, kg) or volume (cc, ml, cl, l), then a
basis: per volume of mixture ("/hl", "/100 l", "/10 l", "/l") or per hectare ("/ha"). Pests traps, "/qt" of seeds,
"/arbre", "%" are not converted.
Conversions (exact):
  per volume V litres of mixture -> sprayer of TANK_L litres: dose x TANK_L / V
  per hectare                    -> area A ha:                 dose x A
A per-volume dose is never turned into a per-hectare amount (or the reverse): that needs the volume of mixture per
hectare, which the list does not give for the use. The answer then says to read the label ("..._absent").
When a dose has several parts, the first one of each basis is used ("0.5 l/ha (300-500 l/ha)": the second is the
volume of water). Quantities are written in g or ml (kg or l from 1000), with 2 decimals under 1, 1 under 100,
none from 100: check() accepts a written value within half a unit of its last decimal.
"""
import re

TANK_L = 16
NUM = r"\d+(?:[.,]\d+)?"
MASS, VOLUME = {"g": 1.0, "gr": 1.0, "kg": 1000.0}, {"cc": 1.0, "ml": 1.0, "cl": 10.0, "l": 1000.0}
PART = re.compile(rf"(?P<a>{NUM})(?:\s*(?:-|à|a)\s*(?P<b>{NUM}))?\s*(?P<u>kg|gr|g|cc|ml|cl|l)\b\.?\s*/\s*"
                  rf"(?:(?P<hl>hl\b)|(?P<v>{NUM})?\s*(?P<l>l(?:itres?)?)\b|(?P<ha>ha)(?=\b|volume))", re.I)


def _num(s):
    return float(s.replace(",", "."))


def parse(dose):
    """'3 kg/ha (300 g/hl)' -> [{"min": 3000, "max": 3000, "base": "g", "par": "ha", "litres": None, "texte": ...},
    {"min": 300, ..., "par": "volume", "litres": 100}]: amounts in g or ml."""
    out = []
    for m in PART.finditer(str(dose or "")):
        u = m.group("u").lower()
        factor, base = (MASS[u], "g") if u in MASS else (VOLUME[u], "ml")
        a = _num(m.group("a")) * factor
        b = _num(m.group("b")) * factor if m.group("b") else a
        if m.group("ha"):
            par, litres = "ha", None
        else:
            par = "volume"
            litres = 100.0 if m.group("hl") else (_num(m.group("v")) if m.group("v") else 1.0)
            if litres <= 0:
                continue
        out.append({"min": min(a, b), "max": max(a, b), "base": base, "par": par, "litres": litres,
                    "texte": m.group(0).strip()})
    return out


def decimals(v):
    return 2 if v < 1 else 1 if v < 100 else 0


def fmt(v_base, base, lang="fr"):
    """48.0 g -> '48 g'; 1500 g -> '1,5 kg'; 4.8 ml -> '4,8 ml'; 0.32 ml -> '0,32 ml'."""
    big = {"g": "kg", "ml": "l"}[base]
    v, unit = (v_base / 1000, big) if v_base >= 1000 else (v_base, base)
    d = 3 if unit == big else decimals(v)
    s = f"{v:.{d}f}".rstrip("0").rstrip(".") if d else f"{v:.0f}"
    return s.replace(".", ",") + " " + unit


def area_text(ha):
    """0.5 -> '0,5'; 2.0 -> '2'; 0.125 -> '0,125' (hectares as the farmer gave them)."""
    return f"{ha:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def qty_text(lo, hi, base, lang="fr"):
    """One quantity, or a range: '4,8 à 8 ml' (same unit), '800 ml à 1,2 l' (two units)."""
    a, b = fmt(lo, base, lang), fmt(hi, base, lang)
    if a == b:
        return a
    sep = " à " if lang == "fr" else " إلى "
    return a.split(" ")[0] + sep + b if a.split(" ")[1] == b.split(" ")[1] else a + sep + b


def practical_dose(dose, area_ha=None, lang="fr", tank_l=TANK_L):
    parts = parse(dose)
    if not parts:
        return None
    vol = next((p for p in parts if p["par"] == "volume"), None)
    ha = next((p for p in parts if p["par"] == "ha"), None)
    out = {"officielle": dose, "pulverisateur": None, "surface": None, "pulverisateur_absent": None,
           "surface_absente": None, "reservoir_l": tank_l, "ha_demandes": area_ha}
    if vol:
        k = tank_l / vol["litres"]
        out["pulverisateur"] = {"min": vol["min"] * k, "max": vol["max"] * k, "base": vol["base"],
                                "texte": qty_text(vol["min"] * k, vol["max"] * k, vol["base"], lang),
                                "source": vol["texte"]}
    else:
        out["pulverisateur_absent"] = "volume_par_ha"
    if area_ha:
        if ha:
            out["surface"] = {"min": ha["min"] * area_ha, "max": ha["max"] * area_ha, "base": ha["base"],
                              "texte": qty_text(ha["min"] * area_ha, ha["max"] * area_ha, ha["base"], lang),
                              "source": ha["texte"], "ha": area_ha}
        else:
            out["surface_absente"] = "volume_par_ha"
    return out


QTY = re.compile(rf"({NUM})\s*(kg|ml|g|l)(?![A-Za-z])")  # lower-case units: "16 L" (the sprayer) is not a quantity


RANGE = re.compile(rf"({NUM})\s*(?:à|إلى)\s*({NUM})\s*(kg|ml|g|l)(?![A-Za-z])")  # "3,2 à 4 g": the unit is written once


def written_quantities(line):
    """'Dose pratique : 48 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha' -> [(48.0, 'g'), (1.5, 'kg')];
    '3,2 à 4 g' -> [(3.2, 'g'), (4.0, 'g')]"""
    out = [(_num(a), u) for a, _, u in RANGE.findall(line)]
    return out + [(_num(n), u) for n, u in QTY.findall(line)]


def to_base(v, unit):
    return v * {"g": 1, "kg": 1000, "ml": 1, "l": 1000}[unit], {"g": "g", "kg": "g", "ml": "ml", "l": "ml"}[unit]


def check(line, expected):
    """The quantities written in a practical-dose line equal the exact conversion of the official dose: every written
    quantity is within half a unit of its last decimal of one of the expected bounds, and every bound is written.
    expected: practical_dose(...) of the official dose. Returns the list of errors (empty when exact)."""
    bounds = []
    for key in ("pulverisateur", "surface"):
        q = expected.get(key) if expected else None
        if q:
            bounds += [(q["min"], q["base"]), (q["max"], q["base"])] if q["min"] != q["max"] else [(q["min"], q["base"])]
    errors, found = [], set()
    for v, unit in written_quantities(line):
        b, base = to_base(v, unit)
        # half a unit of the last decimal that fmt() writes for this value (kg and l: 3 decimals)
        d = 3 if unit in ("kg", "l") else decimals(v)
        tol = 0.5 * 10 ** -d * (1000 if unit in ("kg", "l") else 1) + 1e-9
        hit = [i for i, (x, xb) in enumerate(bounds) if xb == base and abs(x - b) <= tol]
        if not hit:
            errors.append(f"{v} {unit} ne correspond pas à la dose officielle convertie")
        found.update(hit)
    missing = [bounds[i] for i in range(len(bounds)) if i not in found]
    if missing:
        errors.append("quantité attendue absente : " + ", ".join(fmt(x, b) for x, b in missing))
    return errors
