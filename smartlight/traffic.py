# -*- coding: utf-8 -*-
"""
交通仿真：车辆、车道、红绿灯、路口
==================================
这里只有“物理世界”，不管画面，也不管 AI。
所以它可以在电脑窗口里跑，也可以在网页里跑，还可以在测试里飞快地跑。

坐标约定：每辆车只需要一个数 s 表示“车头沿着车道走了多远”。
  s = 0          车头刚进入画面
  s = STOP_S     车头到达停止线
  s = ROAD_LEN   车头到达画面另一边
"""
import math
from collections import deque

from . import config as C

DIRS = ("N", "E", "S", "W")                     # 车从哪个方向开过来
AXIS_OF = {"N": "NS", "S": "NS", "E": "EW", "W": "EW"}
DIR_NAME = {"N": "北", "E": "东", "S": "南", "W": "西"}
AXIS_NAME = {"NS": "南北向", "EW": "东西向"}


class CarSpec(object):
    """一辆“即将到来”的车的样子。同一个 CarSpec 会同时送到两个路口，保证公平对比。"""
    __slots__ = ("kind", "color", "vmax")

    def __init__(self, kind, color, vmax):
        self.kind = kind        # "car" 小汽车 / "bus" 公交 / "amb" 救护车
        self.color = color
        self.vmax = vmax

    @property
    def length(self):
        return {"bus": C.BUS_LEN, "amb": C.AMB_LEN}.get(self.kind, C.CAR_LEN)


class Car(object):
    __slots__ = ("spec", "s", "v", "wait", "born")

    def __init__(self, spec, s, v, born, wait=0.0):
        self.spec = spec
        self.s = s          # 车头位置
        self.v = v          # 速度
        self.born = born    # 到达路口的时刻
        self.wait = wait    # 累计等待了多少秒

    @property
    def length(self):
        return self.spec.length

    @property
    def kind(self):
        return self.spec.kind


class Lane(object):
    """一条进口车道。cars[0] 是离路口最近（最前面）的车。"""

    def __init__(self, origin):
        self.origin = origin
        self.cars = []
        self.backlog = []   # 画面装不下、排在画面外面的车：[(spec, 到达时刻), ...]


class TrafficLight(object):
    """
    信号灯状态机：  绿灯(G) → 黄灯(Y) → 全红(R) → 另一个方向绿灯(G) ...
    控制器（不管是定时的还是 AI）只能做一件事：request_switch() “申请切换”。
    最短绿灯、黄灯、全红这些安全规则由信号灯自己保证，AI 想违规也做不到。
    """

    def __init__(self, green_axis="NS"):
        self.green_axis = green_axis
        self.stage = "G"
        self.timer = 0.0        # 当前阶段已经持续了多久
        self.switches = 0

    @property
    def red_axis(self):
        return "EW" if self.green_axis == "NS" else "NS"

    def signal(self, axis):
        """某个方向现在看到的灯色：'G' / 'Y' / 'R'"""
        if axis != self.green_axis or self.stage == "R":
            return "R"
        return self.stage

    def request_switch(self, force=False):
        if self.stage == "G" and (force or self.timer >= C.MIN_GREEN):
            self.stage, self.timer = "Y", 0.0
            return True
        return False

    def step(self, dt):
        self.timer += dt
        if self.stage == "Y" and self.timer >= C.YELLOW:
            self.stage, self.timer = "R", 0.0
        elif self.stage == "R" and self.timer >= C.ALL_RED:
            self.green_axis = self.red_axis
            self.stage, self.timer = "G", 0.0
            self.switches += 1


class AxisInfo(object):
    """一个方向（南北向 / 东西向）此刻的路况快照，给控制器和统计用。"""
    __slots__ = ("demand", "waiting", "cost", "max_wait", "amb")

    def __init__(self):
        self.demand = 0       # 还没过停止线的车（含画面外排队的）
        self.waiting = 0      # 停着不动的车
        self.cost = 0.0       # “着急程度”总和：每辆在等的车 1 分，等得越久分越高
        self.max_wait = 0.0   # 等得最久的那辆车等了多少秒
        self.amb = False      # 有没有救护车在等


class Stats(object):
    """
    记录一个路口的成绩单。
    “平均等待” = 所有车一共等了多少秒 ÷ 来了多少辆车。
    （注意：不能只统计“已经开走的车”，否则一直被堵着、走不了的车就被忽略了，成绩会虚高。）
    """

    def __init__(self):
        self.arrived = 0
        self.passed = 0
        self.idle = 0.0         # 所有车加起来一共等了多少秒（车·秒）
        self.co2 = 0.0          # 怠速排放（克）
        self.amb_wait = None    # 最近一辆救护车等了多久
        self.window = deque()   # 每秒一格：[第几秒, 这一秒的等待车·秒, 这一秒来的车]

    def _cell(self, now):
        sec = int(now)
        if not self.window or self.window[-1][0] != sec:
            self.window.append([sec, 0.0, 0])
            while self.window[0][0] < sec - C.STAT_WINDOW:
                self.window.popleft()
        return self.window[-1]

    def on_arrive(self, now):
        self.arrived += 1
        self._cell(now)[2] += 1

    def on_step(self, now, dt, idle_cars):
        self.idle += idle_cars * dt
        self.co2 += idle_cars * dt * C.CO2_PER_IDLE_SEC
        self._cell(now)[1] += idle_cars * dt

    def on_exit(self, car):
        self.passed += 1
        if car.kind == "amb":
            self.amb_wait = car.wait

    def avg_wait(self):
        """最近 STAT_WINDOW 秒的平均等待（秒/辆）。"""
        idle = sum(c[1] for c in self.window)
        cars = sum(c[2] for c in self.window)
        return idle / cars if cars else None

    def overall_wait(self):
        return self.idle / max(1, self.arrived)


class Intersection(object):
    """一个十字路口：4 条进口车道 + 1 个信号灯 + 1 个控制器（大脑）。"""

    def __init__(self, controller, title=""):
        self.controller = controller
        self.title = title
        self.light = TrafficLight()
        self.lanes = dict((d, Lane(d)) for d in DIRS)
        self.time = 0.0
        self.stats = Stats()
        self.snap = self.scan()

    # ---------------------------------------------------------------- 车流 --
    def add_car(self, origin, spec):
        """新车到达：先排进“画面外队列”，等画面里有空位再开进来。"""
        self.lanes[origin].backlog.append((spec, self.time))
        self.stats.on_arrive(self.time)

    def queue_len(self, axis=None):
        if axis is None:
            return self.snap["NS"].waiting + self.snap["EW"].waiting
        return self.snap[axis].waiting

    # ---------------------------------------------------------------- 观察 --
    def scan(self):
        snap = {"NS": AxisInfo(), "EW": AxisInfo()}
        for d, lane in self.lanes.items():
            info = snap[AXIS_OF[d]]
            for car in lane.cars:
                if car.s > C.STOP_S + 1:
                    continue                      # 已经过了停止线，不用再管
                info.demand += 1
                if car.kind == "amb":
                    info.amb = True
                if car.v < C.WAIT_SPEED:
                    info.waiting += 1
                    info.cost += 1.0 + car.wait / C.WAIT_PENALTY
                    if car.wait > info.max_wait:
                        info.max_wait = car.wait
            for spec, born in lane.backlog:
                w = self.time - born
                info.demand += 1
                info.waiting += 1
                info.cost += 1.0 + w / C.WAIT_PENALTY
                if w > info.max_wait:
                    info.max_wait = w
                if spec.kind == "amb":
                    info.amb = True
        return snap

    # ---------------------------------------------------------------- 前进 --
    def step(self, dt):
        self.snap = self.scan()
        self.controller.update(self, dt)
        self.light.step(dt)
        for d in DIRS:
            lane = self.lanes[d]
            self._release_backlog(lane)
            self._move_lane(lane, self.light.signal(AXIS_OF[d]), dt)
        self.stats.on_step(self.time, dt, self.snap["NS"].waiting + self.snap["EW"].waiting)
        self.time += dt

    def _release_backlog(self, lane):
        if not lane.backlog:
            return
        last = lane.cars[-1] if lane.cars else None
        spec = lane.backlog[0][0]
        v = spec.vmax if last is None else min(spec.vmax, last.v)
        if last is not None and last.s - last.length < C.MIN_GAP + v * C.HEADWAY:
            return                                # 入口被堵住了，进不来
        spec, born = lane.backlog.pop(0)
        lane.cars.append(Car(spec, 0.0, v, born, wait=self.time - born))

    def _move_lane(self, lane, signal, dt):
        lead = None
        for car in lane.cars:
            # 1) 前方“必须停下”的位置：前车车尾，或者红灯时的停止线
            limit = soft = 1e9
            if lead is not None:
                limit = lead.s - lead.length - C.MIN_GAP
                soft = limit - car.v * C.HEADWAY      # 开得越快，留的距离越大
            if signal != "G" and car.s <= C.STOP_S + 0.5:
                dist = C.STOP_S - car.s
                can_stop = dist >= car.v * car.v / (2 * C.COMFORT_DECEL)
                if signal == "R" or can_stop:     # 黄灯：停得下就停，停不下就过
                    limit = min(limit, C.STOP_S)
                    soft = min(soft, C.STOP_S)
            # 2) 在这段距离内能安全刹住的最高速度
            gap = soft - car.s
            v_safe = math.sqrt(2 * C.DECEL * gap) if gap > 0 else 0.0
            target = min(car.spec.vmax, v_safe)
            if target > car.v:
                car.v = min(target, car.v + C.ACCEL * dt)
            else:
                car.v = target
            # 3) 往前开，但绝不会撞上前车 / 冲过红灯
            new_s = car.s + car.v * dt
            if new_s > limit:
                new_s = max(car.s, limit)
            car.s = new_s
            if car.v < C.WAIT_SPEED and car.s <= C.STOP_S + 1:
                car.wait += dt
            lead = car
        # 4) 开出画面的车：记成绩，然后移除
        while lane.cars and lane.cars[0].s - lane.cars[0].length > C.ROAD_LEN:
            self.stats.on_exit(lane.cars.pop(0))
