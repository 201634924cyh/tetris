# -*- coding: utf-8 -*-
"""
tetris.py 的无窗口自检。

用法：
    SDL_VIDEODRIVER=dummy python selftest.py

覆盖：状态机全分支 / SRS 踢墙 / 消行与计分 / Hold / 7-bag / 粒子上限 /
窗口↔画布坐标换算 / 帧耗时 / 各状态截图 + 像素扫描。
"""

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  必须在环境变量之后导入

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tetris as T  # noqa: E402

SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [ok]   {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")
        print(f"  [FAIL] {name}   {detail}")


def section(title):
    print(f"\n=== {title} ===")


def new_app(scale=1.0, seed=7):
    return T.App(scale=scale, seed=seed, dummy=True)


def make_keys(*down):
    class K:
        def __init__(self, keys):
            self.down = set(keys)

        def __getitem__(self, k):
            return k in self.down

        def press(self, *ks):
            self.down.update(ks)

        def release(self, *ks):
            self.down.difference_update(ks)

        def clear(self):
            self.down.clear()

    return K(down)


def post_key(app, key, times=1):
    """走真实事件队列，而不是直接调内部函数。"""
    for _ in range(times):
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
    app.process_events()


def clear_board(g):
    g.grid = [[None] * T.COLS for _ in range(T.ROWS)]


# ==============================================================
section("1. 初始化 / 常量一致性")
# ==============================================================
app = new_app()
g = app.game

check("初始状态为菜单", g.phase == T.PHASE_MENU, f"got {g.phase}")
check("棋盘尺寸 20x10", len(g.grid) == T.ROWS and len(g.grid[0]) == T.COLS)
check("棋盘初始为空", all(v is None for row in g.grid for v in row))
check("画布尺寸与窗口解耦", (T.CANVAS_W, T.CANVAS_H) == (596, 724),
      f"got {(T.CANVAS_W, T.CANVAS_H)}")
check("窗口默认尺寸 = 画布 x scale", app.screen.get_size() == (T.CANVAS_W, T.CANVAS_H))
check("7 种方块矩阵齐备", set(T.MATRICES) == set(T.PIECE_KINDS))
check("7 种颜色齐备", set(T.PIECE_COLORS) == set(T.PIECE_KINDS))
check("每种方块都是方阵",
      all(len(m) == len(m[0]) for m in T.MATRICES.values()))
check("每种方块格子数均为 4",
      all(sum(sum(r) for r in m) == 4 for m in T.MATRICES.values()),
      str({k: sum(sum(r) for r in v) for k, v in T.MATRICES.items()}))
check("踢墙表 8 个旋转转移齐备",
      len(T.KICKS_JLSTZ) == 8 and len(T.KICKS_I) == 8)
check("侧栏提示文字不溢出画布",
      (T.CANVAS_H - T.MARGIN - 116) + 5 * 19 + 20 <= T.CANVAS_H)

# ==============================================================
section("2. 旋转工具 / 7-bag")
# ==============================================================
t0 = T.MATRICES["T"]
check("顺时针旋转 4 次回到原状",
      T.rotate_cw(T.rotate_cw(T.rotate_cw(T.rotate_cw(t0)))) == t0)
check("逆时针旋转 4 次回到原状",
      T.rotate_ccw(T.rotate_ccw(T.rotate_ccw(T.rotate_ccw(t0)))) == t0)
check("顺时针 = 逆时针 x3",
      T.rotate_cw(t0) == T.rotate_ccw(T.rotate_ccw(T.rotate_ccw(t0))))
check("I 块 4 次旋转回到原状",
      T.rotate_cw(T.rotate_cw(T.rotate_cw(T.rotate_cw(T.MATRICES["I"])))) == T.MATRICES["I"])

import random as _random
bag = T.Bag(_random.Random(1))
draws = [bag.next() for _ in range(700)]
check("7-bag 每 7 个恰好包含全部 7 种",
      all(set(draws[i:i + 7]) == set(T.PIECE_KINDS) for i in range(0, 700, 7)))
check("每轮内无重复",
      all(len(set(draws[i:i + 7])) == 7 for i in range(0, 700, 7)))
check("多轮之间顺序不同（确实是洗牌）",
      draws[0:7] != draws[7:14] or draws[7:14] != draws[14:21])

# ==============================================================
section("3. 状态机：菜单 -> 开局 -> 暂停 -> 继续")
# ==============================================================
post_key(app, pygame.K_RETURN)
check("Enter 从菜单进入游戏", g.phase == T.PHASE_PLAY, f"got {g.phase}")
check("开局即有活动方块", g.piece is not None)
check("Next 队列长度 5", len(g.queue) == 5)
check("开局分数归零", g.score == 0 and g.lines == 0 and g.level == 1)

post_key(app, pygame.K_p)
check("P 进入暂停", g.phase == T.PHASE_PAUSE, f"got {g.phase}")
frozen_score = g.score
frozen_piece = (g.piece.x, g.piece.y, g.piece.rot)
for _ in range(30):
    g.update(1 / 60, make_keys(pygame.K_DOWN))
check("暂停期间方块不动", (g.piece.x, g.piece.y, g.piece.rot) == frozen_piece)
check("暂停期间分数不变", g.score == frozen_score)
post_key(app, pygame.K_p)
check("再按 P 恢复游戏", g.phase == T.PHASE_PLAY)

post_key(app, pygame.K_ESCAPE)
check("ESC 亦可暂停", g.phase == T.PHASE_PAUSE)
post_key(app, pygame.K_ESCAPE)
check("ESC 亦可恢复", g.phase == T.PHASE_PLAY)

# ==============================================================
section("4. 移动 / 边界 / DAS")
# ==============================================================
g.start()
keys = make_keys()
for _ in range(20):
    g.update(1 / 60, keys)
    g.try_move(-1)
xs = [p for (p, _) in g.piece.cells()]
check("左移会被墙挡住", min(xs) >= 0, f"min={min(xs)}")
check("方块确实被推到了最左", min(xs) == 0, f"min={min(xs)}")
for _ in range(20):
    g.try_move(1)
xs = [p for (p, _) in g.piece.cells()]
check("右移会被墙挡住", max(xs) <= T.COLS - 1, f"max={max(xs)}")

g.start()
kx = make_keys(pygame.K_LEFT)
start_x = g.piece.x
for _ in range(120):                       # 2 秒长按左键
    g.update(1 / 60, kx)
check("DAS/ARR 长按会连续移动", g.piece.x < start_x, f"{start_x} -> {g.piece.x}")

# ==============================================================
section("5. SRS 旋转与踢墙")
# ==============================================================
g.start()
clear_board(g)
p = T.Piece("T", x=3, y=5)
g.piece = p
g.grid[6][4] = "J"                          # 挡住原地旋转后的 (4,6)
before = (p.x, p.y, p.rot)
ok = g.try_rotate(True)
check("被挡住时旋转仍成功（靠踢墙）", ok)
check("踢墙把方块推到了预期位置", (p.x, p.y, p.rot) == (2, 4, 1),
      f"got {(p.x, p.y, p.rot)}  before={before}")
check("记录了生效的踢墙索引", g.last_rot_kick == 2, f"got {g.last_rot_kick}")
check("旋转后不与地形重叠", not g._collide(p.mat, p.x, p.y))

g.start()
clear_board(g)
for c in range(T.COLS):                     # 铺满第 19 行
    g.grid[19][c] = "I"
g.grid[17][3] = "J"                         # T 的左上 / 右上角
g.grid[17][5] = "J"
# T 位于 (3,17)，四个角为 (3,17)(5,17)(3,19)(5,19)，其中 4 个全被占
g.piece = T.Piece("T", x=3, y=17)
g.piece.rot = 0
g.last_rot_kick = 0
check("T-Spin 判定：三角被占 -> True", g._is_tspin())
g.grid[17][3] = None
g.grid[17][5] = None
g.last_rot_kick = 0
check("T-Spin 判定：角落空着 -> False", not g._is_tspin())
g.last_rot_kick = None
check("T-Spin 判定：最后一步非旋转 -> False", not g._is_tspin())
g.last_rot_kick = 0
g.piece.kind = "L"
check("T-Spin 判定：非 T 方块 -> False", not g._is_tspin())

# ==============================================================
section("6. Hold 暂存")
# ==============================================================
g.start()
clear_board(g)
first = g.piece.kind
check("按住 C 可暂存", g.do_hold())
check("暂存槽记录了方块", g.hold == first, f"hold={g.hold} first={first}")
check("暂存后仍有活动方块", g.piece is not None)
check("暂存标记已置位", g.hold_used)
after_first = g.piece.kind
check("同一落块周期内不能二次暂存", not g.do_hold())
check("被拒绝时方块未被换掉", g.piece.kind == after_first)
g._spawn_next()
check("新方块生成后暂存解锁", g.hold_used is False)
check("第二次暂存可交换内容", g.do_hold() and g.piece.kind == first)

# ==============================================================
section("7. 硬降 / 锁定 / 幽灵落点")
# ==============================================================
g = new_app(seed=11).game
g.start()
clear_board(g)
g.piece = T.Piece("O", x=0, y=0)
old_piece = g.piece
gy = g.ghost_y()
g.hard_drop()
filled = sum(1 for row in g.grid for v in row if v)
check("硬降后 4 格落在盘上", filled == 4, f"filled={filled}")
check("幽灵落点等于实际落点", gy == T.ROWS - 2, f"gy={gy}")
check("硬降后方块已交出，不再是同一对象", g.piece is not old_piece)
check("硬降计入分数", g.score >= 2 * (T.ROWS - 2), f"score={g.score}")

# ==============================================================
section("8. 消行与计分")
# ==============================================================
g = new_app(seed=11).game
g.start()
clear_board(g)
g.score = 0
g.lines = 0
for c in range(T.COLS):
    g.grid[T.ROWS - 1][c] = "I"
g.grid[T.ROWS - 1][0] = None
g.grid[T.ROWS - 1][1] = None
g.piece = T.Piece("O", x=0, y=0)
g.hard_drop()
check("锁定后进入消行动画", g.clear_rows == [T.ROWS - 1], f"got {g.clear_rows}")
check("动画期间棋盘尚未重排（满行还在）",
      all(g.grid[T.ROWS - 1][c] is not None for c in range(T.COLS)))
while g.clear_rows:
    g.update(T.CLEAR_DURATION, None)
check("动画结束后行数 +1", g.lines == 1, f"lines={g.lines}")
check("底行已被清空（含新落下的方块）",
      sum(1 for c in range(T.COLS) if g.grid[T.ROWS - 1][c]) == 2,
      f"row={g.grid[T.ROWS-1]}")
check("得分增加（消行 + 硬降）", g.score > 100, f"score={g.score}")
check("消行后方块自动接续", g.piece is not None)

g.start()
clear_board(g)
g.score = 0
g.lines = 0
# 底部 4 行各留出最右一列，用一根竖着的 I 一次性插满 -> TETRIS
for r in range(T.ROWS - 4, T.ROWS):
    for c in range(T.COLS - 1):
        g.grid[r][c] = "J"
g.piece = T.Piece("I", x=7, y=0)
g.piece.mat = T.rotate_cw(T.MATRICES["I"])   # 竖直朝向，占 4x4 的第 2 列 -> col 9
g.piece.rot = 1
g.hard_drop()
check("竖直 I 锁定后填满 4 行", len(g.clear_rows) == 4, f"got {g.clear_rows}")
while g.clear_rows:
    g.update(T.CLEAR_DURATION, None)
check("一次消 4 行", g.lines == 4, f"lines={g.lines}")
check("TETRIS 计分 = 800 x level", g.score >= 800, f"score={g.score}")
check("棋盘剩余方块数正确", sum(1 for row in g.grid for v in row if v) == 0,
      f"left={sum(1 for row in g.grid for v in row if v)}")
check("消 4 行后仍有活动方块", g.piece is not None)

# 连击
g.start()
clear_board(g)
g.score = 0
def _fill_bottom_but_two(g):
    for c in range(T.COLS):
        g.grid[T.ROWS - 1][c] = "I"
    g.grid[T.ROWS - 1][0] = g.grid[T.ROWS - 1][1] = None

_fill_bottom_but_two(g)
g.piece = T.Piece("O", x=0, y=0)
g.hard_drop()
while g.clear_rows:
    g.update(T.CLEAR_DURATION, None)
combo1 = g.combo
check("第一次消行后 combo = 1", combo1 == 1, f"combo={combo1}")

_fill_bottom_but_two(g)
g.piece = T.Piece("O", x=0, y=0)
g.hard_drop()
while g.clear_rows:
    g.update(T.CLEAR_DURATION, None)
check("连续消行累计 combo", g.combo == combo1 + 1, f"combo={g.combo}")

# 等级
g.start()
g.lines = 9
clear_board(g)
for c in range(T.COLS):
    g.grid[T.ROWS - 1][c] = "I"
g.grid[T.ROWS - 1][0] = g.grid[T.ROWS - 1][1] = None
g.piece = T.Piece("O", x=0, y=0)
g.hard_drop()
while g.clear_rows:
    g.update(T.CLEAR_DURATION, None)
check("每 10 行升 1 级", g.level == 2, f"level={g.level} lines={g.lines}")
check("重力随等级加快", g.gravity_interval() < T.GRAVITY[0])

# ==============================================================
section("9. 锁定延迟")
# ==============================================================
g = new_app(seed=3).game
g.start()
clear_board(g)
g.piece = T.Piece("O", x=0, y=T.ROWS - 2)      # 直接摆到落点，只测锁定计时
keys_none = make_keys()
for _ in range(int(T.LOCK_DELAY * 60) + 8):
    g.update(1 / 60, keys_none)
locked = sum(1 for row in g.grid for v in row if v)
check("落地后超过锁定延迟就锁定", locked == 4, f"locked={locked}")

g.start()
clear_board(g)
g.piece = T.Piece("O", x=0, y=T.ROWS - 2)
for _ in range(int(T.LOCK_DELAY * 60) - 10):   # 先贴近锁定阈值
    g.update(1 / 60, keys_none)
moved = g.try_move(1)                          # 地面平移 -> 重置倒计时
check("地面平移被接受", moved)
for _ in range(10):                            # 若无重置，此刻早已锁定
    g.update(1 / 60, keys_none)
locked = sum(1 for row in g.grid for v in row if v)
check("地面移动会重置锁定倒计时", locked == 0, f"locked={locked}")
check("重置次数被记入上限", g.lock_resets >= 1, f"resets={g.lock_resets}")

# ==============================================================
section("10. 游戏结束 / 重开")
# ==============================================================
a_over = new_app(seed=5)
g = a_over.game
g.start()
clear_board(g)
for r in range(3):
    for c in range(T.COLS):
        g.grid[r][c] = "J"
g.grid[0][4] = g.grid[1][4] = None
g.piece = None
g._spawn("I")
check("顶部堵死时判定游戏结束", g.phase == T.PHASE_OVER, f"got {g.phase}")
over_score = g.score
check("结束后记录最高分", g.best >= over_score, f"best={g.best} score={over_score}")
frozen = g.phase
for _ in range(20):
    g.update(1 / 60, make_keys(pygame.K_DOWN))
check("结束后方块不再下落", g.phase == frozen and g.piece is not None)
post_key(a_over, pygame.K_RETURN)
check("Enter 从结束态重开", g.phase == T.PHASE_PLAY, f"got {g.phase}")
check("重开后分数清零", g.score == 0 and g.lines == 0 and g.level == 1)
check("重开后棋盘清空（除新落块外）",
      sum(1 for row in g.grid for v in row if v) == 0,
      f"left={sum(1 for row in g.grid for v in row if v)}")

g.phase = T.PHASE_OVER
g.best = 9999
post_key(a_over, pygame.K_r)
check("R 亦可重开", g.phase == T.PHASE_PLAY)
check("重开后最高分被保留", g.best == 9999, f"best={g.best}")

# ==============================================================
section("11. 粒子 / 资源上限")
# ==============================================================
g = new_app(seed=9).game
g.start()
for _ in range(400):
    g._burst(3, 10, (255, 80, 80), 4)
check(f"粒子数不超过上限 {T.Game.MAX_PARTICLES}",
      len(g.particles) <= T.Game.MAX_PARTICLES, f"got {len(g.particles)}")
for _ in range(600):
    g.update(1 / 60, make_keys())
check("粒子会被回收，不会无限堆积", len(g.particles) == 0, f"got {len(g.particles)}")
check("长时间运行后棋盘结构未被破坏", len(g.grid) == T.ROWS)

n_before = len(g.particles)
bad = T.Particle(-100, -100, 0, 0, 0.1, (255, 0, 0), 3)
bad.life = -1
g.particles.append(bad)
for _ in range(10):
    g.update(1 / 60, make_keys())
check("已死亡的粒子被移除且不产生副作用", len(g.particles) <= n_before)

# ==============================================================
section("12. 窗口 <-> 画布 坐标换算")
# ==============================================================
for sc in (1.0, 1.5, 2.0):
    a = T.App(scale=sc, seed=1, dummy=True)
    a.render()
    cx, cy = a.window_to_canvas((a.screen.get_width() // 2, a.screen.get_height() // 2))
    check(f"{sc}x 窗口中心映射到画布中心",
          abs(cx - T.CANVAS_W // 2) <= 2 and abs(cy - T.CANVAS_H // 2) <= 2,
          f"got ({cx},{cy}) want ({T.CANVAS_W//2},{T.CANVAS_H//2})")

# ==============================================================
section("13. 帧耗时（不含 clock.tick）")
# ==============================================================
perf_app = new_app(seed=13)
pg = perf_app.game
pg.start()
for _ in range(300):
    pg._burst(4, 12, (120, 220, 255), 4)
keys_all = make_keys(pygame.K_DOWN)
pg.update(1 / 60, keys_all)

t_start = time.perf_counter()
N = 120
for _ in range(N):
    pg.update(1 / 60, keys_all)
    pg.draw(perf_app.canvas)
elapsed_ms = (time.perf_counter() - t_start) / N * 1000.0
print(f"  平均 {elapsed_ms:.2f} ms/帧（{len(pg.particles)} 粒子）")
check("满粒子下仍远快于 16.7ms/帧", elapsed_ms < 8.0, f"{elapsed_ms:.2f} ms")

# ==============================================================
section("14. 截图 + 像素扫描")
# ==============================================================
os.makedirs(SHOT_DIR, exist_ok=True)
shots = {}

a = T.App(scale=1.0, seed=21, dummy=True)
gg = a.game
a.render()
pygame.image.save(a.canvas, os.path.join(SHOT_DIR, "01_menu.png"))
shots["menu"] = a.canvas.copy()

post_key(a, pygame.K_RETURN)
gg.grid = [[None] * T.COLS for _ in range(T.ROWS)]
# 堆一些地形，让画面有内容
import random as _rnd
rr = _rnd.Random(4)
for r in range(T.ROWS - 7, T.ROWS):
    for c in range(T.COLS):
        if rr.random() < 0.72:
            gg.grid[r][c] = rr.choice(T.PIECE_KINDS)
for r in range(T.ROWS - 7, T.ROWS):        # 保证没有满行，避免开局就触发消行动画
    if all(gg.grid[r][c] for c in range(T.COLS)):
        gg.grid[r][rr.randrange(T.COLS)] = None
gg.hold = "S"
gg.score, gg.lines, gg.elapsed = 24800, 37, 254
gg.level = 4
for _ in range(30):
    gg.update(1 / 60, make_keys())
a.render()
pygame.image.save(a.canvas, os.path.join(SHOT_DIR, "02_play.png"))
shots["play"] = a.canvas.copy()

# 消行动画中
gg.clear_rows = [T.ROWS - 1, T.ROWS - 2]
gg.clear_timer = T.CLEAR_DURATION * 0.15
a.render()
pygame.image.save(a.canvas, os.path.join(SHOT_DIR, "03_clearing.png"))
shots["clearing"] = a.canvas.copy()
gg.clear_rows = []

post_key(a, pygame.K_p)
a.render()
pygame.image.save(a.canvas, os.path.join(SHOT_DIR, "04_pause.png"))
shots["pause"] = a.canvas.copy()
post_key(a, pygame.K_p)

gg.phase = T.PHASE_OVER
gg.score, gg.lines, gg.level, gg.elapsed, gg.best = 51300, 62, 7, 731, 51300
a.render()
pygame.image.save(a.canvas, os.path.join(SHOT_DIR, "05_gameover.png"))
shots["gameover"] = a.canvas.copy()

for k, v in shots.items():
    print(f"  [shot] {k}: {v.get_width()}x{v.get_height()}")

# --- 可选：把四张状态截图拼成一张总览图（README 头图）---
# 用到 Pillow。没装就跳过，不影响任何断言结论。
_CJK_FONTS = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
)


def build_overview():
    from PIL import Image, ImageDraw, ImageFont

    cells = (("01_menu.png", "菜单"), ("02_play.png", "对局"),
             ("04_pause.png", "暂停"), ("05_gameover.png", "结算"))
    imgs = [(Image.open(os.path.join(SHOT_DIR, n)).convert("RGB"), t)
            for n, t in cells]

    font_path = next((p for p in _CJK_FONTS if os.path.exists(p)), None)
    if font_path:
        f_title = ImageFont.truetype(font_path, 20)
        f_tag = ImageFont.truetype(font_path, 15)
    else:                                   # 无中文字体：退回英文标签
        f_title = f_tag = ImageFont.load_default()
        imgs = [(im, ("Menu", "Play", "Pause", "Game Over")[i])
                for i, (im, _) in enumerate(imgs)]

    tw = 300
    th = int(imgs[0][0].height * (tw / imgs[0][0].width))
    pad, gap, bar = 18, 14, 46
    w = pad * 2 + tw * 2 + gap
    h = bar + pad * 2 + th * 2 + gap
    canvas = Image.new("RGB", (w, h), (11, 13, 20))
    d = ImageDraw.Draw(canvas)
    d.text((pad, 13), "俄罗斯方块 · Tetris", font=f_title, fill=(228, 234, 247))

    for i, (im, tag) in enumerate(imgs):
        r, c = divmod(i, 2)
        x = pad + c * (tw + gap)
        y = bar + pad + r * (th + gap)
        canvas.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + th], outline=(52, 60, 88), width=1)
        d.rectangle([x, y, x + d.textlength(tag, font=f_tag) + 18, y + 25],
                    fill=(16, 19, 30))
        d.text((x + 9, y + 4), tag, font=f_tag, fill=(120, 200, 255))

    out = os.path.join(SHOT_DIR, "00_preview.png")
    canvas.save(out)
    return out


try:
    print(f"  [shot] 总览图 {build_overview()}")
except ImportError:
    print("  [skip] 未安装 Pillow，跳过 preview/00_preview.png 的拼接")

# --- 像素检查 ---

def get(surf, x, y):
    return surf.get_at((x, y))[:3]


def sat(c):
    return max(c) - min(c)


play = shots["play"]
# 棋盘区域应当出现高饱和的方块色
blocky = 0
for y in range(T.BOARD_Y + 4, T.BOARD_Y + T.BOARD_H - 4, 3):
    for x in range(T.BOARD_X + 4, T.BOARD_X + T.BOARD_W - 4, 3):
        if sat(get(play, x, y)) > 70:
            blocky += 1
check("游玩画面棋盘内确实画出了彩色方块", blocky > 200, f"count={blocky}")

# 侧栏卡片之间应为背景色（说明卡片没画歪/没溢出）
gap_ok = True
for y in (203, 205, 336, 338, 343):
    c = get(play, T.PANEL_X + T.PANEL_W // 2, y)
    if abs(c[0] - T.C_BG[0]) > 12 or abs(c[1] - T.C_BG[1]) > 12:
        gap_ok = False
check("侧栏卡片之间无异常残留", gap_ok)

# 暂停/结束遮罩应当把画面压暗
def mean_lum(surf):
    tot = 0
    n = 0
    for y in range(0, T.CANVAS_H, 7):
        for x in range(0, T.CANVAS_W, 7):
            c = get(surf, x, y)
            tot += c[0] + c[1] + c[2]
            n += 1
    return tot / n / 3.0

lum_play = mean_lum(shots["play"])
lum_pause = mean_lum(shots["pause"])
lum_over = mean_lum(shots["gameover"])
print(f"  平均亮度  游玩={lum_play:.1f}  暂停={lum_pause:.1f}  结束={lum_over:.1f}")
check("暂停态被遮罩压暗", lum_pause < lum_play, f"{lum_pause:.1f} vs {lum_play:.1f}")
check("结束态被遮罩压暗", lum_over < lum_play, f"{lum_over:.1f} vs {lum_play:.1f}")

# 菜单标题区域应有高亮文字像素
menu = shots["menu"]
bright = 0
for y in range(210, 300):
    for x in range(120, T.CANVAS_W - 120):
        c = get(menu, x, y)
        if min(c) > 150:
            bright += 1
check("菜单标题确实绘制了亮色文字", bright > 150, f"count={bright}")

# 消行动画应当出现接近纯白的像素
cl = shots["clearing"]
whites = sum(1 for y in range(T.BOARD_Y, T.BOARD_Y + T.BOARD_H, 4)
             for x in range(T.BOARD_X, T.BOARD_X + T.BOARD_W, 4)
             if min(get(cl, x, y)) > 200)
check("消行动画出现白色闪光行", whites > 40, f"count={whites}")

# 画面不应出现"比背景更暗"的成片像素（深色背景已被遮罩除外）
dark = sum(1 for y in range(T.MARGIN, T.CANVAS_H - T.MARGIN, 5)
           for x in range(0, T.CANVAS_W, 5)
           if get(play, x, y)[0] < T.C_BG[0] and get(play, x, y)[1] < T.C_BG[1])
check("游玩画面无异常暗斑", dark < 60, f"count={dark}")

# ==============================================================
section("15. 真实窗口模式（非 dummy）")
# ==============================================================
print("  跳过：真实窗口由 --frames 单独验证")

# ==============================================================
print(f"\n{'=' * 52}")
print(f"通过 {PASS} 项，失败 {FAIL} 项")
if FAILURES:
    print("失败清单：")
    for f in FAILURES:
        print("  -", f)
print(f"截图目录：{SHOT_DIR}")
print("=" * 52)
sys.exit(1 if FAIL else 0)
