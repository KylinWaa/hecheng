# 合成小眯眼（本地版）

从 https://yhsome.github.io/BigNaiWa/v1/ 抓取的完整源码，纯前端实现，无需构建。

## 本地运行

方式一：本地 HTTP 服务器（推荐）

```bash
cd bignaiwa
python -m http.server 8642
# 浏览器打开 http://127.0.0.1:8642/
```

方式二：直接双击 `index.html` 用浏览器打开（游戏本身可运行，
排行榜的跨域请求在部分浏览器下可能受限）。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `index.html` | 页面结构（棋盘 / 侧边面板 / 排行榜与打赏弹窗） |
| `style.css` | 全部样式 |
| `game.js` | 游戏主逻辑：自研物理、投放瞄准、合成、复活币、音效 |
| `assets/fruits/*.webp` | 11 级奶娃贴图（葡萄 → 大西瓜） |
| `assets/fruits/parts.js` | 按贴图轮廓自动生成的碰撞形状数据 |
| `assets/fruits/blur.js` | 内联 data URL 的极模糊占位图 |
| `leaderboard.min.js` | 在线排行榜（混淆，连 tinywebdb.appinventor.space 公共数据库） |
| `sponsor.js` | 打赏弹窗 |
| `assets/sponsor-qr.jpg` | 微信收款码 |
| `assets/sounds/final_merge.mp3` | 合出最终神奶蛙（10→11 级）的专属音效，取自视频前 20s |

## 备注

- **贴图已替换为本地人像素材**：由 `F:\hecheng\img` 的 11 张照片经
  rembg 整人抠图生成（透明背景 WebP），碰撞形状 `parts.js` 亦按新人形
  轮廓重新生成。原版水果素材备份在 `assets/fruits/_original_backup/`。
  处理脚本：`F:\hecheng\process_faces.py`（抠图/分级）、
  `F:\hecheng\build_parts.py`（碰撞形状）。
  抠图结果与等级映射见 `F:\hecheng\img\cutouts\`。
- 游戏本体完全离线可玩；最高分、静音状态存 localStorage。
- 排行榜需要联网，走 `https://tinywebdb.appinventor.space/api`，
  离线时只有排行榜不可用，不影响游戏。
- 控制台调试句柄：`__DNW__`（`.state` / `.reset()` / `.FRUITS` 等）。
- 10 级合成 11 级播放 `assets/sounds/final_merge.mp3`（game.js 里的 `FinalMerge`），
  其余合成仍是 WebAudio 合成音；受音效开关控制。
