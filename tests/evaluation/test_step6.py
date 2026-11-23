"""Step 6 of the improvement plan: small heads on frozen features (selection on field validation, weights)."""
import unittest

import numpy as np

from src.evaluation import foundation as F


class TestHeads(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        centres = rng.normal(0, 3, (4, 16))
        y = rng.integers(0, 4, 600)
        self.x = (centres[y] + rng.normal(0, 1, (600, 16))).astype(np.float32)
        self.y = y

    def test_linear_and_mlp_learn_separable_classes(self):
        for kind in ("linear", "mlp"):
            head, acc, ep = F.train_head(kind, self.x[:500], self.y[:500], np.ones(500), self.x[500:], self.y[500:],
                                         4, epochs=10, lr=3e-2, batch=32)
            self.assertGreater(acc, 0.9, kind)
            self.assertTrue(1 <= ep <= 10)

    def test_same_seed_same_head(self):
        a = F.train_head("linear", self.x, self.y, np.ones(600), self.x, self.y, 4, epochs=3)[0]
        b = F.train_head("linear", self.x, self.y, np.ones(600), self.x, self.y, 4, epochs=3)[0]
        self.assertTrue(np.allclose(a.weight.detach().numpy(), b.weight.detach().numpy()))

    def test_head_shapes(self):
        self.assertEqual(F.make_head("linear", 384, 51).out_features, 51)
        self.assertEqual(F.make_head("mlp", 512, 60)[-1].out_features, 60)


if __name__ == "__main__":
    unittest.main()
