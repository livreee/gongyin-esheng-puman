# -*- coding: utf-8 -*-
import io
p = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\21天财富剧本.html"
out = r"C:\Users\Lenovo\Doubao\chats\2026-09-17\new-chat\21天财富剧本-Demo\_shots\_check_grad.html"
s = io.open(p, encoding="utf-8").read()
marker = "render();\n</script>"
assert marker in s
inject = ("history.replaceState(null,'','#/grad'); "
          "S.line='home'; S.completed.home=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]; "
          "S.idou=4200; S.beans=210; S.lastAmount=35; render();\n</script>")
s = s.replace(marker, inject)
io.open(out, "w", encoding="utf-8").write(s)
print("grad check file ready")
