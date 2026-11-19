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


if __name__ == "__main__":
    unittest.main()
