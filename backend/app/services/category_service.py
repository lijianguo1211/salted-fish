"""分类数据访问：种子 + 查询 + 管理员 CRUD。"""
from sqlalchemy.orm import Session

from ..models import Category, Item

# 面向小学/社区以物换物：按真实闲置拆开，方便筛选，又不超过一屏。
# (name, value_base 1–15, note, sort_order)  其他永远排最后。
DEFAULT_CATEGORIES = [
    ("卡牌贴纸", 3, "奥特曼/宝可梦/球星卡/贴纸；看品相与稀有度", 1),
    ("绘本图书", 4, "绘本、桥梁书、课外读物；看缺页、涂鸦、书脊", 2),
    ("漫画杂志", 3, "漫画、儿童杂志、期刊；看缺期与折痕", 3),
    ("积木拼插", 4, "乐高、磁力片、积木；看配件是否齐全", 4),
    ("毛绒公仔", 3, "玩偶、抱枕公仔；看干净与破损", 5),
    ("手办模型", 4, "人偶、高达、恐龙模型；看盒配件与掉色", 6),
    ("益智桌游", 3, "棋类、拼图、卡牌桌游；看配件是否齐全", 7),
    ("遥控电动", 4, "遥控车、电动玩具；看能否正常玩", 8),
    ("文具学习", 2, "笔、本、橡皮、尺子；消耗品估值偏低", 9),
    ("美术手工", 2, "彩笔、粘土、折纸、画具；看剩余量", 10),
    ("体育户外", 4, "跳绳、球类、护具；看使用痕迹", 11),
    ("乐器配件", 4, "竖笛、口琴、口风琴等适龄乐器；看能否发声", 12),
    ("书包配饰", 3, "挂件、徽章、文具袋；看完好程度", 13),
    ("其他", 2, "不好归类的闲置，建议补照片方便交换", 99),
]

# 旧分类名 → 新分类名（刷新表时同步已上架物品）
LEGACY_CATEGORY_MAP = {
    "奥特曼卡": "卡牌贴纸",
    "绘本/课外书": "绘本图书",
    "玩具": "益智桌游",
    "文具": "文具学习",
    "体育用品": "体育户外",
}


def fallback_map() -> dict:
    """{ 分类名: (value_base, note) }，规则引擎离线兜底。"""
    return {name: (base, note) for name, base, note, _ in DEFAULT_CATEGORIES}


def seed_categories(db: Session) -> None:
    """表为空时写入默认分类（幂等）。"""
    if db.query(Category).count() > 0:
        return
    for name, base, note, sort_order in DEFAULT_CATEGORIES:
        db.add(Category(name=name, value_base=base, note=note, sort_order=sort_order))
    db.commit()


def replace_categories(db: Session) -> int:
    """删除现有分类，写入默认分类，并把旧物品分类名映射过去。"""
    for old, new in LEGACY_CATEGORY_MAP.items():
        db.query(Item).filter(Item.category == old).update(
            {Item.category: new}, synchronize_session=False
        )
    db.query(Category).delete()
    for name, base, note, sort_order in DEFAULT_CATEGORIES:
        db.add(Category(name=name, value_base=base, note=note, sort_order=sort_order))
    db.commit()
    return len(DEFAULT_CATEGORIES)


def categories_map(db: Session) -> dict:
    """返回 { 分类名: (value_base, note) }，供 AI 定价使用。"""
    rows = db.query(Category).filter(Category.is_active.is_(True)).all()
    return {c.name: (c.value_base, c.note) for c in rows}


def list_active(db: Session):
    """供前端选择：只返回启用中的分类，按排序。"""
    return (
        db.query(Category)
        .filter(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
        .all()
    )
