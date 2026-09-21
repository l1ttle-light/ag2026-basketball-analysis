#!/usr/bin/env python3
"""Generate 16:9 visual cards for the Bilibili rough cut."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG, PANEL = "#0B0D12", "#151923"
RED, BLUE, GOLD = "#EF3340", "#38BDF8", "#F6C453"
WHITE, MUTED, GREEN = "#F8FAFC", "#AAB2C0", "#3DDC97"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT if bold else FONT_LIGHT, size)


def centered(draw, text, y, face, fill=WHITE):
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((W - box[2] + box[0]) / 2, y), text, font=face, fill=fill)


def base(kicker, page):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 70, 1840, 1010), 32, fill=PANEL)
    draw.rectangle((80, 70, 104, 1010), fill=RED)
    draw.text((145, 110), kicker, font=font(34), fill=RED)
    draw.text((1665, 110), f"{page:02d}", font=font(34), fill=MUTED)
    draw.text((145, 950), "2026 爱知·名古屋亚运会男篮数据分析", font=font(25, False), fill=MUTED)
    return image, draw


def title():
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 22), fill=RED)
    draw.text((120, 120), "亚运会男篮数据分析", font=font(38), fill=RED)
    draw.text((120, 280), "场均 90.5 分", font=font(122), fill=WHITE)
    draw.text((120, 445), "却无缘奖牌", font=font(122), fill=GOLD)
    draw.rounded_rectangle((116, 660, 1804, 850), 28, outline="#3A4352", width=3)
    centered(draw, "中国男篮是“超级原始人”？", 710, font(70))
    draw.text((120, 940), "官方逐事件数据｜快攻、阵地战为规则估算", font=font(25, False), fill=MUTED)
    image.save(OUT / "00_片头标题.png")


def thesis():
    image, draw = base("结论先行", 1)
    draw.text((145, 205), "不是单纯的进攻差，也不是单纯的防守差", font=font(64), fill=WHITE)
    draw.text((145, 315), "而是强项无法在高强度比赛里形成闭环", font=font(64), fill=GOLD)
    for index, (head, body, color) in enumerate([
        ("传统能力", "尺寸、对抗、篮板、转换", GREEN),
        ("现代短板", "空间、三分、连续决策、轮转", RED),
    ]):
        x = 145 + index * 825
        draw.rounded_rectangle((x, 500, x + 730, 800), 26, fill="#0E1118", outline=color, width=4)
        draw.text((x + 50, 550), head, font=font(52), fill=color)
        draw.text((x + 50, 660), body, font=font(38, False), fill=WHITE)
    image.save(OUT / "01_结论先行.png")


def overall():
    image, draw = base("四队整体表现", 2)
    draw.text((145, 205), "场均得分很高，不等于高强度比赛进攻可靠", font=font(62), fill=WHITE)
    teams = [("中国", 90.5, RED), ("韩国", 90.3, BLUE), ("日本", 84.3, GOLD), ("伊朗", 69.2, GREEN)]
    for index, (name, value, color) in enumerate(teams):
        y = 390 + index * 125
        draw.text((155, y), name, font=font(44), fill=WHITE)
        draw.rounded_rectangle((320, y + 7, 320 + int(value * 12.5), y + 65), 16, fill=color)
        draw.text((1490, y - 2), f"{value:.1f} 分", font=font(46), fill=color)
    draw.text((145, 870), "中国 6 场 4 胜 2 负｜最后两场均负", font=font(40), fill=MUTED)
    image.save(OUT / "02_四队场均得分.png")


def turning_point():
    image, draw = base("分水岭", 3)
    draw.text((145, 205), "前四场 vs 最后两场", font=font(76), fill=WHITE)
    for index, (tag, attack, defense, color) in enumerate([
        ("前四场", "进攻效率 126.9", "防守效率 83.0", GREEN),
        ("最后两场", "进攻效率 100.9", "防守效率 120.8", RED),
    ]):
        x = 145 + index * 825
        draw.rounded_rectangle((x, 390, x + 735, 760), 26, fill="#0E1118", outline=color, width=4)
        draw.text((x + 48, 445), tag, font=font(54), fill=color)
        draw.text((x + 48, 560), attack, font=font(48), fill=WHITE)
        draw.text((x + 48, 650), defense, font=font(48), fill=WHITE)
    draw.text((145, 850), "样本强度变化后，优势没有被稳定兑现", font=font(48), fill=GOLD)
    image.save(OUT / "03_前四场与最后两场.png")


def fastbreak():
    image, draw = base("为什么快攻突然消失", 4)
    draw.text((145, 205), "快攻不是一个孤立技能，而是一条攻防因果链", font=font(62), fill=WHITE)
    x = 150
    for index, (label, color) in enumerate([("防住", BLUE), ("收下篮板", GREEN), ("第一传", GOLD), ("提前终结", RED)]):
        draw.rounded_rectangle((x, 455, x + 300, 610), 24, fill="#0E1118", outline=color, width=4)
        box = draw.textbbox((0, 0), label, font=font(42))
        draw.text((x + 150 - (box[2] - box[0]) / 2, 505), label, font=font(42), fill=color)
        if index < 3:
            draw.line((x + 315, 532, x + 405, 532), fill=MUTED, width=8)
            draw.polygon([(x + 405, 512), (x + 440, 532), (x + 405, 552)], fill=MUTED)
        x += 430
    draw.text((145, 770), "日本半决赛：中国估算快攻 6 分，占总得分 7.8%", font=font(48), fill=RED)
    image.save(OUT / "04_快攻因果链.png")


def key_games():
    image, draw = base("两场关键失利", 5)
    games = [
        ("半决赛", "中国 77—97 日本", "防守失效｜对手三分 40%｜仅 3 次失误", RED),
        ("三四名", "中国 70—79 伊朗", "阵地进攻 92.6｜对手三分 15/33", GOLD),
    ]
    for index, (stage, score, reason, color) in enumerate(games):
        y = 225 + index * 335
        draw.text((145, y), stage, font=font(42), fill=color)
        draw.text((145, y + 70), score, font=font(76), fill=WHITE)
        draw.text((145, y + 180), reason, font=font(42, False), fill=MUTED)
        if index == 0:
            draw.line((145, y + 285, 1750, y + 285), fill="#343B49", width=3)
    image.save(OUT / "05_两场关键失利.png")


def modern():
    image, draw = base("原始篮球 vs 现代篮球", 6)
    columns = [
        ("原始篮球的强", ["尺寸与力量", "篮板与冲击", "单点终结", "简单直接"], GREEN),
        ("现代篮球的要求", ["空间与出手价值", "连续决策", "五人联动", "攻防闭环"], BLUE),
    ]
    for index, (head, lines, color) in enumerate(columns):
        x = 145 + index * 825
        draw.text((x, 210), head, font=font(58), fill=color)
        draw.rounded_rectangle((x, 320, x + 735, 820), 26, fill="#0E1118", outline=color, width=4)
        for row, line in enumerate(lines):
            draw.ellipse((x + 55, 397 + row * 95, x + 75, 417 + row * 95), fill=color)
            draw.text((x + 105, 372 + row * 95), line, font=font(44), fill=WHITE)
    draw.text((145, 865), "中国队的问题：拥有零件，但系统稳定性不足", font=font(48), fill=GOLD)
    image.save(OUT / "06_原始与现代.png")


def ending():
    image, draw = base("最终判断", 7)
    centered(draw, "“超级原始人”不是结论", 250, font(76))
    centered(draw, "而是对转型阶段的描述", 370, font(76), GOLD)
    draw.rounded_rectangle((300, 590, 1620, 760), 24, fill="#0E1118", outline=RED, width=4)
    centered(draw, "真正的升级：让传统优势进入现代体系", 642, font(52))
    centered(draw, "完整数据、代码与口径见视频简介", 860, font(34, False), MUTED)
    image.save(OUT / "07_结尾判断.png")


if __name__ == "__main__":
    for make in (title, thesis, overall, turning_point, fastbreak, key_games, modern, ending):
        make()
    print(f"Generated 8 assets in {OUT}")
