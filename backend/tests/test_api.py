"""端到端 API 测试：注册 → 上架(AI 定价) → 发起交换 → 家长双确认 → 完成 → 咸鱼币结算 → 排行榜。

用 FastAPI TestClient + 独立文件 DB，跑通核心故事线。
"""
import os
import tempfile

# 独立测试数据库（TestClient 内共享同一进程 token 解析，不需要跨进程）
_tmp = tempfile.mkdtemp(prefix="salted_fish_test_")
os.environ["SALTED_FISH_DB"] = os.path.join(_tmp, "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import db_init  # noqa: F401,E402  建表

client = TestClient(app)


def login(nickname: str, grade_class: str = "三年级2班") -> dict:
    return client.post(
        "/auth/login",
        json={"code": f"test-{nickname}", "nickname": nickname, "grade_class": grade_class},
    ).json()


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
            "category": "奥特曼卡",
            "condition": "九成新",
            "want_tags": ["绘本"],
            "description": "卡面无划痕",
        },
    )
    assert r.status_code == 200, r.text
    item_a = r.json()
    assert item_a["value_coins"] == 3, item_a
    assert login("测试小明")["user"]["coin_balance"] == 12

    r = client.post(
        f"/items?token={tb}",
        json={
            "name": "神奇校车 1-5 册",
            "category": "绘本/课外书",
            "condition": "九成新",
            "want_tags": ["奥特曼卡"],
        },
    )
    item_b = r.json()
    assert item_b["value_coins"] == 3

    client.post(
        f"/items?token={tb}",
        json={
            "name": "晨光中性笔 5 支",
            "category": "文具",
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
    r = client.post(
        "/items/ai-pricing",
        json={"name": "限量版赛罗卡", "category": "奥特曼卡", "condition": "崭新"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["suggested_coins"] >= 3
    assert "建议" in data["explanation"]


def test_cancel_flow_with_penalty():
    a = login("甲")
    b = login("乙")
    ta, tb = a["token"], b["token"]
    bootstrap_org(ta, tb, name="取消测试校")

    ia = client.post(
        f"/items?token={ta}",
        json={"name": "旧跳绳", "category": "体育用品", "condition": "有磨损", "want_tags": []},
    ).json()
    ib = client.post(
        f"/items?token={tb}",
        json={"name": "橡皮擦", "category": "文具", "condition": "九成新", "want_tags": []},
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
        json={"name": "正常橡皮", "category": "文具", "condition": "崭新", "want_tags": []},
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
    assert "奥特曼卡" in names and "其他" in names
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
        json={"name": "甲校卡牌", "category": "奥特曼卡", "condition": "九成新"},
    ).json()
    client.post(
        f"/items?token={tb}",
        json={"name": "乙校绘本", "category": "绘本/课外书", "condition": "九成新"},
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
            "note": "测试",
        },
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["api_key_set"] is True
    assert "abcdefg" not in row["api_key"]  # 脱敏
    assert "…" in row["api_key"] or "****" in row["api_key"]
    pid = row["id"]

    listed = client.get("/admin/llm/providers", params={"token": tok}).json()
    assert any(x["id"] == pid for x in listed)

    # 留空 api_key 不覆盖
    up = client.put(
        f"/admin/llm/providers/{pid}",
        params={"token": tok},
        json={"name": "硅基免费1-改", "api_key": ""},
    )
    assert up.status_code == 200
    assert up.json()["name"] == "硅基免费1-改"
    assert up.json()["api_key_set"] is True

    # active_endpoints 能读到
    from app.services import llm_service
    db = db_init.SessionLocal()
    eps = llm_service.active_endpoints(db)
    db.close()
    assert any(e["name"] == "硅基免费1-改" for e in eps)

    dele = client.delete(f"/admin/llm/providers/{pid}", params={"token": tok})
    assert dele.status_code == 200
