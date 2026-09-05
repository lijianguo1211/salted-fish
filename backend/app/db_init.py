"""数据库建表入口：import 即建表（uvicorn 启动时执行）。

含轻量迁移：给已存在的旧表补新列（SQLite 不支持直接加列带默认约束，简单 ADD COLUMN 即可）。
"""
import logging

from .config import Base, engine, SessionLocal

from . import models  # noqa: F401  确保模型注册
from .services import wechat_service  # noqa: F401  确保 Notification 表注册
from .services import category_service  # noqa: F401

logger = logging.getLogger("salted_fish.db_init")

# 需要迁移的新列：(表名, 列名, DDL 定义)
_MIGRATIONS = [
    ("items", "reported", "INTEGER DEFAULT 0"),
    ("items", "flagged", "BOOLEAN DEFAULT 0"),
    ("items", "removed_reason", "VARCHAR(255) DEFAULT ''"),
    ("items", "removed_by", "INTEGER DEFAULT 0"),
    ("items", "org_id", "INTEGER"),
    ("users", "active_org_id", "INTEGER"),
]


def _migrate():
    """对已存在的旧表补齐缺失列，幂等。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, col, ddl in _MIGRATIONS:
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if col in existing:
            continue
        try:
            with engine.connect() as conn:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {ddl}'))
                conn.commit()
            logger.info("迁移：表 %s 补列 %s", table, col)
        except Exception as e:  # noqa: BLE001
            logger.warning("迁移 %s.%s 失败：%s", table, col, e)


Base.metadata.create_all(bind=engine)
_migrate()

# 确保默认分类存在（表空则写入，之后由管理员后台维护）
db = SessionLocal()
try:
    category_service.seed_categories(db)
finally:
    db.close()