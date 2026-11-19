"""Time to diagnose one photo, as the app will do it (batch of 1), on GPU and on CPU.

Usage: python src/vision/speed.py models/diseases_effnet models/diseases_vit ...
Prints, per model folder: parameters, file size, median milliseconds per photo on GPU (if any) and CPU.
Run it when no training uses the machine, otherwise the times are too high.
"""
import os
import statistics
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(__file__))
from evaluate import load_model  # noqa: E402


@torch.no_grad()
def median_ms(net, device, runs):
    x = torch.randn(1, 3, 224, 224, device=device)
    for _ in range(5):  # warm-up
        net(x)
    times = []
    for _ in range(runs):
        if device.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        net(x)
        if device.type == "cuda":
            torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(times), 1)


def main():
    torch.set_num_threads(os.cpu_count() // 2 or 1)
    devices = [torch.device("cuda")] if torch.cuda.is_available() else []
    devices.append(torch.device("cpu"))
    print("model | arch | params (M) | file (MB) | " + " | ".join(f"ms/photo {d.type}" for d in devices))
    for folder in sys.argv[1:]:
        cells = []
        for d in devices:
            net, _ = load_model(folder, d)
            cells.append(median_ms(net, d, runs=50 if d.type == "cuda" else 20))
        ckpt_arch = torch.load(os.path.join(folder, "model.pt"), map_location="cpu")["arch"]
        params = sum(p.numel() for p in net.parameters()) / 1e6
        size = os.path.getsize(os.path.join(folder, "model.pt")) / 2**20
        print(f"{os.path.basename(folder)} | {ckpt_arch} | {params:.1f} | {size:.0f} | " + " | ".join(map(str, cells)))


if __name__ == "__main__":
    main()
