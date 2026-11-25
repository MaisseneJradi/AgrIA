import colorsys
import os
import sys
import unittest

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "vision"))
from dataset import RandomMotionBlur, RandomShadow, field_transform  # noqa: E402

from src.evaluation import compare  # noqa: E402


def hue_sat(img):
    """Mean hue and saturation of a uint8 (3, H, W) tensor."""
    px = img.permute(1, 2, 0).reshape(-1, 3).float().numpy() / 255
    hs = np.array([colorsys.rgb_to_hsv(*p)[:2] for p in px[::7]])
    return hs.mean(0)


class TestFieldAugmentation(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0)
        y, x = torch.meshgrid(torch.linspace(0, 1, 64), torch.linspace(0, 1, 64), indexing="ij")
        self.img = torch.stack([60 + 40 * x, 120 + 80 * y, 40 + 20 * x * y]).round().to(torch.uint8)  # greenish leaf

    def test_shadow_keeps_hue_and_saturation(self):
        out = RandomShadow(p=1.0)(self.img)
        self.assertLess(out.float().mean(), self.img.float().mean())  # darker
        h0, s0 = hue_sat(self.img)
        h1, s1 = hue_sat(out)
        self.assertAlmostEqual(h0, h1, delta=0.01)
        self.assertAlmostEqual(s0, s1, delta=0.02)

    def test_motion_blur_keeps_shape_and_colour(self):
        out = RandomMotionBlur(p=1.0)(self.img)
        self.assertEqual(out.shape, self.img.shape)
        self.assertEqual(out.dtype, torch.uint8)
        self.assertAlmostEqual(hue_sat(out)[0], hue_sat(self.img)[0], delta=0.02)

    def test_p_zero_changes_nothing(self):
        self.assertTrue(torch.equal(RandomShadow(p=0.0)(self.img), self.img))
        self.assertTrue(torch.equal(RandomMotionBlur(p=0.0)(self.img), self.img))

    def test_pipeline_has_no_hue_or_saturation_change(self):
        t = field_transform()
        jitter = [m for m in t.transforms if m.__class__.__name__ == "ColorJitter"]
        self.assertEqual(len(jitter), 1)
        self.assertIsNone(jitter[0].hue)
        self.assertIsNone(jitter[0].saturation)
        from PIL import Image
        x = t(Image.fromarray(self.img.permute(1, 2, 0).numpy()))
        self.assertEqual(tuple(x.shape), (3, 224, 224))


class TestRule5(unittest.TestCase):
    def test_decision(self):
        cur = {"field_acc": 0.80, "lab_acc": 0.99}
        self.assertTrue(compare.decide(cur, {"field_acc": 0.83, "lab_acc": 0.985}, 0.01)[0].startswith("CANDIDAT"))
        self.assertIn("McNemar", compare.decide(cur, {"field_acc": 0.83, "lab_acc": 0.99}, 0.2)[1][0])
        self.assertTrue(any("labo" in r for r in compare.decide(cur, {"field_acc": 0.85, "lab_acc": 0.97}, 0.001)[1]))
        self.assertIn("pas de gain sur le terrain", compare.decide(cur, {"field_acc": 0.80, "lab_acc": 0.99}, 0.01)[1])


if __name__ == "__main__":
    unittest.main()
