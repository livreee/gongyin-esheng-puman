# -*- coding: utf-8 -*-
import io
p = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\21天财富剧本.html"
out = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\_shots\_check_badge.html"
s = io.open(p, encoding="utf-8").read()
marker = "render();\n</script>"
assert marker in s
s = s.replace(marker, "history.replaceState(null,'','#/home'); render(); switchTab('badge');\n</script>")
io.open(out, "w", encoding="utf-8").write(s)
print("badge check file ready v3")
