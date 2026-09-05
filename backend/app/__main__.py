"""`uv run python -m app` 启动入口。

读 backend/.env 的 SALTED_FISH_HOST / SALTED_FISH_PORT 启动 FastAPI。
等价：uv run uvicorn app.main:app --host $SALTED_FISH_HOST --port $SALTED_FISH_PORT
"""
from app.main import main

if __name__ == "__main__":
    main()