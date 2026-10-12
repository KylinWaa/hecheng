# -*- coding: utf-8 -*-
"""主目录（assets/fruits）为最新版本，以其为准修复：
1. 修正缺失后缀的文件名（02.webp -> 02-cherry.webp 等）
2. 每张贴图统一到所在等级的标准像素尺寸（76..512）
3. 同步到 cutouts/webp/NN-face.webp 并更新 mapping.json
4. 重建 parts.js 碰撞形状
主目录当前排布（用户手动调整）：
  tier1<-嘘(原5) tier2<-戴麦(原4) tier3<-大嘴男(原1) tier4<-捂胸(原3) tier5<-竖拇指(原2) tier6-11不变
"""
import os, json, glob
import numpy as np
from PIL import Image

CUT = r"F:\hecheng\img\cutouts"
WEBP = os.path.join(CUT, "webp")
GAME = r"F:\hecheng\bignaiwa\assets\fruits"
IMG = r"F:\hecheng\img"
TIER_SIZES = [76, 100, 136, 172, 212, 252, 300, 352, 412, 472, 512]
GAME_NAMES = ["01-grape", "02-cherry", "03-orange", "04-lemon", "05-kiwi",
              "06-tomato", "07-peach", "08-pineapple", "09-coconut",
              "10-halfmelon", "11-watermelon"]
# 主目录排布对应的源图短名（与 mapping/修复脚本对账用）
TIER_SRC8 = ["7d13d489", "c8950106", "b0e52047", "207a3d2e", "b2d28899",
             "1dda02b4", "d65fcfda", "c8989496", "683d6ab3", "6e4553a3", "9a9337bb"]

# 1) 修正文件名
renames = {"02.webp": "02-cherry.webp", "03.webp": "03-orange.webp",
           "04.webp": "04-lemon.webp"}
for old, new in renames.items():
    p = os.path.join(GAME, old)
    if os.path.exists(p):
        os.replace(p, os.path.join(GAME, new))
        print(f"renamed {old} -> {new}")

# 2) 主目录贴图统一到各等级标准尺寸，并同步 cutouts/webp
for tier in range(1, 12):
    size = TIER_SIZES[tier - 1]
    game_path = os.path.join(GAME, GAME_NAMES[tier - 1] + ".webp")
    img = Image.open(game_path).convert("RGBA")
    if img.width != size:
        img = img.resize((size, size), Image.LANCZOS)
        img.save(game_path, "WEBP", quality=90)
        print(f"tier {tier:2d}: resized {GAME_NAMES[tier - 1]}.webp -> {size}px")
    else:
        print(f"tier {tier:2d}: {GAME_NAMES[tier - 1]}.webp already {size}px")
    img.save(os.path.join(WEBP, f"{tier:02d}-face.webp"), "WEBP", quality=90)

# 3) 更新 mapping.json（按新排布）
mapping = []
for tier in range(1, 12):
    src8 = TIER_SRC8[tier - 1]
    full = glob.glob(os.path.join(IMG, src8 + "*.jpg"))
    canvas = Image.open(os.path.join(CUT, src8 + ".png"))
    bbox = canvas.getchannel("A").getbbox()
    span = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else 0
    mapping.append({"tier": tier, "file": f"{tier:02d}-face.webp",
                    "src": os.path.basename(full[0]) if full else src8 + ".jpg",
                    "px": int(span)})
with open(os.path.join(CUT, "mapping.json"), "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)
print("mapping.json updated")
