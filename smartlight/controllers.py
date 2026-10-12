# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组 · 代码由 AI 编程助手 Claude 协助编写
"""
两种“红绿灯指挥官”
==================
FixedTimeController  传统定时灯：不看路况，到点就切。
AIController         AI 灯：看路况 → 查 Q 表做决定 → 看结果 → 更新 Q 表。

两个控制器的接口完全一样（都只有 update 方法），所以路口不需要知道
自己被谁指挥 —— 这就是“面向接口编程”，以后想加新的算法也很方便。
"""
from . import config as C
from .brain import bucket
from .traffic import AXIS_NAME


class FixedTimeController(object):
    kind = "fixed"

    def __init__(self, green=C.FIXED_GREEN):
        self.green = green
        self.thought = "每 %d 秒机械切换一次，不看有没有车" % green

    def countdown(self, light):
        if light.stage != "G":
            return None
        return max(0.0, self.green - light.timer)

    def update(self, inter, dt):
        light = inter.light
        if light.stage == "G" and light.timer >= self.green:
            light.request_switch()


class AIController(object):
    kind = "ai"

    def __init__(self, brain, explore=C.EPS_PLAY, learn=True):
        self.brain = brain
        self.explore = explore
        self.learn = learn
        self.thought = "正在观察路口..."
        self.state = None           # 当前路况（给画面上的 Q 表高亮用）
        self.last_explored = False
        self.decisions = 0
        self.reset_memory()

    def reset_memory(self):
        self.prev = None            # 上一次的 (路况, 动作)
        self.reward = 0.0           # 上次决定后累计的奖励
        self.elapsed = 0.0          # 上次决定后过去了多少秒
        self.since_decision = 0.0

    # -------------------------------------------------------------------
    def observe(self, inter):
        """把路口的样子“翻译”成 AI 看得懂的状态：(绿灯方向车数档, 红灯方向车数档, 红灯方向最久等待档)"""
        light, snap = inter.light, inter.snap
        g = snap[light.green_axis]
        r = snap[light.red_axis]
        return (bucket(g.demand, C.QUEUE_BUCKETS),
                bucket(r.demand, C.QUEUE_BUCKETS),
                bucket(r.max_wait, C.STARVE_BUCKETS))

    def update(self, inter, dt):
        light, snap = inter.light, inter.snap
        # 奖励 = 负的“着急程度”：路口里等着的车越多、等得越久，奖励越低
        cost = snap["NS"].cost + snap["EW"].cost
        self.reward -= cost * dt / C.REWARD_SCALE
        self.elapsed += dt
        self.since_decision += dt
        if light.stage != "G":
            return

        # ---- 安全规则层：救护车优先（规则写死，不交给 AI 去“试错”）----
        if snap[light.red_axis].amb and not snap[light.green_axis].amb:
            if light.timer >= 1.0 and light.request_switch(force=True):
                self.thought = "发现%s来了救护车！立刻为它开绿灯" % AXIS_NAME[light.red_axis]
                self.reset_memory()   # 这次是规则做的决定，不算 AI 的经验
            return
        if snap[light.green_axis].amb:
            self.thought = "救护车正在通过，保持绿灯"
            return

        # ---- AI 决策层 ----
        if light.timer < C.MIN_GREEN or self.since_decision < C.DECISION_DT:
            return
        self.since_decision = 0.0
        state = self.observe(inter)
        if self.prev is not None and self.learn:
            self.brain.learn(self.prev[0], self.prev[1], self.reward, state, self.elapsed)
        if light.timer >= C.MAX_GREEN and snap[light.red_axis].demand > 0:
            action, explored = 1, False            # 规则：绿灯到上限，必须轮换
        else:
            action, explored = self.brain.act(state, self.explore)
        if action == 1:
            light.request_switch()
        self.prev = (state, action)
        self.reward = 0.0
        self.elapsed = 0.0
        self.state = state
        self.last_explored = explored
        self.decisions += 1
        self.thought = self.explain(inter, action, explored)

    def explain(self, inter, action, explored):
        """可解释 AI：把决定翻译成人话。"""
        light, snap = inter.light, inter.snap
        g, r = snap[light.green_axis], snap[light.red_axis]
        gname, rname = AXIS_NAME[light.green_axis], AXIS_NAME[light.red_axis]
        if light.timer >= C.MAX_GREEN and action == 1:
            return "%s绿灯已亮 %d 秒到达上限，公平起见轮换" % (gname, light.timer)
        if explored:
            return "随机探索：试试“%s”会怎样，说不定有新发现" % ("切换" if action else "保持")
        if action == 1:
            if r.max_wait > C.STARVE_BUCKETS[1]:
                return "%s已经等了 %d 秒，要公平！切换" % (rname, r.max_wait)
            return "%s有 %d 辆车在等，%s只剩 %d 辆 → 切换" % (rname, r.demand, gname, g.demand)
        if g.demand == 0 and r.demand == 0:
            return "路口没有车，安静待命"
        return "%s还有 %d 辆车要过，继续放行" % (gname, g.demand)
