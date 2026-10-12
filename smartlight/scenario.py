# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组 · 代码由 AI 编程助手 Claude 协助编写
"""
车流场景：一天中不同时间，各个方向来多少车
==========================================
龙华有很多居民早上往南去福田、南山上班，晚上再回到龙华，
所以“早高峰南下的车多（车从北边来），晚高峰北上的车多（车从南边来）”。
数值单位：每个方向每秒平均来多少辆车。
"""
import math
import random

from . import config as C
from .traffic import DIRS, CarSpec


def _gauss(x, mu, sigma):
    return math.exp(-((x - mu) ** 2) / (2 * sigma * sigma))


def _clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def day_rates(minute):
    """一天里第 minute 分钟（0~1440）的车流强度。"""
    h = (minute % 1440) / 60.0
    daylight = _clamp01((h - 5.5) / 1.5) * _clamp01((23.5 - h) / 1.5)
    morning = _gauss(h, 8.0, 0.8)
    evening = _gauss(h, 18.3, 0.9)
    base = 0.03 + 0.09 * daylight
    return {
        "N": base + 0.43 * morning + 0.06 * evening,   # 从北边来、往南开：早高峰主力
        "S": base + 0.07 * morning + 0.41 * evening,   # 从南边来、往北开：晚高峰主力
        "E": base + 0.05 * morning + 0.05 * evening,
        "W": base + 0.06 * morning + 0.04 * evening,
    }


# (代号, 名字, 固定在几点的车流；None 表示时间流动)
SCENARIOS = (
    ("day", "智能一天", None),
    ("morning", "早高峰", 8 * 60),
    ("evening", "晚高峰", 18 * 60 + 20),
    ("flat", "平峰", 14 * 60),
    ("night", "深夜", 23 * 60 + 30),
)


def scenario_rates(index, clock_minute):
    fixed = SCENARIOS[index][2]
    return day_rates(clock_minute if fixed is None else fixed)


def clock_text(minute):
    m = int(minute) % 1440
    return "%02d:%02d" % (m // 60, m % 60)


def period_name(minute):
    h = (minute % 1440) / 60.0
    if 7.0 <= h < 9.5:
        return "早高峰"
    if 17.3 <= h < 19.8:
        return "晚高峰"
    if 6.0 <= h < 22.5:
        return "平峰"
    return "深夜"


class TrafficSource(object):
    """随机来车。两个路口共用同一个来车源，所以车流一模一样。"""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def make_spec(self, kind=None):
        rng = self.rng
        if kind is None:
            kind = "bus" if rng.random() < C.BUS_RATE else "car"
        if kind == "bus":
            return CarSpec("bus", C.BUS_COLOR, C.BUS_SPEED)
        if kind == "amb":
            return CarSpec("amb", "#ffffff", C.AMB_SPEED)
        return CarSpec("car", rng.choice(C.CAR_COLORS), rng.uniform(*C.CAR_SPEED))

    def step(self, rates, dt):
        """这一小段时间里，有哪些方向来了新车？（泊松到达）"""
        arrivals = []
        for d in DIRS:
            if self.rng.random() < rates[d] * dt:
                arrivals.append((d, self.make_spec()))
        return arrivals
