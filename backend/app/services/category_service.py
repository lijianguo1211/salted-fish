"""分类数据访问：种子 + 查询 + 管理员 CRUD。"""
from sqlalchemy.orm import Session

from ..models import Category

# 默认分类（首次启动无数据时写入，之后由管理员在后台维护）
DEFAULT_CATEGORIES = [
    ("奥特曼卡", 3, "卡面磨损、卡位稀有度影响估值", 1),
    ("绘本/课外书", 4, "缺页、涂鸦、书脊破损影响估值", 2),
    ("玩具", 3, "配件齐全度、功能完好度影响估值", 3),
    ("文具", 2, "消耗程度影响估值", 4),
    ("体育用品", 4, "使用痕迹影响估值", 5),
    ("其他", 2, "按类别参照，建议交换中人工补照片", 99),
]


def seed_categories(db: Session) -> None:
    """表为空时写入默认分类（幂等）。"""
    if db.query(Category).count() > 0:
        return
    for name, base, note, sort_order in DEFAULT_CATEGORIES:
        db.add(Category(name=name, value_base=base, note=note, sort_order=sort_order))
    db.commit()


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