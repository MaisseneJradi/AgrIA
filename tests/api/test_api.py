"""Tests of the HTTP API and of the web app files (models on CPU)."""
import io
import os
import unittest

os.environ.setdefault("AGRIA_DEVICE", "cpu")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

LATE_BLIGHT = "data/processed/diseases/test/tomato__late_blight/tomato__late_blight_01622.jpg"


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()  # runs the startup: models loaded once

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def post(self, photo=LATE_BLIGHT, **form):
        files = {"photo": ("feuille.jpg", open(photo, "rb"), "image/jpeg")} if photo else None
        try:
            return self.client.post("/diagnose", data=form, files=files)
        finally:
            if files:
                files["photo"][1].close()

    def test_health_and_governorates(self):
        h = self.client.get("/health").json()
        self.assertTrue({"deficiency", "diseases", "fruits", "routing"} <= set(h["modeles"]))
        g = self.client.get("/gouvernorats").json()
        self.assertEqual(len(g), 24)
        self.assertIn({"fr": "Sfax", "ar": "صفاقس"}, g)

    def test_diagnose_french(self):
        r = self.post(message="taches sur ma tomate", gouvernorat="Nabeul", langue="fr", mois="5")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["issue"], "conseil")
        self.assertEqual(body["langue"], "fr")
        self.assertTrue(body["produits"])
        self.assertTrue(body["verification"]["valide"])
        self.assertTrue(body["trace"])

    def test_diagnose_arabic(self):
        body = self.post(message="", gouvernorat="Nabeul", langue="ar").json()
        self.assertEqual(body["langue"], "ar")
        self.assertIn("التشخيص", body["texte"])

    def test_identify_detects_the_crop_of_a_leaf(self):
        with open(LATE_BLIGHT, "rb") as f:
            r = self.client.post("/identify", files={"photo": ("feuille.jpg", f, "image/jpeg")})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["feuille"])
        self.assertEqual(body["culture"], "tomato")
        self.assertTrue(body["sure"])
        self.assertEqual(len(self.client.get("/cultures").json()), 14)

    def test_identify_rejects_a_non_image(self):
        r = self.client.post("/identify", files={"photo": ("x.jpg", io.BytesIO(b"nope"), "image/jpeg")})
        self.assertEqual(r.status_code, 415)

    def test_message_without_photo_asks_for_one(self):
        r = self.post(photo=None, message="ma tomate a des taches")
        self.assertEqual(r.json()["issue"], "autre_photo")

    def test_rejects_bad_input(self):
        r = self.client.post("/diagnose", data={"message": "x"},
                             files={"photo": ("notes.jpg", io.BytesIO(b"not an image"), "image/jpeg")})
        self.assertEqual(r.status_code, 415)
        self.assertEqual(self.post(langue="de").status_code, 422)
        self.assertEqual(self.post(mois="13").status_code, 422)

    def test_journal_and_feedback_in_test_mode_only(self):
        import tempfile
        from unittest import mock
        import src.api.main as api
        self.assertNotIn("journal_id", self.post().json())  # off by default: nothing kept
        self.assertEqual(self.client.post("/feedback", data={"journal_id": "x", "correct": "non"}).status_code, 404)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AGRIA_JOURNAL": "1"}), \
                mock.patch.object(api, "JOURNAL_DIR", api.Path(tmp)):
            body = self.post(message="test").json()
            jid = body["journal_id"]
            self.assertTrue((api.Path(tmp) / f"{jid}.jpg").exists())
            r = self.client.post("/feedback", data={"journal_id": jid, "correct": "non", "vraie_reponse": "olivier"})
            self.assertEqual(r.status_code, 200)
            import json
            rec = json.loads((api.Path(tmp) / f"{jid}.json").read_text(encoding="utf-8"))
            self.assertEqual(rec["avis"]["vraie_reponse"], "olivier")
            self.assertEqual(self.client.post("/feedback", data={"journal_id": "../x", "correct": "non"}).status_code,
                             422)

    def test_web_app_is_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("AgrIA", page.text)
        for f in ("app.js", "style.css", "manifest.webmanifest", "icon.svg"):
            self.assertEqual(self.client.get(f"/{f}").status_code, 200, f)
        self.assertEqual(self.client.get("/docs").status_code, 200)


    def test_answers_match_the_documented_schemas(self):
        # src/api/schemas.py describes the JSON (extra fields forbidden): the frontend types stay in sync
        from src.api import schemas as S
        S.Health.model_validate(self.client.get("/health").json())
        for g in self.client.get("/gouvernorats").json():
            S.Gouvernorat.model_validate(g)
        for c in self.client.get("/cultures").json():
            S.Culture.model_validate(c)
        with open(LATE_BLIGHT, "rb") as f:
            S.Identify.model_validate(self.client.post("/identify", files={"photo": ("f.jpg", f, "image/jpeg")}).json())
        S.Identify.model_validate(self.client.post(
            "/identify", files={"photo": ("i.png", io.BytesIO(_png()), "image/png")}).json())
        for body in (self.post(message="taches", gouvernorat="Nabeul", langue="fr", mois="5", culture="tomato").json(),
                     self.post(photo=None, message="ma tomate a des taches", langue="ar").json()):
            S.Diagnose.model_validate(body)

    def test_openapi_file_of_the_frontend_is_up_to_date(self):
        from src.api.export_openapi import OUT, schema_text
        self.assertTrue(OUT.exists(), "python -m src.api.export_openapi")
        self.assertEqual(OUT.read_text(encoding="utf-8"), schema_text(),
                         "schéma de l'API modifié : python -m src.api.export_openapi puis npm run api:types")


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 120, 120)).save(buf, "PNG")  # a grey square: not a plant
    return buf.getvalue()


class TestReactServing(unittest.TestCase):
    def test_spa_file(self):
        import tempfile
        from pathlib import Path
        from src.api.main import IMMUTABLE, NO_CACHE, spa_file
        with tempfile.TemporaryDirectory() as d:
            dist = Path(d) / "dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text("<html></html>", encoding="utf-8")
            (dist / "assets" / "app-abc.js").write_text("x", encoding="utf-8")
            (dist / "sw.js").write_text("x", encoding="utf-8")
            (Path(d) / "secret.txt").write_text("x", encoding="utf-8")
            self.assertEqual(spa_file("assets/app-abc.js", dist), ((dist / "assets" / "app-abc.js").resolve(),
                                                                   IMMUTABLE))
            self.assertEqual(spa_file("sw.js", dist)[1], NO_CACHE)
            for route in ("", "historique", "a-propos", "admin/test"):  # routes of the app -> index.html
                self.assertEqual(spa_file(route, dist)[0], (dist / "index.html").resolve(), route)
            self.assertIsNone(spa_file("assets/missing.js", dist))
            self.assertIsNone(spa_file("missing.png", dist))
            self.assertIsNone(spa_file("../secret.txt", dist))  # never outside the build



class TestReactApi(unittest.TestCase):
    """Additions for the React app (A2 cards, A3 level, A6 feedback, A7 admin, test mode in /health)."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def diagnose(self, **form):
        with open(LATE_BLIGHT, "rb") as f:
            return self.client.post("/diagnose", data=form, files={"photo": ("f.jpg", f, "image/jpeg")}).json()

    def test_cards_are_the_checked_text(self):
        for lang in ("fr", "ar"):
            body = self.diagnose(culture="tomato", gouvernorat="Nabeul", langue=lang, mois="5")
            self.assertEqual("\n\n".join(c["texte"] for c in body["cartes"]), body["texte"])
            self.assertIn(body["diagnostic"]["niveau"], ("sur", "probable", "incertain"))
            for card in body["cartes"]:
                for p in card.get("produits") or []:
                    for line in p["lignes"]:
                        self.assertIn(line["texte"], body["texte"])
                        if line.get("url"):
                            self.assertIn(line["url"], line["texte"])
        no_photo = self.client.post("/diagnose", data={"message": "taches"}).json()
        self.assertEqual(no_photo["cartes"][0]["type"], "autre_photo")
        self.assertIsNone(no_photo["diagnostic"])

    def test_health_says_test_mode(self):
        from unittest import mock
        self.assertFalse(self.client.get("/health").json()["mode_test"])
        with mock.patch.dict(os.environ, {"AGRIA_JOURNAL": "1", "AGRIA_ADMIN_TOKEN": "t"}):
            h = self.client.get("/health").json()
        self.assertTrue(h["mode_test"] and h["admin"])

    def test_feedback_verdict_and_admin(self):
        import json
        import tempfile
        from unittest import mock
        import src.api.main as api
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AGRIA_JOURNAL": "1"}), \
                mock.patch.object(api, "JOURNAL_DIR", api.Path(tmp)):
            jid = self.diagnose(culture="tomato", langue="fr")["journal_id"]
            r = self.client.post("/feedback", data={"journal_id": jid, "verdict": "partiel", "vraie_culture": "tomato",
                                                     "vrai_probleme": "mildiou", "commentaire": "bonne culture"})
            self.assertEqual(r.status_code, 200)
            avis = json.loads((api.Path(tmp) / f"{jid}.json").read_text(encoding="utf-8"))["avis"]
            self.assertEqual((avis["verdict"], avis["correct"], avis["vrai_probleme"]), ("partiel", False, "mildiou"))
            self.assertFalse(avis["garder_photo"])
            self.assertEqual(self.client.post("/feedback", data={"journal_id": jid, "verdict": "bof"}).status_code, 422)
            self.assertEqual(self.client.post("/feedback", data={"journal_id": jid}).status_code, 422)
            # admin: off without a token, refused with a wrong one
            self.assertEqual(self.client.get("/admin/journal").status_code, 404)
            with mock.patch.dict(os.environ, {"AGRIA_ADMIN_TOKEN": "secret"}):
                self.assertEqual(self.client.get("/admin/journal", headers={"Authorization": "Bearer x"}).status_code,
                                 401)
                body = self.client.get("/admin/journal", headers={"Authorization": "Bearer secret"}).json()
                from src.api import schemas as S
                S.AdminJournal.model_validate(body)
                self.assertEqual(body["analyses"][0]["verdict"], "partiel")
                self.assertEqual(body["par_culture"][0]["culture"], "tomato")
                csv = self.client.get("/admin/journal.csv", headers={"Authorization": "Bearer secret"})
                self.assertEqual(csv.status_code, 200)
                self.assertIn("verdict", csv.text.splitlines()[0])
                self.assertIn(jid, csv.text)


if __name__ == "__main__":
    unittest.main()
