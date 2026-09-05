"""一次性把咸鱼小市场的 wxss 主题从『草绿橙』重映射为『薄荷绿 + 奶油黄』。

配色板（环保 · 闲置循环）：
  主色   #54C7A5  (薄荷绿)        按钮/选中/强调
  主渐变 #6FD6B6 (浅薄荷)        primary 渐变亮端
  深主   #2C9B80  (深薄荷)     文字/图标强调
  背景   #F7FCF9  (薄荷白)     页面背景
  浅底   #E7F6F0   浅薄荷       卡片内浅色块
  边框   #B5E5D6 / #BDE7DA     薄荷描边
  辅助色 #FFD978  (奶油黄)     辅助高亮/礼盒
  浅奶油 #FFF6DD                 奶油底
  深文字 #2B4A42   深青
用法：python retheme.py （在仓库根执行）
"""
import glob
import re

# (旧色, 新色) —— 只映射当前版本实际出现的绿色家族
MAP = {
    "#2FA84F": "#54C7A5",  # 主绿 -> 薄荷
    "#58C259": "#6FD6B5",  # 渐变亮端
    "#58C266": "#6FD6B5",
    "#2E8B57": "#2C9B80",  # 深绿 accent
    "#4CAF50": "#54C7A5",
    "#1F7A3B": "#248F74",  # 深标题
    "#5E8A5C": "#4E8F7C",

    "#243126": "#21473C",
    "#2B2320": "#21473C",
    "#F2F8F0": "#F7FCF9",  # 背景
    "#E9F5E4": "#E7F6F0",
    "#EAF5E6": "#E7F6F0",
    "#EAF5E5": "#E7F6F0",
    "#E8F6E7": "#E7F6F0",
    "#E8F6E2": "#E7F6F0",
    "#EAF6EC": "#DCEFE8",
    "#EFF7EB": "#EAF8F3",
    "#F2F7EF": "#F0FBF7",
    "#F4F8F1": "#F0FBF7",

    "#DFF2D8": "#D8F3E9",
    "#E4F4DF": "#E0F3EA",
    "#B9E4AC": "#BFEADC",
    "#BFE4B3": "#BFEADD",
    "#9CCB86": "#FFD978",  # 渐变里当奶油黄辅助
    "#9CCB85": "#F2D48F",
    "#A8DC9F": "#C9EBDE",
    "#BFE6B0": "#B5E5D6",
    "#C9E8BB": "#BDE7DA",
    "#CBD9C2": "#C9EADC",
    "#E4F2FF": "#DCEFF6",  # 交换信息浅蓝 -> 浅薄荷
    "#1E88E5": "#2C9B80",  # 交换蓝 -> 薄荷

    "#3D2C22": "#2B4A42",
    "#6B5F54": "#46635A",
    "#8B7F75": "#5F7A70",
    "#8B7E71": "#5F7A70",
    "#C0B5AA": "#A8BFB6",
    "#C9BEB2": "#A9C0B6",
    "#B7A695": "#96ADA4",
    "#5A6C5B": "#3F6359",
    "#6E7A6A": "#3F6357",
    "#9CCB88": "#FFD978",
}

def repl_all(paths):
    for p in paths:
        s = open(p).read()
        orig = s
        for old, new in MAP.items():
            if old and old in s:
                s = s.replace(old, new)
        if s != orig:
            open(p, "w").write(s)
            print(f"rewrote {p}")

if __name__ == "__main__":
    import sys
    files = glob.glob("miniprogram/**/*.wxss", recursive=True) + ["miniprogram/app.wxss"]
    if len(sys.argv) > 1 and sys.argv[1] == "--dry":
        cnt = 0
        for p in files:
            t = open(p).read()
            for old in MAP:
                if old and old.lower() in t.lower():
                    cnt += t.lower().count(old.lower())
        print("公开发生的替换值数:", cnt)
    else:
        repl_all(files)
        print("done")