"""Pretrained backbones (torchvision, ImageNet weights) with a new output layer for our classes.

  efficientnet_b0     5.3 M parameters, default: good accuracy for its size, fits a 4 GB GPU
  mobilenet_v3_large  5.5 M, the fastest, for a phone or a CPU server
  convnext_tiny       28 M, a stronger CNN
  vit_b_16            86 M, the transformer to compare with (small batches on 4 GB)
"""
import torch.nn as nn
from torchvision import models

ARCHS = {
    "efficientnet_b0": (models.efficientnet_b0, models.EfficientNet_B0_Weights.DEFAULT),
    "mobilenet_v3_large": (models.mobilenet_v3_large, models.MobileNet_V3_Large_Weights.DEFAULT),
    "convnext_tiny": (models.convnext_tiny, models.ConvNeXt_Tiny_Weights.DEFAULT),
    "vit_b_16": (models.vit_b_16, models.ViT_B_16_Weights.DEFAULT),
}


def build(arch, n_classes, pretrained=True):
    """Backbone `arch` whose last layer outputs `n_classes` scores."""
    if arch not in ARCHS:
        raise ValueError(f"unknown model {arch!r}, expected one of {list(ARCHS)}")
    fn, weights = ARCHS[arch]
    net = fn(weights=weights if pretrained else None)
    if arch == "vit_b_16":
        net.heads.head = nn.Linear(net.heads.head.in_features, n_classes)
    elif arch == "convnext_tiny":
        net.classifier[2] = nn.Linear(net.classifier[2].in_features, n_classes)
    else:  # efficientnet, mobilenet: the last module of the classifier is the output layer
        net.classifier[-1] = nn.Linear(net.classifier[-1].in_features, n_classes)
    return net
