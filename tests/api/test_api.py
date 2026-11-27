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


if __name__ == "__main__":
    unittest.main()
