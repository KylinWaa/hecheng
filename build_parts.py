# -*- coding: utf-8 -*-
"""从新贴图的 alpha 轮廓重新生成游戏的碰撞形状 parts.js。
格式与原版一致：window.SUIKA_PARTS = [{"parts":[[ox,oy,s],...], "rb": 1.xx}, ...]
坐标/半径单位均为「以球半径 r 为 1」：
  贴图边长 S 画在 box = 2r/0.92 的正方形里 → 1 像素 = 2.1739/S 个 r
贪心圆覆盖：反复取距离变换最大点放内切圆，直到覆盖率达标或圆数上限。
"""
import glob, os
import numpy as np
import cv2

TEX_DIR = r"F:\hecheng\img\cutouts\webp"
OUT_JS = r"F:\hecheng\img\cutouts\parts.js"
ASSET_FILL = 0.92
PX2R = 2.0 / ASSET_FILL          # 乘以 (1/S) 得到每像素的 r 数
MAX_CIRCLES = 26
MIN_CIRCLE_R = 0.05              # 小于这个半径（r 单位）的圆丢弃
COVERAGE_TARGET = 0.995

tiers = sorted(glob.glob(os.path.join(TEX_DIR, "*.webp")))
assert len(tiers) == 11, tiers
shapes = []
from PIL import Image
for path in tiers:
    im = np.array(Image.open(path).convert("RGBA"))
    S = im.shape[0]
    mask = (im[:, :, 3] >= 128).astype(np.uint8)
    scale = PX2R / S

    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    covered = np.zeros_like(mask, dtype=bool)
    circles = []
    ys, xs = np.nonzero(mask)
    total = len(ys)
    for _ in range(MAX_CIRCLES):
        free = (~covered).astype(np.float32)
        score = dt * free
        y, x = np.unravel_index(np.argmax(score), score.shape)
        r_px = float(dt[y, x])
        if r_px * scale < MIN_CIRCLE_R:
            break
        circles.append((x, y, r_px))
        cv2.circle(covered, (int(x), int(y)), int(np.ceil(r_px)), 1, -1)
        cov = 1.0 - covered[ys, xs].mean() if total else 1.0
        cov = covered[ys, xs].mean()
        if cov >= COVERAGE_TARGET:
            break

    parts = [[float((x - S / 2) * scale), float((y - S / 2) * scale), float(r * scale)]
             for x, y, r in circles]
    parts.sort(key=lambda p: -p[2])
    # rb：形状上离球心最远的距离（r 单位）
    my, mx = np.nonzero(mask)
    rb = float(np.max(np.hypot(mx - S / 2, my - S / 2)) * scale)
    shapes.append({"parts": [[round(v, 3) for v in p] for p in parts],
                   "rb": round(rb, 3)})
    cov_pct = covered[ys, xs].mean() * 100
    print(f"{os.path.basename(path)}: S={S} circles={len(circles)} coverage={cov_pct:.1f}% rb={rb:.3f}")

js = "/* 自动生成，请勿手改 —— 由 build_parts.py 从整人剪影贴图的 alpha 轮廓生成\n" \
     "   parts: [ox, oy, s]，单位是「以 r 为 1」；rb: 碰撞包围圆半径（同样以 r 为单位） */\n" \
     "window.SUIKA_PARTS = " + str(shapes).replace("'", '"') + ";\n"
with open(OUT_JS, "w", encoding="utf-8") as f:
    f.write(js)
print("written", OUT_JS)
