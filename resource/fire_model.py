"""Procedural holographic-table fire: shared by the numpy preview and the DXIL emitter."""
from fire_dsl import *

u, h, c1x, c1y, alpha, t_raw = (inp(n) for n in ("u", "h", "c1x", "c1y", "alpha", "time"))
t = frc(t_raw * 0.001) * 1000.0   # wrap every 1000 s to keep hash inputs precise


def hash21(px, py):
    # Dave Hoskins "hash without sine" (float-only, GPU friendly)
    ax, ay, az = frc(px * 0.1031), frc(py * 0.1031), frc(px * 0.1031)
    d = ax * (ay + 33.33) + ay * (az + 33.33) + az * (ax + 33.33)
    ax, ay, az = ax + d, ay + d, az + d
    return frc((ax + ay) * az)


def vnoise(px, py):
    fx, fy = frc(px), frc(py)
    ix, iy = px - fx, py - fy
    sx, sy = fx * fx * (3.0 - fx * 2.0), fy * fy * (3.0 - fy * 2.0)
    a, b = hash21(ix, iy), hash21(ix + 1.0, iy)
    c, d = hash21(ix, iy + 1.0), hash21(ix + 1.0, iy + 1.0)
    return mix(mix(a, b, sx), mix(c, d, sx), sy)


def build(gain=1.1):
    up = select_le(ddy(h), 0.0, h, 1.0 - h)          # 0 = base, 1 = tip, from screen orientation
    x = u * 2.0 - 1.0
    seed = frc(c1x * 0.0137 + c1y * 0.0071) * 97.0     # per-particle offset from the stock random UV
    n1 = vnoise(x * 2.2 + seed, up * 3.0 - t * 2.1)
    n2 = vnoise(x * 4.6 + seed * 1.3, up * 6.0 - t * 3.7)
    sway = vnoise(up * 1.1 - t * 0.8, seed * 0.37)
    wob = (sway - 0.5) * 0.7 * up
    w = sqrt(sat(1.0 - up * 0.92)) * 0.78 + 0.02
    shape = sat(1.0 - fabs(x + wob) / w)
    turb = n1 * 0.65 + n2 * 0.35
    dens = shape * sat(up * 6.0 + 0.15) * (1.05 - up * 0.75) + (turb - 0.5) * (0.35 + up * 0.75) * sat(shape * 2.5 + 0.1) - 0.18
    flick = vnoise(t * 2.7 + seed, seed * 0.53) * 0.35 + 0.8
    edge = sat((1.0 - up) * 4.0) * sat((1.0 - fabs(x)) * 5.0)
    heat = sat(dens * 1.9) * flick * alpha * edge
    r = sat(heat * 2.2)
    g = sat(heat * 1.8 - 0.45) * 0.75
    b = sat(heat * 2.6 - 1.95) * 0.35
    return {"r": r * gain, "g": g * gain, "b": b * gain}
