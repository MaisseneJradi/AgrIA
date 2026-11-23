"""Phyto plan, step 6: weather of the next hours (src/tools/weather.py), protective equipment, WHO hazard class and bee
warning (src/tools/hazard.py, docs/substance_hazard.csv and docs/bee_hazard.csv, proposed rows unused), Vérificateur
rules 15 to 18."""
import csv
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.agent import paths  # noqa: F401
from src.agent.redaction import P, compose
from src.evaluation import eval_phyto as E
import hazard  # noqa: E402  (src/tools)
import ranking  # noqa: E402
import weather  # noqa: E402
from safety import chemical_terms, check_answer  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hourly(rain, wind, proba=None, start="2026-11-23T10:00"):
    day, hour = start.split("T")
    times = [f"{day}T{h:02d}:00" for h in range(int(hour[:2]), 24)] + [f"2026-11-24T{h:02d}:00" for h in range(24)]
    n = len(times)
    return {"hourly": {"time": times, "precipitation": (rain + [0] * n)[:n],
                       "precipitation_probability": ((proba or []) + [0] * n)[:n],
                       "wind_speed_10m": (wind + [5] * n)[:n]}}


class TestTables(unittest.TestCase):
    def test_who_classes(self):
        rows = {r["substance"]: r for r in read(ranking.HAZARD)}
        self.assertEqual({r["status"] for r in rows.values()}, {"proposed"})
        self.assertTrue(all(r["classe_oms"] in ("Ia", "Ib", "II", "III", "U") for r in rows.values()))
        expected = {"Oxamyl": "Ia", "Abamectin (aka avermectin)": "Ib", "Dichlorvos": "Ib", "Imidacloprid": "II",
                    "Deltamethrin": "II", "Cymoxanil": "II", "Azoxystrobin": "U", "Glyphosate": "III"}
        for s, c in expected.items():
            self.assertEqual(rows[s]["classe_oms"], c, s)

    def test_bee_hazard(self):
        rows = {r["substance"] for r in read(hazard.BEES)}
        self.assertEqual({r["status"] for r in read(hazard.BEES)}, {"proposed"})
        for s in ("Imidacloprid", "Thiamethoxam", "Deltamethrin", "Spinosad", "Abamectin (aka avermectin)"):
            self.assertIn(s, rows)
        for s in ("Glyphosate", "Azoxystrobin", "Copper hydroxide"):  # not in the list: nothing is said
            self.assertNotIn(s, rows)

    def test_proposed_rows_are_not_used(self):
        self.assertIsNone(hazard.who_class({"substances": "Imidacloprid"}))
        self.assertEqual(hazard.bee_toxic({"substances": "Imidacloprid"}), [])


class TestWeather(unittest.TestCase):
    NOW = "2026-11-23T10:00"

    def test_thresholds(self):
        c = weather.conditions(hourly([0.6, 0.6], [10]), self.NOW)
        self.assertTrue(c["pluie"])  # 1.2 mm in 24 h
        self.assertEqual(c["pluie_mm"], 1.2)
        self.assertFalse(c["vent"])
        self.assertTrue(weather.conditions(hourly([0], [5], proba=[70]), self.NOW)["pluie"])  # probability 70 %
        self.assertFalse(weather.conditions(hourly([0.5], [15]), self.NOW)["vent"])  # 15 km/h is not above 15
        c = weather.conditions(hourly([0], [5] * 11 + [16]), self.NOW)
        self.assertTrue(c["vent"])
        self.assertEqual(c["vent_max_kmh"], 16)
        self.assertFalse(weather.conditions(hourly([0], [5] * 12 + [40]), self.NOW)["vent"])  # after 12 h
        self.assertFalse(weather.conditions(hourly([0] * 24 + [9], [5]), self.NOW)["pluie"])  # rain after 24 h

    def test_failure_is_silent_and_result_cached(self):
        weather._CACHE.clear()
        with mock.patch.dict(os.environ, {"AGRIA_METEO": "1"}):
            def down(lat, lon):
                raise OSError("no network")
            self.assertIsNone(weather.spray_conditions("Sfax", fetch=down))
            calls = []

            def up(lat, lon):
                calls.append(1)
                return hourly([2], [20], start=self.NOW)
            weather._CACHE.clear()
            self.assertTrue(weather.spray_conditions("Sousse", fetch=up, now=self.NOW)["pluie"])
            weather.spray_conditions("Sousse", fetch=up, now=self.NOW)
            self.assertEqual(len(calls), 1)
        with mock.patch.dict(os.environ, {"AGRIA_METEO": "0"}):
            self.assertIsNone(weather.spray_conditions("Sousse", fetch=up))
        weather._CACHE.clear()


class WithValidated(unittest.TestCase):
    """Copies of the two tables where every row is validated (the real files stay proposed)."""
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.saved = (ranking.HAZARD, hazard.BEES)
        for src, attr in ((ranking.HAZARD, "HAZARD"), (hazard.BEES, "BEES")):
            rows = [dict(r, status="validated") for r in read(src)]
            path = cls.dir / Path(src).name
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            setattr(ranking if attr == "HAZARD" else hazard, attr, path)
        ranking._hazard.cache_clear()
        hazard._bees.cache_clear()

    @classmethod
    def tearDownClass(cls):
        ranking.HAZARD, hazard.BEES = cls.saved
        ranking._hazard.cache_clear()
        hazard._bees.cache_clear()
        shutil.rmtree(cls.dir)


PPE = "Protection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes"


class TestRules15to18(WithValidated):
    BASE = {"task": "diseases", "classe": "tomato__late_blight", "culture": "tomate", "fiable": True}
    GOOD = {"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}  # cymoxanil II + copper oxychl. II
    LINE = "- CIMOXATE C WG (Cymoxanil + Copper oxychloride) : dose 3 kg/ha (300 g/hl) ; délai avant récolte : 3 jours"

    def check(self, why, extra=PPE, **kw):
        return check_answer(dict(self.BASE, produits=[self.GOOD], texte=self.LINE + "\n  " + why + "\n" + extra, **kw))

    def test_who_class(self):
        self.assertEqual(hazard.who_class({"substances": "Cymoxanil + Copper oxychloride"}), "II")
        self.assertTrue(self.check("Pourquoi : classe de toxicité OMS II (modérément dangereux)")["valide"])
        r = self.check("Pourquoi : classe de toxicité OMS III (peu dangereux)")
        self.assertTrue(any("fausse" in x for x in r["raisons"]), r["raisons"])
        r = self.check("Pourquoi : homologué contre ce problème sur votre culture")
        self.assertTrue(any("non écrite" in x for x in r["raisons"]), r["raisons"])

    def test_protective_equipment_required(self):
        r = self.check("Pourquoi : classe de toxicité OMS II (modérément dangereux)", extra="")
        self.assertTrue(any("protection" in x for x in r["raisons"]), r["raisons"])

    def test_weather_warning_with_its_numbers(self):
        why = "Pourquoi : classe de toxicité OMS II (modérément dangereux)"
        meteo = {"pluie": True, "pluie_mm": 3.2, "pluie_proba": 80, "vent": False, "vent_max_kmh": 9}
        rain = P["fr"]["meteo_pluie"].format(mm="3,2", p=80)
        self.assertTrue(self.check(why, PPE + "\n" + rain, meteo=meteo)["valide"])
        self.assertFalse(self.check(why, PPE, meteo=meteo)["valide"])
        self.assertFalse(self.check(why, PPE + "\n" + P["fr"]["meteo_pluie"].format(mm="1", p=80), meteo=meteo)["valide"])

    def test_bee_warning_required(self):
        base = {"task": "diseases", "classe": "tomato__leaf_miner", "culture": "tomate", "fiable": True}
        spino = {"nom": "SPINOBEST", "dose": "0.25l/ha (25 cc/hl)", "dar_jours": 0}
        line = "- SPINOBEST (Spinosad) : dose 0.25l/ha (25 cc/hl) ; délai avant récolte : 0 jour"
        why = "  Pourquoi : classe de toxicité OMS III (peu dangereux)"
        r = check_answer(dict(base, produits=[spino], texte="\n".join([line, why, PPE])))
        self.assertTrue(any("abeilles" in x for x in r["raisons"]), r["raisons"])
        bee = P["fr"]["abeilles"].format(nom="SPINOBEST")
        r = check_answer(dict(base, produits=[spino], texte="\n".join([line, why, PPE, bee])))
        self.assertTrue(r["valide"], r["raisons"])


class TestAnswers(WithValidated):
    CASE = {"crop": "tomato", "disease_or_deficiency": "tomato__leaf_miner", "governorate": "Nabeul",
            "days_to_harvest": "15", "market": "local", "organic": "n", "stage": "spread"}

    def test_answer_has_class_ppe_bees_and_weather(self):
        storm = {"pluie": True, "pluie_mm": 4.5, "pluie_proba": 90, "vent": True, "vent_max_kmh": 27.0,
                 "heure": "x", "source": "Open-Meteo"}
        with mock.patch("src.agent.agents.specialistes.spray_conditions", return_value=storm):
            out, _ = E.run_case(self.CASE)
        r = out["reponse"]
        self.assertTrue(r["verification"]["valide"], r["verification"])
        t = r["texte"]
        self.assertIn(P["fr"]["epi"], t)
        self.assertIn("pluie prévue dans les 24 heures (4,5 mm", t)
        self.assertIn("vent jusqu'à 27 km/h", t)
        for p in out["traitements"]["produits"]:
            if p["classe_oms"]:
                self.assertIn(f"OMS {p['classe_oms']} ", t)
            if p["abeilles"]:
                self.assertIn(P["fr"]["abeilles"].format(nom=p["nom"]), t)
        safety = t[t.index(P["fr"]["securite"]):]
        self.assertEqual(chemical_terms("\n".join(x for x in safety.splitlines()
                                                  if not any(p["nom"] in x for p in out["traitements"]["produits"]))),
                         [])

    def test_greenhouse_skips_weather_and_failure_is_silent(self):
        with mock.patch("src.agent.agents.specialistes.spray_conditions") as sc:
            out, _ = E.run_case(dict(self.CASE, greenhouse="y"))
            sc.assert_not_called()
        self.assertNotIn("Météo", out["reponse"]["texte"])
        with mock.patch("src.agent.agents.specialistes.spray_conditions", return_value=None):
            out, _ = E.run_case(self.CASE)
        self.assertTrue(out["reponse"]["verification"]["valide"])
        self.assertNotIn("Météo", out["reponse"]["texte"])

    def test_arabic_safety_lines(self):
        facts = {"issue": "conseil", "diagnostic": {"classe": "tomato__leaf_miner", "nom": "M", "confiance": 90},
                 "produits": [{"nom": "X EC", "substances": "S", "dose": "1 l/ha", "dar_jours": 3, "classe_oms": "Ib",
                               "abeilles": True, "raisons": [("relation", "direct"), ("toxicite", "Ib")]}],
                 "meteo": {"pluie": True, "pluie_mm": 2.0, "pluie_proba": 70, "vent": False, "vent_max_kmh": 8}}
        text = compose(facts, "ar")
        for part in ("السلامة:", "الوقاية:", "X EC: صنف Ib", "X EC: شديد السمية للنحل", "أمطار متوقعة خلال 24 ساعة (2 مم",
                     "صنف السمية Ib حسب منظمة الصحة العالمية (عالي الخطورة)"):
            self.assertIn(part, text)


if __name__ == "__main__":
    unittest.main()
