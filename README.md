# 工银e生 · 21天扑满计划

面向青年用户的理财知识与储蓄习惯互动 Demo。项目将生活目标、21 天剧情任务、像素宠物养成、答题画像和时序行为分析结合起来，让用户通过小任务理解预算、储蓄、应急金与金融知识。

**当前主版本是 `web/index.html`，完整运行入口是 `python web/server.py`。** 本文统一介绍主版本、历史原型、素材、计划书、技术实现和交付方法。`21day-wealth-script/` 为历史静态版本，新功能以 `web/` 为准。

本项目为比赛演示原型。页面中的存钱金额、金币、i 豆和队友进度为演示数据，不连接真实银行账户，不执行转账、扣款或投资交易；页面出现的“存入账户”等描述不代表实际资金到账。

## 1. 快速运行

准备 Python 3.10 或以上版本（推荐 3.11+）和现代浏览器。主版本不需要安装第三方 Python 包，不需要 Node.js 或前端构建工具。

解压项目，在包含本 README 的目录打开终端：

```powershell
python --version
python web/server.py
```

访问 [本机主页面](http://127.0.0.1:8000/index.html)。终端保持运行，结束时按 `Ctrl+C`。首次运行会自动创建 `web/puman.sqlite3` 数据库。

建议演示顺序：

1. 点击“开始我的 21 天”，完成四道生活偏好题。
2. 查看财富画像、建议习惯及“看看答题依据”，选择一条剧情线。
3. 完成今日剧情、存钱挑战或每日理财一问，查看攒钱进度与“我的参与节奏”。
4. 切换日历、小队、徽章与纪念品页面，体验宠物旅行和阶段成长。
5. 需要比较不同画像时，返回选择页点击“重新测一测”；已经完成的旅程任务会保留。

也可直接双击 `web/index.html` 体验本地模式：进度保存在浏览器 `localStorage`，答题后会生成基础分析。真实 AI 生成、服务端存档和时序行为推断需要启动后端。字体使用外部样式链接，断网时会使用浏览器的备用字体。

### GitHub Pages + Render 部署

GitHub Pages 只运行静态页面，Python API 由 Render Web Service 运行。本项目后端地址为 [Render 服务](https://gongyin-esheng-puman.onrender.com)，`web/config.js` 已配置此公开网址；配置文件中没有真实密钥。[GitHub Pages](https://livreee.github.io/gongyin-esheng-puman/) 通过该地址调用 API。

如需重新部署或部署自己的副本，可使用仓库中的 `render.yaml`，按以下步骤操作：

1. 确认部署文件已提交至 [项目仓库](https://github.com/livreee/gongyin-esheng-puman) 的 `main` 分支。
2. 打开 [从本仓库创建 Render 服务](https://render.com/deploy?repo=https://github.com/livreee/gongyin-esheng-puman)，登录 Render，授权访问该仓库，按 `render.yaml` 创建 Blueprint。也可在 Render 使用 **New → Blueprint** 选择该仓库。
3. 要启用 DeepSeek，在 Render 服务的 **Environment → Add Environment Variable** 中添加 `LLM_API_KEY`，保存并重新部署。它用于后端调用模型，不应填写到 GitHub 源码、前端配置或 README。可以先不添加密钥来验证连接；未配置时自动使用规则画像。本机 Windows 加密配置不会自动上传到 Render。
4. 等待服务显示 **Live**，复制 Render 分配的实际 HTTPS 地址。先访问 `实际地址/api/health`，应返回 `ok: true`；访问 `实际地址/` 即可使用同源完整版本。`/api/ai/status` 中的 `configured` 仅表示配置齐全，需要实际生成一次画像才能确认模型调用成功。
5. 在 GitHub 编辑 **`web/config.js`**，将 `apiBaseUrl` 更新为上一步的实际地址，例如 `https://你的实际服务名.onrender.com`，不要追加 `/api`、`/index.html` 或仓库路径。提交至 `main`。此文件只存公开后端网址，不能放任何密钥。
6. GitHub **Settings → Pages** 保持从 `main` 分支的根目录发布。等待 Pages 部署完成后打开 [当前网页](https://livreee.github.io/gongyin-esheng-puman/)，根入口会跳转到 `web/` 主版本。页面应显示“后端已连接”，完成任务后可保存进度、查询参与节奏，并在配置有效时生成 AI 画像。

Render 默认自动部署所连接分支的后续提交，提交前应运行本文的本地回归测试。若使用 Fork，需将 `render.yaml` 中的 `ALLOWED_ORIGINS` 改为自己的 Pages 来源，例如 `https://你的用户名.github.io`，不含仓库路径。CORS 以域名来源区分，无法只允许同一 Pages 域名下的某一个仓库；它也不能代替用户身份认证。

默认 Blueprint 使用免费实例，不会配置付费磁盘。免费服务空闲后会休眠，首次访问需要等待唤醒；其 SQLite 位于临时磁盘，**重启、重新部署或休眠后可能丢失服务端存档与行为记录**。浏览器已有本地进度仍可保留，但不能恢复完整的历史行为事件。需要稳定保留数据时，在 Render 升级为支持持久磁盘的付费实例，挂载路径设为 `/var/data`，并将 `DB_PATH` 改为 `/var/data/puman.sqlite3`；同时更新 `render.yaml` 中的计划、磁盘及变量配置，避免以后同步 Blueprint 时覆盖设置。只改 `DB_PATH` 而未挂载磁盘不具备持久性。SQLite 版本保持单实例运行。

本方案沿用比赛原型的 Python HTTP 服务和匿名用户标识，适合小规模演示。公开 AI 接口尚未提供正式登录鉴权与调用额度控制，填写真实模型密钥前应在供应商侧设置用量预算；正式运营前需完成文末所列的上线改造。

## 2. 产品内容与体验

### 五条生活剧情线

| 标识 | 剧情线 | 生活目标 | 场景变化 |
| --- | --- | --- | --- |
| `home` | 我的小家 | 第一笔装修基金 | 从毛坯房到温馨小家 |
| `baby` | 宝贝计划 | 第一笔育儿基金 | 从空房间到布置好的婴儿房 |
| `travel` | 说走就走 | 第一笔旅行基金 | 从空行李箱到出行装备齐备 |
| `gap` | 自由 Gap | 为阶段休整准备安全垫 | 从“不敢停”到“已批准” |
| `solo` | 第一次独居 | 第一笔独居基金 | 从空出租屋到温馨小屋 |

每条线包含 21 天剧情，并以“觉醒、积累、守护”组织三个阶段。用户可切换剧情线，各条线分别记录任务完成情况。

### 已实现的模块

| 模块 | 当前行为 |
| --- | --- |
| 财富人格问卷 | 四道生活偏好题；按答案计算剧情匹配，并给出画像依据 |
| 财富画像 | 真实大模型生成或答案规则分析；支持重测、更新、保存和过期响应丢弃 |
| 今日剧情与任务 | 多种任务玩法、模拟储蓄记录、金币与 i 豆反馈 |
| 每日挑战与理财一问 | 自定义演示存钱金额、答题解析和奖励反馈 |
| 参与节奏 | 基于已记录行为展示阶段、趋势、连续完成与活跃天数 |
| 攒钱进度与日历 | 简洁图案、阶段标签、完成比例及 21 个旅程日 |
| 扑满养成 | 六种表情、点击互动、成长阶段与四季小屋 |
| 旅行与纪念品 | 每完成三天任务触发宠物旅行，返回后收集各地风物纪念品 |
| 拼豆徽章 | 八枚经典徽章、四枚旅行徽章及解锁状态 |
| 小队 | 展示模拟队友进度和团队目标；尚未实现真实邀请、多人同步或聊天 |
| 行囊与结业 | 储蓄记录、纪念品图鉴和 21 天结业回顾 |
| 音乐与音效 | Web Audio 生成复古背景音乐及交互音效，支持静音 |

## 3. 项目文件说明

```text
工银e生-21天扑满计划/
├─ README.md                         全项目唯一说明文档
├─ .gitignore                        私有配置、运行数据和交付产物排除规则
├─ .nojekyll                         GitHub Pages 直接发布静态文件
├─ index.html                        GitHub Pages 根入口，跳转至 web/ 主版本
├─ render.yaml                       Render 后端部署与环境变量模板
├─ web/                              当前主版本
│  ├─ index.html                     页面、样式、交互与本地存档
│  ├─ config.js                      公开后端网址；不存放密钥
│  ├─ server.py                      本地 HTTP 服务、API 与 SQLite 持久化
│  ├─ ai_service.py                  答题解释、画像/陪伴生成、模型请求与降级
│  ├─ behavior_model.py              时序行为特征和 HMM-Lite 前向推断
│  ├─ private_config.py              Windows 私有密钥配置工具
│  ├─ test_ai_profile.py             答题画像与模型降级测试
│  ├─ test_behavior.py               行为建模和接口测试
│  ├─ test_private_config.py         加密、配置隔离和访问边界测试
│  ├─ test_deployment.py             云端域名、跨域与存档联通测试
│  ├─ .env.example                   无真实密钥的配置示例
│  ├─ .gitignore                     单独分享 web 时的排除规则
│  └─ assets/                        主版本使用的小猪表情、四季房间等素材
├─ 21day-wealth-script/              历史静态原型及旧制作脚本
│  ├─ index.html                     早期纯前端版本
│  ├─ assets/                        原型素材
│  └─ *.py                           历史页面改造、检查与音频处理脚本
├─ picture_copy/                     封面、小猪、四季小屋等原始图片
├─ 工银e生-21天扑满计划-项目计划书.docx
├─ 工银e生-21天扑满计划-项目计划书（修改稿）.docx
└─ tools/package_project.py          生成分享包、文件清单和校验值
```

两份 Word 计划书与原始图片随完整项目保留，便于参赛材料查阅和设计修改；它们不参与网页启动。原有子目录 README 的有效说明已合并至本文。

## 4. 技术架构与数据流

前端使用原生 HTML、CSS、JavaScript，主页面内联样式和业务脚本，适配手机宽度。后端使用 Python 标准库 `ThreadingHTTPServer` 和 SQLite。本地和 Render 完整版本采用同源 API；GitHub Pages 主版本通过 `web/config.js` 指向 Render API，并由服务端校验来源、处理跨域预检。浏览器生成匿名演示用户 ID，通过 `X-User-ID` 请求头区分状态；该标识不属于生产级身份认证。Pages 与 Render 页面的浏览器存储属于不同来源，不会自动共享存档。

| 环节 | 处理方式 | 保存位置 |
| --- | --- | --- |
| 用户交互 | 更新页面状态，同时尝试同步服务端 | 浏览器 `localStorage`、`user_states` |
| 行为采集 | 记录任务、答题、挑战、存钱和旅程日切换 | `events` |
| 行为分析 | 按旅程日聚合特征，计算阶段概率与趋势 | `daily_behavior_features`、`behavior_states` |
| 财富画像 | 校验答案 → 服务端评分 → 组织题干与选项 → 模型或规则生成 | `ai_outputs`，以及前端同步的用户状态 |
| 陪伴建议 | 根据旅程、已完成任务和画像重点生成行动提示 | `ai_outputs`，以及前端同步的用户状态 |

数据库连接按请求提交或回滚并关闭。每个浏览器中的存档与匿名 ID 相互关联；不同浏览器或清除本地存储后，不会自动关联到原来的匿名账户。离线状态下仍可保存本地进度，但没有完整的离线事件队列与跨设备冲突解决机制。

## 5. DeepSeek 与财富画像

### 配置真实模型

分享包不含任何真实 API Key，也不携带原作者的私有配置。接收者需要自己的密钥；未配置时可以正常体验基础答题分析。

Windows 推荐使用隐藏输入配置工具：

```powershell
python web/private_config.py
```

在提示处粘贴密钥，输入不会回显。配置保存至 `%LOCALAPPDATA%\Puman21\deepseek.json`，由 Windows DPAPI 以当前用户范围加密；实际路径可能受 Windows 应用目录重定向影响，工具会显示保存位置。文件在项目目录外，拷贝或压缩源码目录不会带上它。更换电脑或 Windows 用户后，应重新配置。

默认接口为 `https://api.deepseek.com`，模型为 `deepseek-flash`。使用 JSON 输出，关闭思考模式，限制输出长度，默认等待上限为 40 秒。官方说明见 [DeepSeek API 文档](https://api-docs.deepseek.com/)。

配置或替换密钥后，先结束正在运行的旧服务，再执行：

```powershell
python web/server.py
```

访问 [AI 配置状态](http://127.0.0.1:8000/api/ai/status) 可查看 `configured` 与模型名；`configured: true` 仅表示配置齐全。已有基础画像可点击“更新画像”，只有调用成功且输出字段有效，页面才显示“AI 财富画像”。

其他操作系统或部署环境可以直接提供以下环境变量：

| 变量 | 用途 | 示例或默认值 |
| --- | --- | --- |
| `LLM_BASE_URL` | 兼容 Chat Completions 的服务地址 | `https://api.deepseek.com` |
| `LLM_API_KEY` | 后端鉴权密钥 | 由接收者通过秘密变量提供 |
| `LLM_MODEL` | 模型名称 | `deepseek-flash` |
| `LLM_TIMEOUT` | 请求等待秒数，代码限定为 1—60 秒 | 私有配置为 `40`，通用适配器缺省为 `15` |

显式环境变量优先于私有文件。`web/.env.example` 仅为配置参考，不含真实密钥；服务不会自动加载项目目录中的 `.env`。不要把实际密钥粘贴到 HTML、README、共享脚本或截图中。

后端部署还支持以下非秘密环境变量：

| 变量 | 用途 | 默认或配置方式 |
| --- | --- | --- |
| `HOST` | 监听地址 | 本地 `127.0.0.1`；Render 模板设为 `0.0.0.0` |
| `PORT` | HTTP 端口 | 本地 `8000`；云端采用 Render 分配值 |
| `DB_PATH` | SQLite 文件位置 | 本地 `web/puman.sqlite3`；云端按临时或持久磁盘配置 |
| `PUBLIC_ORIGIN` | 自定义后端域名来源 | 可选，例如 `https://api.example.com`，不含路径 |
| `RENDER_EXTERNAL_URL` | Render 后端公网来源 | 由 Render 自动提供，无需手动填写 |
| `ALLOWED_ORIGINS` | 可跨域调用 API 的前端来源 | 逗号分隔的完整来源；本项目为 `https://livreee.github.io`；不支持 `*` |

### 画像如何依据答案产生

四道题分别涉及生活愿望、工资分配习惯、向往的生活场景和额外收入用途，没有标准正确答案。浏览器提交四个选项下标，服务器根据固定题库重新计算剧情匹配计数，不采用客户端传入的 `line` 或 `scores`。

计数相同按 `home → baby → travel → gap → solo` 的顺序选择。该计数只表示剧情匹配，不代表资产状况、理财能力或风险承受能力。修改同一目标下的工资习惯或额外收入选择，也会改变相应的基础建议。

服务器向模型发送题干、所选选项文字、计算后的匹配结果和参考分析。有效结果包含 `title`、`stage`、`focus`、`habit`、`message`；教育用途提示由服务器固定。页面展示四条答题依据，并支持重新测评、同答案缓存和手动更新。

| 返回来源 | 触发条件 | 页面表现 |
| --- | --- | --- |
| `provider: llm` | 模型请求成功且必要字段完整 | AI 财富画像 |
| `provider: rules` | 未配置、请求失败或模型输出无效 | 财富画像 · 答题分析 |
| 本地基础分析 | 直接打开 HTML 或后端不可用 | 标明本地答题分析，仍可继续旅程 |

`fallback_reason` 区分缺少配置与服务不可用。服务端审计中保存答案依据、输出、来源、模型名和时间；不保存密钥。重新答题后，旧请求迟到返回也不会覆盖新画像。AI 陪伴接口同样具有规则降级，但其结果不等于交易指令或投资建议。

## 6. 时序行为建模

`behavior_model.py` 实现无第三方依赖的 HMM-Lite 前向推断，模型版本为 `hmm-lite-v1`，输出启动期、尝试期、稳定期、波动期和回归期。

有效行为包括任务完成、每日答题、存钱挑战、储蓄记录、进入旅程日和选择剧情线；系统生成 AI 结果等事件不计入参与强度。每日聚合任务完成标志、答题次数与正确率、挑战完成、活动强度、连续完成天数和中断间隔，再通过固定状态转移矩阵和特征原型计算阶段概率。

未答题属于缺少证据，不按答错处理；空白旅程日会中断连续完成统计；补交旧日期事件时，重新计算后续已缓存日期。每日原始特征与每日状态摘要分别入库，前端“我的参与节奏”展示对应摘要。

当前版本按演示中的 `day=1…21` 聚合，不是按自然日自动计时；用户可以推进旅程日，因此“连续完成三天”表示连续三个旅程日有完成记录。分析当前按匿名用户聚合，不隔离不同剧情线的行为。正式研究或运营需明确自然日、时区、旅程轮次和不同剧情线的统计口径。

模型参数为人工设定的可解释先验，尚未用真实用户样本训练、校准或验证准确率。它用于参与节奏与习惯形成反馈，不用于信用、投资或金融风险判断。

## 7. API 与数据库

API 与页面同源，默认地址为 `http://127.0.0.1:8000`。用户接口需提供 `X-User-ID`（8—80 位字母、数字及 `_ . : -`）；健康检查与 AI 配置状态无需用户标识。JSON 请求使用 `Content-Type: application/json`。

| 方法 | 地址 | 作用 |
| --- | --- | --- |
| GET | `/api/health` | 服务健康状态 |
| GET | `/api/state` | 读取匿名用户存档及版本 |
| PUT | `/api/state` | 保存 `{"state": {...}}` |
| POST | `/api/events` | 写入 `event_type` 和 `payload` |
| GET | `/api/metrics` | 当前用户各类事件计数 |
| GET | `/api/behavior/state?day=3` | 截至指定旅程日的状态摘要 |
| GET | `/api/behavior/timeline?day=3` | 截至指定旅程日的每日状态 |
| POST | `/api/behavior/recompute` | 以 `{"day":3}` 重新计算特征和状态 |
| GET | `/api/ai/status` | 配置是否齐全及模型名称，不返回密钥 |
| POST | `/api/ai/profile` | 根据 `{"answers":[0,0,0,0]}` 生成画像 |
| POST | `/api/ai/coach` | 根据剧情线、`day`、已完成数量、剧情和画像重点生成陪伴建议 |

画像答案必须恰好四个，选项下标为整数 0—3。行为事件的 `payload.day` 必须为整数 1—21，每日答题的 `correct` 必须是布尔值。画像响应含 `profile`、`context`、`provider`、`model`、`fallback_reason` 和 `audit_id`。

| SQLite 表 | 内容 |
| --- | --- |
| `user_states` | 用户 JSON 状态、版本和更新时间 |
| `events` | 行为类型、内容和记录时间 |
| `ai_outputs` | 画像/陪伴请求、输出与来源审计 |
| `daily_behavior_features` | 每个用户每天的聚合特征 |
| `behavior_states` | 每个用户每天的阶段、概率、摘要与模型版本 |

数据库属于运行数据，不随分享包提供。接收者运行后会自行创建空数据库。后端只公开主 HTML、公开网址配置 `config.js` 和允许的静态资源；私有配置、Python 文件、SQLite 数据库及目录列表不可通过后端 HTTP 下载。API 默认同源，可为部署显式允许指定前端来源；模型请求不转发重定向中的鉴权头。GitHub 仓库及 Pages 中的源文件仍是公开的，因此秘密只放在项目外的本机私有配置或 Render 环境变量中。

## 8. 测试与常见问题

在项目根目录运行：

```powershell
python -m unittest discover -s web -p "test_*.py" -v
```

回归测试覆盖答题校验、规则与模型输出、模型异常降级、时序特征、缓存更新、用户隔离、DPAPI 加密、Git 外配置路径、HTTP 访问边界，以及 Render 域名与 Pages 跨域存档。测试使用临时数据库和虚构密钥，不调用付费模型；Windows 专属的加密测试在其他系统上跳过。

| 现象 | 处理方式 |
| --- | --- |
| `python` 命令不可用 | 安装 Python 并加入 PATH；Windows 也可将命令中的 `python` 换成可用的 `py` |
| 8000 端口被占用 | 先结束旧的本项目服务；若是其他程序占用，设置环境变量 `PORT` 后按新端口访问，例如 PowerShell 先执行 `$env:PORT='8001'` |
| Pages 显示本地模式 | 检查 `web/config.js` 是否填写真实 Render HTTPS 地址、Pages 是否完成部署；再检查 Render 服务是否已唤醒 |
| 云端接口返回 403 | 检查 `ALLOWED_ORIGINS` 是否与页面来源一致；自定义后端域名还需配置 `PUBLIC_ORIGIN` |
| 只显示答题分析 | 检查 `/api/ai/status`；配置密钥后重启服务，再点击“更新画像” |
| 已配置但 AI 暂不可用 | 检查 DeepSeek 账户余额、密钥有效性和网络；页面会保留规则分析 |
| 双击 HTML 没有行为模型或 AI | 使用 `python web/server.py` 启动完整服务，不要用普通静态服务器代替 |
| 更换电脑后私有配置不能解密 | 在新电脑上运行 `python web/private_config.py`，重新输入自己的密钥 |
| 受限沙箱中 DPAPI 测试失败 | 在正常 Windows 用户终端运行；不要改成把明文密钥写回源码 |
| 打开后没有声音 | 浏览器通常要求先点击页面；同时检查音乐开关和浏览器静音状态 |

## 9. 历史原型和素材

`21day-wealth-script/` 保存早期纯前端实现，可直接打开其中的 `index.html` 查看。原 README 记录的静态演示地址为 [GitHub Pages 历史原型](https://livreee.github.io/21day-wealth-script/)，该地址不代表当前主版本的后端服务，也不保证与本次源码同步。

历史脚本 `build_retro.py`、`build_bgm.py`、`fix_attr.py`、`make_check.py`、`make_grad_check.py` 和 `dl_bgm.py` 保留了早期制作过程，其中包含原开发机器的绝对路径和旧素材地址。它们不是启动或构建主版本的必要步骤，未经调整不应作为当前项目的一键构建脚本运行。

`picture_copy/` 存放计划书封面、小猪原图和四季小屋原始图片。主版本实际引用的资源位于 `web/assets/`；其中 PNG 与 WebP 同时保留，方便设计修改。页面内的进度图案与拼豆徽章由 SVG 绘制。

## 10. 分享、打包与后续维护

运行以下命令可重新生成完整分享包：

```powershell
python tools/package_project.py
```

结果位于 `dist/`：一个带日期的 ZIP 和对应 `.sha256` 校验文件。ZIP 中只有一个项目顶层文件夹，包含本文、主版本、历史原型、素材、两份计划书、测试和打包工具；`MANIFEST.sha256` 记录包内各文件的校验值。

打包工具采用指定目录与文件范围，排除私有配置、`.env`（保留 `.env.example`）、数据库、日志、缓存、Word 锁定文件和 Git 历史。打包前还会检查疑似密钥，命中时中止并仅报告文件名。根目录和 `web/` 的 `.gitignore` 为 Git 分享提供第二层排除保护。不要另外将 Windows 私有配置目录放入压缩包。

打包不会清空原项目的用户数据，也不会删除本机配置或历史 Git 仓库。接收者按本文启动即可使用空白演示环境；要使用真实 AI，需要配置自己的密钥。若密钥曾经进入其他公开文件或 Git 历史，应在供应商控制台撤销并更换，新增忽略规则不能清除已有历史。

继续开发时优先修改 `web/`；若调整财富问卷，需同步前端 `QUIZ` 与后端 `QUIZ_CONTENT`、`QUIZ_WEIGHTS`。模型参数和画像版本变更时，应更新相应版本字段并运行测试。正式上线前还需要真实身份认证、服务端业务校验、支付/账户接口、真实小队数据、可靠的离线同步、运维监控与针对真实数据的模型评估。
