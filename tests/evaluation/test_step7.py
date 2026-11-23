"""Step 7 of the improvement plan: temperature scaling and coverage/accuracy of thresholds."""
import unittest

import numpy as np

from src.evaluation import temperature as T


class TestTemperature(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        n, k = 4000, 5
        self.true_logits = rng.normal(0, 1.5, (n, k))
        p = T.softmax(self.true_logits)
        self.y = np.array([rng.choice(k, p=row) for row in p])  # labels drawn from the true probabilities

    def test_recovers_overconfidence(self):
        t = T.fit_temperature(3.0 * self.true_logits, self.y)  # a model 3 times too sure
        self.assertAlmostEqual(t, 3.0, delta=0.3)

    def test_calibrated_model_keeps_t_near_one(self):
        self.assertAlmostEqual(T.fit_temperature(self.true_logits, self.y), 1.0, delta=0.1)

    def test_temperature_lowers_ece_and_keeps_predictions(self):
        z = 3.0 * self.true_logits
        t = T.fit_temperature(z, self.y)
        before, _, ok_b = T.scores(z, self.y, 1.0)
        after, _, ok_a = T.scores(z, self.y, t)
        self.assertTrue(np.array_equal(ok_b, ok_a))  # same answers
        self.assertLess(after["ece"], before["ece"])
        self.assertLess(after["nll"], before["nll"])

    def test_coverage_and_propose(self):
        conf = np.array([0.99, 0.95, 0.9, 0.6, 0.55] * 10)
        ok = np.array([True, True, True, False, False] * 10)
        rows = {r["threshold"]: r for r in T.coverage(conf, ok)}
        self.assertEqual(rows[0.5]["coverage"], 1.0)
        self.assertEqual(rows[0.9]["coverage"], 0.6)
        self.assertEqual(rows[0.9]["accuracy_kept"], 1.0)
        self.assertEqual(rows[0.9]["errors_caught"], 1.0)
        self.assertEqual(T.propose(conf, ok, 0.95), 0.61)


if __name__ == "__main__":
    unittest.main()


class TestAgentThresholds(unittest.TestCase):
    """src/evaluation/agent_thresholds.py: the confidence the Diagnostic agent really uses."""
    W = {"kind": {"leaf": 1.0, "vlm": 0.5}, "deficiency": {"leaf": 1.0, "deficiency": 0.0},
         "disease": {"diseases": 1.0, "leaf": 0.5}}

    def test_deficiency_confidence_is_class_share_times_kind_share(self):
        from src.evaluation import agent_thresholds as A
        leaf = {"N_deficiency": 0.6, "K_deficiency": 0.2, "tomato__early_blight": 0.2}
        cls, conf = A.deficiency_answer({"leaf": leaf}, "tomato", self.W)
        self.assertEqual(cls, "N_deficiency")
        self.assertAlmostEqual(conf, 0.75 * 0.8, places=6)  # 0.6 / 0.8 within deficiencies, times share 0.8

    def test_disease_photo_sent_to_disease_branch(self):
        from src.evaluation import agent_thresholds as A
        leaf = {"N_deficiency": 0.1, "tomato__early_blight": 0.9}
        self.assertEqual(A.deficiency_answer({"leaf": leaf}, "tomato", self.W), (None, 0.0))

    def test_table_counts_wrong_answers_given(self):
        from src.evaluation import agent_thresholds as A
        t = A.table([0.95, 0.85, 0.6, 0.3], [True, False, True, False], ths=(0.8,))
        self.assertEqual(t[0.8], (0.5, 0.5, 0.25))
