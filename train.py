# -*- coding: utf-8 -*-
"""
命令行训练 & 考试脚本（不需要画面，跑得飞快，方便调试）
=======================================================
用法：
    python train.py              # 从零训练 8 小时虚拟车流，然后考试，存成 pretrained_brain.json
    python train.py --hours 2    # 只训练 2 小时
    python train.py --exam       # 不训练，直接给现有的大脑考试
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from smartlight.brain import QBrain                       # noqa: E402
from smartlight.scenario import SCENARIOS, day_rates      # noqa: E402
from smartlight.world import Trainer, compare             # noqa: E402

BRAIN_PATH = os.path.join(HERE, "smartlight", "pretrained_brain.json")


def exam(brain, seconds=1200):
    print("\n考试：同一股车流，定时灯 vs AI 灯（各跑 %d 秒）" % seconds)
    print("%-8s %10s %10s %8s %12s" % ("场景", "定时等待", "AI等待", "提升", "AI减排(克)"))
    total_gain = []
    for key, name, minute in SCENARIOS:
        if minute is None:
            rates = (lambda t: day_rates(6 * 60 + t / 60.0 * 60))   # 1 秒 = 1 分钟
        else:
            rates = day_rates(minute)
        r = compare(brain, rates, seconds=seconds, seed=11)
        f, a = r["fixed"], r["ai"]
        gain = (f["avg_wait"] - a["avg_wait"]) / max(0.01, f["avg_wait"]) * 100
        total_gain.append(gain)
        print("%-8s %9.1fs %9.1fs %7.0f%% %12.0f" % (name, f["avg_wait"], a["avg_wait"], gain,
                                                    f["co2"] - a["co2"]))
    print("平均提升：%.0f%%" % (sum(total_gain) / len(total_gain)))


def main():
    args = sys.argv[1:]
    brain = QBrain(seed=1)
    if "--exam" in args:
        brain.load(BRAIN_PATH)
        exam(brain)
        return
    hours = float(args[args.index("--hours") + 1]) if "--hours" in args else 8.0
    trainer = Trainer(brain, seconds=hours * 3600, seed=2026)
    t0 = time.time()
    while not trainer.finished:
        trainer.run(600)
        print("训练进度 %5.1f%%   已学习 %6d 次   用时 %.1f 秒"
              % (trainer.progress * 100, brain.updates, time.time() - t0))
    brain.save(BRAIN_PATH)
    print("已保存：", BRAIN_PATH)
    exam(brain)


if __name__ == "__main__":
    main()
