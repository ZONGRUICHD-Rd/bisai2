# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组 · 代码由 AI 编程助手 Claude 协助编写
"""
生成网页版（GitHub Pages）：把 web/ 页面和 Python 源代码一起复制到 _site/ 文件夹。
用法：
    python tools/build_site.py            # 生成 _site/
    python -m http.server -d _site 8000   # 本地预览：浏览器打开 http://localhost:8000
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "_site")

from smartlight.brain import QBrain                      # noqa: E402
from smartlight.scenario import SCENARIOS, day_rates     # noqa: E402
from smartlight.world import compare                     # noqa: E402

DOCS = {
    "main.py": "电脑版入口（tkinter 画图）",
    "smartlight/traffic.py": "交通仿真：车、车道、信号灯、路口",
    "smartlight/brain.py": "AI 大脑：Q 学习（不依赖 AI 库）",
    "smartlight/controllers.py": "定时控制器 & AI 控制器 & 安全规则层",
    "smartlight/scenario.py": "一天的车流变化",
    "smartlight/world.py": "对比实验场 & 极速训练",
    "smartlight/render.py": "把世界翻译成绘图指令",
    "smartlight/ui.py": "按钮、键盘、浮层",
    "smartlight/config.py": "所有可调参数",
    "smartlight/web_bridge.py": "网页版和 JavaScript 对接",
    "train.py": "命令行训练 & 考试",
    "tests/test_smartlight.py": "自动测试",
    "tools/pil_backend.py": "第四种画法：把绘图指令画成图片（做视频用）",
    "tools/make_video.py": "生成作品介绍视频",
}


def exam_results():
    brain = QBrain()
    brain.load(os.path.join(ROOT, "smartlight", "pretrained_brain.json"))
    rows = []
    for key, name, minute in SCENARIOS:
        rates = (lambda t: day_rates(6 * 60 + t)) if minute is None else day_rates(minute)
        r = compare(brain, rates, seconds=1200, seed=11)
        f, a = r["fixed"], r["ai"]
        rows.append({"name": name, "fixed": f["avg_wait"], "ai": a["avg_wait"],
                     "gain": (f["avg_wait"] - a["avg_wait"]) / max(0.01, f["avg_wait"]) * 100,
                     "co2": f["co2"] - a["co2"]})
    return {"rows": rows, "brain_updates": brain.updates}


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "web"), OUT)
    package = sorted("smartlight/" + f for f in os.listdir(os.path.join(ROOT, "smartlight"))
                     if f.endswith((".py", ".json")) and f != "my_brain.json")
    code = [f for f in DOCS if os.path.exists(os.path.join(ROOT, f))]
    lines = 0
    for f in set(package) | set(code):
        dst = os.path.join(OUT, "src", f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(ROOT, f), dst)
        if f.endswith(".py"):
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                lines += sum(1 for _ in fh)
    order = ["smartlight/brain.py", "smartlight/controllers.py", "smartlight/traffic.py"]
    code.sort(key=lambda f: (order.index(f) if f in order else len(order), f))
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"package": package, "code": code, "docs": DOCS, "lines": lines}, fh, ensure_ascii=False)
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(exam_results(), fh, ensure_ascii=False)
    video = os.path.join(ROOT, "作品介绍视频.mp4")
    if os.path.exists(video):                     # 作品介绍视频也放到网页上
        shutil.copy(video, os.path.join(OUT, "video.mp4"))
        shutil.copy(os.path.join(ROOT, "docs", "images", "video_poster.jpg"), os.path.join(OUT, "video_poster.jpg"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print("网页已生成：%s（Python 源码共 %d 行）" % (OUT, lines))


if __name__ == "__main__":
    main()
