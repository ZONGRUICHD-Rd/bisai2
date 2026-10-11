# -*- coding: utf-8 -*-
"""
论文里所有实验的复现脚本：python tools/experiments.py
结果写到 paper/results.json，论文中的表格和曲线都来自这里。
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smartlight import config as C                       # noqa: E402
from smartlight.brain import QBrain                      # noqa: E402
from smartlight.scenario import SCENARIOS, day_rates     # noqa: E402
from smartlight.world import Trainer, World, compare     # noqa: E402

TEST_POINTS = (("早高峰", 8 * 60), ("平峰", 14 * 60), ("晚高峰", 18 * 60 + 20), ("深夜", 23 * 60 + 30))


def main_results():
    """实验一：预训练大脑在 5 个场景下与定时灯对比（1200 秒，种子 11）。"""
    brain = QBrain()
    brain.load(os.path.join(ROOT, "smartlight", "pretrained_brain.json"))
    rows = []
    for key, name, minute in SCENARIOS:
        rates = (lambda t: day_rates(6 * 60 + t)) if minute is None else day_rates(minute)
        r = compare(brain, rates, seconds=1200, seed=11)
        rows.append({"name": name, "fixed": r["fixed"], "ai": r["ai"]})
    return {"updates": brain.updates, "rows": rows}


def ablation(seeds=(1, 2, 3, 4, 5, 6), hours=2.0):
    """实验二：经验回放消融。同样训练 2 小时，K=0（不回放）与 K=20 各 6 个随机种子。"""
    out = {}
    fixed = None
    for k in (0, C.REPLAY_K):
        C.REPLAY_K = k
        runs = []
        for seed in seeds:
            b = QBrain(seed=seed)
            Trainer(b, seconds=hours * 3600, seed=seed).run(hours * 3600)
            res = [compare(b, day_rates(m), seconds=900, seed=5) for _, m in TEST_POINTS]
            runs.append([r["ai"]["avg_wait"] for r in res])
            fixed = [r["fixed"]["avg_wait"] for r in res]
        out[str(k)] = runs
    C.REPLAY_K = 20
    return {"points": [n for n, _ in TEST_POINTS], "fixed": fixed, "runs": out, "seeds": list(seeds)}


def learning_curve(minutes=12):
    """实验三：清空大脑后在早高峰边用边学，每分钟记录一次两个路口的平均等待。"""
    brain = QBrain(seed=3)
    world = World(brain, seed=9)
    world.scenario = 1
    curve = []
    for m in range(1, minutes + 1):
        for _ in range(60 * C.FPS):
            world.step(C.SIM_DT)
        curve.append({"minute": m, "fixed": world.fixed.stats.avg_wait(), "ai": world.ai.stats.avg_wait(),
                      "updates": brain.updates})
    return curve


def main():
    t0 = time.time()
    data = {"main": main_results()}
    print("实验一完成 %.0f 秒" % (time.time() - t0))
    data["ablation"] = ablation()
    print("实验二完成 %.0f 秒" % (time.time() - t0))
    data["curve"] = learning_curve()
    print("实验三完成 %.0f 秒" % (time.time() - t0))
    os.makedirs(os.path.join(ROOT, "paper"), exist_ok=True)
    with open(os.path.join(ROOT, "paper", "results.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(json.dumps(data["ablation"], ensure_ascii=False))
    for r in data["main"]["rows"]:
        print(r["name"], round(r["fixed"]["avg_wait"], 2), round(r["ai"]["avg_wait"], 2),
              round(r["fixed"]["co2"] - r["ai"]["co2"]), r["fixed"]["passed"], r["ai"]["passed"])
    for c in data["curve"]:
        print(c)


if __name__ == "__main__":
    main()
