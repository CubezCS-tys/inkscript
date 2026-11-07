"""Experiment 82, step 3: the learned path rebuilder's network.

A small U-Net reads the grey line crop (96 px high, any width) and predicts, per pixel:
  0  centre line   - the pen's centre line (logit); trained on a 1-px truth line blurred to a ridge
  1-2 direction    - the line's local axis as (cos 2a, sin 2a), learned on the line only (an auxiliary task: it makes
                     the network follow strokes through blobs instead of painting blob middles)
  3  counter       - the paper inside a closed loop of the CLEAN letter (logit), even where the ink has filled it
The centre line is decoded (decode()) to a 1-px line, which path82.rebuild(method='learned') turns into the ordered
pen path with exp 79's own graph and right-to-left walk.  The network never sees letters.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def block(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, c=(24, 48, 96, 160), out=4):
        super().__init__()
        self.e = nn.ModuleList()
        prev = 1
        for ch in c:
            self.e.append(block(prev, ch))
            prev = ch
        self.mid = block(c[-1], c[-1])
        self.up = nn.ModuleList()
        self.d = nn.ModuleList()
        for i in range(len(c) - 1, -1, -1):
            self.up.append(nn.ConvTranspose2d(prev, c[i], 2, stride=2) if i < len(c) - 1 else nn.Identity())
            self.d.append(block(c[i] * 2 if i < len(c) - 1 else c[i] * 2, c[i]))
            prev = c[i]
        self.head = nn.Conv2d(c[0], out, 1)

    def forward(self, x):
        skips = []
        for i, b in enumerate(self.e):
            x = b(x)
            skips.append(x)
            if i < len(self.e) - 1:
                x = F.max_pool2d(x, 2)
        x = self.mid(x)
        for j, (u, d) in enumerate(zip(self.up, self.d)):
            s = skips[len(skips) - 1 - j]
            x = u(x)
            x = d(torch.cat([x, s], 1))
        return self.head(x)


def prep(grey: np.ndarray) -> torch.Tensor:
    """Grey crop -> 1x1xHxW tensor, ink bright, width padded to a multiple of 8."""
    g = (255.0 - grey.astype(np.float32)) / 255.0
    H, W = g.shape
    Wp = (W + 7) // 8 * 8
    Hp = (H + 7) // 8 * 8
    g = np.pad(g, ((0, Hp - H), (0, Wp - W)))
    return torch.from_numpy(g)[None, None]


@torch.no_grad()
def predict(model, grey: np.ndarray, device="cpu") -> np.ndarray:
    """-> (4, H, W) float: centre-line probability, cos2a, sin2a, counter probability."""
    H, W = grey.shape
    y = model(prep(grey).to(device))[0].float().cpu().numpy()[:, :H, :W]
    y[0] = 1 / (1 + np.exp(-y[0]))
    y[3] = 1 / (1 + np.exp(-y[3]))
    return y


def decode(y: np.ndarray, thr: float = 0.5) -> np.ndarray:
    """Centre-line probability -> a 1-px line (thinned threshold, specks dropped)."""
    from sig79 import thin
    m = (y[0] >= thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    for k in range(1, n):
        if st[k][4] < 3:
            m[lab == k] = 0
    return thin(m).astype(bool)
