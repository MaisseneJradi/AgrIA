import unittest

import numpy as np
import torch
from PIL import Image

from src.evaluation import gradcam as gc


class Tiny(torch.nn.Module):
    """Two 'features' blocks and a classifier, shaped like torchvision's EfficientNet (net.features[-1])."""

    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.features = torch.nn.Sequential(torch.nn.Conv2d(3, 4, 3, padding=1), torch.nn.Conv2d(4, 8, 3, padding=1))
        self.head = torch.nn.Linear(8, 3)

    def forward(self, x):
        return self.head(self.features(x).mean((2, 3)))


class TestGradCAM(unittest.TestCase):
    def test_map_shape_and_range(self):
        cam, probs, idx = gc.GradCAM(Tiny())(torch.rand(1, 3, 32, 32))
        self.assertEqual(cam.shape, (32, 32))
        self.assertGreaterEqual(cam.min(), 0.0)
        self.assertLessEqual(cam.max(), 1.0 + 1e-6)
        self.assertAlmostEqual(float(probs.sum()), 1.0, places=5)
        self.assertEqual(idx, int(probs.argmax()))

    def test_chosen_class(self):
        _, _, idx = gc.GradCAM(Tiny())(torch.rand(1, 3, 16, 16), class_idx=2)
        self.assertEqual(idx, 2)

    def test_overlay(self):
        img = Image.new("RGB", (8, 8), (0, 0, 0))
        out = gc.overlay(img, np.ones((8, 8)), alpha=0.5)
        self.assertEqual(out.size, (8, 8))
        self.assertGreater(np.asarray(out).sum(), 0)  # the heat colour shows on a black photo

    def test_focus(self):
        mask = np.zeros((10, 10), dtype=np.float32)
        mask[:5] = 1  # half the photo is lesion
        cam = np.zeros((10, 10))
        cam[:5] = 1  # all the map on the lesion
        f = gc.focus(cam, mask)
        self.assertAlmostEqual(f["cam_in_lesion"], 1.0)
        self.assertAlmostEqual(f["focus_ratio"], 2.0)
        self.assertTrue(f["pointing_hit"])
        f = gc.focus(np.ones((10, 10)), mask)  # a flat map = chance
        self.assertAlmostEqual(f["focus_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
