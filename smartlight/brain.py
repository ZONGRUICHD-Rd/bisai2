# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组 · 代码由 AI 编程助手 Claude 协助编写
"""
AI 大脑：Q 学习（Q-Learning）—— 纯 Python 实现，不依赖任何 AI 库
==================================================================
Q 表就像 AI 的“经验笔记本”：
  每一行是一种路况（状态），每一行有两个分数：
      Q[路况][0] = 在这种路况下“保持当前绿灯”有多好
      Q[路况][1] = 在这种路况下“切换红绿灯”有多好
  AI 做决定时，选分数更高的那个动作（偶尔随机试试别的，叫“探索”）。

每做完一个动作，AI 会看到结果（奖励 = 负的“大家的着急程度”），
然后用下面这条公式更新笔记本 —— 这就是“学习”：

  Q[s][a] ← Q[s][a] + α × ( 奖励 + γ^t × max(Q[s'])  −  Q[s][a] )
                           └──────── 新的估计 ────────┘  └ 旧的估计 ┘

  α 学习率：新经验占多大比重；γ 折扣：多看重未来；t：这个动作持续了几秒。

另外还用了“经验回放”（DeepMind 训练 DQN 玩游戏时用的技巧）：
  AI 把经历过的事情存进回忆库，每学一条新经验，就再随机回忆几条旧经验复习一遍，
  就像我们睡前回想白天的事 —— 同样多的经历，学得更快、更稳。
"""
import json
import math
import random

from . import config as C

ACTIONS = ("保持", "切换")
N_QUEUE = len(C.QUEUE_BUCKETS) + 1      # 车辆数分 5 档
N_STARVE = len(C.STARVE_BUCKETS) + 1    # 等待时长分 3 档


def bucket(value, edges):
    """把一个数字分档：比如 edges=(0,2,5,9) 时，0→0档, 1~2→1档, 3~5→2档 ..."""
    for i, edge in enumerate(edges):
        if value <= edge:
            return i
    return len(edges)


class QBrain(object):
    def __init__(self, alpha=C.ALPHA, gamma=C.GAMMA, seed=None):
        self.alpha = alpha
        self.gamma = gamma
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        """清空大脑：忘掉一切，从零开始学。"""
        self.q = {}         # 状态 -> [保持的分数, 切换的分数]
        self.visits = {}    # 状态 -> 学习过多少次
        self.updates = 0    # 总共学习了多少次
        self.memory = []    # 回忆库：最近的经验 (路况, 动作, 奖励, 新路况, 持续秒数)

    # ------------------------------------------------------------ 思考 ----
    def values(self, state):
        if state not in self.q:
            self.q[state] = [0.0, 0.0]
        return self.q[state]

    def epsilon(self, floor):
        """探索率：新大脑多探索，经验越多越自信。"""
        return max(floor, C.EPS_FRESH * math.exp(-self.updates / C.EPS_DECAY))

    def act(self, state, floor):
        """返回 (动作, 是否是随机探索)"""
        if self.rng.random() < self.epsilon(floor):
            return self.rng.randrange(2), True
        v = self.values(state)
        return (1 if v[1] > v[0] else 0), False

    # ------------------------------------------------------------ 学习 ----
    def _update(self, state, action, reward, next_state, duration, rate):
        v = self.values(state)
        target = reward + (self.gamma ** duration) * max(self.values(next_state))
        td_error = target - v[action]
        v[action] += rate * td_error
        return td_error

    def learn(self, state, action, reward, next_state, duration):
        n = self.visits.get(state, 0) + 1
        # 第一次遇到某种路况时多相信新经验（学得快），见多了就稳定在 α（不会被一次意外带偏）
        td_error = self._update(state, action, reward, next_state, duration, max(self.alpha, 1.0 / n))
        self.visits[state] = n
        self.updates += 1
        # 经验回放：把这条经验记进“回忆库”，再随机回忆几条旧经验重新学一遍
        item = (state, action, reward, next_state, duration)
        if len(self.memory) < C.REPLAY_SIZE:
            self.memory.append(item)
        else:                                   # 回忆库满了：随机忘掉一条旧的
            self.memory[self.rng.randrange(C.REPLAY_SIZE)] = item
        for _ in range(C.REPLAY_K):
            self._update(*self.memory[self.rng.randrange(len(self.memory))], rate=self.alpha)
        return td_error

    def preference(self, state):
        """切换比保持好多少（正数=想切换，负数=想保持）。没见过的路况返回 None。"""
        if not self.visits.get(state):
            return None
        v = self.q[state]
        return v[1] - v[0]

    # ------------------------------------------------------------ 存档 ----
    def to_dict(self):
        return {
            "format": "smartlight-qbrain-1",
            "updates": self.updates,
            "q": dict(("%d,%d,%d" % s, [round(x, 4) for x in v]) for s, v in self.q.items()),
            "visits": dict(("%d,%d,%d" % s, n) for s, n in self.visits.items()),
        }

    def load_dict(self, data):
        self.reset()
        for key, v in data.get("q", {}).items():
            self.q[tuple(int(x) for x in key.split(","))] = [float(v[0]), float(v[1])]
        for key, n in data.get("visits", {}).items():
            self.visits[tuple(int(x) for x in key.split(","))] = int(n)
        self.updates = int(data.get("updates", 0))

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=0)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.load_dict(json.load(f))
