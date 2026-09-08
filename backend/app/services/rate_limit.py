"""简易内存限流：滑动窗口。单进程有效，适合当前单机部署。

SALTED_FISH_RATE_LIMIT=0 时关闭（测试用）。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from ..config import RATE_LIMIT_ENABLED

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check(scope: str, key: str, max_hits: int, window_sec: int = 60) -> None:
    if not RATE_LIMIT_ENABLED:
        return
    now = time.time()
    bucket = f"{scope}:{key}"
    with _lock:
        q = _hits[bucket]
        cutoff = now - window_sec
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_hits:
            raise HTTPException(429, "请求过于频繁，请稍后再试")
        q.append(now)
