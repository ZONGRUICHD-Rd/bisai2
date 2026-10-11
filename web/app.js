// 作者：欧阳卓元（深圳市龙华区和平实验小学 四年级三班）
// 网页版外壳：只负责“把 Python 跑起来”和“把 Python 给的绘图指令画出来”。
// 仿真、AI、界面逻辑全部在 Python 里（smartlight 包），和电脑版是同一份代码。
"use strict";

const W = 1280, H = 780, FPS = 30;
const FONT = '"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif';
const ALIGN = { nw: ["left", "top"], n: ["center", "top"], ne: ["right", "top"], w: ["left", "middle"],
  center: ["center", "middle"], e: ["right", "middle"], sw: ["left", "bottom"], s: ["center", "bottom"],
  se: ["right", "bottom"] };

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const loader = document.getElementById("loader");
const loadMsg = document.getElementById("load-msg");
const loadBar = document.getElementById("load-bar");

function setLoad(msg, pct) {
  loadMsg.textContent = msg;
  loadBar.style.width = pct + "%";
}

// ---------------------------------------------------------------- 画布 --
function fitCanvas() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cssW = canvas.clientWidth || W;
  const scale = (cssW / W) * dpr;
  canvas.width = Math.round(W * scale);
  canvas.height = Math.round(H * scale);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
}

// ---------------------------------------------------------------- 全屏 --
// iPhone 的浏览器不支持“让网页元素全屏”，所以自己做：一个铺满屏幕的层。
// 手机竖着拿时，把整个层旋转 90° 变成横屏，画面能大一倍。
const stage = document.getElementById("stage");
const wrap = document.getElementById("screen-wrap");

function isFs() { return stage.classList.contains("fs"); }
function isRotated() { return stage.classList.contains("rot"); }

function layout() {
  if (!isFs()) {
    stage.removeAttribute("style");
    wrap.removeAttribute("style");
    stage.classList.remove("rot");
    fitCanvas();
    return;
  }
  const vw = window.innerWidth, vh = window.innerHeight;
  const rot = vh > vw;                       // 竖屏 → 旋转成横屏
  const lw = rot ? vh : vw, lh = rot ? vw : vh;
  stage.classList.toggle("rot", rot);
  stage.style.width = lw + "px";
  stage.style.height = lh + "px";
  stage.style.transform = rot ? "translateX(" + vw + "px) rotate(90deg)" : "none";
  const ctrlW = lw >= 1000 ? 170 : 128;
  const cw = Math.max(200, Math.min(lw - ctrlW - 26, (lh - 16) * W / H));
  wrap.style.width = Math.floor(cw) + "px";
  fitCanvas();
}

function enterFs() {
  stage.classList.add("fs");
  document.body.classList.add("fs-open");
  layout();
  const root = document.documentElement;
  const req = root.requestFullscreen || root.webkitRequestFullscreen;
  if (req) {                                  // 支持的浏览器（安卓、电脑）顺便隐藏地址栏并锁定横屏
    try {
      const p = req.call(root);
      if (p && p.then) {
        p.then(() => screen.orientation && screen.orientation.lock && screen.orientation.lock("landscape"))
          .catch(() => {}).then(() => setTimeout(layout, 300));
      }
    } catch (e) { /* 不支持就算了，铺满屏幕的层照样能用 */ }
  }
  canvas.focus({ preventScroll: true });
}

function exitFs() {
  stage.classList.remove("fs");
  document.body.classList.remove("fs-open");
  layout();
  const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
  const exit = document.exitFullscreen || document.webkitExitFullscreen;
  if (fsEl && exit) {
    const p = exit.call(document);
    if (p && p.catch) p.catch(() => {});
  }
}

window.addEventListener("resize", layout);
window.addEventListener("orientationchange", () => setTimeout(layout, 300));
function onNativeFsChange() {
  if (!(document.fullscreenElement || document.webkitFullscreenElement) && isFs()) exitFs();
  else setTimeout(layout, 100);
}
document.addEventListener("fullscreenchange", onNativeFsChange);
document.addEventListener("webkitfullscreenchange", onNativeFsChange);
document.getElementById("fullscreen").addEventListener("click", enterFs);
document.getElementById("fs-exit").addEventListener("click", exitFs);

// 屏幕上的一点 → 画布里的逻辑坐标（1280×780），旋转时要“转回来”
function toLogical(e) {
  if (isRotated()) {
    const u = e.clientY, v = window.innerWidth - e.clientX;   // 旋转层自己的坐标
    let x = 0, y = 0, el = canvas;
    while (el && el !== stage) { x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; }
    return [(u - x) * W / canvas.offsetWidth, (v - y) * H / canvas.offsetHeight];
  }
  const r = canvas.getBoundingClientRect();
  return [(e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height];
}

function roundRect(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  if (r < 1) { ctx.rect(x, y, w, h); return; }
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function draw(cmds) {
  for (const c of cmds) {
    switch (c[0]) {
      case "r": {
        const [, x, y, w, h, fill, outline, width, r, alpha] = c;
        ctx.globalAlpha = alpha;
        roundRect(x, y, w, h, r);
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        if (outline) { ctx.strokeStyle = outline; ctx.lineWidth = width; ctx.stroke(); }
        ctx.globalAlpha = 1;
        break;
      }
      case "c": {
        const [, x, y, rad, fill, outline, width] = c;
        ctx.beginPath();
        ctx.arc(x, y, rad, 0, Math.PI * 2);
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        if (outline) { ctx.strokeStyle = outline; ctx.lineWidth = width; ctx.stroke(); }
        break;
      }
      case "l": {
        const [, pts, color, width] = c;
        ctx.beginPath();
        ctx.moveTo(pts[0], pts[1]);
        for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
        ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = "round"; ctx.lineJoin = "round";
        ctx.stroke();
        break;
      }
      case "p": {
        const [, pts, fill, outline, width] = c;
        ctx.beginPath();
        ctx.moveTo(pts[0], pts[1]);
        for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
        ctx.closePath();
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        if (outline) { ctx.strokeStyle = outline; ctx.lineWidth = width; ctx.stroke(); }
        break;
      }
      case "t": {
        const [, x, y, s, color, size, bold, anchor] = c;
        const [align, base] = ALIGN[anchor] || ALIGN.nw;
        ctx.font = (bold ? "700 " : "400 ") + size + "px " + FONT;
        ctx.textAlign = align; ctx.textBaseline = base; ctx.fillStyle = color;
        ctx.fillText(s, x, y);
        break;
      }
    }
  }
}

// ---------------------------------------------------------------- 启动 --
async function loadText(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error("无法读取 " + path);
  return res.text();
}

async function boot() {
  layout();
  setLoad("正在把 Python 解释器搬进浏览器…", 10);
  const pyodide = await loadPyodide();
  setLoad("正在载入 smartlight 源代码…", 70);
  const manifest = JSON.parse(await loadText("manifest.json"));
  pyodide.FS.mkdirTree("/home/pyodide/smartlight");
  for (const f of manifest.package) {
    pyodide.FS.writeFile("/home/pyodide/" + f, await loadText("src/" + f));
  }
  setLoad("正在唤醒 AI 大脑…", 90);
  const bridge = pyodide.pyimport("smartlight.web_bridge");
  bridge.start();
  loader.classList.add("done");

  canvas.addEventListener("pointerdown", (e) => {
    const [x, y] = toLogical(e);
    bridge.click(x, y);
    canvas.focus({ preventScroll: true });
  });
  for (const btn of document.querySelectorAll("#controls button[data-key]")) {
    btn.addEventListener("click", () => {
      bridge.key(btn.dataset.key);
      canvas.focus({ preventScroll: true });
    });
  }
  canvas.addEventListener("keydown", (e) => {
    const map = { " ": "space", Escape: "escape", Enter: "return" };
    const key = map[e.key] || e.key;
    if (key.length === 1 || map[e.key]) {
      e.preventDefault();
      bridge.key(key);
    }
  });

  let last = performance.now(), acc = 0;
  function loop(now) {
    acc += Math.min(now - last, 250);
    last = now;
    let ticks = 0;
    let cmds = null;
    while (acc >= 1000 / FPS && ticks < 2) {
      cmds = bridge.frame();
      acc -= 1000 / FPS;
      ticks++;
    }
    if (ticks === 2) acc = 0;     // 电脑太慢就跳过，不要越积越多
    if (cmds) draw(JSON.parse(cmds));
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

boot().catch((err) => {
  console.error(err);
  loader.classList.add("error");
  setLoad("加载失败：" + err.message + "（请检查网络后刷新）", 100);
});

// ---------------------------------------------------------------- 成绩表 --
loadText("results.json").then((txt) => {
  const data = JSON.parse(txt);
  const tbody = document.querySelector("#exam-table tbody");
  tbody.innerHTML = "";
  let sum = 0;
  for (const row of data.rows) {
    sum += row.gain;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.name}</td><td class="fixed">${row.fixed.toFixed(1)} 秒</td>` +
      `<td class="ai">${row.ai.toFixed(1)} 秒</td>` +
      `<td><span class="barcell" style="width:${Math.max(4, row.gain)}px"></span>${row.gain.toFixed(0)}%</td>` +
      `<td>${Math.round(row.co2)} 克</td>`;
    tbody.appendChild(tr);
  }
  const avg = Math.round(sum / data.rows.length);
  document.querySelector("#chip-gain b").textContent = avg + "%";
}).catch(() => {});

// ---------------------------------------------------------------- 源码 --
loadText("manifest.json").then(async (txt) => {
  const manifest = JSON.parse(txt);
  const tabs = document.getElementById("tabs");
  const view = document.getElementById("code-view");
  const meta = document.getElementById("code-meta");
  const cache = {};
  async function show(file, btn) {
    for (const b of tabs.children) b.setAttribute("aria-selected", b === btn ? "true" : "false");
    const src = cache[file] || (cache[file] = await loadText("src/" + file));
    const doc = (manifest.docs || {})[file] || "";
    meta.textContent = `${file} · ${src.split("\n").length} 行` + (doc ? " · " + doc : "");
    view.textContent = src;
    view.removeAttribute("data-highlighted");
    if (window.hljs) hljs.highlightElement(view);
  }
  manifest.code.forEach((file, i) => {
    const btn = document.createElement("button");
    btn.textContent = file.replace("smartlight/", "");
    btn.setAttribute("role", "tab");
    btn.addEventListener("click", () => show(file, btn));
    tabs.appendChild(btn);
    if (i === 0) show(file, btn);
  });
});
