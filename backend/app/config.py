"""项目配置：环境变量 + 数据库连接。

配置优先级（从高到低）：
  1) 进程已存在的环境变量（如 shell 里 export 的、运维平台注入的）
  2) 项目根  backend/.env  文件（python-dotenv 读取，默认不覆盖已有变量）

复制模板：
  cp .env.example .env    # 在 backend/ 目录下
"""
import os

# 先尝试载入 .env（幂等：缺失不报错；不覆盖已在环境中存在的变量）
try:
    from dotenv import load_dotenv

    load_dotenv()  # 默认从当前工作目录起向上找 .env；不覆盖已有变量
except ImportError:  # python-dotenv 未安装时静默跳过，配置仍可用默认值
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ---- 服务监听（IP + 端口，放在 .env 里统一管理） -----------------------
# 上线改 IP/端口不用碰代码，改 backend/.env 即可。
HOST = os.environ.get("SALTED_FISH_HOST", "0.0.0.0")  # 0.0.0.0 = 局域网设备可访问
PORT = int(os.environ.get("SALTED_FISH_PORT", "8000"))

# 允许跨域的小程序来源（小程序本身不受浏览器同源限制，CORS 主要给调试工具/网页端）
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("SALTED_FISH_CORS_ORIGINS", "").split(",")
    if o.strip()
] or ["*"]

# ---- 数据库 -------------------------------------------------------------
DB_PATH = os.environ.get("SALTED_FISH_DB", "salted_fish.db")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DB_PATH}"
)

# ---- 图片上传 ------------------------------------------------------------
UPLOAD_DIR = os.environ.get("SALTED_FISH_UPLOAD_DIR", "uploads")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：每个请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- 咸鱼币（纯积分，非货币） --------------------------------------------
# 设计约束（合规红线）：
#   1. 咸鱼币不可兑换现金、不可购买、不可转账，仅作为行为积分存在。
#   2. 积分只能由系统规则发放/扣除（上架、完成交换等），不存在用户间转移。
#   3. 排行榜只展示昵称与积分，用于情绪价值激励，不构成任何兑付承诺。

COIN_NAME = "咸鱼币"
COIN_INITIAL_BALANCE = 10          # 新用户注册赠送
COIN_REWARD_LIST_ITEM = 2          # 上架一件闲置
COIN_REWARD_COMPLETE_SWAP = 10     # 交换完成奖励（双方各得）
COIN_PENALTY_CANCEL_SWAP = 2       # 无故取消交换（恶意行为治理）

COIN_RULES = [
    {"action": "注册", "delta": 10, "note": "欢迎加入循环小市场"},
    {"action": "上架闲置", "delta": 2, "note": "让闲置游起来"},
    {"action": "完成交换", "delta": 10, "note": "双方各 +10，绿色消费践行者"},
    {"action": "取消交换", "delta": -2, "note": "无故取消扣 2 枚，守护契约精神"},
]

# ---- 交换状态机 ----------------------------------------------------------
# pending_parent:   发起方家长未确认
# pending_peer:      接收方家长未确认
# accepted:          双方家长已确认，等待线下当面交换
# completed:         已当面完成（双方家长点"交换完成"）
# cancelled:         任一方取消（扣发起方 2 咸鱼币）

SWAP_STATUSES = [
    "pending_parent",
    "pending_peer",
    "accepted",
    "completed",
    "cancelled",
]

# ---- AI 定价（演示用规则引擎，可替换为视觉大模型） --------------------------
# 类别 -> (参考价值枚数, 新旧档位说明)
ITEM_CATEGORIES = {
    "卡牌贴纸": (3, "奥特曼/宝可梦/球星卡/贴纸；看品相与稀有度"),
    "绘本图书": (4, "绘本、桥梁书、课外读物；看缺页、涂鸦、书脊"),
    "漫画杂志": (3, "漫画、儿童杂志、期刊；看缺期与折痕"),
    "积木拼插": (4, "乐高、磁力片、积木；看配件是否齐全"),
    "毛绒公仔": (3, "玩偶、抱枕公仔；看干净与破损"),
    "手办模型": (4, "人偶、高达、恐龙模型；看盒配件与掉色"),
    "益智桌游": (3, "棋类、拼图、卡牌桌游；看配件是否齐全"),
    "遥控电动": (4, "遥控车、电动玩具；看能否正常玩"),
    "文具学习": (2, "笔、本、橡皮、尺子；消耗品估值偏低"),
    "美术手工": (2, "彩笔、粘土、折纸、画具；看剩余量"),
    "体育户外": (4, "跳绳、球类、护具；看使用痕迹"),
    "乐器配件": (4, "竖笛、口琴、口风琴等适龄乐器；看能否发声"),
    "书包配饰": (3, "挂件、徽章、文具袋；看完好程度"),
    "其他": (2, "不好归类的闲置，建议补照片方便交换"),
}

CONDITION_SCALE = ["崭新", "九成新", "八成新", "七成新", "有磨损"]

AI_PRICING_SOURCE = "rule-engine v1"

# ---- AI 视觉估值（可选，接入 OpenAI 兼容的视觉大模型） -----------------------
# 开启后优先调用视觉模型识别照片估值；未开启/调用失败自动回退规则引擎。
AI_VISION_ENABLED = os.environ.get("AI_VISION_ENABLED", "0") == "1"
AI_VISION_BASE_URL = os.environ.get("AI_VISION_BASE_URL", "https://api.openai.com/v1")
AI_VISION_API_KEY = os.environ.get("AI_VISION_API_KEY", "")
AI_VISION_MODEL = os.environ.get("AI_VISION_MODEL", "gpt-4o-mini")

# ---- 家长确认 & 微信生态 ---------------------------------------------------
# 订阅消息模板：发起方家长 -> 接收方家长 -> 线下交换 -> 双方点完成
PARENT_CONFIRM_REQUIRED = True

WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
WECHAT_MOCK = os.environ.get("WECHAT_MOCK", "1") == "1"  # 比赛演示：默认 mock

WECHAT_SUBSCRIBE_MESSAGE_TEMPLATE = {
    "template_id": os.environ.get("WECHAT_TEMPLATE_ID", ""),
    # 场景：你的孩子发起了/收到一个交换请求，请确认
}

WECHAT_SUBSCRIBE_MESSAGE_FIELDS = [
    {"name": "thing1", "value": "陈小明"},
    {"name": "thing2", "value": "奥特曼卡 x1"},
    {"qrcode_scene": "pages/swap/swap-detail?id=1"},
]

# ---- 排行榜（情绪价值，不构成兑付承诺） -----------------------------------
LEADERBOARD_TOP_N = 50

# 演示开关：不校验签名，直接用 openid 登录（比赛演示专用，勿上生产）
DEMO_MODE = os.environ.get("SALTED_FISH_DEMO", "1") == "1"

# 令牌有效期（小时）；小程序令牌与独立后台令牌共用
TOKEN_EXPIRE_HOURS = int(os.environ.get("SALTED_FISH_TOKEN_EXPIRE_HOURS", "24"))

# ---- 管理员 & 内容治理 -----------------------------------------------------
# 这些 openid 登录后自动置为 admin 角色，可进入「管理员」后台处理举报/下架。
# 演示模式：登录昵称即 openid，把想要的管理员昵称写进来即可（逗号分隔）。
ADMIN_OPENIDS = [
    o.strip()
    for o in os.environ.get("ADMIN_OPENIDS", "管理员").split(",")
    if o.strip()
]

# 举报固定理由（可追加/删减）；家长还可在提交时附上自由备注
REPORT_REASONS = [
    "垃圾或不适合的内容",
    "不当交易（要求付钱/买卖）",
    "信息不符或虚假",
    "涉及隐私或被他人冒用",
    "其他问题",
]

# 物品被举报后列表仍可见但下沉（举报即公示），由管理员处理下架/驳回

# 接口限流：0 / false / off 关闭（pytest 会关掉）
RATE_LIMIT_ENABLED = os.environ.get("SALTED_FISH_RATE_LIMIT", "1").strip().lower() not in (
    "0", "false", "off", "no",
)
