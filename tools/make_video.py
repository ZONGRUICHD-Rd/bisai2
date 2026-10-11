# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
生成《会学习的红绿灯》作品介绍视频
==================================
画面：程序真实运行的每一帧（和电脑版、网页版同一份绘图指令清单，用 Pillow 画成图片）
     + 讲解卡片（同样用绘图指令画）+ 字幕。
声音：中文配音（edge-tts 合成）+ 很轻的背景音乐（程序生成）。
用法：
    pip install pillow numpy edge-tts
    python tools/make_video.py            # 生成 作品介绍视频.mp4 和 作品介绍视频字幕.srt
需要 ffmpeg。
"""
import asyncio
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import numpy as np                                      # noqa: E402
from PIL import Image, ImageEnhance, ImageFilter        # noqa: E402

import pil_backend as pb                                # noqa: E402
from smartlight import config as C                      # noqa: E402
from smartlight.brain import QBrain                     # noqa: E402
from smartlight.render import CARD_BRAIN, CARD_CMP, CHART, PANELS, Painter, _car_box  # noqa: E402
from smartlight.scenario import SCENARIOS, day_rates    # noqa: E402
from smartlight.traffic import AXIS_OF, DIR_NAME, DIRS  # noqa: E402
from smartlight.ui import App                           # noqa: E402
from smartlight.world import compare                    # noqa: E402

BUILD = os.path.join(ROOT, "video_build")
OUT = os.path.join(ROOT, "作品介绍视频.mp4")
SRT = os.path.join(ROOT, "作品介绍视频字幕.srt")
VW, VH, FPS = 1920, 1080, 30
APP_K, APP_X, BAND_Y = 1.25, 160, 975          # 程序画面放大 1.25 倍放在中间，下面留字幕条
VOICE = "zh-CN-YunxiNeural"
LEAD, TAIL = 0.5, 0.9                          # 每段配音前后留白（秒）
COL = C.COL
WHITE = "#ffffff"
CA = "/root/.ccr/ca-bundle.crt"

# ============================================================== 分镜和台词 ==
SHOTS = [
    dict(key="title", kind="card", min=7,
         text="大家好！我是深圳市龙华区和平实验小学四年级三班的欧阳卓元。我的作品叫《会学习的红绿灯》，它是一个用 Python 从零手写人工智能算法、会自己学会指挥十字路口的红绿灯。"),
    dict(key="problem", kind="card", min=10,
         text="每天上学路上，我常常看到：一边排着长长的车队，另一边一辆车都没有，可红灯还是要亮满时间。"
              "因为传统红绿灯是定时的，它不会看路况。"
              "在龙华，很多人早上往南去上班，晚上再回来，早晚高峰的车流方向正好相反，一个固定的时间表很难照顾好所有时段。"),
    dict(key="idea", kind="card", min=8,
         text="于是我想：能不能让红绿灯像人一样，自己观察、自己尝试、自己总结经验？这正是人工智能里的强化学习。"),
    dict(key="intro", kind="app", min=18, chapter=("01", "公平对比"),
         text="这就是我的作品。左边是传统定时红绿灯，每十五秒机械地切换一次；右边是我写的 AI 红绿灯。"
              "两个路口迎来完全相同的车流，每一辆车都在同一时刻、从同一个方向到达，这样的比较才公平。"),
    dict(key="rush", kind="app", min=34, chapter=("02", "早高峰"),
         text="现在把速度调到八倍，进入早高峰，从北边往南开的车特别多。"
              "左边的定时灯给两个方向一样长的绿灯，车越排越长；右边的 AI 会把更多绿灯时间分给车多的方向，排队一直很短。"
              "下面的曲线记录着平均等待时间，右上角的对比卡显示，AI 让大家少等了一大半，还少排放了很多尾气。"),
    dict(key="ambulance", kind="app", min=22, chapter=("03", "救护车优先"),
         text="再来派一辆救护车。AI 路口发现救护车在红灯方向，马上为它开绿灯；定时路口的救护车却只能在红灯前干等。"
              "救护车优先、最短绿灯和最长绿灯，都写在安全规则层里，AI 想违规也做不到。"),
    dict(key="principle", kind="card", min=30,
         text="AI 是怎么学会的呢？"
              "第一步，观察：把路口翻译成三个数，绿灯方向几辆车、红灯方向几辆车、红灯方向最久等了多久。"
              "第二步，决定：查 Q 表，也就是 AI 的经验笔记本，看看保持和切换哪个分数高。"
              "第三步，打分：等的车越多、等得越久，分数就越低。"
              "第四步，学习：用这个公式修正笔记本，好的动作分数变高，下次就更愿意这样做。"),
    dict(key="relearn", kind="app", min=27, chapter=("04", "从零学起"),
         text="为了证明 AI 真的是自己学会的，我按 R 键清空它的大脑。Q 表变成了一片问号，AI 一开始比定时灯还笨。"
              "但它边用边学，几分钟后，Q 表慢慢长出了规律，它又反超了定时灯。"
              "我还可以按 T 键，让它在看不见的虚拟路口里做梦练习两个小时，几秒钟就学完了。"),
    dict(key="results", kind="card", min=12,
         text="我用同一股车流，给两种红绿灯做了五个场景的考试。早高峰、晚高峰、平峰、深夜和智能一天，AI 红绿灯全部获胜，平均减少了百分之六十的等待时间。"),
    dict(key="tech", kind="card", min=16,
         text="整个作品只用 Python 自带的标准库，Q 学习算法的每一行都是我自己写的。"
              "我把画面抽象成一份绘图指令清单，同一份代码可以在电脑窗口、网页和手机上运行，连这个视频的画面也是用它一帧一帧画出来的。"
              "我还写了九个自动测试，保证车不会追尾、不会闯红灯。"),
    dict(key="outro", kind="card", min=9,
         text="以后，我想让多个路口的 AI 互相配合，形成绿波带，再加入行人和左转。欢迎打开网页亲自试一试，谢谢大家！"),
]


# ================================================================ 配音 ====
async def _tts(text, mp3):
    import certifi
    if os.path.exists(CA):                      # 云端环境的网络代理需要它
        certifi.where = lambda: CA
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate="+4%", proxy=os.environ.get("HTTPS_PROXY"))
    sents = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "SentenceBoundary":
                sents.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))
    return sents


def audio_len(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", path])
    return float(out.strip())


def prepare_voice(shot):
    tag = hashlib.md5((VOICE + shot["text"]).encode("utf-8")).hexdigest()[:10]
    mp3 = os.path.join(BUILD, "voice_%s_%s.mp3" % (shot["key"], tag))
    meta = mp3 + ".json"
    if not os.path.exists(meta):
        for attempt in range(4):
            try:
                sents = asyncio.run(_tts(shot["text"], mp3))
                break
            except Exception as e:                  # 网络偶尔会断，重试
                print("  配音失败，重试：", e)
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError("配音失败")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(sents, f, ensure_ascii=False)
    with open(meta, encoding="utf-8") as f:
        sents = json.load(f)
    shot["mp3"] = mp3
    shot["voice_len"] = audio_len(mp3)
    shot["dur"] = max(shot["min"], LEAD + shot["voice_len"] + TAIL)
    shot["sents"] = [(LEAD + s, d) for s, d, _ in sents]      # 每句话在这个镜头里开始的时间
    shot["captions"] = make_captions(sents)


def make_captions(sents, limit=32):
    """一句话太长就按逗号拆成几条字幕，时间按字数分配。"""
    caps = []
    for start, dur, text in sents:
        parts, cur = [], ""
        for ch in text:
            cur += ch
            if ch in "，；：、" and len(cur) >= 8:
                parts.append(cur)
                cur = ""
        if cur:
            parts.append(cur)
        merged = []
        for part in parts:
            if merged and len(merged[-1]) + len(part) <= limit:
                merged[-1] += part
            else:
                merged.append(part)
        total = sum(len(m) for m in merged) or 1
        t = start
        for m in merged:
            d = dur * len(m) / total
            caps.append((LEAD + t, LEAD + t + d, m.rstrip("，；：、。")))
            t += d
    return caps


def sent_start(shot, i):
    s = shot["sents"]
    return s[min(i, len(s) - 1)][0] if s else 0.0


# ================================================================ 叠加层 ==
def overlay(shot, t, keys=()):
    p = Painter()
    p.rect(0, BAND_Y, VW, VH - BAND_Y, "#070b16")
    p.line([0, BAND_Y, VW, BAND_Y], COL["border"], 1)
    cap = next((c for a, b, c in shot["captions"] if a <= t < b + 0.15), None)
    if cap:
        p.text(VW / 2, BAND_Y + 53, cap, WHITE, 38, False, "center")
    if shot["kind"] == "app":
        num, title = shot["chapter"]
        p.text(80, 64, num, COL["ai"], 56, True, "center")
        p.line([56, 104, 104, 104], COL["ai"], 3)
        for i, ch in enumerate(title):
            p.text(80, 150 + i * 46, ch, COL["text"], 36, True, "center")
        for t0, key, label in keys:
            if 0 <= t - t0 < 2.6:
                pop = min(1.0, (t - t0) / 0.15)
                s = 100 * (0.7 + 0.3 * pop)
                p.rect(1840 - s / 2, 430 - s / 2, s, s, COL["panel2"], COL["warn"], 4, 18)
                p.text(1840, 430, key, COL["warn"], 50 * (0.7 + 0.3 * pop), True, "center")
                p.text(1840, 512, "按下", COL["muted"], 22, False, "center")
                for j, line in enumerate((label[:4], label[4:])):
                    if line:
                        p.text(1840, 548 + j * 32, line, COL["text"], 26, True, "center")
    return p.cmds


def ring(p, box, color, width=4, r=16, pad=6):
    x, y, w, h = box
    p.rect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, None, color, width, r)


def ambulance_rings(app, frame):
    p = Painter()
    pulse = 14 + 6 * math.sin(frame / 4.0)
    for key, inter in (("fixed", app.world.fixed), ("ai", app.world.ai)):
        ox, oy = PANELS[key]
        for d in DIRS:
            for car in inter.lanes[d].cars:
                if car.kind != "amb":
                    continue
                x, y, w, h, _ = _car_box(d, car.s, car.length, ox, oy)
                cx, cy = x + w / 2, y + h / 2
                if ox <= cx <= ox + C.VIEW and oy <= cy <= oy + C.VIEW:
                    p.circle(cx, cy, pulse + 10, None, COL["danger"], 3)
    return p.cmds


# ============================================================ 程序镜头 ====
def frames_intro(shot, app):
    n = int(shot["dur"] * FPS)
    s2 = sent_start(shot, 1)
    for i in range(n):
        t = i / FPS
        app.overlay = "intro" if t < 5.5 else None
        app.tick()
        cmds = app.render()
        p = Painter()
        if 6.0 <= t < s2:
            ring(p, PANELS["fixed"] + (C.VIEW, C.VIEW), COL["fixed"], 5)
            ring(p, PANELS["ai"] + (C.VIEW, C.VIEW), COL["ai"], 5)
        yield "app", cmds + p.cmds, overlay(shot, t)


def frames_rush(shot, app):
    n = int(shot["dur"] * FPS)
    s3 = sent_start(shot, 2)
    keys = [(0.3, "S", "8 倍速")]
    for i in range(n):
        t = i / FPS
        if i == int(0.3 * FPS):
            app.speed_i = 2
            app.toast("倍速 x8", 1.2)
        app.tick()
        p = Painter()
        if t >= s3:
            ring(p, CHART, COL["warn"], 4)
            ring(p, CARD_CMP, COL["warn"], 4)
        yield "app", app.render() + p.cmds, overlay(shot, t, keys)


def frames_ambulance(shot, app):
    w = app.world
    app.speed_i = 1
    # 先在后台快进到“两个路口都是同一方向绿灯、定时灯还要亮很久”的时刻，救护车从红灯方向来
    for _ in range(2000):
        f, a = w.fixed.light, w.ai.light
        cd = w.fixed.controller.countdown(f)
        if f.stage == "G" and a.stage == "G" and f.green_axis == a.green_axis and cd and cd > 10:
            break
        w.step(C.SIM_DT)
    red = w.fixed.light.red_axis
    n = int(shot["dur"] * FPS)
    keys = [(1.0, "A", "派救护车")]
    for i in range(n):
        t = i / FPS
        if i == int(1.0 * FPS):
            options = [d for d in DIRS if AXIS_OF[d] == red]
            origin = min(options, key=lambda d: len(w.ai.lanes[d].cars) + len(w.ai.lanes[d].backlog))
            spec = w.source.make_spec("amb")
            for inter in w.pair:
                inter.add_car(origin, spec)
            app.toast("救护车从%s边开来了！看哪个路口先给它让路" % DIR_NAME[origin], 4)
        app.tick()
        p = Painter()
        if t > 1.0:
            p.cmds += ambulance_rings(app, app.frame)
        if w.fixed.stats.amb_wait is not None:
            x, y, cw, ch = CARD_CMP
            ring(p, (x + 10, y + 142, cw - 20, 22), COL["danger"], 3, 8, 2)
        yield "app", app.render() + p.cmds, overlay(shot, t, keys)


def frames_relearn(shot, app):
    n = int(shot["dur"] * FPS)
    s2, t_train = sent_start(shot, 1), sent_start(shot, 3) + 1.2
    keys = [(0.4, "R", "清空大脑"), (t_train, "T", "极速训练")]
    for i in range(n):
        t = i / FPS
        if i == int(0.4 * FPS):
            app.reset_brain()
            app.speed_i = 2
        if i == int(t_train * FPS):
            stats = (app.world.fixed.stats.avg_wait(), app.world.ai.stats.avg_wait())
            print("    训练前：定时 %.1f 秒  AI %.1f 秒" % stats)
            app.train()
        fast = 2.5 <= t < t_train - 0.5            # 快进：一帧推进四次（32 倍速）
        app.tick()
        if fast and app.trainer is None:
            for _ in range(3):
                app.tick()
        p = Painter()
        if s2 > t >= 1.5 or t >= t_train + 4.5:
            ring(p, CARD_BRAIN, COL["warn"], 4)
        extra = []
        if fast:
            q = Painter()
            q.rect(1780, 250, 120, 56, COL["panel2"], COL["blue"], 2, 28)
            q.text(1840, 278, "快进 x32", COL["blue"], 24, True, "center")
            extra = q.cmds
        yield "app", app.render() + p.cmds, overlay(shot, t, keys) + extra


# ============================================================ 卡片镜头 ====
def card_bg(p):
    p.rect(0, 0, VW, VH, COL["bg"])


def traffic_light(p, x, y, lit, scale=1.0):
    w, h, r = 150 * scale, 420 * scale, 52 * scale
    p.rect(x, y, w, h, "#070b18", COL["border"], 3, 75 * scale)
    for i, color in enumerate(("#ff3b5c", "#ffc83d", "#33f08e")):
        cy = y + (80 + i * 130) * scale
        cx = x + w / 2
        if i == lit:
            p.circle(cx, cy, r * 1.45, pb_mix(color, COL["bg"], 0.75))
            p.circle(cx, cy, r, color)
        else:
            p.circle(cx, cy, r, pb_mix(color, "#070b18", 0.8))


def pb_mix(a, b, t):
    ra, ga, ba = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    rb, gb, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


def frames_title(shot, bg_path, outro=False):
    n = int(shot["dur"] * FPS)
    for i in range(n):
        t = i / FPS
        p = Painter()
        p.cmds.append(["img", bg_path, 0, 0, VW, VH])
        traffic_light(p, 250, 230, int(t) % 3)
        if not outro:
            p.text(520, 360, "会学习的红绿灯", WHITE, 124, True, "w")
            p.text(526, 490, "龙华智慧路口 · AI 交通指挥官", COL["muted"], 50, False, "w")
            p.rect(526, 570, 940, 64, COL["panel"], COL["ai"], 2, 32)
            p.text(996, 602, "Python 小学组 · 纯手写 Q 学习 · 0 个第三方库", COL["ai"], 30, True, "center")
            p.text(526, 700, "作者：%s" % C.AUTHOR, COL["warn"], 44, True, "w")
            p.text(526, 762, "%s　%s" % (C.SCHOOL, C.CLASS_NAME), COL["text"], 34, False, "w")
            p.text(526, 815, C.CONTEST, COL["muted"], 28, False, "w")
        else:
            p.text(520, 330, "谢谢观看！", WHITE, 120, True, "w")
            p.text(526, 450, "在线体验：zongruichd-rd.github.io/bisai2", COL["ai"], 40, True, "w")
            p.text(526, 510, "源代码：github.com/ZONGRUICHD-Rd/bisai2", COL["muted"], 34, False, "w")
            if t >= 0.6:
                for j, chip in enumerate(("多路口绿波带", "行人和左转", "真实交通数据")):
                    x = 526 + j * 330
                    p.rect(x, 600, 300, 66, COL["panel2"], COL["blue"], 2, 33)
                    p.text(x + 150, 633, chip, COL["text"], 30, True, "center")
                p.text(526, 720, "下一步想做的", COL["dim"], 26, False, "w")
            p.text(526, 820, "作者：%s　%s %s" % (C.AUTHOR, C.SCHOOL, C.CLASS_NAME), COL["warn"], 34, True, "w")
        yield "card", p.cmds, overlay(shot, t)


def frames_problem(shot):
    n = int(shot["dur"] * FPS)
    s3 = sent_start(shot, 2)
    for i in range(n):
        t = i / FPS
        p = Painter()
        card_bg(p)
        p.text(120, 100, "问题从哪里来？", WHITE, 60, True, "w")
        # 左：定时灯空等
        p.rect(120, 170, 820, 740, COL["panel"], COL["border"], 2, 24)
        p.text(160, 225, "定时红绿灯：不看路况", COL["fixed"], 40, True, "w")
        p.rect(160, 470, 740, 90, COL["road"])
        p.rect(560, 270, 90, 560, COL["road"])
        p.rect(548, 470, 4, 90, COL["mark"])
        for k in range(min(8, int(t * 3) + 1)):              # 车一辆一辆排上来
            p.rect(500 - k * 50, 498, 40, 22, C.CAR_COLORS[k % len(C.CAR_COLORS)], None, 1, 6)
        traffic_light(p, 470, 330, 0, 0.32)
        traffic_light(p, 670, 600, 2, 0.32)
        p.text(160, 610, "红灯：车越排越长", COL["danger"], 30, True, "w")
        p.text(690, 760, "绿灯：一辆车都没有", COL["ai"], 30, True, "w")
        p.text(530, 870, "每 15 秒机械切换一次", COL["muted"], 30, False, "center")
        # 右：龙华潮汐车流
        if t >= s3 - 0.2:
            a = min(1.0, (t - s3 + 0.2) / 0.4)
            p.rect(1000, 170, 800, 740, COL["panel"], COL["border"], 2, 24)
            p.text(1040, 225, "龙华的“潮汐车流”", COL["warn"], 40, True, "w")
            p.rect(1360, 300, 80, 520, COL["road"])
            p.rect(1280, 290, 240, 60, COL["panel2"], COL["border"], 2, 30)
            p.text(1400, 320, "龙华（住家）", WHITE, 30, True, "center")
            p.rect(1260, 780, 280, 60, COL["panel2"], COL["border"], 2, 30)
            p.text(1400, 810, "福田 · 南山（上班）", WHITE, 28, True, "center")
            if a >= 1:
                p.poly([1190, 400, 1190, 640, 1150, 640, 1210, 720, 1270, 640, 1230, 640, 1230, 400],
                       COL["fixed"])
                p.text(1210, 380, "早上往南", COL["fixed"], 30, True, "s")
                p.poly([1570, 720, 1570, 480, 1530, 480, 1590, 400, 1650, 480, 1610, 480, 1610, 720],
                       COL["blue"])
                p.text(1590, 760, "晚上回来", COL["blue"], 30, True, "n")
                p.text(1400, 875, "早晚高峰方向正好相反", COL["muted"], 30, False, "center")
        yield "card", p.cmds, overlay(shot, t)


def frames_idea(shot):
    n = int(shot["dur"] * FPS)
    s2 = sent_start(shot, 1)
    chips = ("观察", "尝试", "看结果", "总结经验")
    for i in range(n):
        t = i / FPS
        p = Painter()
        card_bg(p)
        p.text(VW / 2, 300, "能不能让红绿灯", WHITE, 70, True, "center")
        p.text(VW / 2, 400, "自己学会看路况？", COL["warn"], 70, True, "center")
        shown = 0 if t < 2.5 else min(4, int((t - 2.5) / 0.7) + 1)
        x0 = VW / 2 - (4 * 260 + 3 * 70) / 2
        for k in range(shown):
            x = x0 + k * 330
            p.rect(x, 540, 260, 100, COL["panel2"], COL["ai"], 3, 50)
            p.text(x + 130, 590, chips[k], COL["text"], 42, True, "center")
            if k < 3:
                p.poly([x + 275, 575, x + 315, 590, x + 275, 605], COL["muted"])
        if t >= s2:
            p.text(VW / 2, 760, "这就是人工智能里的「强化学习」", COL["ai"], 50, True, "center")
            p.text(VW / 2, 840, "不用人告诉答案，AI 自己从经验里学", COL["muted"], 34, False, "center")
        yield "card", p.cmds, overlay(shot, t)


def frames_principle(shot, brain):
    n = int(shot["dur"] * FPS)
    starts = [sent_start(shot, k) for k in range(1, 5)]
    steps = (("1", "观察", ("把路口翻译成 3 个数：", "绿灯方向几辆车", "红灯方向几辆车", "红灯方向最久等多久")),
             ("2", "决定", ("查 Q 表（经验笔记本）", "保持和切换", "谁的分数高选谁")),
             ("3", "打分", ("奖励 = − 着急程度", "等的车越多、越久", "分数越低")),
             ("4", "学习", ("用公式修正笔记本", "好动作分数变高", "+ 经验回放：复习旧经验")))
    for i in range(n):
        t = i / FPS
        p = Painter()
        card_bg(p)
        p.text(120, 100, "AI 是怎么学会的？", WHITE, 60, True, "w")
        p.text(1800, 100, "Q 学习（强化学习）", COL["muted"], 34, False, "e")
        for k, (num, name, lines) in enumerate(steps):
            if t < starts[k] - 0.1:
                continue
            x = 120 + k * 430
            active = starts[k] <= t < (starts[k + 1] if k < 3 else 1e9)
            p.rect(x, 170, 380, 430, COL["panel"], COL["ai"] if active else COL["border"], 4 if active else 2, 24)
            p.circle(x + 60, 235, 32, COL["ai"] if active else COL["panel2"])
            p.text(x + 60, 235, num, "#0b1020" if active else COL["text"], 34, True, "center")
            p.text(x + 110, 235, name, WHITE, 44, True, "w")
            for j, line in enumerate(lines):
                p.text(x + 30, 315 + j * 50, line, COL["text"] if j else COL["warn"], 29, j == 0, "w")
            if k == 1:                                     # 真正的 Q 表缩略图
                for r in range(5):
                    for g in range(5):
                        pref = brain.preference((g, r, 0))
                        col = "#1a2140" if pref is None else (
                            pb_mix(COL["panel2"], "#ff9f43" if pref > 0 else COL["blue"],
                                   0.3 + 0.7 * min(1, abs(pref) / 1.2)))
                        p.rect(x + 100 + g * 36, 470 + r * 22, 33, 19, col, None, 1, 4)
            if k < 3:
                p.poly([x + 392, 370, x + 418, 385, x + 392, 400], COL["muted"])
        if t >= starts[3]:
            p.rect(120, 650, 1680, 230, COL["panel"], COL["warn"], 3, 24)
            p.text(VW / 2, 730, "Q[s][a]  ←  Q[s][a] + α × ( 奖励 + γ^t × 未来最好的分 − Q[s][a] )",
                   COL["warn"], 44, True, "center")
            p.text(VW / 2, 810, "α = 0.1 学习率      γ = 0.95 每秒折扣      t = 这个动作持续的秒数",
                   COL["muted"], 30, False, "center")
        yield "card", p.cmds, overlay(shot, t)


def exam_rows():
    brain = QBrain()
    brain.load(os.path.join(ROOT, "smartlight", "pretrained_brain.json"))
    rows = []
    for key, name, minute in SCENARIOS:
        rates = (lambda tt: day_rates(6 * 60 + tt)) if minute is None else day_rates(minute)
        r = compare(brain, rates, seconds=1200, seed=11)
        rows.append((name, r["fixed"]["avg_wait"], r["ai"]["avg_wait"]))
    rows.sort(key=lambda r: -r[1])
    return rows


def frames_results(shot, rows):
    n = int(shot["dur"] * FPS)
    avg = sum((f - a) / f for _, f, a in rows) / len(rows) * 100
    X = lambda v: 420 + v / 12.0 * 1000                   # noqa: E731
    for i in range(n):
        t = i / FPS
        p = Painter()
        card_bg(p)
        p.text(120, 100, "考试成绩：同一股车流，各跑 20 分钟", WHITE, 56, True, "w")
        p.circle(140, 185, 12, COL["fixed"])
        p.text(162, 185, "定时红绿灯", COL["muted"], 30, False, "w")
        p.circle(400, 185, 12, COL["ai"])
        p.text(422, 185, "AI 红绿灯", COL["muted"], 30, False, "w")
        p.text(640, 185, "（每辆车平均等待，秒）", COL["dim"], 28, False, "w")
        p.text(1800, 185, "AI 减少等待", COL["muted"], 30, False, "e")
        for v in range(0, 13, 2):
            p.line([X(v), 230, X(v), 800], "#1f2a4f", 2)
            p.text(X(v), 830, "%d" % v, COL["dim"], 26, False, "center")
        for k, (name, f, a) in enumerate(rows):
            y = 280 + k * 115
            prog = max(0.0, min(1.0, (t - 0.6 - k * 0.35) / 1.0))
            ease = 1 - (1 - prog) ** 3
            cur = f + (a - f) * ease
            p.text(120, y, name, WHITE, 38, True, "w")
            p.line([X(cur), y, X(f), y], "#3a4466", 10)
            p.circle(X(f), y, 16, COL["fixed"])
            p.text(X(f) + 28, y, "%.1f" % f, COL["fixed"], 32, True, "w")
            p.circle(X(cur), y, 16, COL["ai"])
            if prog >= 1:
                p.text(X(a) - 28, y, "%.1f" % a, COL["ai"], 32, True, "e")
                p.text(1800, y, "-%d%%" % round((f - a) / f * 100), COL["ai"], 44, True, "e")
        if t >= 3.0:
            p.rect(560, 878, 800, 70, COL["panel2"], COL["ai"], 3, 35)
            p.text(VW / 2, 913, "5 个场景全部获胜 · 平均减少等待 %d%%" % round(avg), COL["ai"], 36, True, "center")
        yield "card", p.cmds, overlay(shot, t)


def frames_tech(shot):
    n = int(shot["dur"] * FPS)
    s2, s3 = sent_start(shot, 1), sent_start(shot, 2)
    img = os.path.join(ROOT, "docs", "images")
    items = (("0", "个第三方库", "只用 Python 自带的标准库", 0.0),
             ("Q", "纯手写 Q 学习", "+ 经验回放 + 安全规则层", 1.5),
             ("1", "套代码，四种画法", "电脑 · 网页 · 手机 · 视频", s2),
             ("9", "个自动测试", "不追尾、不闯红灯、AI 胜过定时灯", s3))
    for i in range(n):
        t = i / FPS
        p = Painter()
        card_bg(p)
        p.text(120, 100, "技术亮点", WHITE, 60, True, "w")
        for k, (big, head, sub, at) in enumerate(items):
            if t < at:
                continue
            y = 170 + k * 190
            p.rect(120, y, 860, 160, COL["panel"], COL["border"], 2, 24)
            p.text(210, y + 80, big, COL["ai"], 80, True, "center")
            p.text(300, y + 58, head, WHITE, 40, True, "w")
            p.text(300, y + 112, sub, COL["muted"], 30, False, "w")
        if t >= s2:
            p.cmds.append(["img", os.path.join(img, "demo_desktop.jpg"), 1060, 170, 740, 451])
            p.text(1430, 650, "电脑版（tkinter）", COL["muted"], 26, False, "center")
            p.cmds.append(["img", os.path.join(img, "demo_phone.jpg"), 1150, 690, 560, 235])
            p.text(1430, 950, "手机全屏版（Pyodide 在浏览器里运行 Python）", COL["muted"], 26, False, "center")
        yield "card", p.cmds, overlay(shot, t)


# ================================================================ 渲染 ====
_card_cache = {}


def render_job(job):
    kind, main, over = job
    if kind == "app":
        frame = Image.new("RGB", (VW, VH), COL["bg"])
        frame.paste(pb.render(main, 1600, 975, k=APP_K, ss=2), (APP_X, 0))
    else:
        key = hashlib.md5(json.dumps(main).encode("utf-8")).hexdigest()
        if key not in _card_cache:
            _card_cache.clear()
            _card_cache[key] = pb.render(main, VW, VH, k=1.0, ss=2)
        frame = _card_cache[key].copy()
    pb.draw_cmds(frame, over)
    return frame.tobytes()


def make_title_bg():
    path = os.path.join(BUILD, "title_bg.png")
    app = App(platform="video")
    app.overlay, app.speed_i = None, 2
    app.world.scenario = 1
    for _ in range(450):
        app.tick()
    img = pb.render(app.render(), VW, int(VW * 780 / 1280), k=VW / 1280.0, ss=1)
    img = img.crop((0, 0, VW, VH)).filter(ImageFilter.GaussianBlur(10))
    ImageEnhance.Brightness(img).enhance(0.35).save(path)
    return path


def all_frames(rows):
    bg = make_title_bg()
    app_a = App(platform="video")
    app_a.world.scenario = 1                       # 早高峰
    app_b = App(platform="video")
    app_b.overlay = None
    app_b.world.scenario = 1
    gens = {
        "title": lambda s: frames_title(s, bg),
        "problem": frames_problem,
        "idea": frames_idea,
        "intro": lambda s: frames_intro(s, app_a),
        "rush": lambda s: frames_rush(s, app_a),
        "ambulance": lambda s: frames_ambulance(s, app_a),
        "principle": lambda s: frames_principle(s, app_a.brain),
        "relearn": lambda s: frames_relearn(s, app_b),
        "results": lambda s: frames_results(s, rows),
        "tech": frames_tech,
        "outro": lambda s: frames_title(s, bg, outro=True),
    }
    for shot in SHOTS:
        print("镜头 %-10s %5.1f 秒" % (shot["key"], shot["dur"]))
        for job in gens[shot["key"]](shot):
            yield job


def list_or_stream(gen):
    for job in gen:
        yield job


# ================================================================ 声音 ====
def make_music(total, path):
    sr = 44100
    t = np.arange(int(total * sr)) / sr
    chords = ((130.81, 164.81, 196.00, 246.94), (110.00, 130.81, 164.81, 196.00),
              (87.31, 110.00, 130.81, 164.81), (98.00, 123.47, 146.83, 164.81))
    out = np.zeros_like(t)
    seg = 4.0
    for k in range(int(total / seg) + 1):
        notes = chords[k % len(chords)]
        a, b = k * seg - 1.0, (k + 1) * seg + 1.0
        m = (t >= a) & (t < b)
        tt = t[m] - a
        env = np.sin(np.pi * np.clip(tt / (b - a), 0, 1)) ** 2
        for f in notes:
            out[m] += env * (np.sin(2 * np.pi * f * t[m]) + 0.4 * np.sin(2 * np.pi * f * 2.003 * t[m]))
    out /= np.max(np.abs(out)) + 1e-9
    fade = np.minimum(1, np.minimum(t / 2.0, (total - t) / 3.0))
    out = (out * fade * 0.6 * 32767).astype(np.int16)
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out.tobytes())


def make_audio(total):
    music = os.path.join(BUILD, "music.wav")
    make_music(total, music)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    parts, start = [], 0.0
    for idx, shot in enumerate(SHOTS):
        cmd += ["-i", shot["mp3"]]
        ms = int((start + LEAD) * 1000)
        parts.append("[%d:a]aresample=44100,adelay=%d|%d[v%d]" % (idx, ms, ms, idx))
        start += shot["dur"]
    cmd += ["-i", music]
    n = len(SHOTS)
    filt = ";".join(parts) + ";" + "".join("[v%d]" % i for i in range(n)) + \
        "amix=inputs=%d:normalize=0,volume=1.3[voice];[%d:a]volume=0.07[bgm];" % (n, n) + \
        "[voice][bgm]amix=inputs=2:normalize=0:duration=longest,atrim=0:%.2f,alimiter=limit=0.89:level=0[out]" % total
    out = os.path.join(BUILD, "audio.m4a")
    cmd += ["-filter_complex", filt, "-map", "[out]", "-c:a", "aac", "-b:a", "160k", out]
    subprocess.check_call(cmd)
    return out


def write_srt():
    def ts(x):
        ms = int(round(x * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
    lines, start, k = [], 0.0, 1
    for shot in SHOTS:
        for a, b, text in shot["captions"]:
            lines.append("%d\n%s --> %s\n%s\n" % (k, ts(start + a), ts(start + b), text))
            k += 1
        start += shot["dur"]
    with open(SRT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ================================================================ 总装 ====
def main():
    os.makedirs(BUILD, exist_ok=True)
    print("1/4 合成配音 ...")
    for shot in SHOTS:
        prepare_voice(shot)
    total = sum(s["dur"] for s in SHOTS)
    print("    总时长 %d 分 %02d 秒" % (total // 60, total % 60))
    print("2/4 考试成绩 ...")
    rows = exam_rows()
    print("3/4 逐帧渲染画面 ...")
    silent = os.path.join(BUILD, "video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", "%dx%d" % (VW, VH), "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                            silent], stdin=subprocess.PIPE)
    t0 = time.time()
    done = 0
    with Pool(max(1, os.cpu_count() or 1)) as pool:
        batch = []
        for job in list_or_stream(all_frames(rows)):
            batch.append(job)
            if len(batch) == 64:
                for data in pool.map(render_job, batch, chunksize=4):   # 一批一批来，内存不会爆
                    enc.stdin.write(data)
                done += len(batch)
                batch = []
                if done % 640 == 0:
                    print("    已渲染 %d 帧  %.0f 秒" % (done, time.time() - t0))
        for data in pool.map(render_job, batch, chunksize=4):
            enc.stdin.write(data)
    enc.stdin.close()
    enc.wait()
    print("4/4 混音并合成 ...")
    audio = make_audio(total)
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", audio, "-c:v", "copy",
                           "-c:a", "copy", "-shortest", "-movflags", "+faststart", OUT])
    write_srt()
    size = os.path.getsize(OUT) / 1e6
    print("完成：%s（%.1f MB，%d 分 %02d 秒）" % (OUT, size, total // 60, total % 60))


if __name__ == "__main__":
    main()
