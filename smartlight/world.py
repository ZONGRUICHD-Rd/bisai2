# -*- coding: utf-8 -*-
"""
对比实验场
==========
World    两个路口并排：左边传统定时灯，右边 AI 灯，迎来完全相同的车流。
Trainer  “极速训练”：让 AI 在一个看不见的虚拟路口里飞快地练习（AI 在做梦）。
compare  不画画面，直接跑一段时间比成绩 —— 给训练脚本和自动测试用。
"""
from collections import deque

from . import config as C
from .controllers import AIController, FixedTimeController
from .scenario import SCENARIOS, TrafficSource, day_rates, scenario_rates
from .traffic import DIRS, Intersection


class World(object):
    def __init__(self, brain, seed=2026):
        self.brain = brain
        self.fixed = Intersection(FixedTimeController(), "传统定时红绿灯")
        self.ai = Intersection(AIController(brain), "AI 自学习红绿灯")
        self.source = TrafficSource(seed)
        self.scenario = 0
        self.clock = float(C.DAY_START)     # 时钟（一天中的第几分钟）
        self.time = 0.0
        self.history = {"fixed": deque(maxlen=C.CHART_POINTS),
                        "ai": deque(maxlen=C.CHART_POINTS)}
        self._next_sample = 0.0
        self.ambulances = 0

    @property
    def pair(self):
        return (self.fixed, self.ai)

    def rates(self):
        return scenario_rates(self.scenario, self.clock)

    def next_scenario(self):
        self.scenario = (self.scenario + 1) % len(SCENARIOS)
        return SCENARIOS[self.scenario][1]

    def spawn_ambulance(self):
        origin = self.source.rng.choice(DIRS)
        spec = self.source.make_spec("amb")
        for inter in self.pair:
            inter.add_car(origin, spec)
        self.ambulances += 1
        return origin

    def step(self, dt):
        for origin, spec in self.source.step(self.rates(), dt):
            for inter in self.pair:
                inter.add_car(origin, spec)
        for inter in self.pair:
            inter.step(dt)
        self.time += dt
        if SCENARIOS[self.scenario][2] is None:
            self.clock = (self.clock + dt * C.CLOCK_MIN_PER_SEC) % 1440
        if self.time >= self._next_sample:
            self._next_sample += C.CHART_SAMPLE
            for key, inter in (("fixed", self.fixed), ("ai", self.ai)):
                w = inter.stats.avg_wait()
                hist = self.history[key]
                if w is None:
                    w = hist[-1] if hist else 0.0
                hist.append(w)


class Trainer(object):
    """在后台虚拟路口里快速练习。每隔 5 分钟随机换一种车流，让 AI 见多识广。"""

    def __init__(self, brain, seconds=C.TRAIN_SECONDS, seed=None, dt=C.TRAIN_DT):
        self.brain = brain
        self.inter = Intersection(AIController(brain, explore=C.EPS_TRAIN), "训练场")
        self.source = TrafficSource(seed)
        self.total = float(seconds)
        self.done = 0.0
        self.dt = dt
        self.start_updates = brain.updates
        self._pick_rates()

    def _pick_rates(self):
        rng = self.source.rng
        rates = day_rates(rng.uniform(0, 1440))
        k = rng.uniform(0.6, 1.5)                      # 随机让车流更大或更小
        self.rates = dict((d, rates[d] * k * rng.uniform(0.7, 1.3)) for d in DIRS)
        self._next_switch = self.done + 300.0

    @property
    def progress(self):
        return min(1.0, self.done / self.total)

    @property
    def finished(self):
        return self.done >= self.total

    @property
    def learned(self):
        return self.brain.updates - self.start_updates

    def run(self, seconds):
        end = min(self.total, self.done + seconds)
        while self.done < end:
            if self.done >= self._next_switch:
                self._pick_rates()
            for origin, spec in self.source.step(self.rates, self.dt):
                self.inter.add_car(origin, spec)
            self.inter.step(self.dt)
            self.done += self.dt


def compare(brain, rates, seconds=900, seed=7, dt=C.TRAIN_DT, learn=False):
    """
    同一股车流，分别交给定时灯和 AI 灯，跑 seconds 秒，返回成绩单。
    rates 可以是固定的 {方向: 车流}，也可以是函数 f(第几秒) -> {方向: 车流}。
    """
    fixed = Intersection(FixedTimeController(), "定时")
    ai = Intersection(AIController(brain, explore=0.0, learn=learn), "AI")
    source = TrafficSource(seed)
    t = 0.0
    while t < seconds:
        r = rates(t) if callable(rates) else rates
        for origin, spec in source.step(r, dt):
            fixed.add_car(origin, spec)
            ai.add_car(origin, spec)
        fixed.step(dt)
        ai.step(dt)
        t += dt
    result = {}
    for key, inter in (("fixed", fixed), ("ai", ai)):
        s = inter.stats
        result[key] = {
            "avg_wait": s.overall_wait(),
            "passed": s.passed,
            "co2": s.co2,
            "queue": inter.queue_len(),
        }
    return result
