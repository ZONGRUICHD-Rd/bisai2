# -*- coding: utf-8 -*-
# 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）· 2026 年深圳市龙华区人工智能创意编程挑战赛 Python 小学组
"""
smartlight —— 会学习的红绿灯
============================
文件分工（从底层到上层）：
    config.py       所有可调参数
    traffic.py      交通仿真：车、车道、信号灯、路口
    brain.py        AI 大脑：Q 学习（纯手写）
    controllers.py  定时控制器 & AI 控制器
    scenario.py     一天的车流变化
    world.py        对比实验场 & 极速训练
    render.py       把世界翻译成绘图指令
    ui.py           按钮、键盘、浮层
    web_bridge.py   网页版和 JavaScript 对接
"""
__version__ = "1.0.0"
__author__ = "欧阳卓元（深圳市龙华区和平实验小学 四年级三班）"
