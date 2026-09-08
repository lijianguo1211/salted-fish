# 咸鱼小市场 🐟

> 让孩子手里的闲置「游」起来 —— 同班/同小区孩子**以物换物** + AI 估值 + AI 合规审核 + 家长双确认 + 咸鱼币攒荣誉。

![mode](https://img.shields.io/badge/mode-demo-orange) ![stack](https://img.shields.io/badge/FastAPI-%2B-WeChat_MiniProgram-blue) ![admin](https://img.shields.io/badge/admin-React_%2B_Vite-green)

---

## 一句话价值

把「买卖」换成「交换」，把「平台」换成「工具」：全程**零金钱流**，规避未成年人网络交易的全部合规雷区，给孩子一个安全、被家长和学校认可的闲置交换方式。

## 核心特性
- 🏘 **组织隔离**：内容按组织（学校 / 小区 / 其他）隔离，先申请创建（平台超管审核）或凭邀请码加入，避免全国混用。
- 👨‍👩‍👧 **组织管理在小程序**：创建者可邀请成员、审核加入、下架本组织内容、复制邀请码、申请超额创建额度；平台超管在独立后台只管「创建审批」与「超额额度审批」。
- 🎫 **组织创建额度与审核**：每人默认可建组织数可在后台配置；额度用尽可提交「超额申请」（附原因 + 证明材料如教师资格证）等平台审核。
- 🔄 **以物换物**：只能用自己的闲置换别人的闲置，全程零金钱流，「掏钱」买卖被列为举报项；一物多换被拦截。
- 🐟 **咸鱼币＝积分**：不可兑现金、不可转账、不可买商品；完成交换双方各 +10，排行榜只拼荣誉。
- 👨👩👧 **家长双确认**：发起 / 接收交换，双方家长都要点确认，完成后各 +10；异常取消发起方 -2。
- 🤖 **AI 一键估值**：多厂商大模型识别成色建议咸鱼币枚数，未配置 / 失败自动回退规则引擎（不挂）。
- 🛡️ **AI 内容合规审核**：上架时自动检测烟酒、毒品、暴力、色情、管制刀具等不宜内容；多模型审核 + 本地关键词兜底，可在后台一键开关。
- 🧠 **AI 家长助手**：小程序内置 AI 问答，基于产品规则库回答「怎么换物 / 家长怎么确认 / 咸鱼币能兑现金吗」等问题（腾讯云开发混元）。
- 📷 **真实图片上传**：`POST /upload` 存到 `/uploads` 并静态托管，鱼塘/详情展示真实照片。
- 🔐 **真实微信登录 + 令牌**：`wx.login → jscode2session → openid`，HMAC 签名令牌（demo 模式仍可免登录）。
- 🏅 **排行榜**：前三领奖台 + 全榜，只有昵称/班级/头像，保护隐私（按当前组织成员）。
- 🛡️ **举报 + 管理员治理**：任何人可举报不当内容（固定理由 + 自由备注），管理员后台下架/驳回，被举报物品下沉公示。
- ✏️ **自主调估**：物主可随时修改自己闲置的参考枚数，让交换更公平。
- 🌏 **一键重置演示数据**：`python -m app.reset_database` 可清空并重建全库，方便反复演示/回归。
- 🛠️ **独立 Web 管理后台**：React + Vite，支持举报处理、物品、分类、孩子/积分、组织审核、超额额度审核、大模型管理、AI 开关。
- ⛓️ **接口限流**：滑动窗口限流（scope+key），默认开启，测试默认关闭。
- 📄 **合规入口**：小程序内置《用户协议》与《隐私政策》页，登录前可查看。

---

## 二、技术栈
- 后端：`FastAPI + SQLAlchemy + SQLite`（uv 管理依赖）
- 前端：微信小程序（原生 WXML/WXSS/JS）+ 管理后台（React + Vite）
- AI：OpenAI 兼容多厂商（OpenAI / DeepSeek / 硅基流动 / 月之暗面 / 智谱 / 通义千问 / Groq / 自定义），支持文本 / 视觉 / 音频输入，多 Key 按优先级故障切换
- 演示模式：`SALTED_FISH_DEMO=1`（免 code 化登录）、`WECHAT_MOCK=1`（订阅消息落库，落库展示）
- 管理后台安全：RSA-OAEP(SHA-256) 密码传输加密 + PBKDF2-HMAC-SHA256 存储，RSA-2048 私钥本地自动生成

### 目录结构
```
salted-fish/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── main.py     # 入口
│   │   ├── config.py   # 配置 + 咸鱼币经济参数 + AI/限流参数
│   │   ├── db_init.py  # 建表 + 启动轻量迁移 + 默认分类
│   │   ├── models.py   # User/AdminUser/Org/Item/Swap/CoinLedger/Report/...
│   │   ├── seed.py     # 演示种子数据（1 组织 + 5 孩子 + 8 件闲置）
│   │   ├── reset_database.py  # 重置全库（清空重播种）
│   │   ├── admin_cli.py        # 建独立后台管理员（邮箱+密码）
│   │   ├── schemas.py  # Pydantic 模型
│   │   ├── routers/    # auth items swaps coins parent orgs admin upload ...
│   │   └── services/   # coin ai_pricing ai_moderation llm org swap rate_limit ...
│   └── tests/          # pytest 端到端故事线（含限流用例）
├── miniprogram/        # 微信小程序
│   ├── app.json / app.js / app.wxss
│   ├── pages/ (login/gate/list/setup/index/swap-list/rank/mine/publish/item-detail/
│   │           swap-detail/org/apply|join|quota-apply|manage|invite/admin/aichat/legal/...)
│   └── images/         # tabbar 图标（脚本生成）
├── admin-web/          # 独立 Web 管理后台（React + Vite + Antd）
└── docs/PRD.md          # 产品需求文档（含合规自查）
```

---

## 三、本地跑起来

### 1) 启动并初始化后端（依赖统一用 uv 管理）
```bash
cd backend
# 一键：按 uv.lock 解析依赖并重建 .venv（require-python ≥3.10，缺解释器会自动下载）
uv sync --extra dev

#（强烈建议）用 .env 覆盖默认配置：模板见 backend/.env.example
cp .env.example .env

# 建表 + 演示数据（1 个组织「示范小学」+ 5 个孩子 + 8 件闲置）
uv run python -m app.seed

# 启动后端（自动读 .env 里的端口 / host）
uv run python -m app
```
打开 http://127.0.0.1:<端口>/docs 可交互调试 API（端口在 `.env` 改）。

> **依赖管理说明**：唯一真相源是 `pyproject.toml` + `uv.lock`。
> - 改依赖：更新 `pyproject.toml [dependencies]` → `uv lock` → `uv sync --extra dev`
> - 不用 uv 的备用：`pip install -r requirements.txt && pip install pytest`

**一键重置演示数据**（如需清空旧库 / 反复演示）：
```bash
cd backend && uv run python -m app.reset_database
```
会重建所有表并按 `seed.py` 写入干净的演示数据。

**环境变量（可选，均带默认值）**：
| 变量 | 默认 | 说明 |
|---|---|---|
| `SALTED_FISH_HOST` | `0.0.0.0` | 服务监听 IP |
| `SALTED_FISH_PORT` | `8000` | 服务端口（开发常用 30089） |
| `SALTED_FISH_RELOAD` | `0` | `1`=改代码自动重启（仅开发） |
| `SALTED_FISH_CORS_ORIGINS` | ``(→`*`) | CORS 允许来源（逗号分隔） |
| `SALTED_FISH_DEMO` | `1` | 演示模式：本地设备 ID 免真实 code 登录 |
| `WECHAT_MOCK` | `1` | 订阅消息落库展示，不真发微信 |
| `WECHAT_APPID` / `WECHAT_APP_SECRET` | ``(空) | 真实微信登录用（配后建议 `SALTED_FISH_DEMO=0`） |
| `SALTED_FISH_TOKEN_SECRET` | 开发默认值 | 签名令牌密钥，生产务必更换 |
| `SALTED_FISH_TOKEN_EXPIRE_HOURS` | `24` | 令牌有效期（小时） |
| `SALTED_FISH_DB` | `salted_fish.db` | 数据库文件 |
| `SALTED_FISH_UPLOAD_DIR` | `uploads` | 上传图片目录 |
| `SALTED_FISH_RATE_LIMIT` | `1` | `0/off` 关闭接口限流（测试用） |
| `ADMIN_OPENIDS` | `管理员` | 这些 openid 登录自动置 admin（演示即昵称） |
| `ADMIN_RSA_KEY_PATH` | `backend/app/keys/admin_rsa.pem` | 后台登录私钥路径（首次自动生成） |
| `AI_VISION_ENABLED` | `0` | 遗留兼容：库中无任何启用模型时才生效 |

> 大模型配置**优先走数据库**（`admin-web`「大模型管理」维护的 `llm_providers`），`.env` 里的 `AI_VISION_*` 仅作为「库内没有任何启用模型」时的兜底，一般无需再单独配置。

### 2) 小程序
1. 微信开发者工具 → 导入 `miniprogram/` 目录，AppID 用「测试号」。
2. 打开 `config.js`：
   - `BASE_URL=http://127.0.0.1:<端口>`（真机联调改局域网 IP，并勾选「不校验合法域名」；默认演示用 30089）。
   - `REAL_LOGIN`：`false`（演示）→ `true`（真实微信登录，需后端配 `WECHAT_APPID` 且 `SALTED_FISH_DEMO=0`）。
   - `CLOUD_ENV`：腾讯云开发环境 ID（AI 小助手用，`wx.cloud.extend.AI`）。
3. 编译运行 → 登录 → 选/加入/创建组织（完整填写昵称班级）→ 进鱼塘。

> 首个账号默认 `ADMIN_OPENIDS` 里包含 `管理员` → 演示时用昵称上登录即为 admin 可进「组织管理」。

### 3) Web 管理后台（`admin-web`，React 独立部署）
```bash
# 1) 起后端
cd backend && uv run python -m app

# 2) 建独立后台管理员（邮箱 + 密码，PBKDF2 盐哈希存储）
cd backend && uv run python -m app.admin_cli create 管理员@example.com --password '123456' --name 校长

# 3) 起前端
cd admin-web && npm install && npm run dev   # 打开 http://localhost:5173
```
**后台六大模块**：举报处理（下架/驳回）、物品管理（浏览/下架/恢复）、分类管理（增删改/估值基准/排序/启停）、孩子/积分（查余额/停启用）、组织审核（审批新组织 + 超额度申请）、大模型管理（多厂商增删改/启停/连通性测试）。
另在设置页可开关 AI 估值与 AI 合规审核。

**后端接口安全**
- `GET /admin-auth/public-key`：返回 RSA 公钥（SPKI PEM）
- `POST /admin-auth/login`：入参 `{ email, encrypted_password }`，密码经 RSA-OAEP(SHA-256) 公钥加密传输
- 登录后所有 `/admin/*` 治理接口可用 `admin-web-` 令牌访问（也接小程序管理员令牌）

**独立部署（生产）**
```bash
cd admin-web
VITE_API_BASE=https://你的后端域名 npm run build   # 产物在 dist/
```
把 `dist/` 交给任意静态服务器即可，`VITE_API_BASE` 指到 FastAPI 后端根地址。

### 4) 跑测试
```bash
cd backend
python -m pytest tests/ -q
```
覆盖：注册 → AI 定价 → 上架 → 发起交换 → 家长双确认 → 完成 → 咸鱼币结算 → 排行榜 → 取消扣分 / 一物多换拦截 / 接口限流。

### 5) AI 综合能力（估值 + 内容审核）
- **配置**：推荐在 Web 后台「大模型管理」添加厂商（OpenAI/DeepSeek/硅基流动等），多 Key 自动故障切换，支持文本/视觉/音频。
- **AI 估值**：上架时传图，优先调视觉模型识别照片成色 → 建议咸鱼币枚数；未配置 Key / 调用失败**自动回退规则引擎**，保证不挂。
- **AI 内容合规**（后台「AI 设置」开启）：发布闲置时自动审核名称/描述/图片，拦截暴力、色情、烟酒、毒品、管制刀具、易燃易爆、违禁品、成人用品等；优先走已启用 LLM，全挂时用本地关键词兜底（开启状态下不放行未知）。

---

## 四、演示账号（seed 后）
组织「示范小学」已通过平台审核，邀请码 **`DEMO2026`**；全员正式成员。账号 = 昵称（演示模式直接用昵称登录）。

| 昵称 | 班级 | 备注 |
|---|---|---|
| 陈小明 | 三年级2班 | 上架奥特曼卡 |
| 李栋栋 | 三年级2班 | 上架绘本、热卖中性笔 |
| 王浩浩 | 三年级1班 | 上架乐高、恐龙模型 |
| 赵彤彤 | 三年级2班 | 文具 |
| 孙一一 | 四年级1班 | 体育用品 |

> 陈小明为组织创建者，可在小程序「组织管理」里审成员、下架、复制邀请码、发起超额额度申请。

---

## 五、合规说明（比赛答辩要点）
- **无支付、无退款、无未成年交易责任** —— 纯以物换物，全程零金钱流。
- **咸鱼币三铁律** —— 不可兑现金 / 不可转账 / 不可买商品。
- **家长双确认** —— 每一步都有记录，异常取消有扣分治理。
- **AI 内容合规** —— 上架自动审核，违禁品不入池；1 键举报下架。
- **校园共建** ——「互换」而非「交易」的叙事，配套老师/家委会话术，内置《用户协议》与《隐私政策》。

详见 [`docs/PRD.md`](docs/PRD.md)。

---

## 六、Roadmap
- v0.1 比赛 demo（当前，含 AI 估值 / 审核 / 后台 / 组织配额）
- v0.2 学校试点 + 义卖日工具化 + 更多 AI 估值模型适配
- v0.3 咸鱼币兑换小文具（家委会运营）/ 环保数据

---

*一个小栗子：孩子拍一张奥特曼卡 → AI 说「建议 3 咸鱼币」→ 合规审核通过上架 → 同学发来换 → 双方家长手机同时弹确认 → 课间当面换 → 排行榜「本月我环保」。*