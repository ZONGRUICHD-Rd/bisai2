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
window.addEventListener("resize", fitCanvas);
document.addEventListener("fullscreenchange", () => setTimeout(fitCanvas, 50));

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
  fitCanvas();
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
    const r = canvas.getBoundingClientRect();
    bridge.click((e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height);
    canvas.focus({ preventScroll: true });
  });
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

// ---------------------------------------------------------------- 全屏 --
document.getElementById("fullscreen").addEventListener("click", () => {
  const stage = document.getElementById("stage");
  if (document.fullscreenElement) document.exitFullscreen();
  else if (stage.requestFullscreen) stage.requestFullscreen();
  canvas.focus({ preventScroll: true });
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
