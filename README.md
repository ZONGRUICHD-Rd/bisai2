# 会学习的红绿灯 · 龙华智慧路口 AI 交通指挥官

> **作者：欧阳卓元**　深圳市龙华区和平实验小学 四年级三班
> 2026 年深圳市龙华区人工智能创意编程挑战赛 · Python 小学组

一个用 **纯 Python 从零手写 Q 学习算法**、会自己学会指挥十字路口的 AI 红绿灯。
左边传统定时灯、右边 AI 灯，迎来**完全相同的车流**，实时比较谁让大家等得更少、排放更低。

**在线演示（评委无需安装）：** https://zongruichd-rd.github.io/bisai2/
**作品介绍视频：** [作品介绍视频.mp4](作品介绍视频.mp4)（3 分 56 秒，带配音和字幕；网页上也能直接播放）

| AI 平均减少等待 | 第三方库 | 代码 |
| --- | --- | --- |
| **约 60%**（早高峰 60%、深夜 67%） | **0 个**，只用 Python 标准库 | 电脑版和网页版是**同一份** Python 源码 |

## 快速开始

```bash
python main.py            # 打开图形界面（也可以用海龟编辑器 / IDLE 打开 main.py 直接运行）
python train.py           # 从零训练 AI 24 小时虚拟车流并考试（约 10 秒）
python train.py --exam    # 只给现有的 AI 考试
python -m unittest        # 运行自动测试
```

> 需要 Python 3.6+。请保持 `main.py` 和 `smartlight/` 文件夹在同一个目录。

### 操作

| 按键 | 功能 |
| --- | --- |
| 空格 | 暂停 / 继续 |
| S / 1 2 3 | 倍速 x1 / x3 / x8 |
| C | 切换场景：智能一天、早高峰、晚高峰、平峰、深夜 |
| A | 派出救护车 |
| T | 极速训练：AI 在虚拟路口“做梦”练习 2 小时 |
| R | 清空 AI 大脑，看它从零学起 |
| L | 载入训练好的“学霸大脑” |
| V | 保存当前大脑到 `my_brain.json`（电脑版） |
| H | AI 原理说明 |

## 项目结构

```
main.py                    电脑版入口（tkinter）
train.py                   命令行训练 & 考试
smartlight/
  config.py                所有可调参数
  traffic.py               交通仿真：车、车道、信号灯、路口
  brain.py                 AI 大脑：Q 学习 + 经验回放（纯手写）
  controllers.py           定时控制器 / AI 控制器 / 安全规则层
  scenario.py              一天的车流变化
  world.py                 对比实验场 / 极速训练 / 考试
  render.py                把世界翻译成“绘图指令清单”
  ui.py                    按钮、键盘、浮层
  web_bridge.py            网页版对接
  pretrained_brain.json    训练好的大脑
web/                       网页版外壳（Pyodide 在浏览器里运行上面的 Python）
tools/build_site.py        生成网页版到 _site/
tests/                     自动测试
作品说明文档.md / .pdf     参赛说明文档（设计意图、功能、材料、实现过程、反思）
作品论文.pdf               LaTeX 论文版（源文件 paper/main.tex，实验 tools/experiments.py）
作品介绍视频.mp4           介绍视频（由 tools/make_video.py 生成）
```

## 网页版

网页版用 [Pyodide](https://pyodide.org) 在浏览器里运行**同一份** `smartlight` Python 代码，JavaScript 只负责把 Python 生成的绘图指令画到 canvas 上。

本地预览：

```bash
python tools/build_site.py
python -m http.server -d _site 8000     # 打开 http://localhost:8000
```

推送到 GitHub 后，`.github/workflows/pages.yml` 会自动运行测试、生成网页并发布到 GitHub Pages
（第一次需要在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**）。

更多细节见 [作品说明文档.md](作品说明文档.md)。
