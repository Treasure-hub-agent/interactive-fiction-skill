#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""A.2.2 — 生成 Social Preview 图（1280x640 意境）。

设计语言（v3 文艺感）：
- 米白宣纸底
- 三层远山淡墨
- 几笔飞鸟
- 标题 + 副标题 + 诗化引文 + 朱砂印章
- 输出：social-preview.png
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math

W, H = 1280, 640
img = Image.new("RGB", (W, H), "#faf7f2")
d = ImageDraw.Draw(img)

# 三层远山（近深远浅）
def mountain(y_base, amp, phase, color):
    pts = [(0, y_base + amp * math.sin(phase))]
    for x in range(0, W + 1, 6):
        y = y_base + amp * math.sin(x / 380 + phase) + 12 * math.sin(x / 160 + phase * 2)
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    d.polygon(pts, fill=color)

mountain(500, 60, 0.5, (213, 203, 187))   # 远
mountain(540, 45, 1.8, (201, 190, 172))   # 中
mountain(575, 30, 3.1, (188, 176, 155))   # 近

# 柔光
img = img.filter(ImageFilter.GaussianBlur(0.6))
d = ImageDraw.Draw(img)

# 飞鸟（三点远笔）
for bx, by, s in [(980, 180, 1.0), (1010, 195, 0.8), (1040, 175, 0.7), (1080, 205, 0.6)]:
    d.arc([bx - s * 8, by - 4, bx, by + 4], 200, 340, fill=(120, 108, 95), width=1)
    d.arc([bx, by - 4, bx + s * 8, by + 4], 200, 340, fill=(120, 108, 95), width=1)

# 字体
try:
    f_title = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc", 64)
    f_sub = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc", 26)
    f_quote = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc", 20)
    f_seal = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc", 22)
except Exception:
    f_title = f_sub = f_quote = f_seal = ImageFont.load_default()

# 标题
d.text((90, 170), "互动小说创作规范", font=f_title, fill=(43, 36, 32))
d.text((94, 260), "Interactive Fiction · 选项驱动的沉浸式创作", font=f_sub, fill=(107, 95, 85))

# 诗化引文（右下独立一行）
d.text((880, 400), "以选项为笔墨，以剧情为山河", font=f_quote, fill=(138, 124, 111))

# 印章（金句末尾右侧，不遮挡文字）
d.rounded_rectangle((1140, 385, 1200, 445), radius=8, fill=(163, 75, 58, 218))
d.text((1156, 400), "拾", font=f_seal, fill=(253, 248, 242))

# 底部细线
d.line((90, 580, 1190, 580), fill=(181, 168, 150), width=2)

img.save("social-preview.png", "PNG")
print(f"social-preview.png 生成完成: {img.size}")
