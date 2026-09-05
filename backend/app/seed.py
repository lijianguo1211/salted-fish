"""建表 + 比赛演示种子数据。

跑法：python -m app.seed
（自动检测：表不存在则建表；数据已存在则跳过）
"""
from .config import SessionLocal, engine, Base
from .models import Item, Organization, OrgMembership, User
from .services import category_service, coin_service, org_service
from .services.ai_pricing import estimate_value
from .services import wechat_service  # noqa: F401  确保 Notification 表建出来


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("已有数据，跳过种子")
            return

        users_data = [
            ("陈小明", "三年级2班", "奥特曼卡"), ("李朵朵", "三年级2班", "绘本"),
            ("王浩浩", "三年级1班", "玩具"), ("赵彤彤", "三年级2班", "文具"),
            ("孙一一", "四年级1班", "体育用品"),
        ]
        users = []
        for nickname, grade_class, _ in users_data:
            u = User(
                openid=f"demo-{nickname}",
                parent_openid=f"parent-demo-{nickname}",
                nickname=nickname,
                role="student",
                school="示范小学",
                grade_class=grade_class,
            )
            db.add(u)
            db.flush()
            coin_service.grant_register_bonus(db, u)
            users.append(u)

        # 演示组织：已通过平台审核，全员正式成员，邀请码固定便于演示
        org = Organization(
            name="示范小学",
            org_type="school",
            description="比赛演示用组织",
            status="pending",
            creator_id=users[0].id,
        )
        db.add(org)
        db.flush()
        org_service.approve_organization(db, org, reviewer_id=0)
        org.invite_code = "DEMO2026"
        db.flush()

        for i, u in enumerate(users):
            if i == 0:
                # 创建者已在 approve 时成为 owner
                u.active_org_id = org.id
                continue
            db.add(OrgMembership(
                org_id=org.id,
                user_id=u.id,
                role="member",
                status="active",
                handle_note="种子数据自动加入",
            ))
            u.active_org_id = org.id

        items_data = [
            # (owner_idx, name, category, condition, want, desc)
            (0, "闪耀奥特曼卡 HR", "奥特曼卡", "九成新", "绘本,奥特曼卡", "光荣赛罗 HR，卡面无划痕"),
            (0, "赛罗奥特曼双面卡", "奥特曼卡", "八成新", "玩具", "换了三张重复的"),
            (1, "《神奇校车》1-5 册", "绘本/课外书", "九成新", "奥特曼卡,文具", "看完一遍，无涂鸦"),
            (1, "《米小圈上学记》全套", "绘本/课外书", "八成新", "绘本/课外书", "第 12 页有姓名贴"),
            (2, "乐高小汽车积木", "玩具", "八成新", "奥特曼卡", "缺一个轮子盖，其他齐全"),
            (3, "未拆封中性笔 5 支", "文具", "崭新", "绘本/课外书", "义卖剩的，全新"),
            (4, "跳绳（可调节）", "体育用品", "有磨损", "玩具", "学校达标款"),
            (2, "整套恐龙模型", "玩具", "九成新", "体育用品", "12 只装，含霸王龙"),
        ]
        cats_map = category_service.categories_map(db)
        for owner_idx, name, category, condition, want, desc in items_data:
            est = estimate_value(name, category, desc, condition, categories=cats_map)
            item = Item(
                owner_id=users[owner_idx].id,
                org_id=org.id,
                name=name,
                category=category,
                description=desc,
                images="",
                condition=condition,
                value_coins=est["suggested_coins"],
                want_tags=want,
            )
            db.add(item)
            db.flush()
            coin_service.grant_list_item_reward(db, users[owner_idx], item.id)

        db.commit()
        print("种子数据完成：1 个组织（邀请码 DEMO2026）、5 个孩子、8 件闲置")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
