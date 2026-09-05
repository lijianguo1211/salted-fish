"""咸鱼小市场 · FastAPI 主入口。

比赛演示版：DEMO_MODE=1（免 code 登录）、WECHAT_MOCK=1（订阅消息落库展示）。

启动（推荐，自动读 .env 里的 HOST/PORT）：
    uv run python -m app
    # 等价于手动：uv run uvicorn app.main:app --host $SALTED_FISH_HOST --port $SALTED_FISH_PORT
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, DEMO_MODE, UPLOAD_DIR, WECHAT_MOCK
from .routers import admin, admin_auth, auth, coins, items, orgs, parent, swaps, upload
from . import db_init  # noqa: F401  启动建表

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="咸鱼小市场 API",
    description="小学生闲置交换平台（以物换物 · 家长双确认 · 咸鱼币积分）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(items.router)
app.include_router(swaps.router)
app.include_router(coins.router)
app.include_router(parent.router)
app.include_router(upload.router)
app.include_router(admin.router)
app.include_router(admin_auth.router)

# 静态托管上传的图片
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {
        "app": "咸鱼小市场",
        "mode": "demo" if DEMO_MODE else "prod",
        "wechat": "mock" if WECHAT_MOCK else "real",
        "docs": "/docs",
    }


def main():
    """uv run python -m app：按 .env 的 HOST/PORT 启动。"""
    import uvicorn

    from .config import HOST, PORT

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=os.environ.get("SALTED_FISH_RELOAD", "0") == "1")


if __name__ == "__main__":
    main()
