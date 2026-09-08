"""安全重置数据库到「全新空态」：
- drop 全部表（含 sqlite_sequence 自动序号归零）
- 重建完整表结构（等价于初次启动）
- 补齐系统必需：默认分类（app_settings 归零）
- 不写入任何演示账号/组织/物品

用法（在 backend/ 下）：
    .venv/bin/python -m app.reset_db
"""
# 必须先导入 db_init 以确保所有模型注册（含 services 里注册的额外表）
from . import db_init  # noqa: F401
from .config import engine, Base, SessionLocal
from .services import category_service
from sqlalchemy import inspect

print("连接数据库:", engine.url)


def reset():
    insp = inspect(engine)
    tables = insp.get_table_names()
    print("待删除的表:", tables)

    Base.metadata.drop_all(bind=engine)
    print("已删除全部表")

    Base.metadata.create_all(bind=engine)
    print("已重建全部表")

    # 重新写入系统默认分类（表为空则会写入）
    db = SessionLocal()
    try:
        category_service.seed_categories(db)
        from .models import Category
        n = db.query(Category).count()
        print(f"默认分类已写入，共 {n} 条")
    finally:
        db.close()

    print("✅ 数据库已重置为全新空态（无演示数据）。")


if __name__ == "__main__":
    reset()