"""独立后台管理员账号管理 CLI。

用法（在 backend 目录）：
    uv run python -m app.admin_cli create  邮箱  --password 'xxx' --name 管理员
    uv run python -m app.admin_cli reset   邮箱  --password '新密码'
    uv run python -m app.admin_cli list
"""
import argparse
import getpass
import sys

from .config import SessionLocal
from . import db_init  # noqa: F401  确保建表（含 admin_users）
from .models import AdminUser
from .services.admin_auth import hash_password


def _get_db():
    return SessionLocal()


def cmd_create(db, email, password, name):
    email = email.strip().lower()
    if db.query(AdminUser).filter(AdminUser.email == email).first():
        print(f"已存在管理员邮箱：{email}（可用 reset 重置密码）")
        return 1
    db.add(AdminUser(email=email, password_hash=hash_password(password), name=name or "管理员"))
    db.commit()
    print(f"✅ 已创建管理员：{email} → {name or '管理员'}")
    return 0


def cmd_reset(db, email, password):
    email = email.strip().lower()
    u = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not u:
        print(f"不存在该邮箱：{email}（先用 create 创建）")
        return 1
    u.password_hash = hash_password(password)
    db.commit()
    print(f"✅ 已重置密码：{email}")
    return 0


def cmd_list(db):
    rows = db.query(AdminUser).order_by(AdminUser.id).all()
    if not rows:
        print("暂无后台管理员账号。用 `python -m app.admin_create create <邮箱> --password <密码>` 创建。")
        return 0
    for u in rows:
        print(f"  id={u.id}  {u.email}  {'启用' if u.is_active else '停用'}  name={u.name}")
    return 0


def main():
    p = argparse.ArgumentParser(description="独立后台管理员账号管理")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="创建管理员")
    c.add_argument("email")
    c.add_argument("--password"); c.add_argument("--name", default="管理员")

    r = sub.add_parser("reset", help="重置密码")
    r.add_argument("email"); r.add_argument("--password")

    sub.add_parser("list", help="列出管理员")

    args = p.parse_args()
    db = _get_db()
    try:
        if args.cmd == "create":
            pw = args.password or getpass.getpass("密码：")
            return cmd_create(db, args.email, pw, args.name)
        if args.cmd == "reset":
            pw = args.password or getpass.getpass("新密码：")
            return cmd_reset(db, args.email, pw)
        if args.cmd == "list":
            return cmd_list(db)
    finally:
        db.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())