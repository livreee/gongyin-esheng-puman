# -*- coding: utf-8 -*-
import io, os, urllib.request

url = "https://aka.doubaocdn.com/s/qHUObvr7ba"
out_dir = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\assets"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "bgm.wav")

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=60).read()
with open(out_path, "wb") as f:
    f.write(data)
print("saved:", out_path, "size:", len(data))
# 探测文件头
print("head:", data[:16])
