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
    ("users", "profile_completed", "BOOLEAN DEFAULT 0"),
    ("users", "org_create_limit", "INTEGER"),
    ("organizations", "invite_enabled", "BOOLEAN DEFAULT 1"),
    ("organizations", "join_need_review", "BOOLEAN DEFAULT 1"),
    ("llm_providers", "support_text", "BOOLEAN DEFAULT 1"),
    ("llm_providers", "support_image", "BOOLEAN DEFAULT 1"),
    ("llm_providers", "support_audio", "BOOLEAN DEFAULT 0"),
    ("items", "ai_value_coins", "INTEGER DEFAULT 0"),
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


def _backfill_profile_completed():
    """旧用户迁移后 profile_completed 默认为 0；已有真实昵称的视为已完善。"""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE users SET profile_completed = 1 "
                    "WHERE COALESCE(profile_completed, 0) = 0 "
                    "AND nickname IS NOT NULL AND TRIM(nickname) != '' "
                    "AND nickname != '小咸鱼'"
                )
            )
            conn.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("回填 profile_completed 失败：%s", e)


def _backfill_ai_value_coins():
    """旧数据只有 value_coins；补一份 AI 估值，便于对照。"""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE items SET ai_value_coins = value_coins "
                    "WHERE COALESCE(ai_value_coins, 0) = 0 AND COALESCE(value_coins, 0) > 0"
                )
            )
            conn.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("回填 ai_value_coins 失败：%s", e)


Base.metadata.create_all(bind=engine)
_migrate()
_backfill_profile_completed()
_backfill_ai_value_coins()

# 确保默认分类存在（表空则写入，之后由管理员后台维护）
db = SessionLocal()
try:
    category_service.seed_categories(db)
finally:
    db.close()
