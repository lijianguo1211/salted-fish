"""限流单元测试（不走 TestClient 的全局关闭开关）。"""
import pytest
from fastapi import HTTPException

from app.services import rate_limit


def test_rate_limit_trips(monkeypatch):
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_ENABLED", True)
    rate_limit._hits.clear()
    rate_limit.check("t", "k", max_hits=2, window_sec=60)
    rate_limit.check("t", "k", max_hits=2, window_sec=60)
    with pytest.raises(HTTPException) as ei:
        rate_limit.check("t", "k", max_hits=2, window_sec=60)
    assert ei.value.status_code == 429
    rate_limit._hits.clear()
