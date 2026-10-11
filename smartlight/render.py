# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
画面绘制：把整个世界“翻译”成一串绘图指令
==========================================
这里不直接调用 tkinter，也不直接调用网页 canvas，而是生成一个“绘图指令清单”：
    ["r", x, y, w, h, 填充色, 边框色, 线宽, 圆角, 透明度]   矩形
    ["c", cx, cy, 半径, 填充色, 边框色, 线宽]              圆
    ["l", [x1, y1, x2, y2, ...], 颜色, 线宽]               折线
    ["p", [x1, y1, ...], 填充色, 边框色, 线宽]             多边形
    ["t", x, y, 文字, 颜色, 字号, 是否加粗, 锚点]           文字
电脑窗口（tkinter）和网页（canvas）各自把清单画出来就行。
好处：同一份 Python 绘图代码，电脑和网页一模一样；调试时还能直接 print 出来看。
"""
import math
import random

from . import config as C
from .brain import N_QUEUE, N_STARVE
from .scenario import SCENARIOS, clock_text, period_name
from .traffic import AXIS_NAME, DIR_NAME, DIRS

COL = C.COL
S = C.VIEW
R = C.LANE_W                    # 道路半宽（单向一条车道）

# ---- 布局 ----
PANELS = {"fixed": (20, 70), "ai": (460, 70)}
CHART = (20, 504, 860, 260)
CARD_CMP = (900, 70, 360, 196)
CARD_BRAIN = (900, 278, 360, 244)
CARD_CTRL = (900, 534, 360, 230)
BTN_W, BTN_H, BTN_GAP = 159, 32, 6


# =================================================================== 工具 ==
def _rgb(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a, b, t):
    """两种颜色按比例混合，t=0 是 a，t=1 是 b。"""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


def text_width(s, size):
    """粗略估计文字宽度：汉字≈1 个字号宽，英文数字≈0.6 个字号宽。"""
    return sum(size if ord(ch) > 0x2E80 else size * 0.6 for ch in s)


def wrap(s, size, width):
    lines, cur = [], ""
    for ch in s:
        if text_width(cur + ch, size) > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _r1(x):
    return round(x, 1)


class Painter(object):
    def __init__(self):
        self.cmds = []

    def rect(self, x, y, w, h, fill, outline=None, width=1, r=0, alpha=1.0):
        self.cmds.append(["r", _r1(x), _r1(y), _r1(w), _r1(h), fill, outline, width, r, alpha])

    def circle(self, cx, cy, rad, fill, outline=None, width=1):
        self.cmds.append(["c", _r1(cx), _r1(cy), _r1(rad), fill, outline, width])

    def line(self, pts, color, width=1):
        self.cmds.append(["l", [_r1(v) for v in pts], color, width])

    def poly(self, pts, fill, outline=None, width=1):
        self.cmds.append(["p", [_r1(v) for v in pts], fill, outline, width])

    def text(self, x, y, s, color, size=14, bold=False, anchor="nw"):
        self.cmds.append(["t", _r1(x), _r1(y), s, color, size, bold, anchor])

    def clipped_rect(self, box, x, y, w, h, fill, r=0):
        """只画出在 box 范围内的部分（车开出画面边缘时用）。"""
        bx, by, bw, bh = box
        x0, y0 = max(x, bx), max(y, by)
        x1, y1 = min(x + w, bx + bw), min(y + h, by + bh)
        if x1 - x0 < 0.5 or y1 - y0 < 0.5:
            return
        clipped = (x0, y0, x1, y1) != (x, y, x + w, y + h)
        self.rect(x0, y0, x1 - x0, y1 - y0, fill, r=0 if clipped else r)

    def card(self, box, title=None, accent=None):
        x, y, w, h = box
        self.rect(x, y, w, h, COL["panel"], COL["border"], 1, 12)
        if title:
            if accent:
                self.rect(x + 14, y + 15, 4, 16, accent, r=2)
            self.text(x + 24, y + 12, title, COL["text"], 15, True)


# ================================================================ 路口底图 ==
_DECOR_CACHE = {}


def _decor(ox, oy):
    """路口周围的街区、楼房、树（只算一次，之后直接复用）。"""
    key = (ox, oy)
    if key in _DECOR_CACHE:
        return _DECOR_CACHE[key]
    p = Painter()
    cx, cy = ox + S / 2, oy + S / 2
    p.rect(ox, oy, S, S, COL["walk"])
    blk = S / 2 - R - 8                        # 每个街区的边长
    corners = ((ox, oy), (cx + R + 8, oy), (ox, cy + R + 8), (cx + R + 8, cy + R + 8))
    for qi, (bx, by) in enumerate(corners):
        rng = random.Random(100 + qi)          # 固定种子：两个路口的街景一模一样
        p.rect(bx, by, blk, blk, COL["grass"])
        lot = blk / 2
        for li in range(4):
            lx, ly = bx + (li % 2) * lot, by + (li // 2) * lot
            if rng.random() < 0.72:            # 楼房（从上往下看到的屋顶）
                w, h = rng.uniform(52, 72), rng.uniform(52, 72)
                x, y = lx + (lot - w) / 2, ly + (lot - h) / 2
                roof = rng.choice(C.ROOF_COLORS)
                p.rect(x + 5, y + 5, w, h, "#0a1410", r=4)                 # 影子
                p.rect(x, y, w, h, roof, mix(roof, "#ffffff", 0.25), 1, 4)
                p.rect(x + 6, y + 6, w - 12, h - 12, mix(roof, "#ffffff", 0.08), r=3)
                for _ in range(rng.randint(2, 5)):                       # 亮着灯的窗
                    wx, wy = x + rng.uniform(9, w - 15), y + rng.uniform(9, h - 13)
                    p.rect(wx, wy, 6, 4, rng.choice(("#ffe08a", "#ffd166", "#9fd3ff")))
            else:                              # 小公园
                p.rect(lx + 6, ly + 6, lot - 12, lot - 12, COL["grass2"], r=8)
                for _ in range(rng.randint(3, 5)):
                    tx, ty = lx + rng.uniform(16, lot - 16), ly + rng.uniform(16, lot - 16)
                    rr = rng.uniform(6, 10)
                    p.circle(tx + 2, ty + 2, rr, "#0c1a12")
                    p.circle(tx, ty, rr, rng.choice(("#2f7d4f", "#3c9a5f", "#287046")))
                    p.circle(tx - rr * 0.3, ty - rr * 0.3, rr * 0.45, "#56b97a")
    # 道路
    p.rect(cx - R, oy, 2 * R, S, COL["road"])
    p.rect(ox, cy - R, S, 2 * R, COL["road"])
    # 中心黄线
    stop = C.STOP_S
    p.line([cx, oy, cx, oy + stop - 2], COL["center"], 2)
    p.line([cx, oy + S - stop + 2, cx, oy + S], COL["center"], 2)
    p.line([ox, cy, ox + stop - 2, cy], COL["center"], 2)
    p.line([ox + S - stop + 2, cy, ox + S, cy], COL["center"], 2)
    # 斑马线
    z0, z1 = stop + 5, S / 2 - R - 1
    k = cx - R + 2
    while k < cx + R - 2:
        p.rect(k, oy + z0, 3, z1 - z0, "#7d879c")
        p.rect(k, oy + S - z1, 3, z1 - z0, "#7d879c")
        k += 6
    k = cy - R + 2
    while k < cy + R - 2:
        p.rect(ox + z0, k, z1 - z0, 3, "#7d879c")
        p.rect(ox + S - z1, k, z1 - z0, 3, "#7d879c")
        k += 6
    # 停止线（只画在进口车道上）
    p.rect(cx - R, oy + stop + 1, R, 3, COL["mark"])
    p.rect(cx, oy + S - stop - 4, R, 3, COL["mark"])
    p.rect(ox + stop + 1, cy, 3, R, COL["mark"])
    p.rect(ox + S - stop - 4, cy - R, 3, R, COL["mark"])
    # 路名
    p.text(cx + R + 6, oy + 8, "龙华大道", "#9aa4c8", 11)
    p.text(ox + 8, cy + R + 4, "人民路", "#9aa4c8", 11)
    _DECOR_CACHE[key] = p.cmds
    return p.cmds


# ================================================================ 车辆 ====
def _car_box(origin, s, length, ox, oy):
    """车头位置 s → 屏幕上的矩形 (x, y, w, h)，以及车头朝向。"""
    cx, cy = ox + S / 2, oy + S / 2
    half, w = R / 2.0, C.CAR_W
    if origin == "N":
        return cx - half - w / 2, oy + s - length, w, length, "down"
    if origin == "S":
        return cx + half - w / 2, oy + S - s, w, length, "up"
    if origin == "W":
        return ox + s - length, cy + half - w / 2, length, w, "right"
    return ox + S - s, cy - half - w / 2, length, w, "left"


def _part(x, y, w, h, heading, a0, a1, b0, b1):
    """车身局部坐标（a: 从车尾到车头，b: 从左到右）→ 屏幕矩形。"""
    L = h if heading in ("down", "up") else w
    if heading == "down":
        return x + b0, y + a0, b1 - b0, a1 - a0
    if heading == "up":
        return x + b0, y + L - a1, b1 - b0, a1 - a0
    if heading == "right":
        return x + a0, y + b0, a1 - a0, b1 - b0
    return x + L - a1, y + b0, a1 - a0, b1 - b0


def _draw_car(p, box, car, origin, ox, oy, frame):
    x, y, w, h, hd = _car_box(origin, car.s, car.length, ox, oy)
    L, W = car.length, C.CAR_W
    kind = car.kind
    body = car.spec.color
    p.clipped_rect(box, *_part(x, y, w, h, hd, 1, L + 1, 1, W + 1), fill="#05080f", r=3)  # 影子
    p.clipped_rect(box, x, y, w, h, body, r=4)
    if kind == "bus":
        p.clipped_rect(box, *_part(x, y, w, h, hd, 3, L - 6, 2, W - 2), fill="#d6fbe6")
        p.clipped_rect(box, *_part(x, y, w, h, hd, 5, L - 8, 3, W - 3), fill="#1f9d63")
        p.clipped_rect(box, *_part(x, y, w, h, hd, L - 6, L - 2, 2, W - 2), fill=COL["glass"])
    else:
        p.clipped_rect(box, *_part(x, y, w, h, hd, L * 0.62, L * 0.82, 2, W - 2), fill=COL["glass"])
        p.clipped_rect(box, *_part(x, y, w, h, hd, L * 0.12, L * 0.26, 2, W - 2), fill=COL["glass"])
        if kind == "amb":
            p.clipped_rect(box, *_part(x, y, w, h, hd, L * 0.30, L * 0.40, 0, W), fill=COL["danger"])
            on = (frame // 6) % 2 == 0
            p.clipped_rect(box, *_part(x, y, w, h, hd, L * 0.46, L * 0.56, 1, W / 2),
                           fill="#ff2a4d" if on else "#3a6dff")
            p.clipped_rect(box, *_part(x, y, w, h, hd, L * 0.46, L * 0.56, W / 2, W - 1),
                           fill="#3a6dff" if on else "#ff2a4d")
    # 刹车灯：停着/很慢时亮红灯；车头灯一直亮
    brake = "#ff3355" if car.v < 25 else "#7a1f2c"
    p.clipped_rect(box, *_part(x, y, w, h, hd, 0, 2, 1, 4), fill=brake)
    p.clipped_rect(box, *_part(x, y, w, h, hd, 0, 2, W - 4, W - 1), fill=brake)
    p.clipped_rect(box, *_part(x, y, w, h, hd, L - 2, L, 1, 4), fill="#fff6c8")
    p.clipped_rect(box, *_part(x, y, w, h, hd, L - 2, L, W - 4, W - 1), fill="#fff6c8")
    if car.wait > 25 and car.v < C.WAIT_SPEED and kind != "amb":   # 等太久了，生气！
        fx, fy = x + w / 2, y + h / 2
        if box[0] < fx < box[0] + box[2] and box[1] < fy < box[1] + box[3]:
            p.circle(fx, fy, 5, COL["danger"])
            p.text(fx, fy, "!", "#ffffff", 9, True, "center")


# ================================================================ 信号灯 ==
def _light_housing(p, x, y, sig, label=None):
    p.rect(x, y, 34, 14, "#0b0f1c", "#3a4466", 1, 7)
    for i, (key, color) in enumerate((("R", "#ff3b5c"), ("Y", "#ffc83d"), ("G", "#33f08e"))):
        lx = x + 7 + i * 10
        if sig == key:
            p.circle(lx, y + 7, 8, mix(color, "#0b0f1c", 0.7))
            p.circle(lx, y + 7, 4.5, color)
        else:
            p.circle(lx, y + 7, 3.5, mix(color, "#0b0f1c", 0.78))
    if label:
        p.rect(x + 36, y, 20, 14, "#0b0f1c", None, 1, 4)
        p.text(x + 46, y + 7, label, "#ffffff", 10, True, "center")


def _draw_lights(p, inter, ox, oy):
    cx, cy = ox + S / 2, oy + S / 2
    stop = C.STOP_S
    light, ctrl = inter.light, inter.controller
    labels = {"NS": None, "EW": None}
    if ctrl.kind == "fixed":                       # 定时灯有倒计时数字
        cd = ctrl.countdown(light)
        if cd is not None:
            labels[light.green_axis] = "%d" % math.ceil(cd)
            labels[light.red_axis] = "%d" % math.ceil(cd + C.YELLOW + C.ALL_RED)
    else:
        labels = {"NS": "AI", "EW": "AI"}
    spots = {"N": (cx - R - 40, oy + stop - 16), "S": (cx + R + 6, oy + S - stop + 2),
             "W": (ox + stop - 40, cy + R + 6), "E": (ox + S - stop + 6, cy - R - 20)}
    for d in DIRS:
        axis = "NS" if d in "NS" else "EW"
        x, y = spots[d]
        if d in "NW":
            x -= 22 if labels[axis] else 0
        _light_housing(p, x, y, light.signal(axis), labels[axis])


# ================================================================ 路口 ====
def draw_intersection(p, inter, key, frame):
    ox, oy = PANELS[key]
    box = (ox, oy, S, S)
    accent = COL["ai"] if key == "ai" else COL["fixed"]
    p.cmds.extend(_decor(ox, oy))
    for d in DIRS:
        for car in inter.lanes[d].cars:
            _draw_car(p, box, car, d, ox, oy, frame)
    _draw_lights(p, inter, ox, oy)
    # 画面外排队的车：在入口处显示 +N
    cx, cy = ox + S / 2, oy + S / 2
    for d in DIRS:
        n = len(inter.lanes[d].backlog)
        if not n:
            continue
        label = "+%d" % n
        bw = text_width(label, 12) + 14
        pos = {"N": (cx - R - bw - 4, oy + 50), "S": (cx + R + 4, oy + S - 70),
               "W": (ox + 6, cy + R + 4), "E": (ox + S - bw - 6, cy - R - 24)}[d]
        hot = n >= 10
        p.rect(pos[0], pos[1], bw, 20, COL["danger"] if hot else COL["warn"], None, 1, 10)
        p.text(pos[0] + bw / 2, pos[1] + 10, label, "#1a1a1a" if not hot else "#ffffff", 12, True, "center")
    # 边框和标题
    p.rect(ox, oy, S, S, None, accent, 2, 14)
    title = inter.title
    tw = text_width(title, 15) + 28
    p.rect(ox + 12, oy + 12, tw, 30, "#0b1020", accent, 2, 15)
    p.circle(ox + 26, oy + 27, 5, accent)
    p.text(ox + 36, oy + 27, title, COL["text"], 15, True, "w")
    # 平均等待大数字
    w = inter.stats.avg_wait()
    wtxt = "--" if w is None else "%.1f" % w
    color = COL["ai"] if w is not None and w < 8 else COL["warn"] if w is not None and w < 20 else COL["danger"]
    if w is None:
        color = COL["muted"]
    p.rect(ox + S - 132, oy + 12, 120, 52, "#0b1020", COL["border"], 1, 12)
    p.text(ox + S - 122, oy + 20, "平均等待", COL["muted"], 11)
    p.text(ox + S - 22, oy + 40, wtxt, color, 24, True, "e")
    p.text(ox + S - 20, oy + 46, "秒", COL["muted"], 11, False, "w")
    # 底部状态条
    light = inter.light
    stage_txt = {"G": "绿灯", "Y": "黄灯", "R": "全红清空"}[light.stage]
    axis = AXIS_NAME[light.green_axis]
    if light.stage == "R":
        status = "全红清空中 · 马上轮到%s" % AXIS_NAME[light.red_axis]
    else:
        status = "%s%s · 已亮 %.0f 秒" % (axis, stage_txt, light.timer)
    status += "   |   排队 %d 辆   切换 %d 次" % (inter.queue_len(), light.switches)
    p.rect(ox + 12, oy + S - 40, S - 24, 28, "#0b1020", COL["border"], 1, 14)
    p.text(ox + S / 2, oy + S - 26, status, COL["text"], 12, False, "center")


# ================================================================ 曲线图 ==
def draw_chart(p, world):
    x, y, w, h = CHART
    p.card(CHART, "平均等待时间变化（秒）· 越低越好", COL["blue"])
    lx = x + w - 250
    for i, (key, name) in enumerate((("fixed", "传统定时"), ("ai", "AI 自学习"))):
        col = COL[key]
        p.line([lx + i * 120, y + 22, lx + i * 120 + 22, y + 22], col, 3)
        p.text(lx + i * 120 + 28, y + 22, name, COL["text"], 12, False, "w")
    px, py, pw, ph = x + 50, y + 44, w - 70, h - 74
    hf, ha = world.history["fixed"], world.history["ai"]
    peak = max([10.0] + list(hf) + list(ha))
    top = int(math.ceil(peak * 1.15 / 10.0)) * 10
    for i in range(5):
        gy = py + ph - ph * i / 4.0
        p.line([px, gy, px + pw, gy], "#1f2a4f", 1)
        p.text(px - 8, gy, "%d" % (top * i / 4.0), COL["dim"], 11, False, "e")
    p.text(px, py + ph + 10, "← 6 分钟前", COL["dim"], 11)
    p.text(px + pw, py + ph + 10, "现在", COL["dim"], 11, False, "ne")
    n = C.CHART_POINTS
    for key, hist in (("fixed", hf), ("ai", ha)):
        if len(hist) < 2:
            continue
        pts = []
        start = n - len(hist)
        for i, v in enumerate(hist):
            pts += [px + pw * (start + i) / (n - 1.0), py + ph - ph * min(v, top) / top]
        p.line(pts, COL[key], 3)
        p.circle(pts[-2], pts[-1], 5, COL[key], "#0b1020", 2)
        p.text(pts[-2] - 8, pts[-1] - 12, "%.1f" % hist[-1], COL[key], 12, True, "e")
    if hf and ha and hf[-1] > 0.5:
        gain = (hf[-1] - ha[-1]) / hf[-1] * 100
        if gain > 0:
            p.rect(px + 10, py + 2, 190, 26, "#0b1020", COL["ai"], 1, 13)
            p.text(px + 105, py + 15, "AI 让大家少等 %d%%" % gain, COL["ai"], 13, True, "center")


# ================================================================ 对比卡 ==
def _pct(a, b, lower_better=True):
    if a is None or b is None or a <= 0:
        return "", COL["muted"]
    g = (a - b) / a * 100 if lower_better else (b - a) / a * 100
    if abs(g) < 0.5:
        return "持平", COL["muted"]
    return ("%+d%%" % (-g if lower_better else g)), (COL["ai"] if g > 0 else COL["danger"])


def draw_compare(p, world):
    x, y, w, h = CARD_CMP
    p.card(CARD_CMP, "实时对比", COL["ai"])
    f, a = world.fixed, world.ai
    cols = (x + 210, x + 270, x + 344)
    p.text(cols[0], y + 22, "定时", COL["fixed"], 12, True, "e")
    p.text(cols[1], y + 22, "AI", COL["ai"], 12, True, "e")
    p.text(cols[2], y + 22, "AI 效果", COL["muted"], 12, True, "e")
    fw, aw = f.stats.avg_wait(), a.stats.avg_wait()
    rows = [
        ("平均等待（秒）", "--" if fw is None else "%.1f" % fw, "--" if aw is None else "%.1f" % aw,
         _pct(fw, aw)),
        ("正在排队（辆）", "%d" % f.queue_len(), "%d" % a.queue_len(), _pct(f.queue_len(), a.queue_len())),
        ("怠速碳排放（克）", "%d" % f.stats.co2, "%d" % a.stats.co2, _pct(f.stats.co2, a.stats.co2)),
        ("已通过车辆", "%d" % f.stats.passed, "%d" % a.stats.passed,
         ("%+d" % (a.stats.passed - f.stats.passed), COL["ai"] if a.stats.passed >= f.stats.passed else COL["danger"])),
        ("救护车上次等待", "--" if f.stats.amb_wait is None else "%.1f秒" % f.stats.amb_wait,
         "--" if a.stats.amb_wait is None else "%.1f秒" % a.stats.amb_wait, ("", COL["muted"])),
    ]
    for i, (label, fv, av, (gv, gc)) in enumerate(rows):
        ry = y + 46 + i * 24
        if i % 2 == 0:
            p.rect(x + 10, ry - 3, w - 20, 22, COL["panel2"], r=6)
        p.text(x + 18, ry + 8, label, COL["muted"], 12, False, "w")
        p.text(cols[0], ry + 8, fv, COL["text"], 13, True, "e")
        p.text(cols[1], ry + 8, av, COL["text"], 13, True, "e")
        p.text(cols[2], ry + 8, gv, gc, 13, True, "e")
    saved = f.stats.co2 - a.stats.co2
    if saved > 0:
        trees = saved / C.TREE_CO2_PER_DAY
        msg = "AI 已少排放 %d 克 CO2 ≈ %.1f 棵树一天的吸收量" % (saved, trees)
        p.text(x + w / 2, y + h - 16, msg, COL["ai"], 12, True, "center")


# ================================================================ AI 大脑 ==
def draw_brain(p, world):
    x, y, w, h = CARD_BRAIN
    brain, ctrl = world.brain, world.ai.controller
    p.card(CARD_BRAIN, "AI 大脑 · Q 表（经验笔记本）", COL["warn"])
    state = ctrl.state
    starve = state[2] if state else 0
    gx, gy, cell = x + 50, y + 62, 28
    labels = ("0", "1-2", "3-5", "6-9", "10+")
    p.text(gx + cell * N_QUEUE / 2, y + 42, "→ 绿灯方向车辆", COL["muted"], 11, False, "center")
    p.text(x + 12, y + 42, "红灯↓", COL["muted"], 11, False, "nw")
    for gi in range(N_QUEUE):
        p.text(gx + gi * cell + cell / 2, gy + N_QUEUE * cell + 8, labels[gi], COL["dim"], 10, False, "center")
    for ri in range(N_QUEUE):
        p.text(gx - 6, gy + ri * cell + cell / 2, labels[ri], COL["dim"], 10, False, "e")
        for gi in range(N_QUEUE):
            s = (gi, ri, starve)
            pref = brain.preference(s)
            cx0, cy0 = gx + gi * cell, gy + ri * cell
            if pref is None:
                p.rect(cx0 + 1, cy0 + 1, cell - 2, cell - 2, "#1a2140", r=4)
                p.text(cx0 + cell / 2, cy0 + cell / 2, "?", COL["dim"], 11, False, "center")
                continue
            t = min(1.0, abs(pref) / 1.2)
            color = mix(COL["panel2"], "#ff9f43" if pref > 0 else COL["blue"], 0.25 + 0.75 * t)
            p.rect(cx0 + 1, cy0 + 1, cell - 2, cell - 2, color, r=4)
            if t > 0.15:
                p.text(cx0 + cell / 2, cy0 + cell / 2, "换" if pref > 0 else "保", "#0b1020", 11, True, "center")
    if state:
        cx0, cy0 = gx + state[0] * cell, gy + state[1] * cell
        p.rect(cx0 - 1, cy0 - 1, cell + 2, cell + 2, None, "#ffffff", 3, 6)
    # 右侧图例
    lx = x + 212
    for i, (color, txt) in enumerate((("#ff9f43", "想切换"), (COL["blue"], "想保持"), ("#1a2140", "没遇到过"))):
        p.rect(lx, y + 44 + i * 20, 12, 12, color, r=3)
        p.text(lx + 18, y + 50 + i * 20, txt, COL["muted"], 11, False, "w")
    p.text(lx, y + 112, "红灯方向最久等待：", COL["muted"], 11, False, "w")
    for i, txt in enumerate(("<10秒", "10~25秒", ">25秒")):
        on = i == starve
        p.rect(lx + i * 46, y + 124, 44, 20, COL["warn"] if on else "#1a2140", None, 1, 10)
        p.text(lx + i * 46 + 22, y + 134, txt, "#0b1020" if on else COL["dim"], 10, on, "center")
    p.text(lx, y + 160, "已学习 %s 次" % format(brain.updates, ","), COL["text"], 12, True, "w")
    p.text(lx, y + 180, "探索率 %.0f%%" % (brain.epsilon(ctrl.explore) * 100), COL["muted"], 11, False, "w")
    # AI 心声
    p.rect(x + 10, y + h - 46, w - 20, 38, COL["panel2"], r=8)
    p.text(x + 18, y + h - 27, "AI 心声", COL["warn"], 11, True, "w")
    lines = wrap(ctrl.thought, 12, w - 84)[:2]
    top = y + h - 27 - (len(lines) - 1) * 8          # 一行就居中，两行就上下排
    for i, line in enumerate(lines):
        p.text(x + 74, top + i * 16, line, COL["text"], 12, False, "w")


# ================================================================ 控制台 ==
def button_rects():
    x, y, w, h = CARD_CTRL
    rects = []
    for i in range(8):
        bx = x + 16 + (i % 2) * (BTN_W + 10)
        by = y + 78 + (i // 2) * (BTN_H + BTN_GAP)
        rects.append((bx, by, BTN_W, BTN_H))
    return rects


def draw_controls(p, app):
    x, y, w, h = CARD_CTRL
    world = app.world
    p.card(CARD_CTRL, "控制台", COL["blue"])
    name = SCENARIOS[world.scenario][1]
    if SCENARIOS[world.scenario][2] is None:
        name += " · %s %s" % (clock_text(world.clock), period_name(world.clock))
    p.text(x + w - 16, y + 22, name, COL["warn"], 12, True, "e")
    rates = world.rates()
    p.text(x + 16, y + 52, "来车（辆/分钟）", COL["muted"], 11, False, "w")
    for i, d in enumerate(DIRS):
        bx = x + 112 + i * 60
        v = rates[d] * 60
        p.text(bx, y + 52, DIR_NAME[d], COL["muted"], 11, False, "w")
        p.rect(bx + 15, y + 47, 24, 10, "#1a2140", r=5)
        p.rect(bx + 15, y + 47, max(4, min(24, v / 36.0 * 24)), 10,
               COL["danger"] if v > 24 else COL["warn"] if v > 12 else COL["ai"], r=5)
        p.text(bx + 43, y + 52, "%d" % round(v), COL["text"], 11, True, "w")
    for (bx, by, bw, bh), btn in zip(button_rects(), app.buttons):
        label, hot = btn.label(app), btn.active(app)
        p.rect(bx, by, bw, bh, "#24325f" if hot else COL["panel2"], COL["blue"] if hot else COL["border"], 1, 8)
        p.text(bx + bw / 2, by + bh / 2, label, COL["text"], 13, hot, "center")


# ================================================================ 顶栏 ====
def draw_header(p, app):
    world = app.world
    p.text(20, 14, "会学习的红绿灯", COL["text"], 26, True)
    p.text(214, 22, "龙华智慧路口 · AI 交通指挥官", COL["muted"], 14)
    p.text(214, 42, "作者：%s · %s %s" % (C.AUTHOR, C.SCHOOL, C.CLASS_NAME), COL["dim"], 11)
    cx = 700
    p.rect(cx, 14, 180, 40, COL["panel"], COL["border"], 1, 20)
    if SCENARIOS[world.scenario][2] is None:
        p.text(cx + 20, 34, clock_text(world.clock), COL["text"], 20, True, "w")
        p.text(cx + 168, 34, period_name(world.clock), COL["warn"], 13, True, "e")
    else:
        p.text(cx + 90, 34, "固定场景：" + SCENARIOS[world.scenario][1], COL["warn"], 13, True, "center")
    state = "已暂停" if app.paused else "x%d 倍速" % C.SPEEDS[app.speed_i]
    p.rect(900, 14, 110, 40, COL["panel"], COL["border"], 1, 20)
    p.text(955, 34, state, COL["warn"] if app.paused else COL["text"], 13, True, "center")
    p.rect(1020, 14, 240, 40, COL["panel"], COL["border"], 1, 20)
    p.text(1140, 34, "已模拟 %d 分 %02d 秒" % (world.time // 60, world.time % 60), COL["muted"], 12, False, "center")


# ================================================================ 浮层 ====
def _dim(p):
    p.rect(0, 0, C.WIDTH, C.HEIGHT, "#05070f", None, 1, 0, alpha=0.72)


def draw_intro(p):
    _dim(p)
    w, h = 760, 456
    x, y = (C.WIDTH - w) / 2, (C.HEIGHT - h) / 2
    p.rect(x, y, w, h, COL["panel"], COL["ai"], 2, 18)
    p.text(x + w / 2, y + 44, "会学习的红绿灯", COL["text"], 32, True, "center")
    p.text(x + w / 2, y + 82, "一个会从经验中自己学会指挥交通的 AI —— 全部用 Python 从零手写", COL["muted"], 14, False, "center")
    p.text(x + w / 2, y + 108, "作者：%s　%s %s" % (C.AUTHOR, C.SCHOOL, C.CLASS_NAME), COL["warn"], 13, True, "center")
    y += 26
    items = [
        (COL["fixed"], "左边：传统定时红绿灯", "不管有没有车，每 15 秒机械切换一次"),
        (COL["ai"], "右边：AI 自学习红绿灯", "用 Q 学习算法看路况做决定，边用边学，越来越聪明"),
        (COL["warn"], "公平对比", "两个路口迎来完全相同的车流，看谁让大家等得更少、排放更低"),
        (COL["blue"], "你可以试试", "[A] 派救护车   [C] 切换早晚高峰   [T] 让 AI 极速特训   [R] 清空大脑看它从零学"),
    ]
    for i, (col, head, body) in enumerate(items):
        iy = y + 120 + i * 58
        p.rect(x + 40, iy, w - 80, 48, COL["panel2"], None, 1, 12)
        p.rect(x + 40, iy, 6, 48, col, r=3)
        p.text(x + 62, iy + 14, head, col, 15, True, "w")
        p.text(x + 62, iy + 35, body, COL["text"], 13, False, "w")
    bx, by = x + w / 2 - 110, y + h - 96
    p.rect(bx, by, 220, 46, COL["ai"], None, 1, 23)
    p.text(bx + 110, by + 23, "开始观察 ▶", "#0b1020", 17, True, "center")


def draw_help(p):
    _dim(p)
    w, h = 820, 560
    x, y = (C.WIDTH - w) / 2, (C.HEIGHT - h) / 2
    p.rect(x, y, w, h, COL["panel"], COL["blue"], 2, 18)
    p.text(x + 32, y + 28, "AI 是怎么学会指挥交通的？", COL["text"], 22, True)
    steps = [
        ("1 观察", "把路口“翻译”成 AI 能理解的状态：绿灯方向几辆车、红灯方向几辆车、红灯方向最久等了多久。"),
        ("2 决定", "查 Q 表（经验笔记本）：这种路况下“保持”和“切换”哪个分高就选哪个；偶尔随机试试（探索）。"),
        ("3 打分", "奖励 = 负的“着急程度”：在等的车越多、等得越久，分越低。AI 的目标是让总分尽量高。"),
        ("4 学习", "Q ← Q + α×(奖励 + γ×未来最好的分 − Q)。做得好的动作分数变高，下次更愿意这样做。"),
        ("5 守规矩", "安全规则写死在信号灯里：最短绿灯、黄灯、全红清空、最长绿灯、救护车优先 —— AI 想违规也做不到。"),
    ]
    for i, (head, body) in enumerate(steps):
        iy = y + 76 + i * 56
        p.rect(x + 32, iy, 86, 44, COL["panel2"], COL["blue"], 1, 10)
        p.text(x + 75, iy + 22, head, COL["blue"], 14, True, "center")
        for j, line in enumerate(wrap(body, 13, w - 180)[:2]):
            p.text(x + 134, iy + 12 + j * 20, line, COL["text"], 13)
    keys = ("[空格] 暂停    [S] 倍速    [C] 切换场景    [A] 派救护车    [T] 极速训练",
            "[R] 清空大脑    [L] 载入学霸大脑    [V] 保存大脑（电脑版）    [H] 本说明")
    for j, line in enumerate(keys):
        p.text(x + 32, y + 370 + j * 22, line, COL["warn"], 13)
    p.text(x + 32, y + 430, "看右下角的 Q 表：橙色格子 = AI 在这种路况会切换，蓝色 = 会保持，白框 = 现在的路况。", COL["muted"], 13)
    p.text(x + 32, y + 452, "清空大脑后，你会亲眼看到这张表从一片“？”慢慢长出规律 —— 这就是机器学习。", COL["muted"], 13)
    p.text(x + w / 2, y + h - 34, "点击任意位置关闭", COL["dim"], 13, False, "center")


def draw_training(p, trainer):
    _dim(p)
    w, h = 560, 210
    x, y = (C.WIDTH - w) / 2, 230
    p.rect(x, y, w, h, COL["panel"], COL["warn"], 2, 18)
    p.text(x + w / 2, y + 40, "AI 正在“做梦”特训中...", COL["warn"], 22, True, "center")
    p.text(x + w / 2, y + 74, "在看不见的虚拟路口里，快速经历 %d 小时随机车流" % (trainer.total // 3600),
           COL["muted"], 13, False, "center")
    bx, by, bw = x + 40, y + 104, w - 80
    p.rect(bx, by, bw, 22, "#1a2140", None, 1, 11)
    p.rect(bx, by, max(22, bw * trainer.progress), 22, COL["warn"], None, 1, 11)
    p.text(bx + bw / 2, by + 11, "%d%%" % (trainer.progress * 100), "#0b1020", 12, True, "center")
    p.text(x + w / 2, y + 158, "这次已学习 %s 次经验 · 虚拟时间 %d 分钟" % (format(trainer.learned, ","), trainer.done // 60),
           COL["text"], 14, False, "center")
    p.text(x + w / 2, y + 184, "（这就是 AI 训练：在模拟世界里大量练习，比真实世界快几百倍）", COL["dim"], 12, False, "center")


def draw_toasts(p, toasts):
    for i, (msg, ttl) in enumerate(toasts[-3:]):
        tw = text_width(msg, 15) + 40
        x, y = 450 - tw / 2, 168 + i * 44
        p.rect(x, y, tw, 36, "#0b1020", COL["warn"], 2, 18)
        p.text(450, y + 18, msg, COL["warn"], 15, True, "center")


# ================================================================ 总装 ====
def draw_app(app):
    p = Painter()
    p.rect(0, 0, C.WIDTH, C.HEIGHT, COL["bg"])
    world = app.world
    draw_header(p, app)
    draw_intersection(p, world.fixed, "fixed", app.frame)
    draw_intersection(p, world.ai, "ai", app.frame)
    draw_chart(p, world)
    draw_compare(p, world)
    draw_brain(p, world)
    draw_controls(p, app)
    draw_toasts(p, app.toasts)
    if app.trainer is not None:
        draw_training(p, app.trainer)
    elif app.overlay == "intro":
        draw_intro(p)
    elif app.overlay == "help":
        draw_help(p)
    return p.cmds
