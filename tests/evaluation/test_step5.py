"""Step 5 of the improvement plan: leaf box rule (crop only when the detector is sure and the box is a leaf)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "preparation"))
from leaf_boxes import crop_box  # noqa: E402


class TestCropBox(unittest.TestCase):
    def test_sure_leaf_box_is_cropped_with_margin(self):
        c = crop_box([50, 60, 150, 160], 224, 224, 0.4)
        self.assertEqual(c, (40, 50, 160, 170))

    def test_unsure_detection_keeps_photo(self):
        self.assertIsNone(crop_box([50, 60, 150, 160], 224, 224, 0.05))

    def test_tiny_or_whole_box_keeps_photo(self):
        self.assertIsNone(crop_box([200, 190, 223, 215], 224, 224, 0.5))  # 1 % of the photo: not the leaf
        self.assertIsNone(crop_box([0, 0, 224, 220], 224, 224, 0.5))  # whole photo: nothing to crop

    def test_box_is_clipped_to_the_photo(self):
        x0, y0, x1, y1 = crop_box([-10, -5, 120, 130], 224, 224, 0.3)
        self.assertGreaterEqual(min(x0, y0), 0)
        self.assertLessEqual(max(x1, y1), 224)


if __name__ == "__main__":
    unittest.main()
