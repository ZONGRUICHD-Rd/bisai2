# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
第三种画法：用 Pillow 把绘图指令清单画成图片（用来逐帧生成介绍视频）。
和 main.py（tkinter）、web/app.js（canvas）读的是同一份指令清单。
需要：pip install pillow（只有做视频时才需要，作品本身不需要）
"""
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/opentype/noto/"
FONT_FILES = {False: FONT_DIR + "NotoSansCJK-Regular.ttc", True: FONT_DIR + "NotoSansCJK-Bold.ttc"}
FONT_INDEX = 2       # ttc 里第 3 个字体是简体中文（Noto Sans CJK SC）
ANCHOR = {"nw": "lt", "n": "mt", "ne": "rt", "w": "lm", "center": "mm", "e": "rm",
          "sw": "lb", "s": "mb", "se": "rb"}
_fonts = {}
_images = {}


def font(size, bold=False):
    key = (int(round(size)), bool(bold))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_FILES[key[1]], max(4, key[0]), index=FONT_INDEX)
    return _fonts[key]


def _rgb(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _image(path):
    if path not in _images:
        _images[path] = Image.open(path).convert("RGB")
    return _images[path]


def draw_cmds(img, cmds, k=1.0, ox=0.0, oy=0.0, skip=None):
    """把指令清单画到 img 上：坐标先乘 k，再平移 (ox, oy)。skip = 不用画的指令（已经画在底图上的）。"""
    d = ImageDraw.Draw(img)
    for c in cmds:
        if skip is not None and id(c) in skip:
            continue
        t = c[0]
        if t == "r":
            _, x, y, w, h, fill, outline, width, r, alpha = c
            box = [ox + x * k, oy + y * k, ox + (x + w) * k - 1, oy + (y + h) * k - 1]
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            rr = min(r * k, (box[2] - box[0]) / 2, (box[3] - box[1]) / 2)
            lw = max(1, int(round(width * k))) if outline else 0
            if alpha < 0.99 and fill:
                layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(layer).rounded_rectangle(box, rr, fill=_rgb(fill) + (int(alpha * 255),))
                img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))
                d = ImageDraw.Draw(img)
                fill = None
            d.rounded_rectangle(box, rr, fill=fill or None, outline=outline or None, width=lw)
        elif t == "c":
            _, x, y, rad, fill, outline, width = c
            box = [ox + (x - rad) * k, oy + (y - rad) * k, ox + (x + rad) * k, oy + (y + rad) * k]
            d.ellipse(box, fill=fill or None, outline=outline or None,
                      width=max(1, int(round(width * k))) if outline else 0)
        elif t == "l":
            _, pts, color, width = c
            xy = [(ox + pts[i] * k, oy + pts[i + 1] * k) for i in range(0, len(pts), 2)]
            w = max(1, int(round(width * k)))
            d.line(xy, fill=color, width=w, joint="curve")
            if w >= 3:                       # 圆头
                for px, py in (xy[0], xy[-1]):
                    d.ellipse([px - w / 2, py - w / 2, px + w / 2, py + w / 2], fill=color)
        elif t == "p":
            _, pts, fill, outline, width = c
            xy = [(ox + pts[i] * k, oy + pts[i + 1] * k) for i in range(0, len(pts), 2)]
            d.polygon(xy, fill=fill or None, outline=outline or None,
                      width=max(1, int(round(width * k))) if outline else 1)
        elif t == "t":
            _, x, y, s, color, size, bold, anchor = c
            d.text((ox + x * k, oy + y * k), s, fill=color, font=font(size * k, bold),
                   anchor=ANCHOR.get(anchor, "lt"))
        elif t == "img":                      # 只有视频用：贴一张图片
            _, path, x, y, w, h = c
            pic = _image(path).resize((int(w * k), int(h * k)), Image.LANCZOS)
            img.paste(pic, (int(ox + x * k), int(oy + y * k)))
    return img


def render(cmds, w, h, k=1.0, ss=2, bg="#0b1020"):
    """画一整张图；ss = 超采样倍数（先画大再缩小，边缘更平滑）。"""
    big = Image.new("RGB", (int(w * ss), int(h * ss)), bg)
    draw_cmds(big, cmds, k * ss)
    return big.resize((int(w), int(h)), Image.LANCZOS) if ss != 1 else big
