#!/usr/bin/env python3
"""生成小程序 tabbar 图标（64x64 PNG）。纯标准库 + 3x 超采样抗锯齿。

主题「咸鱼市场」：
  fish  鱼塘  —— 圆润小鱼
  swap  交换  —— 两鱼相对 + 循环箭头
  rank  排行  —— 奖杯
  mine  我的  —— 卡通小人

跑法：python scripts/gen_tabbar_icons.py
输出：miniprogram/images/{name}.png / {name}-active.png
"""
import math
import os
import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _write_png(path: str, size: int, rgba_rows: list[bytes]) -> None:
    raw = b"".join(b"\x00" + row for row in rgba_rows)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(payload)


# ---------- 几何谓词（0..1 归一，再映射到 0..64） ----------
def _in_ellipse(px, py, cx, cy, rx, ry):
    return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0


def _in_circle(px, py, cx, cy, r):
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def _in_triangle(px, py, a, b, c):
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1 = sign((px, py), a, b)
    d2 = sign((px, py), b, c)
    d3 = sign((px, py), c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def _trapezoid(px, py, y_top, y_bot, x_top_half, x_bot_half, cx):
    t = (py - y_top) / (y_bot - y_top) if (y_bot - y_top) > 0 else 1.0
    half = x_top_half + (x_bot_half - x_top_half) * t
    return abs(px - cx) <= half


# 每个 glyph 返回 (body:bool, accent:bool)；accent 用白色强调（眼睛/星星）
def glyph_fish(px, py, s):
    # 大头朝右的圆润小鱼：圆身 + 清晰尾 + 鳍 + 眼
    body = False
    # 身体（圆润椭圆，头朝右）
    if _in_ellipse(px, py, s * 0.46, s * 0.50, s * 0.24, s * 0.16):
        body = True
    # 尾鳍（左侧两个分叉三角——上下张开）
    if _in_triangle(px, py, (s * 0.24, s * 0.50), (s * 0.02, s * 0.30), (s * 0.06, s * 0.50)):
        body = True
    if _in_triangle(px, py, (s * 0.24, s * 0.50), (s * 0.02, s * 0.70), (s * 0.06, s * 0.50)):
        body = True
    # 背鳍（上方小三角）
    if _in_triangle(px, py, (s * 0.50, s * 0.40), (s * 0.40, s * 0.34), (s * 0.56, s * 0.34)):
        body = True
    # 眼睛（右侧白色小圆）
    eye = _in_circle(px, py, s * 0.61, s * 0.42, s * 0.035)
    return body, eye


def glyph_swap(px, py, s):
    # 左鱼(朝右) + 右鱼(朝左) + 中间两颗指示点
    body = False
    accent = False
    # 左鱼身体朝右
    if _in_ellipse(px, py, s * 0.24, s * 0.5, s * 0.16, s * 0.10):
        body = True
        if _in_circle(px, py, s * 0.34, s * 0.43, s * 0.022):
            accent = True
    # 左鱼尾
    if _in_triangle(px, py, (s * 0.12, s * 0.5), (s * 0.00, s * 0.38), (s * 0.00, s * 0.62)):
        body = True
    # 右鱼(朝左)
    if _in_ellipse(px, py, s * 0.76, s * 0.5, s * 0.16, s * 0.10):
        body = True
        if _in_circle(px, py, s * 0.66, s * 0.43, s * 0.022):
            accent = True
    # 右鱼尾
    if _in_triangle(px, py, (s * 0.88, s * 0.5), (s * 1.0, s * 0.38), (s * 1.0, s * 0.62)):
        body = True
    # 中间两个点（循环）
    if _in_circle(px, py, s * 0.50, s * 0.42, s * 0.028) or _in_circle(px, py, s * 0.50, s * 0.60, s * 0.028):
        accent = True
    return body, accent


def glyph_rank(px, py, s):
    # 奖杯：杯体(圆顶梯形) + 双耳 + 底座 + 星
    cx = s * 0.5
    body = False
    accent = False
    # 杯体（上窄下略宽的圆肩梯形），py 0.22..0.58
    if py >= s * 0.24 and py <= s * 0.60:
        half = s * 0.075 + (s * 0.105 - s * 0.075) * ((py - s * 0.24) / (s * 0.36))
        if abs(px - cx) <= half:
            body = True
    # 杯口横沿
    if py >= s * 0.20 and py <= s * 0.26:
        if abs(px - cx) <= s * 0.11:
            body = True
    # 双耳
    if _in_circle(px, py, cx - s * 0.125, s * 0.40, s * 0.045):
        body = True
    if _in_circle(px, py, cx + s * 0.125, s * 0.40, s * 0.045):
        body = True
    # 底座柱 + 底座
    if abs(px - cx) <= s * 0.045 and py >= s * 0.60 and py <= s * 0.72:
        body = True
    if abs(px - cx) <= s * 0.13 and py >= s * 0.72 and py <= s * 0.80:
        body = True
    # 星（accent）
    if _in_circle(px, py, cx, s * 0.36, s * 0.028):
        accent = True
    return body, accent


def glyph_mine(px, py, s):
    cx = s * 0.5
    body = False
    accent = False
    # 头
    if _in_circle(px, py, cx, s * 0.265, s * 0.165):
        body = True
    # 脖子（连接头与肩）
    if abs(px - cx) <= s * 0.05 and py <= s * 0.50:
        body = True
    # 身体（圆肩梯形）
    if py >= s * 0.46 and py <= s * 0.88:
        if _trapezoid(px, py, s * 0.44, s * 0.86, s * 0.17, s * 0.30, cx):
            body = True
    # 眼睛
    if _in_circle(px, py, cx - s * 0.06, s * 0.24, s * 0.024) or \
       _in_circle(px, py, cx + s * 0.06, s * 0.24, s * 0.024):
        accent = True
    return body, accent


GLYPHS = {
    "fish": glyph_fish,
    "swap": glyph_swap,
    "rank": glyph_rank,
    "mine": glyph_mine,
}

SEED = {
    "fish": (84, 199, 165),    # 薄荷绿
    "swap": (44, 155, 128),    # 深薄荷
    "rank": (255, 217, 120),   # 奶油黄(名次)
    "mine": (84, 199, 165),    # 薄荷
}
GRAY = (178, 186, 198, 255)
ACCENT = (255, 255, 255, 255)


def render(size, name, seed, accent):
    fn = GLYPHS[name]
    SS = 3
    rows = []
    for j in range(size):
        row = bytearray()
        for i in range(size):
            rs = gs = bs = aa = 0.0
            covered = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = (i + (sx + 0.5) / SS) / size * 64.0
                    y = (j + (sy + 0.5) / SS) / size * 64.0
                    body, accp = fn(x, y, 64.0)
                    if body or accp:
                        col = accent if accp else seed
                        rs += col[0]; gs += col[1]; bs += col[2]; aa += 1.0
                        covered += 1
            n = SS * SS
            if covered > 0:
                r = int(rs / covered); g = int(gs / covered); b = int(bs / covered)
            else:
                r = g = b = 0
            alpha = int(round(aa / n * 255))
            row += bytes([r, g, b, alpha])
        rows.append(bytes(row))
    return rows


def write(out_dir, size):
    os.makedirs(out_dir, exist_ok=True)
    for name in GLYPHS:
        rows_gray = render(size, name, GRAY, GRAY)
        _write_png(os.path.join(out_dir, f"{name}.png"), size, rows_gray)
        rows_active = render(size, name, SEED[name], ACCENT)
        _write_png(os.path.join(out_dir, f"{name}-active.png"), size, rows_active)
        print("generated", name)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "miniprogram", "images")
    write(out, 64)