import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request

# 每个 IP 在滑动窗口内允许的最大请求次数
# RATE_LIMIT_REQUESTS=0 表示关闭限速
_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "86400"))  # 默认 24 小时

_store: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _get_client_ip(request: Request) -> str:
    """优先读取反向代理注入的真实 IP，否则直接用连接 IP。"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    """对 POST /research/tasks 做 IP 滑动窗口限速。超限返回 429。"""
    if _MAX_REQUESTS <= 0:
        return  # 设为 0 则禁用限速

    ip = _get_client_ip(request)
    now = time.time()
    cutoff = now - _WINDOW_SECONDS

    with _lock:
        # 清除窗口外的旧记录
        _store[ip] = [t for t in _store[ip] if t > cutoff]

        if len(_store[ip]) >= _MAX_REQUESTS:
            window_hours = _WINDOW_SECONDS // 3600
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {_MAX_REQUESTS} requests "
                    f"per {window_hours} hour(s) per IP."
                ),
            )

        _store[ip].append(now)
