# -*- coding: utf-8 -*-
import io
p = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\21天财富剧本.html"
s = io.open(p, encoding="utf-8").read()
old = """+'" width="'+cell+'" height="'+cell+'" rx="1.4" fill="'+fill+'" stroke="#23283C" stroke-width="1" class="'+(on?'bead-pop':'')+'" style="transform-box:fill-box;transform-origin:center;animation-delay:'+(ri*40+ci*40)+'ms"/>';"""
new = """+'" width="'+cell+'" height="'+cell+'" rx="1.4" fill="'+fill+'" stroke="#23283C" stroke-width="1" class="'+(on?'bead-pop':'')+'" style="transform-box:fill-box;transform-origin:center;animation-delay:'+(ri*40+ci*40)+'ms"/>';"""
# 目标：修掉 x 属性值里的多余空格 `x="6 "` -> `x="6"`
old_x = """x="'+(ci*(cell+gap))+' " y="""
new_x = """x="'+(ci*(cell+gap))+'" y="""
assert old_x in s, "pattern not found"
s = s.replace(old_x, new_x)
io.open(p, "w", encoding="utf-8").write(s)
print("fixed x-attr")
