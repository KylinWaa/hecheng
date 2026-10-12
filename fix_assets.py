# -*- coding: utf-8 -*-
"""修复 4 张问题贴图：
01/03: isnet 重抠（保住被 u2net 吃掉的头）+ 连通域去噪点/水印
04:    isnet 重抠 + 手动补回左侧运动模糊的手（HSV 颜色键控）
06:    椭圆遮罩，只留脸（去脖子）
10:    亮度键控删掉下半部的麦当劳纸袋/白袋子
"""
import os
import numpy as np
import cv2
from PIL import Image
from rembg import remove, new_session

IMG = r"F:\hecheng\img"
OUT = r"F:\hecheng\img\cutouts"
WEBP = os.path.join(OUT, "webp")
TMP = os.path.join(IMG, "_fix_preview")
os.makedirs(TMP, exist_ok=True)

TIER_SIZE = {1: 76, 3: 136, 4: 172, 6: 252, 10: 472}
TIER_GAME = {1: "01-grape", 3: "03-orange", 4: "04-lemon", 6: "06-tomato", 10: "10-halfmelon"}
ASSET_FILL = 0.92


def fill92(img, size):
    """alpha 包围盒缩放到占画布 92%，居中"""
    a = np.array(img)[:, :, 3]
    ys, xs = np.nonzero(a > 16)
    if len(xs) == 0:
        return img
    bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    k = (ASSET_FILL * size) / max(bx1 - bx0, by1 - by0)
    nw, nh = max(1, int(round(img.width * k))), max(1, int(round(img.height * k)))
    img = img.resize((nw, nh), Image.LANCZOS)
    bx0, bx1, by0, by1 = int(bx0 * k), int(bx1 * k), int(by0 * k), int(by1 * k)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (int((size - (bx1 - bx0)) / 2 - bx0), int((size - (by1 - by0)) / 2 - by0)), img)
    return out


def inpaint_watermark(rgb):
    """左下角"王李籽73"水印：白字掩码 + 逐行取同行干净像素的中位数填充"""
    h, w = rgb.shape[:2]
    x1, y0 = int(w * 0.40), int(h * 0.82)
    roi = rgb[y0:, :x1].astype(np.float32)
    hsv = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_RGB2HSV)
    v, s = hsv[:, :, 2].astype(np.int32), hsv[:, :, 1].astype(np.int32)
    text = ((v > 165) & (s < 95)) | (v < 60)
    text = cv2.dilate(text.astype(np.uint8) * 255,
                      cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))) > 0
    for r in range(roi.shape[0]):
        clean = ~text[r]
        if clean.sum() >= 8:
            med = np.median(roi[r][clean], axis=0)
        else:                       # 整行都是字就用下一行
            med = np.median(roi[min(r + 2, roi.shape[0] - 1)], axis=0)
        roi[r][text[r]] = med
    # 轻微模糊填充区，融入毛衣纹理
    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    roi[text] = blurred[text]
    rgb[y0:, :x1] = roi.astype(np.uint8)
    return rgb


def keep_main_components(alpha, min_frac=0.04):
    """只保留面积 >= 最大连通域 min_frac 的组件（去水印、去噪点）"""
    m = (alpha > 16).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return alpha
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = np.zeros_like(m)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_frac * stats[big, cv2.CC_STAT_AREA] or i == big:
            keep[lab == i] = 255
    return np.minimum(alpha, keep)


def isnet_cut(fn):
    im = Image.open(os.path.join(IMG, fn)).convert("RGB")
    k = 512 / max(im.size)
    if k > 1:
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    rgb = inpaint_watermark(np.array(im))
    return remove(Image.fromarray(rgb), session=ses_isnet, post_process_mask=True)


ses_isnet = new_session("isnet-general-use")


def fix_01():
    """01-grape: isnet 重抠 + 连通域清理"""
    cut = isnet_cut("b0e52047b70589496748ada1ee631971.jpg")
    a = np.array(cut)[:, :, 3]
    a = keep_main_components(a)
    cut.putalpha(Image.fromarray(a))
    return cut


def fix_03():
    """03-orange: isnet 重抠 + 连通域清理"""
    cut = isnet_cut("207a3d2ef0dd4bdd34ad4ef7d9fe426b.jpg")
    a = np.array(cut)[:, :, 3]
    a = keep_main_components(a)
    cut.putalpha(Image.fromarray(a))
    return cut


def fix_04():
    """04-lemon: isnet 重抠 + 补回左手紫色模糊残影"""
    fn = "c8950106c90720ead93f2019a8a4c118.jpg"
    src = np.array(Image.open(os.path.join(IMG, fn)).convert("RGB"))
    k = 512 / max(src.shape[:2])
    src_big = cv2.resize(src, None, fx=k, fy=k, interpolation=cv2.INTER_LANCZOS4)
    cut = isnet_cut(fn)
    a = keep_main_components(np.array(cut)[:, :, 3])

    # —— 左手区域：紫色运动模糊，H≈128..179、S 0.10..0.30、V>0.36；
    #    只取贴着左缘的窄条（x < 25 源图像素），避开右侧同色相的相框 ——
    H, W = a.shape
    x0, x1 = 0, int(40 * k)
    y0, y1 = int(8 * k), int(130 * k)
    roi = cv2.cvtColor(src_big[y0:y1, x0:x1], cv2.COLOR_RGB2HSV)
    h_, s_, v_ = (roi[:, :, i].astype(np.float32) for i in range(3))
    edge = np.zeros(roi.shape[:2], np.float32)
    edge[:, :int(25 * k)] = 1.0                                       # 空间约束
    hand = (((h_ >= 128) & (h_ <= 172)) & (s_ > 0.12) & (s_ < 0.30) &
            (v_ > 0.36) & (v_ < 0.60) & (edge > 0)).astype(np.uint8) * 255
    hand = cv2.morphologyEx(hand, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    hand = cv2.morphologyEx(hand, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats((hand > 0).astype(np.uint8), 8)
    for i in range(1, n):                                            # 丢掉小碎块
        if stats[i, cv2.CC_STAT_AREA] < 60:
            hand[lab == i] = 0
    hand = cv2.GaussianBlur(hand, (7, 7), 0)
    # 预览蒙版
    prev = src_big[y0:y1, x0:x1].copy()
    prev[hand > 128] = [0, 255, 0]
    Image.fromarray(prev).save(os.path.join(TMP, "04_hand_mask.png"))

    out = np.array(cut)[:, :, :3]
    alpha = a.copy()
    region = a[y0:y1, x0:x1]
    blend = hand.astype(np.float32) / 255
    alpha[y0:y1, x0:x1] = (np.maximum(region, hand)).astype(np.uint8)
    # 手区域内的 RGB 用原图（把键控出来的手影像素带回来）
    ys, xs = np.nonzero(hand > 8)
    out[y0 + ys, x0 + xs] = src_big[y0 + ys, x0 + xs]
    fixed = Image.new("RGBA", cut.size)
    fixed = Image.fromarray(np.dstack([out, alpha]))
    return fixed


def fix_06():
    """06-tomato: 椭圆遮罩只留脸（去脖子），在现有 252 贴图上做"""
    tex = Image.open(os.path.join(WEBP, "06-face.webp")).convert("RGBA")
    S = tex.width
    a = np.array(tex)[:, :, 3].astype(np.float32)
    yy, xx = np.mgrid[0:S, 0:S]
    cx, cy, rx, ry = 128, 112, 96, 110          # 椭圆：发顶到下巴
    ell = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    mask = np.clip((1.0 - ell) * 6.0, 0, 1)      # 边缘羽化
    a = (a * mask).astype(np.uint8)
    out = np.array(tex).copy()
    out[:, :, 3] = a
    img = Image.fromarray(out)
    img = fill92(img, S)                          # 去掉脖子后重新填充居中
    return img


def fix_10():
    """10-halfmelon: 在袋子顶部把下半部整段截掉（半身像），避免色彩键控残边"""
    tex = Image.open(os.path.join(WEBP, "10-face.webp")).convert("RGBA")
    S = tex.width
    arr = np.array(tex)
    cut = int(S * 0.56)                           # 袋子顶缘上方一点
    arr[cut:, :, 3] = 0
    # 底缘轻微羽化，避免生硬直线
    feather = 6
    for i in range(feather):
        y = cut - feather + i
        arr[y, :, 3] = (arr[y, :, 3].astype(np.float32) * (i + 1) / (feather + 1)).astype(np.uint8)
    arr[:, :, 3] = keep_main_components(arr[:, :, 3], 0.05)
    Image.fromarray(arr).save(os.path.join(TMP, "10_nobag.png"))
    img = Image.fromarray(arr)
    img = fill92(img, S)
    return img


FIXES = {1: fix_01, 3: fix_03, 4: fix_04, 6: fix_06, 10: fix_10}

if __name__ == "__main__":
    results = {}
    for tier, fn in FIXES.items():
        img = fn()
        results[tier] = img
        img.save(os.path.join(TMP, f"fix_{tier:02d}.png"))
        print(f"tier {tier} fixed -> {os.path.join(TMP, f'fix_{tier:02d}.png')} {img.size}")

    # 预览拼图
    from PIL import ImageDraw
    H = 230
    keys = sorted(results)
    sheet = Image.new("RGB", (H * len(keys) + 10, H + 12), "#ffe9c0")
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(keys):
        im = results[t].copy()
        im.thumbnail((H - 8, H - 20))
        sheet.paste(im, (i * H + 5 + (H - 8 - im.width) // 2, 8), im)
        d.text((i * H + 8, H - 8), TIER_GAME[t], fill="black")
    sheet.save(os.path.join(TMP, "_all_fixed.png"))
    print("preview:", os.path.join(TMP, "_all_fixed.png"))
