# -*- coding: utf-8 -*-
"""21天财富剧本 Demo v2 —— 像素养成游戏风改版"""
import io, sys

SRC = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\21天财富剧本.html"

with io.open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

# ---------- 1. head：像素风 favicon + 游戏字体 ----------
old_head = '''<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23C7000B'/%3E%3Cpath d='M14 44V22h8v22h-8zm28 0V14h8v30h-8zM6 44h52v6H6z' fill='%23FFFFFF'/%3E%3C/svg%3E">'''
new_head = '''<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' shape-rendering='crispEdges'%3E%3Crect width='32' height='32' fill='%2323283C'/%3E%3Crect x='6' y='6' width='20' height='20' fill='%23C7000B'/%3E%3Crect x='10' y='10' width='4' height='4' fill='%23FFD23F'/%3E%3Crect x='16' y='10' width='4' height='4' fill='%23FFD23F'/%3E%3Crect x='10' y='16' width='4' height='4' fill='%23FFFFFF'/%3E%3Crect x='16' y='16' width='4' height='4' fill='%23FFFFFF'/%3E%3C/svg%3E">
<link rel="stylesheet" href="https://miaoda.feishu.cn/fonts/css2?family=Press+Start+2P&family=ZCOOL+KuaiLe&display=swap">'''
assert old_head in html
html = html.replace(old_head, new_head)

# ---------- 2. 全量替换 <style> ----------
i1 = html.find("<style>")
i2 = html.find("</style>")
assert i1 != -1 and i2 != -1

NEW_CSS = r""":root{
  --red:#C7000B;          /* 工银红 品牌锚点 */
  --red-deep:#9E0008;
  --ink:#23283C;          /* 深墨蓝 描边/主字 */
  --cream:#FFF8EC;        /* 暖奶白 页面底 */
  --paper:#FFFFFF;
  --yellow:#FFD23F;       /* 像素黄 */
  --green:#7BC950;        /* 像素绿 */
  --blue:#4EA8DE;         /* 像素蓝 */
  --purple:#9B5DE5;       /* 像素紫 */
  --orange:#F4845F;       /* 像素橙 */
  --gold:#F5A623;         /* 暖金 */
  --teal:#0E9C8E;
  --line:#DDD3BE;
  --ink-soft:#6B6575;
  --px:3px;
  --shadow:4px 4px 0 var(--ink);
  --shadow-sm:3px 3px 0 var(--ink);
  --radius:10px;
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;image-rendering:pixelated}
html,body{height:100%}
body{
  font-family:"ZCOOL KuaiLe","PingFang SC","Microsoft YaHei","Segoe UI",sans-serif;
  background:#EDE6D6;
  color:var(--ink);
  font-size:15px;
  line-height:1.6;
}
/* 像素点阵背景 */
.stage{min-height:100vh;display:flex;justify-content:center;background:
  radial-gradient(circle, rgba(35,40,60,.10) 1.5px, transparent 1.5px),
  radial-gradient(1200px 500px at 15% -10%, rgba(199,0,11,.07), transparent 60%),
  radial-gradient(1000px 500px at 90% 110%, rgba(14,156,142,.08), transparent 60%), #EDE6D6;
  background-size:14px 14px, 100% 100%, 100% 100%, 100% 100%;}
.phone{
  width:100%;max-width:430px;min-height:100vh;
  background:var(--cream);
  position:relative;
  border-left:3px solid var(--ink);
  border-right:3px solid var(--ink);
}
@media (min-width:520px){
  .phone{margin:24px 0;min-height:calc(100vh - 48px);border-radius:26px;border:4px solid var(--ink);box-shadow:10px 10px 0 rgba(35,40,60,.85);overflow:hidden}
}
.view{display:none;padding:0 16px 96px;animation:fadeIn .22s steps(3)  }
.view.active{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* ===== 像素通用件 ===== */
.fx{font-family:"Press Start 2P","ZCOOL KuaiLe",monospace;letter-spacing:.02em}
.fz{font-family:"ZCOOL KuaiLe","PingFang SC",sans-serif}
.pixel-box{background:var(--paper);border:2.5px solid var(--ink);box-shadow:var(--shadow-sm);border-radius:var(--radius)}
.pixel-tag{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;background:var(--ink);color:#fff;border-radius:6px;padding:3px 9px;letter-spacing:.06em}

/* ===== 启动页（游戏标题画面） ===== */
#view-start{min-height:100vh;display:none;flex-direction:column;padding:0;background:var(--ink)}
#view-start.active{display:flex}
.start-top{flex:1;padding:30px 22px 20px;color:#fff;position:relative;overflow:hidden;
  background:
   linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
   linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px),
   linear-gradient(180deg,#3A4370 0%,#23283C 70%);
  background-size:22px 22px,22px 22px,100% 100%}
/* 像素星空 */
.sky-deco{position:absolute;inset:0;pointer-events:none}
.sky-deco i{position:absolute;width:6px;height:6px;background:var(--yellow);box-shadow:0 0 0 2px rgba(255,210,63,.25);animation:twinkle 2s steps(2) infinite}
.sky-deco i:nth-child(1){left:8%;top:12%}
.sky-deco i:nth-child(2){left:82%;top:8%;animation-delay:.5s}
.sky-deco i:nth-child(3){left:70%;top:24%;width:4px;height:4px;animation-delay:1s}
.sky-deco i:nth-child(4){left:16%;top:34%;width:4px;height:4px;animation-delay:1.4s}
.sky-deco i:nth-child(5){left:90%;top:44%;animation-delay:.8s}
.sky-deco i:nth-child(6){left:30%;top:6%;animation-delay:1.8s}
@keyframes twinkle{0%,100%{opacity:.35}50%{opacity:1}}
/* 像素云 */
.cloud{position:absolute;background:#fff;opacity:.92}
.cloud::before,.cloud::after{content:"";position:absolute;background:#fff}
.cloud.c1{width:64px;height:14px;left:-8px;top:52%;border-radius:2px}
.cloud.c1::before{width:22px;height:22px;left:12px;top:-10px;border-radius:3px}
.cloud.c1::after{width:16px;height:16px;left:34px;top:-6px;border-radius:3px}
.cloud.c2{width:52px;height:12px;right:-6px;top:30%;border-radius:2px}
.cloud.c2::before{width:18px;height:18px;left:10px;top:-8px;border-radius:3px}
.cloud.c2::after{width:14px;height:14px;left:28px;top:-5px;border-radius:3px}
.start-brand{display:flex;align-items:center;gap:10px;font-size:12px;color:#C9D2E0;position:relative;z-index:1}
.start-brand svg{width:30px;height:30px;border:2px solid #fff;border-radius:8px}
.title-box{position:relative;z-index:1;margin-top:38px;text-align:center}
.title-box .kicker{font-size:10px;color:var(--yellow);margin-bottom:16px;letter-spacing:.12em}
.title-box h1{font-size:46px;line-height:1.1;font-weight:700;color:#fff;letter-spacing:.04em;
  text-shadow:3px 3px 0 var(--red),6px 6px 0 rgba(199,0,11,.45)}
.title-box .sub-line{display:inline-block;margin-top:14px;font-size:14px;color:var(--yellow);background:rgba(255,210,63,.12);border:1.5px dashed rgba(255,210,63,.7);border-radius:8px;padding:5px 14px;letter-spacing:.2em}
.title-box p{margin-top:18px;font-size:13.5px;color:#B9C4D8;max-width:26em;line-height:1.8}
.start-cards{display:flex;gap:10px;margin-top:26px;position:relative;z-index:1}
.start-cards>div{flex:1;background:rgba(255,255,255,.09);border:2px solid rgba(255,255,255,.55);border-radius:10px;padding:12px 6px 10px;text-align:center;box-shadow:3px 3px 0 rgba(0,0,0,.3)}
.start-cards b{display:block;font-size:15px;color:var(--yellow);margin-bottom:6px}
.start-cards span{font-size:11.5px;color:#C9D2E0}
.start-bottom{padding:18px 22px 24px;background:var(--ink);border-top:3px solid var(--yellow);position:relative;z-index:1}
.start-bottom .note{font-size:10.5px;color:#8FA0BA;margin-top:12px;text-align:center;line-height:1.7}
.btn{display:block;width:100%;border:0;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer;text-align:center;font-family:inherit;transition:transform .08s ease, box-shadow .08s ease}
.btn:active{transform:translate(3px,3px);box-shadow:none!important}
.btn-start{background:var(--yellow);color:var(--ink);border:3px solid var(--ink);box-shadow:6px 6px 0 rgba(255,255,255,.22);padding:15px 0}
.btn-start .fx{font-size:14px}
.btn-primary{background:var(--red);color:#fff;border:2.5px solid var(--ink);box-shadow:5px 5px 0 var(--ink);padding:14px 0}
.btn-primary:hover{background:var(--red-deep)}
.btn-ghost{background:transparent;color:var(--ink-soft);padding:12px 0;font-size:14px;font-weight:500}
.btn-ghost:hover{color:var(--ink)}
.btn-line{background:var(--paper);border:2.5px solid var(--ink);box-shadow:4px 4px 0 var(--ink);color:var(--ink);padding:13px 0;font-size:15px;border-radius:12px}
.btn-line:hover{background:var(--cream)}
.btn-line:active{box-shadow:none;transform:translate(2px,2px)}
.btn-sm{display:inline-block;width:auto;padding:9px 18px;font-size:14px}

/* ===== 通用头部 ===== */
.app-head{position:sticky;top:0;z-index:20;background:rgba(255,248,236,.94);backdrop-filter:blur(8px);border-bottom:3px solid var(--ink);margin:0 -16px;padding:12px 16px;display:flex;align-items:center;gap:12px}
.app-head .back{background:none;border:2px solid var(--ink);border-radius:8px;cursor:pointer;padding:3px 5px;display:flex;color:var(--ink);box-shadow:2px 2px 0 var(--ink)}
.app-head .back:active{box-shadow:none;transform:translate(2px,2px)}
.app-head h2{font-size:18px;font-weight:700;flex:1;text-align:center;letter-spacing:.04em}
.app-head .spacer{width:34px}
.section-title{font-size:14px;font-weight:700;margin:22px 0 12px;display:flex;align-items:center;gap:8px;letter-spacing:.04em}
.section-title::after{content:"";flex:1;height:3px;background:repeating-linear-gradient(90deg,var(--ink) 0 8px,transparent 8px 16px)}

/* ===== 财富人格测试 ===== */
.quiz-progress{height:12px;background:#E4DCC8;border:2px solid var(--ink);border-radius:6px;margin:18px 0 6px;overflow:hidden}
.quiz-progress i{display:block;height:100%;background:repeating-linear-gradient(90deg,var(--red) 0 12px,#B3000A 12px 24px);border-right:2px solid var(--ink);transition:width .3s steps(6)}
.quiz-step{font-size:12px;color:var(--ink-soft);margin-bottom:18px}
.quiz-step .fx{font-size:11px;color:var(--red)}
.quiz-q{font-size:19px;font-weight:700;line-height:1.5;margin-bottom:20px}
.quiz-opt{display:block;width:100%;text-align:left;background:var(--paper);border:2.5px solid var(--ink);border-radius:12px;padding:14px 16px;margin-bottom:10px;font-size:15px;font-family:inherit;color:var(--ink);cursor:pointer;box-shadow:4px 4px 0 var(--ink);transition:all .08s}
.quiz-opt:hover{transform:translate(-1px,-1px);box-shadow:5px 5px 0 var(--ink)}
.quiz-opt:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--ink)}
.quiz-opt.selected{border-color:var(--red);background:#FFF1D6;font-weight:700;box-shadow:4px 4px 0 var(--red)}
.quiz-skip{display:block;width:100%;background:none;border:0;color:var(--ink-soft);text-align:center;padding:12px 0;font-size:14px;cursor:pointer;font-family:inherit}

/* ===== 剧情线选择 ===== */
.line-card{display:block;width:100%;text-align:left;background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:16px;margin-bottom:12px;cursor:pointer;font-family:inherit;color:var(--ink);box-shadow:4px 4px 0 var(--ink);transition:all .08s}
.line-card:hover,.line-card:focus{transform:translate(-1px,-1px);box-shadow:5px 5px 0 var(--ink);outline:none}
.line-card:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--ink)}
.line-card-top{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.line-icon{width:46px;height:46px;border-radius:12px;border:2.5px solid var(--ink);display:flex;align-items:center;justify-content:center;flex:none;box-shadow:3px 3px 0 var(--ink)}
.line-icon svg{width:24px;height:24px}
.line-card h3{font-size:18px;font-weight:700}
.line-card .tag{font-size:10.5px;color:#fff;border-radius:6px;padding:3px 8px;margin-left:auto;flex:none;letter-spacing:.06em;border:2px solid var(--ink);box-shadow:2px 2px 0 var(--ink)}
.line-card .desc{font-size:13.5px;color:var(--ink-soft);margin-bottom:8px}
.line-card .meta{font-size:12px;color:var(--ink-soft);display:flex;gap:10px;flex-wrap:wrap}
.line-card .meta b{color:var(--teal);font-weight:700}
.line-tip{font-size:12px;color:var(--ink-soft);background:#F3EBD8;border:2px dashed var(--line);border-radius:10px;padding:10px 12px;margin-top:14px;line-height:1.7}

/* ===== 主旅程 ===== */
.journey-hero{border:3px solid var(--ink);border-radius:14px;overflow:hidden;margin-top:16px;position:relative;color:#fff;box-shadow:5px 5px 0 var(--ink)}
.journey-hero .bg{position:absolute;inset:0;z-index:0}
.journey-hero .bg::after{content:"";position:absolute;inset:0;background:
  linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px),
  linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px);
  background-size:18px 18px}
.journey-hero .inner{position:relative;z-index:1;padding:16px 16px 14px}
.journey-line{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;background:var(--ink);color:#fff;border-radius:6px;padding:4px 10px;margin-bottom:10px;letter-spacing:.06em}
.journey-day{font-size:12px;color:rgba(255,255,255,.9);margin-bottom:2px}
.journey-day b{font-size:24px;color:var(--yellow);font-weight:700}
.journey-day .fx{color:var(--yellow)}
.journey-act{font-size:16.5px;font-weight:700;margin-bottom:12px;text-shadow:2px 2px 0 rgba(35,40,60,.35)}
.journey-progress{height:14px;background:rgba(255,255,255,.25);border:2px solid var(--ink);border-radius:7px;overflow:hidden}
.journey-progress i{display:block;height:100%;border-right:2px solid var(--ink);transition:width .5s steps(8);background:repeating-linear-gradient(90deg,var(--yellow) 0 14px,#E8A33D 14px 28px)}
.acts{display:flex;gap:6px;margin-top:10px;font-size:11.5px}
.acts span{flex:1;text-align:center;background:rgba(255,255,255,.14);border:1.5px solid rgba(255,255,255,.5);border-radius:6px;padding:4px 2px;color:rgba(255,255,255,.95)}
.acts span.on{background:var(--yellow);border-color:var(--ink);color:var(--ink);font-weight:700}

.story-card{background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:16px;margin-top:16px;box-shadow:var(--shadow-sm)}
.story-label{font-size:11px;font-weight:700;color:var(--red);letter-spacing:.14em;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.story-label::before{content:"";width:10px;height:10px;background:var(--red);border:2px solid var(--ink);border-radius:3px}
.story-text{font-size:16px;font-weight:700;line-height:1.65;margin-bottom:10px}
.story-idea{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--teal);background:#E2F4E2;border:2px solid var(--teal);border-radius:20px;padding:4px 12px;font-weight:700}

.task-card{background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:16px;margin-top:14px;box-shadow:var(--shadow-sm)}
.task-head{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;margin-bottom:4px;color:var(--ink-soft)}
.task-head .dot{width:12px;height:12px;border-radius:3px;background:var(--yellow);border:2px solid var(--ink);animation:blink 1s steps(2) infinite}
@keyframes blink{50%{opacity:.35}}
.task-title{font-size:17px;font-weight:700;margin-bottom:6px}
.task-sub{font-size:13px;color:var(--ink-soft);margin-bottom:14px;line-height:1.7}
.task-zone{min-height:70px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.box-item{background:var(--yellow);border:3px solid var(--ink);border-radius:14px;padding:16px 18px;text-align:center;cursor:pointer;box-shadow:5px 5px 0 var(--ink);transition:all .08s;font-family:inherit}
.box-item:hover{transform:translate(-1px,-1px);box-shadow:6px 6px 0 var(--ink)}
.box-item:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--ink)}
.box-item b{display:block;font-size:19px;color:var(--ink)}
.box-item span{font-size:12px;color:var(--ink-soft)}
.result-badge{background:var(--green);color:#fff;border:3px solid var(--ink);border-radius:14px;padding:14px 20px;text-align:center;box-shadow:5px 5px 0 var(--ink);animation:fadeIn .25s steps(3)}
.result-badge b{font-size:22px;display:block;text-shadow:2px 2px 0 rgba(35,40,60,.3)}
.result-badge span{font-size:12.5px}
.task-done{background:#E2F4E2;border:2.5px solid var(--green);border-radius:14px;padding:14px;text-align:center;font-size:14px;color:var(--teal);font-weight:700}
.milestone{background:#FFF1D6;border:2.5px solid var(--gold);border-radius:14px;padding:13px 16px;margin-top:14px;font-size:13.5px;color:#8A5A14;line-height:1.7;box-shadow:3px 3px 0 rgba(245,166,35,.4)}

/* ===== 进度可视化（像素拼豆场景） ===== */
.scene-card{background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:14px 16px;margin-top:14px;box-shadow:var(--shadow-sm)}
.scene-label{font-size:12px;font-weight:700;letter-spacing:.1em;color:var(--ink-soft);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.scene-label .pct{color:var(--red);font-size:14px;font-weight:700}
.scene-stage{font-size:15px;font-weight:700;margin-bottom:12px}
.scene-visual{height:124px;border:2.5px solid var(--ink);border-radius:10px;position:relative;overflow:hidden;background:#FDF6E3}
.scene-visual svg{position:absolute;inset:0;width:100%;height:100%}

/* ===== 21天日历 ===== */
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:12px;box-shadow:var(--shadow-sm)}
.cal-cell{aspect-ratio:1;border-radius:8px;border:2px solid var(--ink);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--ink-soft);cursor:pointer;position:relative;background:var(--cream);transition:all .1s;box-shadow:2px 2px 0 var(--ink)}
.cal-cell:hover{border-color:var(--red)}
.cal-cell:active{box-shadow:none;transform:translate(2px,2px)}
.cal-cell.today{border:3px solid var(--red);color:var(--red);background:#FFF1D6}
.cal-cell.done{background:var(--green);border-color:var(--ink);color:#fff}
.cal-cell.done::after{content:"";position:absolute;left:50%;top:50%;width:10px;height:5px;border-left:2.5px solid #fff;border-bottom:2.5px solid #fff;transform:translate(-50%,-60%) rotate(-45deg)}
.cal-cell.milestone::before{content:"";position:absolute;top:3px;left:50%;transform:translateX(-50%);width:8px;height:4px;background:var(--gold);border-radius:2px}
.cal-cell.done.milestone::before{background:#FFF1D6}
.cal-cell.current{outline:3px dashed var(--gold);outline-offset:1px}
.cal-legend{display:flex;gap:14px;font-size:12px;color:var(--ink-soft);margin-top:10px;flex-wrap:wrap}
.cal-legend i{display:inline-block;width:11px;height:11px;border:2px solid var(--ink);border-radius:3px;margin-right:5px;vertical-align:-1px}

/* ===== 小队 ===== */
.squad-card{background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:16px 16px;margin-top:16px;box-shadow:var(--shadow-sm)}
.squad-rule{font-size:12px;color:var(--ink-soft);margin-bottom:14px;display:flex;align-items:center;gap:6px}
.squad-list{display:flex;flex-direction:column;gap:11px}
.squad-row{display:flex;align-items:center;gap:12px}
.squad-ava{width:38px;height:38px;border-radius:8px;border:2.5px solid var(--ink);display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;flex:none;box-shadow:3px 3px 0 var(--ink)}
.squad-name{font-size:14px;font-weight:700;width:64px;flex:none}
.squad-bar{flex:1;height:12px;background:#E4DCC8;border:2px solid var(--ink);border-radius:6px;overflow:hidden}
.squad-bar i{display:block;height:100%;border-right:2px solid var(--ink)}
.squad-num{font-size:12px;color:var(--ink-soft);width:46px;text-align:right;flex:none}

/* ===== 徽章（拼豆） ===== */
.badge-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;background:var(--paper);border:2.5px solid var(--ink);border-radius:14px;padding:16px;box-shadow:var(--shadow-sm)}
.badge{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
.badge .ico{width:74px;height:74px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#F1EAD6;border:2.5px solid var(--ink);box-shadow:3px 3px 0 var(--ink);transition:all .2s}
.badge.lit .ico{background:#FFF8EC;box-shadow:0 0 0 3px rgba(245,166,35,.35),3px 3px 0 var(--ink)}
.badge span{font-size:11.5px;color:var(--ink-soft);line-height:1.35}
.badge.lit span{color:var(--ink);font-weight:700}
.badge .got{font-size:10.5px;color:var(--teal);font-weight:700}
.badge .lock{font-size:10.5px;color:#A9A294}
.bead-pop{animation:beadPop .28s ease backwards}
@keyframes beadPop{0%{transform:scale(.2)}70%{transform:scale(1.15)}100%{transform:scale(1)}}

/* ===== 结业 ===== */
.grad-hero{background:linear-gradient(180deg,#3A4370,#23283C);border:3px solid var(--ink);border-radius:14px;color:#fff;padding:28px 20px;text-align:center;margin-top:16px;position:relative;overflow:hidden;box-shadow:5px 5px 0 var(--ink)}
.grad-hero::after{content:"";position:absolute;right:-40px;top:-40px;width:140px;height:140px;border-radius:50%;background:radial-gradient(circle, rgba(255,210,63,.5), transparent 70%)}
.grad-hero .seal{width:66px;height:66px;border-radius:50%;background:var(--yellow);border:3px solid var(--ink);display:flex;align-items:center;justify-content:center;margin:0 auto 14px;box-shadow:5px 5px 0 rgba(0,0,0,.35)}
.grad-hero .seal svg{filter:drop-shadow(2px 2px 0 rgba(35,40,60,.4))}
.grad-hero h2{font-size:22px;font-weight:700;margin-bottom:6px;position:relative;z-index:1}
.grad-hero p{font-size:14px;color:#C9D2E0;position:relative;z-index:1}
.grad-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
.grad-stat{background:var(--paper);border:2.5px solid var(--ink);border-radius:12px;padding:14px 8px;text-align:center;box-shadow:3px 3px 0 var(--ink)}
.grad-stat b{display:block;font-size:21px;color:var(--red);font-weight:700}
.grad-stat span{font-size:12px;color:var(--ink-soft)}
.next-card{background:#E2F4E2;border:2.5px solid var(--teal);border-radius:14px;padding:16px 16px;margin-top:14px}
.next-card h4{font-size:15px;font-weight:700;color:var(--teal);margin-bottom:6px}
.next-card p{font-size:13px;color:var(--ink-soft);line-height:1.7}
.next-card .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.next-card .chip{background:#fff;border:2px solid var(--teal);color:var(--teal);border-radius:16px;padding:4px 12px;font-size:12px;font-weight:600}

/* ===== 底部导航 ===== */
.bottom-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:430px;background:rgba(255,255,255,.97);backdrop-filter:blur(10px);border-top:3px solid var(--ink);display:flex;z-index:30}
@media (min-width:520px){.bottom-nav{bottom:24px;border-radius:16px;border:3px solid var(--ink);box-shadow:5px 5px 0 rgba(35,40,60,.5);width:calc(100% - 48px)}}
.nav-btn{flex:1;background:none;border:0;padding:10px 0 9px;display:flex;flex-direction:column;align-items:center;gap:3px;cursor:pointer;font-family:inherit;color:#8A8578}
.nav-btn svg{width:22px;height:22px;stroke-width:2.4}
.nav-btn span{font-size:11px;font-weight:700}
.nav-btn.on{color:var(--red)}
.nav-btn.on svg{stroke:var(--red)}

/* ===== 提示与合规 ===== */
.toast{position:fixed;top:18px;left:50%;transform:translateX(-50%) translateY(-90px);background:var(--ink);color:#fff;font-size:13px;padding:11px 20px;border-radius:10px;border:2.5px solid var(--yellow);z-index:99;transition:transform .25s steps(4);max-width:86%;text-align:center;box-shadow:4px 4px 0 rgba(0,0,0,.35)}
.toast.show{transform:translateX(-50%) translateY(0)}
.compliance{font-size:10.5px;color:#A9A294;text-align:center;padding:16px 22px 24px;line-height:1.8}

.hidden{display:none!important}"""

html = html[:i1+len("<style>")] + NEW_CSS + html[i2:]

# ---------- 3. 启动页重写（游戏标题画面） ----------
a1 = html.find("<!-- ===== 视图：启动页 ===== -->")
a2 = html.find("<!-- ===== 视图：财富人格测试 ===== -->")
assert a1 != -1 and a2 != -1

NEW_START = '''<!-- ===== 视图：启动页（游戏标题画面） ===== -->
<section id="view-start" class="view">
  <div class="start-top">
    <div class="sky-deco"><i></i><i></i><i></i><i></i><i></i><i></i></div>
    <div class="cloud c1"></div><div class="cloud c2"></div>
    <div class="start-brand">
      <svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect width="32" height="32" fill="#23283C"/><rect x="6" y="6" width="20" height="20" fill="#C7000B"/><rect x="10" y="10" width="4" height="4" fill="#FFD23F"/><rect x="16" y="10" width="4" height="4" fill="#FFD23F"/><rect x="10" y="16" width="4" height="4" fill="#FFFFFF"/><rect x="16" y="16" width="4" height="4" fill="#FFFFFF"/></svg>
      <span class="fx">ICBC · MONEY RPG</span>
    </div>
    <div class="title-box">
      <div class="kicker fx">21-DAY MONEY RPG</div>
      <h1 class="fz">工银e生</h1>
      <div class="sub-line">21 天扑满计划</div>
      <p>我的小家 · 宝贝计划 · 说走就走 · 自由Gap · 第一次独居<br>选一条人生剧情线，每天 5 分钟，把理财养成一场游戏。</p>
    </div>
    <div class="start-cards">
      <div><b class="fx">21</b><span>天完整剧本</span></div>
      <div><b class="fx">5</b><span>分钟 / 天</span></div>
      <div><b class="fx">5</b><span>条剧情线</span></div>
    </div>
  </div>
  <div class="start-bottom">
    <button class="btn btn-start" onclick="go('#/quiz')"><span class="fx">▶ START</span>　开始我的 21 天</button>
    <div class="note">DEMO v1.0 · 演示数据不连接真实账户 · 正式版理财跳转均走标准风险测评</div>
  </div>
</section>

'''
html = html[:a1] + NEW_START + html[a2:]

# ---------- 4. 场景SVG像素化 ----------
b1 = html.find("function sceneSvg")
b2 = html.find("/* ========== 小队 ========== */")
assert b1 != -1 and b2 != -1

NEW_SCENE = '''function sceneSvg(lineId, done, color){
  const lit = Math.min(7, Math.ceil(done/3));
  let dots = '';
  for(let i=0;i<7;i++){
    const x = 14 + i*7, y = i<lit ? 12 : 14;
    dots += '<rect x="'+x+'" y="'+y+'" width="5" height="5" rx="1" fill="'+(i<lit?color:'#D8CFB8')+'" stroke="#23283C" stroke-width="1"/>';
  }
  const g = '<g stroke="#23283C" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round">';
  const glyph = {
    home:'<path d="M22 66v-18l-16-10-16 10v18"/><rect x="8" y="52" width="8" height="14" stroke-width="2.2"/><rect x="16" y="52" width="8" height="14" stroke-width="2.2"/><rect x="28" y="52" width="8" height="14" stroke-width="2.2"/><rect x="38" y="52" width="8" height="14" stroke-width="2.2"/><path d="M32 42v-6"/><rect x="30" y="34" width="4" height="4"/>',
    baby:'<path d="M28 30c-8 6-8 16 0 22s20 6 20-4c-8 0-14-7-14-16 0-6-3-9-6-2z"/><circle cx="42" cy="56" r="7"/><path d="M39 56h6M42 53v6"/><path d="M22 40h-6a5 5 0 0 0 5 5h1"/>',
    travel:'<rect x="12" y="42" width="34" height="22" rx="4"/><path d="M20 42v-5h18v5"/><rect x="20" y="51" width="18" height="5" rx="2"/><path d="M12 54h34" opacity=".4"/>',
    gap:'<rect x="20" y="26" width="24" height="32" rx="3"/><path d="M26 34h12M26 40h12M26 46h6"/><circle cx="39" cy="47" r="6" stroke="#F5A623" fill="rgba(245,166,35,.25)"/><path d="M36 47h6M39 44v6"/>',
    solo:'<path d="M28 20c0 11-5 16-11 19 6 3 11 8 11 19 0-11 5-16 11-19-6-3-11-8-11-19z"/><path d="M28 58v10"/><rect x="25" y="68" width="6" height="6"/><path d="M20 38c-6-3-11-8-11-19 0 11 5 16 11 19zM36 38c6-3 11-8 11-19 0 11-5 16-11 19z" opacity=".7"/>'
  }[lineId] || '';
  return '<svg viewBox="0 0 62 80" preserveAspectRatio="xMidYMid meet" aria-hidden="true">'
    +'<defs><pattern id="pxgrid" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#FDF6E3"/><rect width="8" height="8" fill="none" stroke="#E9DFC6" stroke-width="1"/></pattern></defs>'
    +'<rect x="2" y="2" width="58" height="76" rx="6" fill="url(#pxgrid)" stroke="#23283C" stroke-width="2.5"/>'
    +'<rect x="10" y="8" width="42" height="14" rx="4" fill="'+(done>0?color:'#EFE7D0')+'" stroke="#23283C" stroke-width="2"/>'
    +dots
    +g+glyph+'</g>'
    +'</svg>';
}

'''
html = html[:b1] + NEW_SCENE + html[b2:]

# ---------- 5. 徽章：拼豆收集册 ----------
c1 = html.find("const BADGES = [")
c2 = html.find("/* ========== 小队页 ========== */")
assert c1 != -1 and c2 != -1

NEW_BADGE = '''const BADGES = [
  {n:'迈出第一步', d:'完成第1天', cond:done=>done>=1, col:'#C7000B'},
  {n:'连续3天', d:'连续打卡3天', cond:done=>done>=3, col:'#F4845F'},
  {n:'觉醒者', d:'完成第7天·第一幕', cond:done=>done>=7, col:'#FFD23F'},
  {n:'积累者', d:'完成第14天·第二幕', cond:done=>done>=14, col:'#7BC950'},
  {n:'坚持14天', d:'连续打卡14天', cond:done=>done>=14, col:'#4EA8DE'},
  {n:'守护者', d:'完成第21天·第三幕', cond:done=>done>=21, col:'#9B5DE5'},
  {n:'全勤毕业', d:'21天全勤', cond:done=>done>=21, col:'#F5A623'},
  {n:'理财启蒙', d:'完成全部21天', cond:done=>done>=21, col:'#0E9C8E'}
];
/* 拼豆图案：8行字符画，. = 灰豆，# = 主题色豆，o = 金色豆 */
const BEAD_ART = [
  ['........','..###...','..####..','..#####.','..####..','..###...','..#.....','..#.....'], /* 起点旗 */
  ['...#...#','..###.##','...#...#','........','....#...','...###..','....#...','........'], /* 三星连珠 */
  ['...#...','.#.#.#.','..#.#..','.##.##.','..#.#..','.#.#.#.','...#...','........'],       /* 太阳觉醒 */
  ['........','..####..','.##oo##.','.#oooo#.','.#oooo#.','.##oo##.','..####..','........'], /* 金币 */
  ['..####..','.##oo##.','.#oooo#.','..##oo..','..####..','..####..','..#..#..','........'], /* 奖杯 */
  ['.######.','.#....#.','.#.##.#.','.#.##.#.','..#..#..','..#..#..','...##...','........'], /* 盾牌 */
  ['#......#','.#....#.','..####..','.##oo##.','.#oooo#.','..####..','........','........'], /* 皇冠 */
  ['....#...','...###..','..#####.','.######.','...###..','..#####.','...#.#..','...#....']  /* 星星 */
];
function beadSvg(art, lit, col){
  const cell = 6, gap = 1, n = art.length;
  const w = n*cell + (n-1)*gap;
  let rects = '';
  art.forEach((row,ri)=>{
    for(let ci=0;ci<row.length;ci++){
      const ch = row[ci];
      if(ch==='.') continue;
      const on = lit;
      const fill = !on ? '#D8CFB8' : (ch==='o' ? '#FFD23F' : col);
      rects += '<rect x="'+(ci*(cell+gap))+' " y="'+(ri*(cell+gap))+'" width="'+cell+'" height="'+cell+'" rx="1.4" fill="'+fill+'" stroke="#23283C" stroke-width="1" class="'+(on?'bead-pop':'')+'" style="transform-box:fill-box;transform-origin:center;animation-delay:'+(ri*40+ci*40)+'ms"/>';
    }
  });
  return '<svg viewBox="0 0 '+w+' '+w+'" width="58" height="58" shape-rendering="crispEdges" aria-hidden="true">'+rects+'</svg>';
}
function renderBadge(){
  const done = doneCount(S.line);
  return '<div class="section-title">徽章墙 · 拼豆收集册</div>'
    +'<p style="font-size:12.5px;color:var(--ink-soft);margin:-4px 0 12px;line-height:1.7">每一枚徽章都是一幅拼豆画——完成对应挑战，豆子一颗颗亮起来。</p>'
    +'<div class="badge-grid">'+BADGES.map((b,i)=>{
      const lit = b.cond(done);
      return '<div class="badge'+(lit?' lit':'')+'"><span class="ico">'+beadSvg(BEAD_ART[i], lit, b.col)+'</span><span>'+b.n+'</span>'+(lit?'<span class="got">已点亮</span>':'<span class="lock">'+b.d+'</span>')+'</div>';
    }).join('')+'</div>'
    +'<div class="line-tip" style="margin-top:14px">拼豆按完成进度逐颗点亮（演示版即时点亮；正式版按T+2到账）。</div>';
}

'''
html = html[:c1] + NEW_BADGE + html[c2:]

with io.open(SRC, "w", encoding="utf-8") as f:
    f.write(html)

print("OK, new length:", len(html))
