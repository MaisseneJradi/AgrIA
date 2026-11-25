"""Step 4 of the improvement plan: TTA views, input size kept in the checkpoint, gradient accumulation and EMA."""
import os
import sys
import tempfile
import unittest

import torch
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "vision"))
from dataset import make_transform  # noqa: E402
from evaluate import load_model, tta_views  # noqa: E402
from models import build  # noqa: E402
from train import run_epoch  # noqa: E402


class CountingSGD(torch.optim.SGD):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.steps = 0

    def step(self, closure=None):
        self.steps += 1
        return super().step(closure)


class TestTTA(unittest.TestCase):
    def test_views_keep_shape_and_include_original_and_mirror(self):
        x = torch.rand(2, 3, 300, 300)
        views = tta_views(x)
        self.assertEqual(len(views), 5)
        for v in views:
            self.assertEqual(tuple(v.shape), (2, 3, 300, 300))
        self.assertTrue(torch.equal(views[0], x))
        self.assertTrue(torch.equal(views[1], x.flip(3)))

    def test_constant_image_gives_constant_views(self):
        x = torch.full((1, 3, 224, 224), 0.5)
        for v in tta_views(x):
            self.assertTrue(torch.allclose(v, x, atol=1e-6))


class TestSize(unittest.TestCase):
    def test_transform_size(self):
        from PIL import Image
        im = Image.new("RGB", (640, 480), (60, 140, 50))
        self.assertEqual(tuple(make_transform(train=False, size=300)(im).shape), (3, 300, 300))
        self.assertEqual(tuple(make_transform(train=False)(im).shape), (3, 224, 224))

    def test_checkpoint_size_is_read_back(self):
        net = build("efficientnet_b0", 3, pretrained=False)
        with tempfile.TemporaryDirectory() as d:
            torch.save({"arch": "efficientnet_b0", "classes": ["a", "b", "c"], "state_dict": net.state_dict(),
                        "size": 300}, os.path.join(d, "model.pt"))
            loaded, classes = load_model(d, torch.device("cpu"))
            self.assertEqual(loaded.input_size, 300)
            self.assertEqual(classes, ["a", "b", "c"])
            torch.save({"arch": "efficientnet_b0", "classes": ["a", "b", "c"], "state_dict": net.state_dict()},
                       os.path.join(d, "model.pt"))
            self.assertEqual(load_model(d, torch.device("cpu"))[0].input_size, 224)  # old checkpoints


class TestAccumulationAndEMA(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        ds = TensorDataset(torch.randn(10, 4), torch.randint(0, 2, (10,)))
        self.loader = DataLoader(ds, batch_size=2)  # 5 batches
        self.net = torch.nn.Linear(4, 2)
        self.scaler = torch.amp.GradScaler(enabled=False)

    def test_accumulation_steps(self):
        opt = CountingSGD(self.net.parameters(), lr=0.1)
        run_epoch(self.net, self.loader, torch.device("cpu"), torch.nn.CrossEntropyLoss(), opt, self.scaler, accum=2)
        self.assertEqual(opt.steps, 3)  # after batches 2, 4 and the last one (5)

    def test_ema_follows_optimizer_steps(self):
        from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
        ema = AveragedModel(self.net, multi_avg_fn=get_ema_multi_avg_fn(0.9), use_buffers=True)
        before = ema.module.weight.detach().clone()
        opt = CountingSGD(self.net.parameters(), lr=0.5)
        run_epoch(self.net, self.loader, torch.device("cpu"), torch.nn.CrossEntropyLoss(), opt, self.scaler,
                  accum=1, ema=ema)
        self.assertEqual(int(ema.n_averaged), 5)
        self.assertFalse(torch.equal(ema.module.weight, before))
        self.assertFalse(torch.equal(ema.module.weight, self.net.weight))  # averaged, not a copy

    def test_label_smoothing_loss_is_higher_on_confident_right_answer(self):
        out, y = torch.tensor([[10.0, -10.0]]), torch.tensor([0])
        self.assertGreater(torch.nn.CrossEntropyLoss(label_smoothing=0.1)(out, y),
                           torch.nn.CrossEntropyLoss()(out, y))


if __name__ == "__main__":
    unittest.main()
