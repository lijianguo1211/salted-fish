"""端到端 API 测试：注册 → 上架(AI 定价) → 发起交换 → 家长双确认 → 完成 → 咸鱼币结算 → 排行榜。

用 FastAPI TestClient + 独立文件 DB，跑通核心故事线。
"""
import os
import tempfile

# 独立测试数据库（TestClient 内共享同一进程 token 解析，不需要跨进程）
_tmp = tempfile.mkdtemp(prefix="salted_fish_test_")
os.environ["SALTED_FISH_DB"] = os.path.join(_tmp, "test.db")
os.environ["SALTED_FISH_RATE_LIMIT"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import db_init  # noqa: F401,E402  建表

client = TestClient(app)


def login(nickname: str, grade_class: str = "三年级2班") -> dict:
    """微信授权登录 + 完善资料（对齐上线流程）。"""
    r = client.post("/auth/login", json={"code": f"test-{nickname}"}).json()
    token = r["token"]
    user = client.put(
        f"/auth/profile?token={token}",
        json={"nickname": nickname, "grade_class": grade_class, "school": "示范小学"},
    ).json()
    return {"token": token, "user": user}


def token_of(nickname: str) -> str:
    return login(nickname)["token"]


def admin_login(email: str, password: str):
    """独立后台登录：拿公钥 → RSA-OAEP 加密密码 → 提交。"""
    from app.services import admin_crypto
    pk = client.get("/admin-auth/public-key").json()["public_key"]
    cipher = admin_crypto.encrypt_with_public(pk.encode(), password.encode())
    import base64
    return client.post(
        "/admin-auth/login",
        json={"email": email, "encrypted_password": base64.b64encode(cipher).decode()},
    )



def admin_web_login(email: str, password: str) -> str:
    """RSA 加密密码后登录独立后台，返回 web token。"""
    import base64
    from app.services import admin_crypto

    pem = admin_crypto.public_key_pem().encode()
    enc = base64.b64encode(
        admin_crypto.encrypt_with_public(pem, password.encode("utf-8"))
    ).decode()
    r = client.post(
        "/admin-auth/login",
        json={"email": email, "encrypted_password": enc},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]

def bootstrap_org(*tokens: str, name: str = "测试组织") -> dict:
    """创建组织 → 平台审核通过 → 其余用户用邀请码加入并由组织管理员通过。"""
    owner_tok = tokens[0]
    r = client.post(
        f"/orgs/apply?token={owner_tok}",
        json={"name": name, "org_type": "school", "description": "测试"},
    )
    assert r.status_code == 200, r.text
    org = r.json()

    admin = login("管理员")
    r = client.post(
        f"/admin/orgs/{org['id']}/review",
        params={"token": admin["token"]},
        json={"action": "approve", "reason": ""},
    )
    assert r.status_code == 200, r.text
    org = r.json()
    code = org["invite_code"]
    assert code

    # 创建者切到该组织
    client.post(f"/orgs/switch?token={owner_tok}", json={"org_id": org["id"]})

    for tok in tokens[1:]:
        jr = client.post(f"/orgs/join?token={tok}", json={"invite_code": code})
        assert jr.status_code == 200, jr.text
        mid = jr.json()["membership"]["id"]
        ar = client.post(
            f"/orgs/{org['id']}/members/{mid}?token={owner_tok}",
            json={"action": "approve"},
        )
        assert ar.status_code == 200, ar.text
        client.post(f"/orgs/switch?token={tok}", json={"org_id": org["id"]})

    return org


def test_full_swap_flow():
    a = login("测试小明", "三年级2班")
    b = login("测试朵朵", "三年级2班")
    assert a["user"]["coin_balance"] == 10
    assert b["user"]["coin_balance"] == 10
    ta, tb = a["token"], b["token"]
    bootstrap_org(ta, tb, name="交换测试校")

    r = client.post(
        f"/items?token={ta}",
        json={
            "name": "闪耀奥特曼卡 HR",
            "category": "卡牌贴纸",
            "condition": "九成新",
            "want_tags": ["绘本"],
            "description": "卡面无划痕",
        },
    )
    assert r.status_code == 200, r.text
    item_a = r.json()
    assert item_a["value_coins"] == 3, item_a
    assert item_a["ai_value_coins"] == 3, item_a
    assert login("测试小明")["user"]["coin_balance"] == 12

    r = client.post(
        f"/items?token={tb}",
        json={
            "name": "神奇校车 1-5 册",
            "category": "绘本图书",
            "condition": "九成新",
            "want_tags": ["卡牌贴纸"],
        },
    )
    item_b = r.json()
    assert item_b["value_coins"] == 3

    client.post(
        f"/items?token={tb}",
        json={
            "name": "晨光中性笔 5 支",
            "category": "文具学习",
            "condition": "崭新",
            "want_tags": ["绘本"],
        },
    )

    r = client.post(
        f"/swaps?token={ta}",
        json={
            "initiator_item_id": item_a["id"],
            "receiver_item_id": item_b["id"],
            "note": "我特别想看神奇校车！",
        },
    )
    assert r.status_code == 200, r.text
    swap = r.json()
    assert swap["status"] == "pending_parent"

    r2 = client.post(
        f"/swaps?token={ta}",
        json={
            "initiator_item_id": item_a["id"],
            "receiver_item_id": item_b["id"],
            "note": "",
        },
    )
    assert r2.status_code == 400

    r = client.post(
        f"/swaps/{swap['id']}/actions?token={ta}",
        json={"action": "parent_confirm"},
    )
    assert r.json()["status"] == "pending_peer"

    r = client.post(
        f"/swaps/{swap['id']}/actions?token={tb}",
        json={"action": "parent_confirm"},
    )
    assert r.json()["status"] == "accepted"

    r = client.post(
        f"/swaps/{swap['id']}/actions?token={ta}", json={"action": "complete"}
    )
    assert r.json()["status"] == "accepted"
    r = client.post(
        f"/swaps/{swap['id']}/actions?token={tb}", json={"action": "complete"}
    )
    assert r.json()["status"] == "completed"

    assert login("测试小明")["user"]["coin_balance"] == 22
    assert login("测试朵朵")["user"]["coin_balance"] == 24

    r = client.get(f"/items?token={ta}&status=all")
    names = {i["name"]: i["status"] for i in r.json()}
    assert names["闪耀奥特曼卡 HR"] == "swapped"

    r = client.get(f"/coins/leaderboard?token={ta}")
    board = r.json()["leaderboard"]
    assert board[0]["nickname"] == "测试朵朵"
    assert any(e["nickname"] == "测试小明" for e in board)


def test_ai_pricing_endpoint():
    tok = login("估价同学")["token"]
    anon = client.post(
        "/items/ai-pricing",
        json={"name": "限量版赛罗卡", "category": "卡牌贴纸", "condition": "崭新"},
    )
    assert anon.status_code == 401
    r = client.post(
        f"/items/ai-pricing?token={tok}",
        json={"name": "限量版赛罗卡", "category": "卡牌贴纸", "condition": "崭新"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["suggested_coins"] >= 3
    assert "建议" in data["explanation"]
    bearer = client.post(
        "/items/ai-pricing",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "限量版赛罗卡", "category": "卡牌贴纸", "condition": "崭新"},
    )
    assert bearer.status_code == 200
    no_upload = client.post("/upload", files={"file": ("a.png", b"not-a-real-png", "image/png")})
    assert no_upload.status_code == 401

    bearer = client.post(
        "/items/ai-pricing",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "限量版赛罗卡", "category": "卡牌贴纸", "condition": "崭新"},
    )
    assert bearer.status_code == 200

    no_upload = client.post("/upload", files={"file": ("a.png", b"not-a-real-png", "image/png")})
    assert no_upload.status_code == 401


def test_cancel_flow_with_penalty():
    a = login("甲")
    b = login("乙")
    ta, tb = a["token"], b["token"]
    bootstrap_org(ta, tb, name="取消测试校")

    ia = client.post(
        f"/items?token={ta}",
        json={"name": "旧跳绳", "category": "体育户外", "condition": "有磨损", "want_tags": []},
    ).json()
    ib = client.post(
        f"/items?token={tb}",
        json={"name": "橡皮擦", "category": "文具学习", "condition": "九成新", "want_tags": []},
    ).json()
    assert ia["value_coins"] == 2

    swap = client.post(
        f"/swaps?token={ta}",
        json={"initiator_item_id": ia["id"], "receiver_item_id": ib["id"], "note": ""},
    ).json()

    r = client.post(
        f"/swaps/{swap['id']}/actions?token={ta}",
        json={"action": "cancel", "reason": "不换了"},
    )
    assert r.json()["status"] == "cancelled"
    assert login("甲")["user"]["coin_balance"] == 10

    r = client.get(f"/items?token={ta}&status=all")
    assert {i["name"]: i["status"] for i in r.json()}["旧跳绳"] == "on_shelf"

    swap2 = client.post(
        f"/swaps?token={ta}",
        json={"initiator_item_id": ia["id"], "receiver_item_id": ib["id"], "note": ""},
    ).json()
    r = client.post(
        f"/swaps/{swap2['id']}/actions?token={tb}", json={"action": "parent_deny"}
    )
    assert r.json()["status"] == "cancelled"
    assert login("甲")["user"]["coin_balance"] == 10


def test_report_and_admin_moderation():
    kid = login("物主小强")
    parent = login("举报家长")
    tk = kid["token"]
    tp = parent["token"]
    bootstrap_org(tk, tp, name="举报测试校")

    item = client.post(
        f"/items?token={tk}",
        json={"name": "可疑玩具", "category": "玩具", "condition": "九成新", "want_tags": []},
    ).json()

    reasons = client.get("/items/report-reasons").json()["reasons"]
    assert len(reasons) >= 1
    r = client.post(
        f"/items/{item['id']}/report?token={tp}",
        json={"reason": "不当交易（要求付钱/买卖）", "note": "这个孩子在要钱"},
    )
    assert r.status_code == 200

    detail = client.get(f"/items/{item['id']}?token={tp}").json()
    assert detail["reported"] == 1
    assert detail["flagged"] is True

    r2 = client.post(
        f"/items/{item['id']}/report?token={tp}",
        json={"reason": "其他问题", "note": "又举报一次"},
    )
    assert r2.status_code == 400

    r3 = client.get("/admin/reports", params={"token": tp})
    assert r3.status_code in (403, 422)

    admin = login("管理员")
    tam = admin["token"]
    assert admin["user"]["is_admin"] is True

    reps = client.get("/admin/reports", params={"token": tam, "status": "pending"})
    assert reps.status_code == 200
    assert any(x["item_id"] == item["id"] for x in reps.json())

    report_id = [x for x in reps.json() if x["item_id"] == item["id"]][0]["id"]

    r4 = client.post(
        f"/admin/reports/{report_id}",
        params={"token": tam},
        json={"action": "remove", "reason": "涉及不当交易，已下架"},
    )
    assert r4.status_code == 200
    assert r4.json()["status"] == "resolved"

    detail2 = client.get(f"/items/{item['id']}?token={tp}").json()
    assert detail2["status"] == "removed"
    list_all = client.get(f"/items?token={tp}&status=on_shelf").json()
    assert all(x["id"] != item["id"] for x in list_all)

    item2 = client.post(
        f"/items?token={tk}",
        json={"name": "正常橡皮", "category": "文具学习", "condition": "崭新", "want_tags": []},
    ).json()
    client.post(
        f"/items/{item2['id']}/report?token={tp}",
        json={"reason": "其他问题", "note": "误报"},
    )
    reps2 = client.get("/admin/reports", params={"token": tam, "status": "pending"}).json()
    rid2 = [x for x in reps2 if x["item_id"] == item2["id"]][0]["id"]
    r5 = client.post(
        f"/admin/reports/{rid2}",
        params={"token": tam},
        json={"action": "reject", "reason": "不违规，驳回"},
    )
    assert r5.status_code == 200
    assert r5.json()["status"] == "rejected"
    detail3 = client.get(f"/items/{item2['id']}?token={tp}").json()
    assert detail3["status"] == "on_shelf"


def test_category_admin_crud():
    pub = client.get("/items/categories").json()["categories"]
    names = [c["name"] for c in pub]
    assert "卡牌贴纸" in names and "其他" in names
    assert pub[-1]["name"] == "其他"

    kid = login("分类路人甲")
    r0 = client.post("/admin/categories", params={"token": kid["token"]},
                     json={"name": "违规", "value_base": 1})
    assert r0.status_code in (403, 422)

    admin = login("管理员")
    tam = admin["token"]
    created = client.post("/admin/categories", params={"token": tam},
                          json={"name": "乐高玩具", "value_base": 5, "note": "拼搭",
                                "sort_order": 6, "is_active": True})
    assert created.status_code == 200
    cid = created.json()["id"]

    dup = client.post("/admin/categories", params={"token": tam},
                      json={"name": "乐高玩具", "value_base": 3})
    assert dup.status_code == 400

    client.post("/admin/categories", params={"token": tam},
                json={"name": "私密类", "value_base": 1, "sort_order": 7, "is_active": False})
    pub_after = [c["name"] for c in client.get("/items/categories").json()["categories"]]
    assert "乐高玩具" in pub_after
    assert "私密类" not in pub_after

    up = client.put(f"/admin/categories/{cid}", params={"token": tam},
                    json={"value_base": 8})
    assert up.status_code == 200 and up.json()["value_base"] == 8
    est = client.post("/items/ai-pricing",
                      params={"token": tam},
                      json={"name": "全新乐高", "category": "乐高玩具",
                            "description": "全新零件", "condition": "崭新"}).json()
    assert est["suggested_coins"] >= 8

    tk = login("分类小明")["token"]
    bootstrap_org(tk, name="分类测试校")
    client.post(f"/items?token={tk}", json={"name": "我的乐高", "category": "乐高玩具"})
    dele = client.delete(f"/admin/categories/{cid}", params={"token": tam})
    assert dele.status_code == 400

    tmp_c = client.post("/admin/categories", params={"token": tam},
                        json={"name": "临时类", "value_base": 1}).json()
    dele2 = client.delete(f"/admin/categories/{tmp_c['id']}", params={"token": tam})
    assert dele2.status_code == 200


def test_org_invite_and_isolation():
    a = login("组织甲")
    b = login("组织乙")
    c = login("组织丙")
    ta, tb, tc = a["token"], b["token"], c["token"]

    org1 = bootstrap_org(ta, name="甲校")
    bootstrap_org(tb, name="乙校")

    ia = client.post(
        f"/items?token={ta}",
        json={"name": "甲校卡牌", "category": "卡牌贴纸", "condition": "九成新"},
    ).json()
    client.post(
        f"/items?token={tb}",
        json={"name": "乙校绘本", "category": "绘本图书", "condition": "九成新"},
    )

    list_a = client.get(f"/items?token={ta}").json()
    assert any(x["id"] == ia["id"] for x in list_a)
    assert all(x["name"] != "乙校绘本" for x in list_a)

    jr = client.post(f"/orgs/join?token={tc}", json={"invite_code": org1["invite_code"]})
    assert jr.status_code == 200
    mid = jr.json()["membership"]["id"]
    sw = client.post(f"/orgs/switch?token={tc}", json={"org_id": org1["id"]})
    assert sw.status_code == 403

    client.post(
        f"/orgs/{org1['id']}/members/{mid}?token={ta}",
        json={"action": "approve"},
    )
    client.post(f"/orgs/switch?token={tc}", json={"org_id": org1["id"]})
    list_c = client.get(f"/items?token={tc}").json()
    assert any(x["id"] == ia["id"] for x in list_c)


def test_admin_web_flow():
    from app.models import AdminUser
    from app.services.admin_auth import hash_password

    db = db_init.SessionLocal()
    db.add(AdminUser(email="admin@xianyu.cn", password_hash=hash_password("pass123"),
                     name="后台管理员"))
    db.commit()
    db.close()

    r = admin_login("admin@xianyu.cn", "pass123")
    assert r.status_code == 200
    web_tok = r.json()["token"]
    assert web_tok.startswith("admin-web-")

    bad = admin_login("admin@xianyu.cn", "wrong")
    assert bad.status_code == 401
    bad2 = client.post("/admin-auth/login", json={"email": "not-an-email", "encrypted_password": "x"})
    assert bad2.status_code == 400

    kid = login("后台看孩子")
    bootstrap_org(kid["token"], name="后台测试校")
    client.post(f"/items?token={kid['token']}",
                json={"name": "后台可见的玩具", "category": "玩具", "condition": "九成新"})

    users = client.get("/admin/users", params={"token": web_tok})
    assert users.status_code == 200
    names = [u["nickname"] for u in users.json()["users"]]
    assert "后台看孩子" in names

    items = client.get("/admin/items/all", params={"token": web_tok})
    assert items.status_code == 200
    assert items.json()["total"] >= 1

    target = [x for x in items.json()["items"] if "后台可见的玩具" in x["name"]][0]
    r2 = client.post(f"/admin/item/{target['id']}/status", params={"token": web_tok, "status": "removed"})
    assert r2.status_code == 200 and r2.json()["status"] == "removed"

    orgs = client.get("/admin/orgs", params={"token": web_tok, "status": "all"})
    assert orgs.status_code == 200
    assert len(orgs.json()) >= 1

    baduser = client.get("/admin/users", params={"token": kid["token"]})
    assert baduser.status_code in (403, 422)

    assert client.get("/admin/categories", params={"token": web_tok}).status_code == 200
    assert client.get("/admin/reports", params={"token": web_tok, "status": "all"}).status_code == 200
    assert client.get("/admin/items/all", params={"token": web_tok}).status_code == 200
    assert client.get("/admin/users", params={"token": web_tok}).status_code == 200



def test_llm_provider_crud():
    """大模型多 Key：后台增删改查 + Key 脱敏；不真正调外部 API。"""
    from app.models import AdminUser
    from app.services.admin_auth import hash_password

    db = db_init.SessionLocal()
    if not db.query(AdminUser).filter(AdminUser.email == "llm-admin@xianyu.cn").first():
        db.add(AdminUser(email="llm-admin@xianyu.cn", password_hash=hash_password("pass123"),
                         name="LLM管理员"))
        db.commit()
    db.close()

    tok = admin_login("llm-admin@xianyu.cn", "pass123").json()["token"]

    vendors = client.get("/admin/llm/vendors", params={"token": tok})
    assert vendors.status_code == 200
    assert any(v["vendor"] == "siliconflow" for v in vendors.json())

    created = client.post(
        "/admin/llm/providers",
        params={"token": tok},
        json={
            "name": "硅基免费1",
            "vendor": "siliconflow",
            "base_url": "https://api.siliconflow.cn/v1",
            "api_key": "sk-test-abcdefg12345678",
            "model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "is_active": True,
            "sort_order": 1,
            "timeout_sec": 20,
            "support_image": True,
            "support_audio": False,
            "note": "测试",
        },
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["api_key_set"] is True
    assert "abcdefg" not in row["api_key"]  # 脱敏
    assert "…" in row["api_key"] or "****" in row["api_key"]
    assert row["support_image"] is True
    assert row["support_audio"] is False
    pid = row["id"]

    listed = client.get("/admin/llm/providers", params={"token": tok}).json()
    assert any(x["id"] == pid for x in listed)

    # 留空 api_key 不覆盖
    up = client.put(
        f"/admin/llm/providers/{pid}",
        params={"token": tok},
        json={"name": "硅基免费1-改", "api_key": "", "support_image": False},
    )
    assert up.status_code == 200
    assert up.json()["name"] == "硅基免费1-改"
    assert up.json()["api_key_set"] is True
    assert up.json()["support_image"] is False

    # active_endpoints 能读到
    from app.services import llm_service
    db = db_init.SessionLocal()
    eps = llm_service.active_endpoints(db)
    db.close()
    assert any(e["name"] == "硅基免费1-改" for e in eps)
    # support_image=False 的配置不应进入视觉候选
    vision_eps = [e for e in eps if e.get("support_image", True)]
    assert all(e["name"] != "硅基免费1-改" for e in vision_eps)

    dele = client.delete(f"/admin/llm/providers/{pid}", params={"token": tok})
    assert dele.status_code == 200


def test_onboarding_profile_gate():
    """登录可无资料；完善资料后 profile_completed=True。"""
    r = client.post("/auth/login", json={"code": "test-newbie-device"}).json()
    assert r["user"]["profile_completed"] is False
    assert r["user"]["nickname"] == "小咸鱼"
    tok = r["token"]
    u = client.put(
        f"/auth/profile?token={tok}",
        json={"nickname": "新同学", "grade_class": "一年级1班", "school": "示范小学"},
    ).json()
    assert u["profile_completed"] is True
    assert u["nickname"] == "新同学"
    me = client.get(f"/auth/me?token={tok}").json()
    assert me["profile_completed"] is True


def test_member_can_get_invite():
    """正式成员（非管理员）也可查看邀请码分享。"""
    owner = login("邀请主理人")
    member = login("邀请成员甲")
    org = bootstrap_org(owner["token"], member["token"], name="邀请测试校")

    # 普通成员可读邀请码
    r = client.get(f"/orgs/{org['id']}/invite", params={"token": member["token"]})
    assert r.status_code == 200, r.text
    assert r.json()["invite_code"]
    assert r.json()["can_refresh"] is False
    assert r.json()["invite_enabled"] is True

    # 管理员可刷新
    assert client.post(
        f"/orgs/{org['id']}/invite/refresh", params={"token": owner["token"]}
    ).status_code == 200
    # 普通成员不能刷新
    assert client.post(
        f"/orgs/{org['id']}/invite/refresh", params={"token": member["token"]}
    ).status_code == 403


def test_org_invite_controls():
    """关闭邀请 / 失效邀请码 / 免审加入。"""
    owner = login("管控主理人")
    joiner = login("管控新同学")
    org = bootstrap_org(owner["token"], name="管控测试校")
    code = org["invite_code"]
    oid = org["id"]
    ot = owner["token"]
    jt = joiner["token"]

    # 关闭邀请后不可加入
    r = client.put(
        f"/orgs/{oid}/settings?token={ot}",
        json={"invite_enabled": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["invite_enabled"] is False
    assert client.post(f"/orgs/join?token={jt}", json={"invite_code": code}).status_code == 400

    # 重新开启
    assert client.put(
        f"/orgs/{oid}/settings?token={ot}",
        json={"invite_enabled": True},
    ).status_code == 200

    # 失效邀请码后旧码不可用
    inv = client.post(f"/orgs/{oid}/invite/invalidate", params={"token": ot})
    assert inv.status_code == 200, inv.text
    assert client.post(f"/orgs/join?token={jt}", json={"invite_code": code}).status_code == 404

    # 换发新码 + 关闭审核 → 直接 active
    new_code = client.post(
        f"/orgs/{oid}/invite/refresh", params={"token": ot}
    ).json()["invite_code"]
    assert new_code and new_code != code
    assert client.put(
        f"/orgs/{oid}/settings?token={ot}",
        json={"join_need_review": False},
    ).status_code == 200
    jr = client.post(f"/orgs/join?token={jt}", json={"invite_code": new_code})
    assert jr.status_code == 200, jr.text
    assert jr.json()["membership"]["status"] == "active"

    # 成员侧：关闭邀请后看不到码
    client.put(f"/orgs/{oid}/settings?token={ot}", json={"invite_enabled": False})
    view = client.get(f"/orgs/{oid}/invite", params={"token": ot}).json()
    assert view["invite_enabled"] is False
    assert view["invite_code"] == ""


def test_org_create_quota_and_raise():
    """默认每人可创建 3 个；用满后需提额申请，超管可配默认额度并审核。"""
    owner = login("额度主理人")
    tok = owner["token"]
    admin = login("管理员")
    at = admin["token"]

    q = client.get(f"/orgs/create-quota?token={tok}").json()
    assert q["limit"] == 3
    assert q["can_create"] is True

    # 平台改默认额度为 1，便于测满额
    assert client.put(
        "/admin/org-settings",
        params={"token": at},
        json={"max_orgs_per_creator": 1},
    ).status_code == 200
    q = client.get(f"/orgs/create-quota?token={tok}").json()
    assert q["limit"] == 1

    # 创建 1 个占满
    r = client.post(
        f"/orgs/apply?token={tok}",
        json={"name": "额度一号校", "org_type": "school", "description": "测"},
    )
    assert r.status_code == 200, r.text
    # 待审也占名额，不能再创建
    r2 = client.post(
        f"/orgs/apply?token={tok}",
        json={"name": "额度二号校", "org_type": "school", "description": "测"},
    )
    assert r2.status_code == 400

    # 提额申请：原因 + 证明
    app = client.post(
        f"/orgs/quota-applications?token={tok}",
        json={
            "reason": "本人同时任教两个年级班主任，需要分别为各班创建组织便于管理。",
            "proof_urls": ["/uploads/fake-teacher-cert.png"],
            "requested_limit": 5,
        },
    )
    assert app.status_code == 200, app.text
    app_id = app.json()["id"]

    # 超管通过
    ok = client.post(
        f"/admin/org-quota-applications/{app_id}/review",
        params={"token": at},
        json={"action": "approve", "reason": ""},
    )
    assert ok.status_code == 200, ok.text
    q = client.get(f"/orgs/create-quota?token={tok}").json()
    assert q["limit"] == 5
    assert q["can_create"] is True

    client.put(
        "/admin/org-settings",
        params={"token": at},
        json={"max_orgs_per_creator": 3},
    )


def test_ai_moderation_gate():
    """关闭合规时放行；开启后关键词拦截不宜上架物品。"""
    settings = client.get("/items/ai-settings").json()
    assert "ai_pricing_enabled" in settings
    assert settings["ai_moderation_enabled"] is False

    admin = login("管理员")
    at = admin["token"]
    # 开启合规检测
    r = client.put(
        "/admin/ai-settings",
        params={"token": at},
        json={"ai_moderation_enabled": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ai_moderation_enabled"] is True

    a = login("合规检测甲")
    ta = a["token"]
    bootstrap_org(ta, name="合规检测校")

    bad = client.post(
        f"/items?token={ta}",
        json={
            "name": "电子烟一套",
            "category": "其他",
            "condition": "九成新",
            "want_tags": [],
            "description": "闲置电子烟",
        },
    )
    assert bad.status_code == 400, bad.text
    assert "不宜上架" in bad.json()["detail"] or "电子烟" in bad.json()["detail"]

    good = client.post(
        f"/items?token={ta}",
        json={
            "name": "未拆封中性笔",
            "category": "文具学习",
            "condition": "崭新",
            "want_tags": ["绘本"],
        },
    )
    # 开启后无 LLM 时也会拒绝（fail closed）；关键词未命中但无模型
    # 若无模型：400；有环境模型则可能 200。测试环境通常无 LLM。
    if good.status_code == 400:
        assert "大模型" in good.json()["detail"] or "合规" in good.json()["detail"] or "重试" in good.json()["detail"]
    else:
        assert good.status_code == 200, good.text

    # 关闭合规
    assert client.put(
        "/admin/ai-settings",
        params={"token": at},
        json={"ai_moderation_enabled": False},
    ).status_code == 200

    ok = client.post(
        f"/items?token={ta}",
        json={
            "name": "橡皮一块",
            "category": "文具学习",
            "condition": "九成新",
            "want_tags": [],
        },
    )
    assert ok.status_code == 200, ok.text


def test_ai_and_user_value_stored_separately():
    """AI 估值与物主自己估值分开存，改自己估值不覆盖 AI。"""
    a = login("估值对照甲")
    ta = a["token"]
    bootstrap_org(ta, name="估值对照校")
    r = client.post(
        f"/items?token={ta}",
        json={
            "name": "未拆封中性笔",
            "category": "文具学习",
            "condition": "崭新",
            "want_tags": [],
            "value_coins": 8,
        },
    )
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["value_coins"] == 8
    assert item["ai_value_coins"] >= 1
    ai_saved = item["ai_value_coins"]
    up = client.put(
        f"/items/{item['id']}?token={ta}",
        json={"value_coins": 5},
    )
    assert up.status_code == 200, up.text
    assert up.json()["value_coins"] == 5
    assert up.json()["ai_value_coins"] == ai_saved

