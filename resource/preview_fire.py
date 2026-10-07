import numpy as np
from PIL import Image
import fire_model as M
from fire_dsl import evaluate

import sys; from pathlib import Path
OUT = M.build()
W, H = 64, 128
uu, hh = np.meshgrid(np.linspace(0, 1, W, dtype=np.float32), np.linspace(1, 0, H, dtype=np.float32))


def flame(time, seed):
    env = {"u": uu, "h": hh, "c1x": np.float32(seed * 37.1) + uu * 2, "c1y": np.float32(seed * 11.3),
           "alpha": np.float32(1), "time": np.float32(time), "__ddy__": lambda a: np.gradient(a, axis=0)}
    c = {}
    return np.stack([evaluate(OUT[k], env, c) for k in "rgb"], -1)


def tonemap(x):
    return np.clip(1 - np.exp(-x * 1.4), 0, 1) ** (1 / 2.2)


frames = []
bg = np.zeros((H * 2, W * 6, 3), np.float32); bg[..., 0] = 0.18; bg[..., 1] = 0.01
for f in range(24):
    img = bg.copy()
    for i in range(6):
        for j in range(2):
            img[j * H:(j + 1) * H, i * W:(i + 1) * W] += flame(54321.0 + f / 12, i * 7 + j * 3 + 1)
    frames.append(Image.fromarray((tonemap(img) * 255).astype(np.uint8)).resize((W * 6 * 2, H * 2 * 2), Image.NEAREST))
out = Path(__file__).resolve().parents[1] / "analysis/fire-flame-shader-24735202"
frames[0].save(out / "preview.gif", save_all=True, append_images=frames[1:], duration=83, loop=0)
frames[12].save(out / "preview.png")
