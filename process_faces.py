# -*- coding: utf-8 -*-
"""把 F:\\hecheng\\img 里的 11 张照片处理成游戏贴图：
1. rembg 抠掉背景（得到人物透明剪影）
2. 定位头部：优先 Haar 人脸检测，失败则用剪影顶部形状启发式
3. 以头部为中心裁出方形，主体占画布 92%（与游戏 ASSET_FILL 一致）
4. 输出：透明 PNG 素材 + 按等级尺寸的 WebP 贴图
"""
import os, glob, json
import numpy as np
from PIL import Image
import cv2
from rembg import remove, new_session

IMG_DIR = r"F:\hecheng\img"
OUT_DIR = os.path.join(IMG_DIR, "cutouts")
TEX_DIR = os.path.join(OUT_DIR, "webp")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TEX_DIR, exist_ok=True)

# 游戏贴图尺寸表（与 assets/fruits/*.webp 一致）
TIER_SIZES = [76, 100, 136, 172, 212, 252, 300, 352, 412, 472, 512]
ASSET_FILL = 0.92

session = new_session("u2net")
YUNET_PATH = r"F:\hecheng\yunet_face.onnx"


def detect_face_box(bgr):
    """YuNet 人脸检测。取置信度最高的脸框 [x,y,w,h]（误检框往往面积大但分数低）"""
    h, w = bgr.shape[:2]
    best = None                       # (box, score)
    attempts = [1.0]
    k = 640.0 / max(h, w)
    if k < 1.0:
        attempts.append(k)
    for scale in attempts:
        size = (max(32, int(w * scale)), max(32, int(h * scale)))
        det = cv2.FaceDetectorYN_create(YUNET_PATH, "", size, score_threshold=0.35)
        ret, faces = det.detect(bgr if scale == 1.0 else cv2.resize(bgr, size))
        if faces is not None and len(faces):
            f = max(faces, key=lambda b: b[14])       # b[14] = score
            box = np.array(f[:4]) / scale
            if best is None or f[14] > best[1]:
                best = (box, float(f[14]))
        if best is not None and best[1] >= 0.6:
            break
    if best is None:
        return None
    print(f"    face score={best[1]:.2f} box={best[0].round().astype(int).tolist()}")
    return best[0]


def head_from_mask(alpha):
    """没有检测到脸时：用人物剪影顶部宽度估计头部范围，返回 (cx, cy, size)"""
    ys, xs = np.nonzero(alpha)
    if len(ys) == 0:
        return None
    top = ys.min()
    h = ys.max() - top + 1
    band_lo, band_hi = top, min(top + max(8, int(h * 0.22)), ys.max())
    band = (ys >= band_lo) & (ys <= band_hi)
    if not band.any():
        return None
    bx = xs[band]
    head_w = np.percentile(bx.max() - bx.min(), 90) if len(bx) > 10 else (bx.max() - bx.min())
    head_w = max(head_w, 24)
    cx = (bx.min() + bx.max()) / 2
    # 头部高度 ≈ 1.25 倍头宽（含发型留余量），中心再上移一点
    size = head_w * 1.45
    cy = band_lo + size * 0.42
    return cx, cy, size


def process(path):
    name = os.path.splitext(os.path.basename(path))[0][:8]
    im = Image.open(path).convert("RGB")
    W, H = im.size
    # rembg 抠背景（小图先放大，u2net 对太小的图效果差）
    scale = max(1.0, 512 / max(W, H))
    if scale > 1.0:
        im_big = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    else:
        im_big = im
    cut = remove(im_big, session=session, post_process_mask=True)
    cut = cut.resize((W, H), Image.LANCZOS)
    alpha = np.array(cut)[:, :, 3]

    bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    box = detect_face_box(bgr)   # 仅用于日志/统计，裁剪保留整人剪影

    # —— 整人模式：不裁剪，整张人物剪影按 92% 填充放进方形画布 ——
    ys, xs = np.nonzero(alpha > 16)
    if len(xs) == 0:
        out, size, person_span = cut, max(W, H), min(W, H) / 2.6
    else:
        bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        bw, bh = bx1 - bx0, by1 - by0
        size = max(W, H)
        person_span = max(bw, bh)          # 人物主体在源图中的最大边（用于分级）
        k = (ASSET_FILL * size) / person_span
        crop = cut.crop((bx0, by0, bx1, by1))
        nw, nh = max(1, int(round(bw * k))), max(1, int(round(bh * k)))
        crop = crop.resize((nw, nh), Image.LANCZOS)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(crop, ((size - nw) // 2, (size - nh) // 2), crop)

    return out, name, False, (box is not None), person_span


def main():
    files = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    assert len(files) == 11, f"应有 11 张图，实际 {len(files)}"
    results = []
    for path in files:
        out, name, clipped, has_face, face_w = process(path)
        out.save(os.path.join(OUT_DIR, name + ".png"))
        results.append({"src": path, "png": name + ".png", "face_px": int(face_w),
                        "face_detected": has_face, "clipped": clipped})
        print(f"{os.path.basename(path)[:16]}  face={has_face}  crop_clip={clipped}  out={out.size}")

    # 分级：按抠出头部的实际分辨率从大到小 → 大等级
    order = sorted(range(11), key=lambda i: results[i]["face_px"])  # 脸宽升序 ↔ 等级尺寸升序配对
    tier_of = {}
    for tier in range(11):          # 0..10 小→大
        tier_of[order[tier]] = tier
    mapping = []
    for i, r in enumerate(results):
        tier = tier_of[i]
        size = TIER_SIZES[tier]
        tex = r  # placeholder
        img = Image.open(os.path.join(OUT_DIR, r["png"])).resize((size, size), Image.LANCZOS)
        fn = f"{tier+1:02d}-face.webp"
        img.save(os.path.join(TEX_DIR, fn), "WEBP", quality=90)
        mapping.append({"tier": tier + 1, "file": fn, "src": os.path.basename(r["src"]),
                        "px": r["face_px"]})
        print(f"tier {tier+1:2d} ({size:3d}px) <- {os.path.basename(r['src'])[:16]} ({r['face_px']}px 脸宽)")
    with open(os.path.join(OUT_DIR, "mapping.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
