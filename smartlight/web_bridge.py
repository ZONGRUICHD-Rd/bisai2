# -*- coding: utf-8 -*-
"""
网页版桥梁：浏览器里的 JavaScript 通过这几个函数和 Python 对话。
（网页里的 Python 由 Pyodide 提供 —— 它把真正的 Python 解释器搬进了浏览器。）
"""
import json

from .ui import App

_app = None


def start():
    global _app
    _app = App(platform="web")


def frame():
    """推进一帧，返回这一帧的绘图指令（JSON 字符串）。"""
    _app.tick()
    return json.dumps(_app.render(), ensure_ascii=False, separators=(",", ":"))


def click(x, y):
    _app.on_click(float(x), float(y))


def key(name):
    _app.on_key(str(name))
