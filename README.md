# 咸鱼小市场 🐟

> 让孩子手里的闲置「游」起来 —— 同班/同小区孩子**以物换物** + AI 估值 + 家长双确认 + 咸鱼币攒荣誉。

![mode](https://img.shields.io/badge/mode-demo-orange) ![stack](https://img.shields.io/badge/FastAPI-%2B-WeChat_MiniProgram-blue)

---

## 一句话价值
把「买卖」换成「交换」，把「平台」换成「工具」：全程**零金钱流**，规避未成年人网络交易的全部合规雷区，给孩子一个安全、被家长和学校认可的闲置交换方式。

## 核心特性
- 🏘 **组织隔离**：先申请创建（平台审核）或邀请码加入；鱼塘按当前组织隔离，避免全国混用。
- 👨‍👩‍👧 **组织管理在小程序**：组织管理员可邀请、审成员、下架本组织内容（超管后台只审创建申请）。
- 🔄 **以物换物**：只能用自己的闲置换别人的闲置，不接受「掏钱」。
- 🐟 **咸鱼币=积分**：不可转账、不可兑现金、不可买商品；完成交换 +10，排行榜是荣誉不是利益。
- 👨👩👧 **家长双确认**：发起/接收交换，双方家长都要点确认，完成后各 +10。
- 🤖 **AI 一键估值**：拍照（真上传到服务器）→ 支持接入视觉大模型识别成色 → 建议咸鱼币枚数。
- 📷 **真实图片上传**：`POST /upload` 存到 `/uploads` 并静态托管，鱼塘/详情展示真实照片。
- 🔐 **真实微信登录**：接 `jscode2session` + HMAC 签名令牌（demo 模式仍可免登录）。
- 🏅 **排行榜**：前三领奖台 + 全榜，只有昵称/班级，保护隐私（按当前组织成员）。
- 🛡️ **举报 + 管理员治理**：家长/任何人可举报不当内容（固定理由+自由备注），管理员后台审核后下架或驳回，被举报物品下沉公示；举报入口在鱼塘卡片和详情页都很显眼。
- ✏️ **自主调价值**：物主可随时修改自己闲置的咸鱼币参考枚数（0–15枚），让交换更公平。

---

## 二、技术栈
- 后端：`FastAPI + SQLAlchemy + SQLite`
- 前端：微信小程序（原生 WXML/WXSS/JS）
- 演示模式：`DEMO_MODE=1`（免 code 登录）、`WECHAT_MOCK=1`（订阅消息落库展示）

```
salted-fish/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── main.py     # 入口
│   │   ├── config.py    # 配置 + 咸鱼币经济参数
│   │   ├── models.py   # User / Item / Swap / CoinLedger
│   │   ├── schemas.py  # Pydantic 模型
│   │   ├── seed.py     # 演示种子数据
│   │   ├── routers/    # auth items swaps coins parent
│   │   └── services/  # coin / ai_pricing / swap / wechat
│   └── tests/          # pytest 端到端故事线
├── miniprogram/        # 微信小程序
│   ├── app.json / app.js / app.wxss
│   ├── pages/ (login/index/publish/item-detail/swap-list/swap-detail/rank/mine)
│   └── images/         # tabbar 图标（脚本生成）
├── scripts/gen_tabbar_icons.py
└── docs/PRD.md          # 产品需求文档（含合规自查）
```

---

## 三、本地跑起来

### 1) 后端（依赖统一用 uv 管理）
```bash
cd backend
# 一键：按 uv.lock 解析依赖并重建 .venv（require-python ≥3.10，缺解释器会自动下载）
uv sync --extra dev

#（可选）用 .env 覆盖默认配置：模板见 backend/.env.example
cp .env.example .env

# 建表 + 演示数据（5 个孩子、8 件闲置）
uv run python -m app.seed

# 启动后端（自动读 .env 里的 SALTED_FISH_HOST / SALTED_FISH_PORT）
uv run python -m app
```
打开 http://127.0.0.1:8000/docs 可交互调试 API
（IP/端口在 `.env` 改，改 `SALTED_FISH_HOST`/`SALTED_FISH_PORT` 即可，不用动代码）。

> **依赖管理说明**：唯一真相源是 `pyproject.toml` + `uv.lock`。
> - 改依赖：更新 `pyproject.toml [dependencies]` → `uv lock` → `uv sync --extra dev`
> - 不用 uv 的备用：`pip install -r requirements.txt && pip install pytest`

**环境变量（可选，均带默认值）**：
| 变量 | 默认 | 说明 |
|---|---|---|
| `SALTED_FISH_HOST` | `0.0.0.0` | 服务监听 IP（`0.0.0.0`=局域网可访问） |
| `SALTED_FISH_PORT` | `8000` | 服务端口 |
| `SALTED_FISH_RELOAD` | `0` | `1`=改代码自动重启（仅开发） |
| `SALTED_FISH_CORS_ORIGINS` | ``(→`*`) | CORS 允许来源（逗号分隔，无需改） |
| `DEMO_MODE` | `1` | 演示模式：code 即昵称，免真实微信 |
| `WECHAT_MOCK` | `1` | 订阅消息落库展示 |
| `SALTED_FISH_DB` | `salted_fish.db` | 数据库文件 |
| `SALTED_FISH_UPLOAD_DIR` | `uploads` | 上传图片目录 |
| `AI_VISION_ENABLED` | `0` | 开启视觉大模型估值（需配下面 3 个） |
| `AI_VISION_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容的视觉接口 |
| `AI_VISION_API_KEY` | ``(空) | 视觉模型 API Key |
| `AI_VISION_MODEL` | `gpt-4o-mini` | 视觉模型名 |
| `WECHAT_APPID` / `WECHAT_APP_SECRET` | ``(空) | 真实微信登录用（配后建议 `DEMO_MODE=0`） |
| `SALTED_FISH_TOKEN_SECRET` | 开发默认值 | 真实模式令牌签名密钥，生产务必更换 |

### 2) 小程序
1. 微信开发者工具 → 导入 `miniprogram/` 目录，AppID 用「测试号」。
2. 打开 `config.js`：
   - `BASE_URL=http://127.0.0.1:8000`（真机联调改局域网 IP，并勾选「不校验合法域名」）。
   - `REAL_LOGIN=false`（演示）→ `true`（真实微信登录，需后端配 WECHAT_APPID）。
3. 编译运行 → 登录页输入昵称（例：`李多多`）→ 进入鱼塘。

### 3) 跑测试
```bash
cd backend
python -m pytest tests/ -q
```
覆盖：注册 → AI 定价 → 上架 → 发起交换 → 家长双确认 → 完成 → 咸鱼币结算 → 排行榜 → 取消扣分 / 一物多换拦截。

### 4) AI 视觉估值（可选，比赛亮点）
```bash
AI_VISION_ENABLED=1 AI_VISION_API_KEY=sk-xxx AI_VISION_MODEL=gpt-4o-mini uvicorn app.main:app --port 8000
```
之后 `POST /items/ai-pricing` 传 `image_urls` 即优先调视觉模型识别照片成色；
未配置 Key / 调用失败 / 无法读取图片时**自动回退规则引擎**，保证功能不挂。

### 5) 闲置分类（数据库可配置，管理员后台维护）
分类不再写死在代码里，而是存在 `categories` 表，管理员可在小程序后台「分类管理」里增删改：

| 字段 | 说明 |
|---|---|
| `name` | 分类名（如 奥特曼卡 / 玩具） |
| `value_base` | AI 估值的建议基准枚数（1–15），AI 定价读这里 |
| `note` | 说明（估值副文案） |
| `sort_order` | 排序，越小越靠前 |
| `is_active` | 停用后发布时不可选、公开列表不显示 |

- 公开读取：`GET /items/categories`（只返回启用中的）
- 管理员维护：`GET/POST/PUT/DELETE /admin/categories`（仅 `role=admin`）
- 被闲置占用中的分类不能删除（会提示改为停用）
- 首次启动会自动写入默认 6 个分类；之后由管理员在后台维护。

---

## 四、演示账号（seed 后）
| 昵称 | 班级 | 备注 |
|---|---|---|
| 陈小明 | 三年级2班 | 上架奥特曼卡 |
| 李栋栋 | 三年级2班 | 上架绘本、热卖中性笔 |
| 王浩浩 | 三年级1班 | 上架乐高、恐龙模型 |
| 赵彤彤 | 三年级2班 | 文具 |
| 孙一一 | 四年级1班 | 体育用品 |

---

## 五、合规说明（比赛答辩要点）
- **无支付、无退款、无未成年交易责任** —— 纯以物换物。
- **咸鱼币三铁律**：不可兑现金 / 不可转账 / 不可购商品。
- **家长双确认** —— 每一步都有记录；异常取消有扣分治理。
- **校园共建** ——「互换」而非「交易」的叙事，配套老师/家委会话术。

详见 [`docs/PRD.md`](docs/PRD.md)。

---

## 六、Roadmap
- v0.1 比赛 demo（当前）
- v0.2 学校试点 + 义卖日工具化
- v0.3 咸鱼币兑换小文具（家委会运营）/ 环保数据

---

*一个小栗子：孩子拍一张奥特曼卡 → AI 说「建议 3 咸鱼币」→ 同学发来交换 → 两位家长手机同时弹确认 → 课间当面换 → 排行榜「本月我环保」。*