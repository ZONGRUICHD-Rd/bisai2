# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组 · 代码由 AI 编程助手 Claude 协助编写
"""
应用主控：按钮、键盘、浮层、提示消息
====================================
App 不关心自己是跑在电脑窗口里还是网页里：
  前端每秒调用 30 次 tick() 和 render()，有点击就调 on_click()，有按键就调 on_key()。
"""
import os

from . import config as C
from .brain import QBrain
from .render import button_rects, draw_app
from .traffic import DIR_NAME
from .world import Trainer, World

HERE = os.path.dirname(os.path.abspath(__file__))
PRETRAINED = os.path.join(HERE, "pretrained_brain.json")
TRAIN_CHUNK = 60.0      # 极速训练时，每一帧在虚拟路口里跑多少秒


class Button(object):
    def __init__(self, label, key, action, active=None):
        self._label = label     # 字符串，或者 function(app) -> 字符串
        self.key = key
        self.action = action
        self._active = active

    def label(self, app):
        return self._label(app) if callable(self._label) else self._label

    def active(self, app):
        return bool(self._active and self._active(app))


class App(object):
    def __init__(self, platform="desktop", save_fn=None):
        self.platform = platform
        self.save_fn = save_fn
        self.brain = QBrain(seed=2026)
        self.has_pretrained = self._load_pretrained()
        self.world = World(self.brain)
        self.speed_i = 0
        self.paused = False
        self.overlay = "intro"
        self.trainer = None
        self.toasts = []        # [[消息, 剩余帧数], ...]
        self.frame = 0
        self.buttons = [
            Button(lambda a: "继续 [空格]" if a.paused else "暂停 [空格]", "space", App.toggle_pause,
                   lambda a: a.paused),
            Button(lambda a: "倍速 x%d [S]" % C.SPEEDS[a.speed_i], "s", App.next_speed,
                   lambda a: a.speed_i > 0),
            Button("切换场景 [C]", "c", App.next_scenario),
            Button("派救护车 [A]", "a", App.ambulance),
            Button("极速训练 [T]", "t", App.train, lambda a: a.trainer is not None),
            Button("清空大脑 [R]", "r", App.reset_brain),
            Button("载入学霸大脑 [L]", "l", App.load_brain),
            Button("原理说明 [H]", "h", App.show_help, lambda a: a.overlay == "help"),
        ]

    # ------------------------------------------------------------ 每一帧 --
    def tick(self):
        self.frame += 1
        for t in self.toasts:
            t[1] -= 1
        self.toasts = [t for t in self.toasts if t[1] > 0]
        if self.trainer is not None:
            self.trainer.run(TRAIN_CHUNK)
            if self.trainer.finished:
                self.toast("特训完成！AI 多积累了 %d 次经验" % self.trainer.learned)
                self.world.ai.controller.reset_memory()
                self.trainer = None
            return
        if self.paused or self.overlay == "help":
            return
        for _ in range(C.SPEEDS[self.speed_i]):
            self.world.step(C.SIM_DT)

    def render(self):
        return draw_app(self)

    def toast(self, msg, seconds=3.0):
        self.toasts.append([msg, int(seconds * C.FPS)])

    # ------------------------------------------------------------ 输入 ----
    def on_click(self, x, y):
        if self.trainer is not None:
            return
        if self.overlay:
            self.overlay = None
            return
        for (bx, by, bw, bh), btn in zip(button_rects(), self.buttons):
            if bx <= x <= bx + bw and by <= y <= by + bh:
                btn.action(self)
                return

    def on_key(self, key):
        key = key.lower()
        if self.trainer is not None:
            return
        if self.overlay:
            self.overlay = None
            if key in ("space", "escape", "return", "h"):
                return
        if key in ("1", "2", "3"):
            self.speed_i = min(int(key) - 1, len(C.SPEEDS) - 1)
            return
        if key == "v":
            self.save_brain()
            return
        for btn in self.buttons:
            if btn.key == key:
                btn.action(self)
                return

    # ------------------------------------------------------------ 动作 ----
    def toggle_pause(self):
        self.paused = not self.paused

    def next_speed(self):
        self.speed_i = (self.speed_i + 1) % len(C.SPEEDS)
        self.toast("倍速 x%d" % C.SPEEDS[self.speed_i], 1.2)

    def next_scenario(self):
        self.toast("场景切换：" + self.world.next_scenario())

    def ambulance(self):
        origin = self.world.spawn_ambulance()
        self.toast("救护车从%s边开来了！看哪个路口先给它让路" % DIR_NAME[origin], 4)

    def train(self):
        self.trainer = Trainer(self.brain, seed=self.frame)

    def reset_brain(self):
        self.brain.reset()
        self.world.ai.controller.reset_memory()
        self.toast("AI 大脑已清空！看 Q 表从“？”开始长出规律", 4)

    def load_brain(self):
        if self._load_pretrained():
            self.world.ai.controller.reset_memory()
            self.toast("已载入学霸大脑（训练过 %s 次）" % format(self.brain.updates, ","))
        else:
            self.toast("没找到 pretrained_brain.json，先运行 train.py 训练一个吧")

    def show_help(self):
        self.overlay = "help"

    def save_brain(self):
        if self.save_fn is None:
            self.toast("网页版不能保存文件，请在电脑版按 V 保存")
            return
        self.toast("已保存：" + self.save_fn(self.brain))

    def _load_pretrained(self):
        if not os.path.exists(PRETRAINED):
            return False
        try:
            self.brain.load(PRETRAINED)
            return True
        except (OSError, ValueError, KeyError):
            return False
