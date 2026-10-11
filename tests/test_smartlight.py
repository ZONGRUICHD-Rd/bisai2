# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
自动测试：python -m unittest
每次改代码后跑一遍，确保“车不会撞、不会闯红灯、AI 真的比定时灯好”。
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smartlight import config as C                                   # noqa: E402
from smartlight.brain import QBrain, bucket                           # noqa: E402
from smartlight.controllers import AIController, FixedTimeController  # noqa: E402
from smartlight.render import draw_app                                # noqa: E402
from smartlight.scenario import TrafficSource, day_rates              # noqa: E402
from smartlight.traffic import AXIS_OF, DIRS, Intersection            # noqa: E402
from smartlight.ui import App                                         # noqa: E402
from smartlight.world import compare                                  # noqa: E402

PRETRAINED = os.path.join(ROOT, "smartlight", "pretrained_brain.json")


def run(inter, rates, seconds, seed=1, dt=0.1, each_step=None):
    src = TrafficSource(seed)
    t = 0.0
    while t < seconds:
        for origin, spec in src.step(rates, dt):
            inter.add_car(origin, spec)
        inter.step(dt)
        if each_step:
            each_step(inter)
        t += dt


class TestBrain(unittest.TestCase):
    def test_bucket(self):
        self.assertEqual([bucket(v, (0, 2, 5, 9)) for v in (0, 1, 2, 3, 5, 6, 9, 10, 99)],
                         [0, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_q_update_formula(self):
        b = QBrain(alpha=0.5, gamma=0.9)
        b.q[(0, 0, 0)] = [1.0, 0.0]
        b.q[(1, 1, 1)] = [2.0, 4.0]
        b._update((0, 0, 0), 0, -1.0, (1, 1, 1), 2.0, rate=0.5)
        # 目标 = -1 + 0.9^2 * 4 = 2.24 ；新值 = 1 + 0.5 * (2.24 - 1) = 1.62
        self.assertAlmostEqual(b.q[(0, 0, 0)][0], 1.62)

    def test_experience_replay_memory(self):
        b = QBrain(seed=1)
        for i in range(C.REPLAY_SIZE + 50):
            b.learn((i % 5, 0, 0), i % 2, -1.0, (0, 0, 0), 1.0)
        self.assertEqual(len(b.memory), C.REPLAY_SIZE)     # 回忆库不会无限变大
        self.assertEqual(b.updates, C.REPLAY_SIZE + 50)

    def test_save_load_roundtrip(self):
        b = QBrain()
        b.learn((1, 2, 0), 1, -3.0, (0, 0, 0), 1.0)
        b2 = QBrain()
        b2.load_dict(json.loads(json.dumps(b.to_dict())))
        self.assertEqual(b2.updates, 1)
        self.assertAlmostEqual(b2.q[(1, 2, 0)][1], b.q[(1, 2, 0)][1], places=4)


class TestTrafficSafety(unittest.TestCase):
    def test_no_collision_and_no_red_running(self):
        inter = Intersection(FixedTimeController())
        prev = {}

        def check(it):
            for d in DIRS:
                cars = it.lanes[d].cars
                for a, b in zip(cars, cars[1:]):
                    self.assertGreaterEqual(a.s - a.length - b.s, C.MIN_GAP - 1e-6, "追尾了！")
                sig = it.light.signal(AXIS_OF[d])
                for car in cars:
                    before = prev.get(id(car))
                    if sig == "R" and before is not None and before <= C.STOP_S:
                        self.assertLessEqual(car.s, C.STOP_S + 1e-6, "闯红灯了！")
            prev.clear()
            for d in DIRS:
                for car in it.lanes[d].cars:
                    prev[id(car)] = car.s

        run(inter, day_rates(8 * 60), 600, each_step=check)
        self.assertGreater(inter.stats.passed, 200)

    def test_light_cycle_respects_safety_times(self):
        inter = Intersection(AIController(QBrain(), explore=1.0))   # 完全乱来的 AI
        greens = []
        last_axis, start = inter.light.green_axis, 0.0

        def check(it):
            nonlocal last_axis, start
            if it.light.green_axis != last_axis:
                greens.append(it.time - start)
                last_axis, start = it.light.green_axis, it.time

        run(inter, day_rates(12 * 60), 600, each_step=check)
        self.assertTrue(greens)
        self.assertGreaterEqual(min(greens), C.MIN_GREEN + C.YELLOW + C.ALL_RED - 0.2)


class TestAI(unittest.TestCase):
    def test_pretrained_ai_beats_fixed_timer(self):
        brain = QBrain()
        brain.load(PRETRAINED)
        for minute in (8 * 60, 14 * 60, 18 * 60 + 20):
            r = compare(brain, day_rates(minute), seconds=900, seed=5)
            self.assertLess(r["ai"]["avg_wait"], r["fixed"]["avg_wait"] * 0.8, "第 %d 分钟" % minute)

    def test_ambulance_gets_priority(self):
        brain = QBrain()
        brain.load(PRETRAINED)
        waits = {}
        for name, ctrl in (("fixed", FixedTimeController()), ("ai", AIController(brain, explore=0))):
            inter = Intersection(ctrl)
            src = TrafficSource(3)
            run(inter, day_rates(14 * 60), 1, seed=3)
            inter.add_car("E", src.make_spec("amb"))      # 东西向此时是红灯
            run(inter, {d: 0.0 for d in DIRS}, 40)
            waits[name] = inter.stats.amb_wait
        self.assertIsNotNone(waits["ai"])
        self.assertLess(waits["ai"], waits["fixed"])


class TestApp(unittest.TestCase):
    def test_app_runs_and_renders(self):
        app = App(platform="test")
        app.on_click(640, 600)                 # 关闭开场说明
        for key in ("a", "c", "s", "space", "space", "t"):
            app.on_key(key)
        for _ in range(200):
            app.tick()
        cmds = draw_app(app)
        self.assertGreater(len(cmds), 100)
        json.dumps(cmds)                        # 网页版要求能转成 JSON


if __name__ == "__main__":
    unittest.main()
