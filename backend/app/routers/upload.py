"""图片上传路由：接收小程序上传的闲置照片，存到 /uploads 并返回可访问 URL。

约束：
  - 必须登录
  - 只允许常用图片类型（jpg/png/webp/gif），限制大小。
  - 返回相对路径 /uploads/xxx.png，前端拼 BASE_URL 使用。
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR, get_db
from ..routers.auth import get_current_user, resolve_token
from ..services import rate_limit

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_SIZE = 8 * 1024 * 1024  # 8 MB


@router.post("")
def upload(
    request: Request,
    file: UploadFile = File(...),
    token: str = Query(""),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(resolve_token(token, authorization), db)
    ip = rate_limit.client_ip(request)
    rate_limit.check("upload", f"user:{user.id}", max_hits=20, window_sec=60)
    rate_limit.check("upload", f"ip:{ip}", max_hits=40, window_sec=60)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的图片类型 {ext or '（无扩展名）'}，仅支持 jpg/png/webp/gif")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    content = file.file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "图片过大，超过 8MB")

    fname = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{fname}"}
