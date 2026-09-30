# -*- coding: utf-8 -*-
import io

p = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\21天财富剧本.html"
s = io.open(p, encoding="utf-8").read()

# 1) CSS：像素风音乐开关按钮
css_anchor = ".hidden{display:none!important}"
assert css_anchor in s
BGM_CSS = """/* ===== 背景音乐开关（像素风） ===== */
.bgm-btn{position:fixed;top:16px;right:max(12px,calc((100vw - 430px)/2 + 12px));z-index:60;width:46px;height:46px;border-radius:12px;border:2.5px solid var(--ink);background:rgba(255,248,236,.94);box-shadow:3px 3px 0 var(--ink);display:flex;align-items:center;justify-content:center;cursor:pointer;font-family:inherit;transition:transform .08s ease, box-shadow .08s ease}
.bgm-btn:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--ink)}
.bgm-btn svg{width:22px;height:22px}
.bgm-btn .mute{display:none;color:#A9A294}
.bgm-btn.muted .play{display:none}
.bgm-btn.muted .mute{display:block}
@media (min-width:520px){.bgm-btn{right:calc((100vw - 430px)/2 + 12px)}}

"""
s = s.replace(css_anchor, BGM_CSS + css_anchor)

# 2) 按钮 + audio 元素（放在 toast 前）
btn_anchor = '<div class="toast" id="toast"></div>'
assert btn_anchor in s
BGM_HTML = """<button class="bgm-btn" id="bgmBtn" onclick="toggleBgm()" aria-label="背景音乐开关">
  <svg class="play" viewBox="0 0 24 24" fill="none" stroke="#F5A623" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
  <svg class="mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/><path d="M3 3l18 18"/></svg>
</button>
<audio id="bgm" src="assets/bgm.wav" loop preload="auto" style="display:none"></audio>
"""
s = s.replace(btn_anchor, BGM_HTML + btn_anchor)

# 3) JS：音乐控制逻辑
js_anchor = "/* ========== 启动 ========== */"
assert js_anchor in s
BGM_JS = """/* ========== 背景音乐 ========== */
const bgm = document.getElementById('bgm');
const bgmBtn = document.getElementById('bgmBtn');
function setBgmBtn(muted){ if(bgmBtn) bgmBtn.classList.toggle('muted', muted); }
function toggleBgm(){
  if(!bgm) return;
  if(bgm.paused){ bgm.play().catch(()=>{ toast('浏览器拦截了自动播放，点击页面任意处即可开启音乐'); setBgmBtn(true); }); setBgmBtn(false); }
  else { bgm.pause(); setBgmBtn(true); }
  try{ localStorage.setItem('bgm', bgm.paused ? 'off' : 'on'); }catch(e){}
}
/* 首次任意点击尝试开播（多数浏览器要求用户手势） */
function tryAutoBgm(){
  if(bgm && bgm.paused){
    try{ if(localStorage.getItem('bgm') === 'off'){ setBgmBtn(true); return; } }catch(e){}
    bgm.play().catch(()=>{ setBgmBtn(true); });
    setBgmBtn(false);
  }
}
document.addEventListener('pointerdown', tryAutoBgm, {once:true});

"""
s = s.replace(js_anchor, BGM_JS + js_anchor)

io.open(p, "w", encoding="utf-8").write(s)
print("bgm wired, length:", len(s))
