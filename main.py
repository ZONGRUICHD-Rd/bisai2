# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
会学习的红绿灯 —— 电脑版入口
============================
运行方法：直接运行本文件即可（海龟编辑器、IDLE、VS Code、命令行 python main.py 都行）。
只用到 Python 自带的 tkinter，不需要安装任何第三方库。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)     # 保证不管从哪里启动，都能找到 smartlight 文件夹

import tkinter as tk                    # noqa: E402
import tkinter.font as tkfont           # noqa: E402

from smartlight import config as C      # noqa: E402
from smartlight.ui import App           # noqa: E402

FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB",
                   "Heiti SC", "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei",
                   "Source Han Sans SC", "SimHei")
ANCHOR = {"nw": "nw", "n": "n", "ne": "ne", "w": "w", "center": "center", "e": "e",
          "sw": "sw", "s": "s", "se": "se"}


class TkFrontend(object):
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("会学习的红绿灯 · 龙华智慧路口 AI 交通指挥官 —— 作者：%s（%s %s）" % (C.AUTHOR, C.SCHOOL, C.CLASS_NAME))
        self.root.configure(bg=C.COL["bg"])
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.k = min(1.0, sw * 0.96 / C.WIDTH, sh * 0.86 / C.HEIGHT)   # 小屏幕自动缩小
        self.canvas = tk.Canvas(self.root, width=int(C.WIDTH * self.k), height=int(C.HEIGHT * self.k),
                                bg=C.COL["bg"], highlightthickness=0)
        self.canvas.pack()
        families = set(tkfont.families(self.root))
        self.family = next((f for f in FONT_CANDIDATES if f in families), "TkDefaultFont")
        self.fonts = {}
        self.app = App(platform="desktop", save_fn=self.save_brain)
        self.canvas.bind("<Button-1>", lambda e: self.app.on_click(e.x / self.k, e.y / self.k))
        self.root.bind("<Key>", self.on_key)
        self.next_time = time.perf_counter()
        self.loop()

    def save_brain(self, brain):
        path = os.path.join(HERE, "my_brain.json")
        brain.save(path)
        return "my_brain.json"

    def on_key(self, event):
        key = event.keysym.lower()
        self.app.on_key({"space": "space", "escape": "escape", "return": "return"}.get(key, key))

    def font(self, size, bold):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = (self.family, -max(6, int(round(size * self.k))), "bold" if bold else "normal")
        return self.fonts[key]

    # ------------------------------------------------------------------ 绘制 --
    def draw(self, cmds):
        cv, k = self.canvas, self.k
        cv.delete("all")
        for c in cmds:
            t = c[0]
            if t == "r":
                _, x, y, w, h, fill, outline, width, r, alpha = c
                self.round_rect(x * k, y * k, (x + w) * k, (y + h) * k, r * k,
                                fill or "", outline or "", width if outline else 0, alpha)
            elif t == "c":
                _, x, y, rad, fill, outline, width = c
                cv.create_oval((x - rad) * k, (y - rad) * k, (x + rad) * k, (y + rad) * k,
                               fill=fill or "", outline=outline or "", width=width if outline else 0)
            elif t == "l":
                _, pts, color, width = c
                cv.create_line(*[v * k for v in pts], fill=color, width=max(1, width * k),
                               capstyle="round", joinstyle="round")
            elif t == "p":
                _, pts, fill, outline, width = c
                cv.create_polygon(*[v * k for v in pts], fill=fill or "", outline=outline or "",
                                  width=width if outline else 0)
            elif t == "t":
                _, x, y, s, color, size, bold, anchor = c
                cv.create_text(x * k, y * k, text=s, fill=color, font=self.font(size, bold),
                               anchor=ANCHOR.get(anchor, "nw"))

    def round_rect(self, x0, y0, x1, y1, r, fill, outline, width, alpha):
        stipple = ""
        if alpha < 0.95:   # tkinter 没有真正的半透明，用点阵花纹模拟
            stipple = "gray75" if alpha > 0.6 else "gray50" if alpha > 0.35 else "gray25"
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        if r < 1.5:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width,
                                         stipple=stipple if fill else "")
            return
        pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0)
        self.canvas.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=width,
                                   stipple=stipple if fill else "")

    # ------------------------------------------------------------------ 主循环 --
    def loop(self):
        self.app.tick()
        self.draw(self.app.render())
        self.next_time += 1.0 / C.FPS
        delay = self.next_time - time.perf_counter()
        if delay < -0.25:            # 电脑太忙落后太多，就别追了
            self.next_time = time.perf_counter()
        self.root.after(max(1, int(delay * 1000)), self.loop)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TkFrontend().run()
