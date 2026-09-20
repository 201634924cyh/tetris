# -*- coding: utf-8 -*-
"""
俄罗斯方块 (Tetris) —— pygame 单文件实现

特性
----
* 标准 SRS 旋转系统（含踢墙表），T-Spin 判定
* 7-bag 随机器（保证每 7 个方块内 7 种各出现一次）
* Hold 暂存、Next 三格预览、幽灵落点
* 锁定延迟 (lock delay) + 移动重置，DAS/ARR 自动重复
* 消行动画 + 粒子、程序化合成音效（无需任何外部素材）
* 固定逻辑画布 + 窗口自由缩放，任意分辨率不失真

运行
----
    python tetris.py                # 正常开始
    python tetris.py --frames 120   # 跑 120 帧后自动退出（自检用）
    python tetris.py --seed 42      # 固定随机种子（复现用）
    python tetris.py --version      # 打印版本号
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys

import pygame

__version__ = "1.1"

# ==============================================================
# 1. 基础配置
# ==============================================================

CELL = 34
COLS, ROWS = 10, 20
MARGIN = 22

BOARD_X = MARGIN
BOARD_Y = MARGIN
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL

PANEL_X = BOARD_X + BOARD_W + 16
PANEL_W = 196
CANVAS_W = PANEL_X + PANEL_W + MARGIN
CANVAS_H = MARGIN * 2 + BOARD_H          # 596 x 724

FPS = 60
DEFAULT_SCALE = 1.0

# 手感参数（秒）
DAS = 0.150            # 长按左右后开始连发前的延迟
ARR = 0.045            # 连发间隔
SOFT_DROP_INTERVAL = 0.040
LOCK_DELAY = 0.500     # 落地后还能操作多久才锁定
MAX_LOCK_RESETS = 15
CLEAR_DURATION = 0.30  # 消行动画时长

# 每级重力间隔（秒/格）
GRAVITY = [0.80, 0.72, 0.63, 0.55, 0.47, 0.38, 0.30, 0.22,
           0.16, 0.12, 0.09, 0.07, 0.055, 0.045, 0.038, 0.032,
           0.027, 0.023, 0.020, 0.017]

LINES_PER_LEVEL = 10

PIECE_KINDS = ("I", "O", "T", "S", "Z", "J", "L")

# ==============================================================
# 2. 配色
# ==============================================================

C_BG        = (13, 15, 24)
C_BG_BOARD  = (19, 22, 34)
C_GRID      = (29, 33, 50)
C_FRAME     = (56, 64, 94)
C_TEXT      = (228, 234, 247)
C_TEXT_DIM  = (124, 136, 168)
C_TEXT_FAINT= (86, 96, 124)
C_ACCENT    = (86, 208, 255)
C_WARN      = (255, 196, 84)
C_CARD      = (25, 29, 44)
C_CARD_EDGE = (43, 49, 72)

PIECE_COLORS = {
    "I": (44, 226, 230),
    "O": (250, 202, 46),
    "T": (168, 96, 246),
    "S": (76, 220, 116),
    "Z": (244, 84, 92),
    "J": (72, 132, 250),
    "L": (250, 152, 56),
}

# 方块矩阵（出生朝向，SRS 标准）
MATRICES = {
    "I": [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    "S": [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    "Z": [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
    "J": [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    "L": [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
}

# SRS 踢墙表（已换算成屏幕坐标：y 向下为正）
KICKS_JLSTZ = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (1, 0): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (1, 2): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (2, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (2, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (3, 2): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (3, 0): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (0, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
}

KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
}

# 计分表：0/1/2/3/4 行（索引即行数），T-Spin 单列
SCORE_LINES = {1: 100, 2: 300, 3: 500, 4: 800}
SCORE_TSPIN = {1: 800, 2: 1200, 3: 1600}
SCORE_TSPIN_MINI = {0: 100, 1: 200, 2: 400}


# ==============================================================
# 3. 小工具
# ==============================================================

def mix(c1, c2, f):
    """按比例 f 混合两个颜色，f=0 取 c1，f=1 取 c2。"""
    f = max(0.0, min(1.0, f))
    return (int(c1[0] + (c2[0] - c1[0]) * f),
            int(c1[1] + (c2[1] - c1[1]) * f),
            int(c1[2] + (c2[2] - c1[2]) * f))


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


# ------------------------------------------------------------------
# 中文字体：跨平台探测 + 字形校验
# ------------------------------------------------------------------
# 按「候选路径 → fontconfig 族名 → SysFont」逐级探测，每一级都必须通过
# 字形校验 —— 只有真的画得出汉字才会被采用。
#
# 为什么非要验字形：pygame 的 match_font 会给出「名字沾边、其实没有汉字」
# 的字体（本机实测 dejavusans / arial / liberationsans 一律命中 Arial
# Narrow），一旦采用，界面中文就会静默变成一屏方框。旧版本把 dejavusans
# 放在候选末尾当兜底 —— 那恰恰是最坏的一种兜底。
FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux（Debian/Ubuntu · Fedora · Arch 的常见安装位置）
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]

# 路径未必覆盖所有发行版，再交给 fontconfig 按族名找一遍。
# 这里刻意不放 dejavusans / arial 这类没有汉字字形的通用族名。
FONT_FAMILIES = ("notosanscjksc,notosanscjk,sourcehansanssc,wqyzenhei,wqymicrohei,"
                 "microsoftyahei,microsoftyaheiui,msyh,simhei,simsun,dengxian,"
                 "pingfangsc,hiraginosansgb,stheiti,heitisc,arialunicodems")

# 等宽族：只用来画分数 / 时间这类数字，不参与汉字渲染
MONO_FAMILIES = ("consolas,dejavusansmono,liberationmono,couriernew,"
                 "notosansmono,monospace")

_CJK_PROBE = "汉字测试"        # 探针：这几个字必须渲染出彼此不同的字形
_FONT_CACHE: dict = {}
_warned_no_cjk = False


def _img_bytes(surf):
    """取 Surface 的原始字节。pygame 2.1.3 起 tostring 改名 tobytes，两版都兼容。"""
    fn = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
    return fn(surf, "RGBA")


def reset_font_cache():
    """清空字体缓存 —— 重新 pygame.init() 之后必须调用。

    为什么不能指望「取用时验活」：pygame.quit() 会释放底层的 TTF_Font，
    缓存里的 Font 对象随即失效，再拿它 render 会**直接崩在 C 层**（段错误），
    连 Python 异常都抓不住。所以只能在每次初始化之后主动清掉再重新探测。
    """
    _FONT_CACHE.clear()


def font_covers_cjk(font) -> bool:
    """这个字体真的画得出汉字吗？

    字体缺字时 pygame 会把所有汉字都画成同一个 .notdef 方框（豆腐块），
    所以拿几个不同的汉字渲染出来比字节：只要有两张位图一模一样，就说明
    字体里根本没有汉字字形，绝不能拿它当界面字体。
    """
    try:
        digs = [_img_bytes(font.render(ch, True, (255, 255, 255)))
                for ch in _CJK_PROBE]
    except Exception:
        return False
    return len(set(digs)) == len(digs)


def _warn_no_cjk_font():
    """只提示一次：一个中文字体都没找到时界面会是方框。"""
    global _warned_no_cjk
    if _warned_no_cjk:
        return
    _warned_no_cjk = True
    print("[提示] 系统里没找到含汉字字形的字体，界面中文会显示成方框。\n"
          "       Linux 装一个即可： sudo apt install fonts-noto-cjk",
          file=sys.stderr)


def get_font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    """找一个真的能显示汉字的字体；全失败则退回默认字体并给出提示。

    mono=True 时走等宽族，只用于数字 / 计分板，不参与汉字渲染。
    """
    key = (size, bold, mono)
    font = _FONT_CACHE.get(key)
    if font is not None:
        return font

    if mono:
        try:
            path = pygame.font.match_font(MONO_FAMILIES, bold=bold)
        except Exception:
            path = None
        font = pygame.font.Font(path, size) if path else pygame.font.Font(None, size)
        font.set_bold(bold)
        _FONT_CACHE[key] = font
        return font

    for path in FONT_CANDIDATES:                      # ① 平台常见路径
        if not os.path.exists(path):
            continue
        try:
            cand = pygame.font.Font(path, size)
        except Exception:
            continue
        cand.set_bold(bold)
        if font_covers_cjk(cand):
            _FONT_CACHE[key] = cand
            return cand

    try:                                              # ② fontconfig 按族名
        path = pygame.font.match_font(FONT_FAMILIES, bold=bold)
        if path:
            cand = pygame.font.Font(path, size)
            cand.set_bold(bold)
            if font_covers_cjk(cand):
                _FONT_CACHE[key] = cand
                return cand
    except Exception:
        pass

    try:                                              # ③ SysFont 最后兜底
        cand = pygame.font.SysFont(FONT_FAMILIES, size, bold=bold)
        if font_covers_cjk(cand):
            _FONT_CACHE[key] = cand
            return cand
    except Exception:
        pass

    # 一个汉字都画不出来的字体不能用，宁可退回 pygame 自带字体并明确提示。
    _warn_no_cjk_font()
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    _FONT_CACHE[key] = font
    return font


def font_regression(bad_path):
    """反事实自检：把候选全换成「没有汉字的字体」，get_font 必须识别出来。

    返回 (bool, str)。旧版本用 dejavusans 兜底 —— 它名字匹配得到、却画不出
    汉字，于是界面静默变成方框。这条断言就是防止那种写法复活。
    """
    global FONT_FAMILIES, _warned_no_cjk
    saved_cands = list(FONT_CANDIDATES)
    saved_fams = FONT_FAMILIES
    saved_cache = dict(_FONT_CACHE)
    saved_warned = _warned_no_cjk
    try:
        FONT_CANDIDATES[:] = [bad_path]
        FONT_FAMILIES = "dejavusans,arial,liberationsans"
        _FONT_CACHE.clear()
        # 这个场景注定找不到汉字字体，别刷出误导性的「你的系统没有中文字体」
        _warned_no_cjk = True
        got = get_font(24)
        ref = pygame.font.Font(None, 24)
        same = (_img_bytes(got.render("汉", True, (255, 255, 255)))
                == _img_bytes(ref.render("汉", True, (255, 255, 255))))
        return same, bad_path
    finally:
        FONT_CANDIDATES[:] = saved_cands
        FONT_FAMILIES = saved_fams
        _FONT_CACHE.clear()
        _FONT_CACHE.update(saved_cache)
        _warned_no_cjk = saved_warned


def draw_text(surf, text, font, color, pos, anchor="topleft", alpha=255):
    """绘制文字。anchor 支持 topleft / center / midleft / topright / midright 等。"""
    img = font.render(text, True, color)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def draw_round_rect(surf, rect, color, radius=8, width=0):
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


# ---- 方块贴图：逐像素做「上亮下暗 + 圆角」，比叠同心圆干净得多 ----

_CELL_CACHE: dict = {}


def _shade_at(x, y, size):
    """返回 0.4 ~ 1.45 的明暗系数：顶面受光、底部成影、左亮右暗。"""
    u = (x + 0.5) / size
    v = (y + 0.5) / size
    s = 1.0
    top = clamp((0.34 - v) / 0.34, 0.0, 1.0)
    s += 0.34 * (top ** 1.15)
    bot = clamp((v - 0.62) / 0.38, 0.0, 1.0)
    s -= 0.36 * bot
    s += 0.10 * (1.0 - 2.0 * u)
    d = min(x, y, size - 1 - x, size - 1 - y)
    if d < 1.2:                      # 内侧描边，让相邻方块之间有分界
        s *= 0.62
    return s


def make_cell_surface(color, size=CELL):
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, size, size),
                     border_radius=max(3, int(size * 0.20)))
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            a = mask.get_at((x, y))[3]
            if a == 0:
                continue
            k = _shade_at(x, y, size)
            out.set_at((x, y), (int(clamp(color[0] * k, 0, 255)),
                                int(clamp(color[1] * k, 0, 255)),
                                int(clamp(color[2] * k, 0, 255)),
                                a))
    return out


def cell_image(color, size=CELL):
    key = (color, size)
    img = _CELL_CACHE.get(key)
    if img is None:
        img = make_cell_surface(color, size)
        _CELL_CACHE[key] = img
    return img


_GHOST_CACHE: dict = {}


def ghost_image(color, size=CELL):
    key = (color, size)
    img = _GHOST_CACHE.get(key)
    if img is None:
        img = pygame.Surface((size, size), pygame.SRCALPHA)
        r = max(3, int(size * 0.20))
        pygame.draw.rect(img, (color[0], color[1], color[2], 46),
                         (1, 1, size - 2, size - 2), border_radius=r)
        pygame.draw.rect(img, (color[0], color[1], color[2], 132),
                         (1, 1, size - 2, size - 2), width=2, border_radius=r)
        _GHOST_CACHE[key] = img
    return img


def rounded_cov_mask(size, radius):
    m = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, size, size), border_radius=radius)
    return m


# ==============================================================
# 4. 程序化音效（numpy 合成，无外部素材；numpy 缺失则静音）
# ==============================================================

try:
    import numpy as _np
except Exception:                                  # pragma: no cover
    _np = None


def _tone_data(f0, f1, dur, vol, wave="square", lp=1, rate=44100):
    n = max(1, int(rate * dur))
    freq = _np.linspace(f0, f1, n)
    phase = _np.cumsum(freq) * 2 * _np.pi / rate
    if wave == "square":
        sig = _np.sign(_np.sin(phase))
    elif wave == "saw":
        sig = 2.0 * ((phase / (2 * _np.pi)) % 1.0) - 1.0
    elif wave == "noise":
        sig = _np.random.uniform(-1.0, 1.0, n)
    else:
        sig = _np.sin(phase)
    if lp > 1:
        sig = _np.convolve(sig, _np.ones(lp) / lp, mode="same")
    env = _np.exp(-_np.linspace(0.0, 4.6, n))
    return sig * env * vol


def _seq(parts, gap=0.0, rate=44100):
    """把若干 (f0,f1,dur,vol,wave,lp) 拼成一条波形。"""
    segs = []
    for p in parts:
        segs.append(_tone_data(*p, rate=rate))
        if gap > 0:
            segs.append(_np.zeros(int(rate * gap)))
    return _np.concatenate(segs) if segs else _np.zeros(1)


def _make_sound(data):
    d = _np.clip(data, -1.0, 1.0) * 32767.0
    arr = _np.int16(d)
    arr = _np.ascontiguousarray(_np.column_stack((arr, arr)))
    return pygame.sndarray.make_sound(arr)


SOUND_DEFS = {
    "move":     [(200, 200, 0.030, 0.16, "square", 1)],
    "rotate":   [(320, 470, 0.055, 0.16, "saw", 1)],
    "lock":     [(150, 70, 0.075, 0.20, "square", 1)],
    "harddrop": [(420, 90, 0.070, 0.20, "noise", 6)],
    "hold":     [(520, 760, 0.070, 0.15, "sine", 1)],
    "clear1":   [(520, 780, 0.130, 0.20, "sine", 1)],
    "clear2":   [(520, 680, 0.070, 0.19, "sine", 1), (680, 900, 0.110, 0.19, "sine", 1)],
    "clear3":   [(520, 660, 0.060, 0.19, "sine", 1), (660, 830, 0.060, 0.19, "sine", 1),
                 (830, 1040, 0.110, 0.19, "sine", 1)],
    "tetris":   [(523, 523, 0.060, 0.20, "sine", 1), (659, 659, 0.060, 0.20, "sine", 1),
                 (784, 784, 0.060, 0.20, "sine", 1), (1046, 1046, 0.150, 0.22, "sine", 1)],
    "tspin":    [(700, 900, 0.050, 0.20, "square", 1), (1000, 1300, 0.120, 0.20, "saw", 1)],
    "levelup":  [(440, 590, 0.070, 0.18, "sine", 1), (590, 740, 0.070, 0.18, "sine", 1),
                 (740, 990, 0.150, 0.20, "sine", 1)],
    "gameover": [(420, 380, 0.120, 0.20, "saw", 1), (320, 260, 0.130, 0.20, "saw", 1),
                 (240, 110, 0.320, 0.22, "saw", 1)],
    "start":    [(400, 620, 0.070, 0.17, "square", 1), (620, 880, 0.110, 0.19, "square", 1)],
    "pause":    [(660, 480, 0.080, 0.15, "sine", 1)],
}


class Sfx:
    def __init__(self, enabled=True):
        self.sounds: dict = {}
        self.muted = not enabled
        self.channels = 16
        if not enabled or _np is None:
            return
        if not pygame.mixer.get_init():
            return
        try:
            for name, parts in SOUND_DEFS.items():
                self.sounds[name] = _make_sound(_seq(parts))
            pygame.mixer.set_num_channels(self.channels)
        except Exception as exc:                    # pragma: no cover
            print("[audio] 音效合成失败，已静音：", exc)
            self.sounds = {}

    @property
    def ok(self):
        return bool(self.sounds)

    def play(self, name, volume=1.0):
        if self.muted or not self.sounds:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.set_volume(volume)
                ch.play(snd)
        except Exception:
            pass

    def toggle(self):
        self.muted = not self.muted
        return self.muted


# ==============================================================
# 5. 方块与随机器
# ==============================================================

def rotate_cw(mat):
    n = len(mat)
    return [[mat[n - 1 - c][r] for c in range(n)] for r in range(n)]


def rotate_ccw(mat):
    n = len(mat)
    return [[mat[c][n - 1 - r] for c in range(n)] for r in range(n)]


class Piece:
    __slots__ = ("kind", "mat", "x", "y", "rot")

    def __init__(self, kind, x=None, y=0, rot=0, mat=None):
        self.kind = kind
        self.mat = mat if mat is not None else [r[:] for r in MATRICES[kind]]
        self.rot = rot
        self.x = (COLS - len(self.mat[0])) // 2 if x is None else x
        self.y = y

    def cells(self, mat=None, dx=0, dy=0):
        m = self.mat if mat is None else mat
        out = []
        for r, row in enumerate(m):
            for c, v in enumerate(row):
                if v:
                    out.append((self.x + c + dx, self.y + r + dy))
        return out

    def clone(self):
        return Piece(self.kind, self.x, self.y, self.rot, [r[:] for r in self.mat])


class Bag:
    """7-bag 随机器"""

    def __init__(self, rng):
        self.rng = rng
        self.bag: list = []

    def next(self):
        if not self.bag:
            self.bag = list(PIECE_KINDS)
            self.rng.shuffle(self.bag)
        return self.bag.pop()


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "grav")

    def __init__(self, x, y, vx, vy, life, color, size, grav=520.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.grav = grav

    def update(self, dt):
        self.life -= dt
        self.vy += self.grav * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0


# ==============================================================
# 6. 游戏主体
# ==============================================================

PHASE_MENU = "menu"
PHASE_PLAY = "playing"
PHASE_PAUSE = "paused"
PHASE_OVER = "gameover"


class Game:
    MAX_PARTICLES = 600

    def __init__(self, sfx=None, seed=None):
        self.sfx = sfx or Sfx(False)
        self.rng = random.Random(seed)
        self.bag = Bag(self.rng)
        self.best = 0
        self.reset()

    # ---------- 生命周期 ----------

    def reset(self):
        self.grid = [[None] * COLS for _ in range(ROWS)]
        self.bag = Bag(self.rng)
        self.queue = [self.bag.next() for _ in range(5)]
        self.piece: Piece | None = None
        self.hold: str | None = None
        self.hold_used = False

        self.score = 0
        self.lines = 0
        self.level = 1
        self.combo = 0
        self.elapsed = 0.0

        self.gravity_timer = 0.0
        self.soft_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.grounded = False

        self.move_dir = 0
        self.das_timer = 0.0
        self.arr_timer = 0.0

        self.particles: list = []
        self.clear_rows: list = []
        self.clear_timer = 0.0
        self.shake = 0.0
        self.flash = 0.0
        self.toast = ""
        self.toast_timer = 0.0

        self.phase = PHASE_MENU
        self.last_cleared = 0
        self.last_tspin = False
        # None = 最后一次操作不是旋转；否则为生效的踢墙索引
        self.last_rot_kick = None

    def start(self):
        self.reset()
        self.phase = PHASE_PLAY
        self._spawn_next()
        self.sfx.play("start")

    def toggle_pause(self):
        if self.phase == PHASE_PLAY:
            self.phase = PHASE_PAUSE
            self.sfx.play("pause")
        elif self.phase == PHASE_PAUSE:
            self.phase = PHASE_PLAY

    # ---------- 棋盘查询 ----------

    def _collide(self, mat, px, py):
        w = len(mat[0])
        for r, row in enumerate(mat):
            for c, v in enumerate(row):
                if not v:
                    continue
                x = px + c
                y = py + r
                if x < 0 or x >= COLS or y >= ROWS:
                    return True
                if y >= 0 and self.grid[y][x]:
                    return True
        return False

    def _valid(self, piece: Piece) -> bool:
        return not self._collide(piece.mat, piece.x, piece.y)

    def ghost_y(self, piece: Piece | None = None) -> int:
        p = piece or self.piece
        if p is None:
            return 0
        y = p.y
        while not self._collide(p.mat, p.x, y + 1):
            y += 1
        return y

    def gravity_interval(self) -> float:
        return GRAVITY[min(self.level - 1, len(GRAVITY) - 1)]

    # ---------- 生成 ----------

    def _spawn(self, kind):
        p = Piece(kind)
        if self._collide(p.mat, p.x, p.y):          # 顶到天花板就再上移一格试试
            p.y = -1
            if self._collide(p.mat, p.x, p.y):
                self.piece = p
                self._game_over()
                return False
        self.piece = p
        self.gravity_timer = 0.0
        self.soft_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.grounded = False
        self.hold_used = False
        self.last_tspin = False
        self.last_rot_kick = None
        return True

    def _spawn_next(self):
        kind = self.queue.pop(0)
        self.queue.append(self.bag.next())
        return self._spawn(kind)

    def _game_over(self):
        self.phase = PHASE_OVER
        self.best = max(self.best, self.score)
        self.sfx.play("gameover")
        if self.piece:
            for (cx, cy) in self.piece.cells():
                self._burst(cx, cy, PIECE_COLORS[self.piece.kind], 3)

    # ---------- 操作 ----------

    def _refresh_lock(self):
        """移动/旋转成功且仍在地面时，重置锁定倒计时（有次数上限）。"""
        if self.grounded and self.lock_resets < MAX_LOCK_RESETS:
            self.lock_timer = 0.0
            self.lock_resets += 1

    def try_move(self, dx, dy=0):
        p = self.piece
        if p is None or self.clear_rows:
            return False
        if not self._collide(p.mat, p.x + dx, p.y + dy):
            p.x += dx
            p.y += dy
            self.last_rot_kick = None      # 平移会取消 T-Spin 资格
            self._refresh_lock()
            return True
        return False

    def try_rotate(self, cw=True):
        p = self.piece
        if p is None or self.clear_rows:
            return False
        if p.kind == "O":
            return False
        new_rot = (p.rot + (1 if cw else -1)) % 4
        mat = rotate_cw(p.mat) if cw else rotate_ccw(p.mat)
        table = KICKS_I if p.kind == "I" else KICKS_JLSTZ
        for idx, (kx, ky) in enumerate(table[(p.rot, new_rot)]):
            if not self._collide(mat, p.x + kx, p.y + ky):
                p.mat = mat
                p.rot = new_rot
                p.x += kx
                p.y += ky
                self.last_rot_kick = idx    # 旋转成功 -> 具备 T-Spin 资格
                self._refresh_lock()
                self.sfx.play("rotate", 0.85)
                return True
        return False

    def do_hold(self):
        if self.piece is None or self.hold_used or self.clear_rows:
            return False
        if self.hold is None:
            self.hold = self.piece.kind
            self._spawn_next()
        else:
            swap = self.hold
            self.hold = self.piece.kind
            self._spawn(swap)
        self.hold_used = True
        self.sfx.play("hold")
        return True

    def hard_drop(self):
        p = self.piece
        if p is None or self.clear_rows:
            return
        target = self.ghost_y(p)
        dist = target - p.y
        if dist > 0:
            p.y = target
            self.score += 2 * dist
        self.shake = min(1.0, self.shake + 0.35 + 0.06 * dist)
        self.sfx.play("harddrop")
        self._lock_piece()

    # ---------- 锁定与消行 ----------

    def _is_tspin(self) -> bool:
        p = self.piece
        if p is None or p.kind != "T" or self.last_rot_kick is None:
            return False
        # T 的旋转中心在 3x3 矩阵的 (1,1)，四个角坐标如下
        corners = ((p.x, p.y), (p.x + 2, p.y), (p.x, p.y + 2), (p.x + 2, p.y + 2))
        filled = 0
        for (cx, cy) in corners:
            if cx < 0 or cx >= COLS or cy >= ROWS:
                filled += 1
            elif cy >= 0 and self.grid[cy][cx]:
                filled += 1
        return filled >= 3

    def _lock_piece(self):
        p = self.piece
        if p is None:
            return
        tspin = self._is_tspin()
        color = PIECE_COLORS[p.kind]
        for (cx, cy) in p.cells():
            if 0 <= cy < ROWS and 0 <= cx < COLS:
                self.grid[cy][cx] = p.kind

        full = [r for r in range(ROWS) if all(self.grid[r][c] for c in range(COLS))]
        self.piece = None
        self.grounded = False
        self.lock_timer = 0.0

        if full:
            self.clear_rows = full
            self.clear_timer = 0.0
            self.last_cleared = len(full)
            self.last_tspin = tspin
            for r in full:
                for c in range(COLS):
                    k = self.grid[r][c]
                    self._burst(c, r, PIECE_COLORS.get(k, color), 4)
            self.shake = min(1.0, self.shake + 0.18 + 0.10 * len(full))
            self.flash = min(1.0, 0.25 + 0.2 * len(full))
        else:
            self.sfx.play("lock", 0.8)
            if tspin:
                self.score += 400
                self._toast("T-SPIN", C_WARN)
                self.sfx.play("tspin")
            self.combo = 0
            self._spawn_next()

    def _apply_clear(self):
        rows = self.clear_rows
        n = len(rows)
        self.clear_rows = []
        self.clear_timer = 0.0

        # 必须先把待消行全部删掉，再统一在顶部补空行。
        # 若边删边 insert，后续行的索引会整体下移，导致漏删（棋盘留下幽灵行）。
        for r in sorted(rows, reverse=True):
            del self.grid[r]
        for _ in range(n):
            self.grid.insert(0, [None] * COLS)

        tspin = self.last_tspin
        base = SCORE_TSPIN.get(n, 0) if tspin else SCORE_LINES.get(n, 0)
        self.score += base * self.level
        self.combo += 1
        if self.combo > 1:
            self.score += 50 * (self.combo - 1) * self.level

        self.lines += n
        new_level = self.lines // LINES_PER_LEVEL + 1
        leveled = new_level > self.level
        self.level = new_level

        if tspin and n:
            self._toast(f"T-SPIN x{n}", C_WARN)
        elif n == 4:
            self._toast("TETRIS!", (255, 120, 140))
        elif n == 3:
            self._toast("TRIPLE", C_ACCENT)
        elif n == 2:
            self._toast("DOUBLE", C_ACCENT)
        if self.combo > 1:
            self.toast = f"{self.toast}  ·  {self.combo}x COMBO" if self.toast else f"{self.combo}x COMBO"

        if n == 4:
            self.sfx.play("tetris")
        elif tspin:
            self.sfx.play("tspin")
        else:
            self.sfx.play({1: "clear1", 2: "clear2", 3: "clear3"}.get(n, "clear1"))

        if leveled:
            self.sfx.play("levelup")
            self._toast(f"LEVEL {self.level}", (150, 255, 190))

        self._spawn_next()

    def _toast(self, text, color=None):
        self.toast = text
        self.toast_timer = 1.1

    def _burst(self, cx, cy, color, count):
        px = BOARD_X + cx * CELL + CELL * 0.5
        py = BOARD_Y + cy * CELL + CELL * 0.5
        for _ in range(count):
            if len(self.particles) >= self.MAX_PARTICLES:
                return
            ang = self.rng.uniform(0, math.tau)
            spd = self.rng.uniform(40, 230)
            life = self.rng.uniform(0.28, 0.62)
            self.particles.append(Particle(
                px + self.rng.uniform(-CELL * 0.3, CELL * 0.3),
                py + self.rng.uniform(-CELL * 0.3, CELL * 0.3),
                math.cos(ang) * spd, math.sin(ang) * spd - 70,
                life, color, self.rng.uniform(2.0, 4.2)))

    # ---------- 主循环 ----------

    def update(self, dt, keys=None):
        if self.phase == PHASE_PLAY:
            self.elapsed += dt

        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 4.2)
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt * 3.4)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

        if self.phase != PHASE_PLAY:
            return

        # 消行动画期间冻结操作
        if self.clear_rows:
            self.clear_timer += dt
            if self.clear_timer >= CLEAR_DURATION:
                self._apply_clear()
            return

        if self.piece is None:
            self._spawn_next()
            if self.phase != PHASE_PLAY:
                return

        self._update_horizontal(dt, keys)
        self._update_vertical(dt, keys)
        self._update_lock(dt)

    def _update_horizontal(self, dt, keys):
        left = bool(keys[pygame.K_LEFT]) if keys else False
        right = bool(keys[pygame.K_RIGHT]) if keys else False
        d = (1 if right else 0) - (1 if left else 0)

        if d != self.move_dir:
            self.move_dir = d
            self.das_timer = 0.0
            self.arr_timer = 0.0
            if d and self.try_move(d):
                self.sfx.play("move", 0.6)
            return

        if d == 0:
            return

        self.das_timer += dt
        if self.das_timer < DAS:
            return
        self.arr_timer += dt
        guard = 0
        while self.arr_timer >= ARR and guard < COLS:
            self.arr_timer -= ARR
            guard += 1
            if not self.try_move(d):
                break

    def _update_vertical(self, dt, keys):
        p = self.piece
        if p is None:
            return
        soft = bool(keys[pygame.K_DOWN]) if keys else False

        if soft:
            self.soft_timer += dt
            guard = 0
            while self.soft_timer >= SOFT_DROP_INTERVAL and guard < ROWS:
                self.soft_timer -= SOFT_DROP_INTERVAL
                guard += 1
                if self._collide(p.mat, p.x, p.y + 1):
                    break
                p.y += 1
                self.score += 1
                self.gravity_timer = 0.0
        else:
            self.soft_timer = 0.0

        interval = self.gravity_interval()
        if soft:
            interval = min(interval, SOFT_DROP_INTERVAL)

        self.gravity_timer += dt
        guard = 0
        while self.gravity_timer >= interval and guard < ROWS:
            self.gravity_timer -= interval
            guard += 1
            if self._collide(p.mat, p.x, p.y + 1):
                self.gravity_timer = 0.0
                break
            p.y += 1

        landed = self._collide(p.mat, p.x, p.y + 1)
        if landed and not self.grounded:
            self.grounded = True
            self.lock_timer = 0.0
        elif not landed:
            self.grounded = False
            self.lock_timer = 0.0

    def _update_lock(self, dt):
        if not self.grounded or self.piece is None:
            return
        self.lock_timer += dt
        if self.lock_timer >= LOCK_DELAY:
            self._lock_piece()

    # ---------- 事件 ----------

    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.phase in (PHASE_PLAY, PHASE_PAUSE):
                self.toggle_pause()
            return True
        if key == pygame.K_p:
            if self.phase in (PHASE_PLAY, PHASE_PAUSE):
                self.toggle_pause()
            return True
        if key == pygame.K_RETURN:
            if self.phase in (PHASE_MENU, PHASE_OVER):
                self.start()
            return True
        if key == pygame.K_r:
            self.start()
            return True

        if self.phase != PHASE_PLAY or self.clear_rows:
            return False

        if key in (pygame.K_UP, pygame.K_x):
            self.try_rotate(True)
        elif key in (pygame.K_z, pygame.K_LCTRL, pygame.K_RCTRL):
            self.try_rotate(False)
        elif key == pygame.K_SPACE:
            self.hard_drop()
        elif key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.do_hold()
        return False

    # ==========================================================
    # 绘制（所有绘制都发生在这里；update() 绝不碰画布）
    # ==========================================================

    def draw(self, canvas: pygame.Surface):
        canvas.fill(C_BG)
        self._draw_ambient(canvas)
        self._draw_board(canvas)
        self._draw_particles(canvas)
        self._draw_panel(canvas)
        if self.phase != PHASE_PLAY:
            # 非游玩态把侧栏额外压暗，免得它从结算面板边上露出来抢视线
            dim = pygame.Surface((PANEL_W + 16, CANVAS_H), pygame.SRCALPHA)
            dim.fill((6, 8, 14, 132))
            canvas.blit(dim, (PANEL_X - 8, 0))
        self._draw_toast(canvas)
        if self.flash > 0:
            self._draw_flash(canvas)
        if self.phase == PHASE_MENU:
            self._draw_menu(canvas)
        elif self.phase == PHASE_PAUSE:
            self._draw_pause(canvas)
        elif self.phase == PHASE_OVER:
            self._draw_over(canvas)

    # ---- 背景氛围 ----

    def _draw_ambient(self, canvas):
        t = pygame.time.get_ticks() / 1000.0
        for i in range(5):
            y = (i * 173 + int(t * 22)) % CANVAS_H
            col = (18, 21, 33)
            canvas.fill(col, pygame.Rect(0, y, CANVAS_W, 1))

    # ---- 棋盘 ----

    def _draw_board(self, canvas):
        ox = oy = 0
        if self.shake > 0.01:
            amp = 3.6 * self.shake
            ox = int(math.sin(pygame.time.get_ticks() * 0.06) * amp)
            oy = int(math.cos(pygame.time.get_ticks() * 0.083) * amp)

        brect = pygame.Rect(BOARD_X + ox, BOARD_Y + oy, BOARD_W, BOARD_H)
        draw_round_rect(canvas, brect, C_BG_BOARD, radius=10)

        # 网格
        for c in range(1, COLS):
            x = brect.x + c * CELL
            pygame.draw.line(canvas, C_GRID, (x, brect.y + 6), (x, brect.bottom - 6), 1)
        for r in range(1, ROWS):
            y = brect.y + r * CELL
            pygame.draw.line(canvas, C_GRID, (brect.x + 6, y), (brect.right - 6, y), 1)

        # 已固定方块
        for r in range(ROWS):
            row = self.grid[r]
            for c in range(COLS):
                kind = row[c]
                if kind:
                    if self.clear_rows and r in self.clear_rows:
                        continue                     # 交给消行动画画
                    canvas.blit(cell_image(PIECE_COLORS[kind]),
                                (brect.x + c * CELL, brect.y + r * CELL))

        # 幽灵 + 当前方块
        if self.piece is not None and not self.clear_rows:
            p = self.piece
            color = PIECE_COLORS[p.kind]
            gy = self.ghost_y(p)
            if gy > p.y:
                gimg = ghost_image(color)
                for (cx, cy) in p.cells():
                    dy = gy + (cy - p.y)
                    if 0 <= dy < ROWS and 0 <= cx < COLS:
                        canvas.blit(gimg, (brect.x + cx * CELL, brect.y + dy * CELL))
            img = cell_image(color)
            for (cx, cy) in p.cells():
                if 0 <= cy < ROWS and 0 <= cx < COLS:
                    canvas.blit(img, (brect.x + cx * CELL, brect.y + cy * CELL))

        # 消行动画：白闪 + 左右收缩
        if self.clear_rows:
            f = clamp(self.clear_timer / CLEAR_DURATION, 0.0, 1.0)
            remain = 1.0 - f
            for r in self.clear_rows:
                cy = brect.y + r * CELL + CELL * 0.5
                w = BOARD_W * (0.25 + 0.75 * remain)
                h = CELL * (0.35 + 0.65 * remain)
                rect = pygame.Rect(0, 0, int(w), int(h))
                rect.center = (brect.x + BOARD_W // 2, int(cy))
                alpha = int(min(255, 120 + 135 * remain))
                layer = pygame.Surface(rect.size, pygame.SRCALPHA)
                layer.fill((255, 255, 255, min(255, alpha)))
                canvas.blit(layer, rect.topleft)

        # 边框
        pygame.draw.rect(canvas, C_FRAME, brect, width=2, border_radius=10)
        if self.grounded and self.piece is not None and not self.clear_rows:
            k = 1.0 - clamp(self.lock_timer / LOCK_DELAY, 0.0, 1.0)
            glow = mix(C_FRAME, C_ACCENT, 0.55 * k)
            pygame.draw.rect(canvas, glow, brect, width=1, border_radius=10)

    def _draw_particles(self, canvas):
        for p in self.particles:
            f = clamp(p.life / p.max_life, 0.0, 1.0)
            col = (int(p.color[0] * f), int(p.color[1] * f), int(p.color[2] * f))
            s = max(1, int(p.size * (0.5 + 0.5 * f)))
            canvas.fill(col, pygame.Rect(int(p.x) - s // 2, int(p.y) - s // 2, s, s))

    # ---- 侧栏 ----

    def _draw_panel(self, canvas):
        x, w = PANEL_X, PANEL_W
        y = MARGIN

        # NEXT
        draw_text(canvas, "NEXT", get_font(13, bold=True), C_TEXT_DIM, (x, y), "topleft")
        y += 22
        box = pygame.Rect(x, y, w, 152)
        draw_round_rect(canvas, box, C_CARD, radius=10)
        pygame.draw.rect(canvas, C_CARD_EDGE, box, width=1, border_radius=10)
        for i in range(3):
            kind = self.queue[i] if i < len(self.queue) else None
            slot = pygame.Rect(box.x + 8, box.y + 8 + i * 46, box.w - 16, 42)
            if kind:
                self._draw_mini(canvas, kind, slot, 20 if i else 24,
                                alpha=255 if i == 0 else 165)
        y = box.bottom + 16

        # HOLD
        draw_text(canvas, "HOLD", get_font(13, bold=True), C_TEXT_DIM, (x, y), "topleft")
        y += 22
        box = pygame.Rect(x, y, w, 96)
        draw_round_rect(canvas, box, C_CARD, radius=10)
        pygame.draw.rect(canvas, C_CARD_EDGE, box, width=1, border_radius=10)
        if self.hold:
            a = 110 if self.hold_used else 255
            self._draw_mini(canvas, self.hold,
                            pygame.Rect(box.x + 8, box.y + 8, box.w - 16, box.h - 16), 24, alpha=a)
        y = box.bottom + 20

        # 统计卡片
        stats = (("SCORE", f"{self.score}"),
                 ("LEVEL", f"{self.level}"),
                 ("LINES", f"{self.lines}"),
                 ("TIME", self._fmt_time()))
        for label, value in stats:
            card = pygame.Rect(x, y, w, 52)
            draw_round_rect(canvas, card, C_CARD, radius=9)
            pygame.draw.rect(canvas, C_CARD_EDGE, card, width=1, border_radius=9)
            draw_text(canvas, label, get_font(12, bold=True), C_TEXT_FAINT,
                      (card.x + 12, card.y + 9), "topleft")
            draw_text(canvas, value, get_font(24, bold=True, mono=True), C_TEXT,
                      (card.right - 12, card.bottom - 9), "bottomright")
            y = card.bottom + 7

        # 底部提示
        tips_y = CANVAS_H - MARGIN - 116
        if y < tips_y:
            y = tips_y
        tips = ("← →  移动", "↑ / X  顺时针", "Z  逆时针",
                "↓  软降   空格  硬降", "C  暂存   P  暂停", "R  重开   M  静音")
        for i, t in enumerate(tips):
            draw_text(canvas, t, get_font(12), C_TEXT_FAINT, (x, y + i * 19), "topleft")

    def _draw_mini(self, canvas, kind, slot, cell_size, alpha=255):
        mat = MATRICES[kind]
        rows = [r for r in range(len(mat)) if any(mat[r])]
        cols = [c for c in range(len(mat[0])) if any(mat[r][c] for r in range(len(mat)))]
        if not rows or not cols:
            return
        r0, r1 = rows[0], rows[-1]
        c0, c1 = cols[0], cols[-1]
        pw = (c1 - c0 + 1) * cell_size
        ph = (r1 - r0 + 1) * cell_size
        if pw > slot.w or ph > slot.h:
            k = min(slot.w / pw, slot.h / ph)
            cell_size = max(8, int(cell_size * k))
            pw = (c1 - c0 + 1) * cell_size
            ph = (r1 - r0 + 1) * cell_size
        ox = slot.x + (slot.w - pw) // 2
        oy = slot.y + (slot.h - ph) // 2
        img = cell_image(PIECE_COLORS[kind], cell_size)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if mat[r][c]:
                    canvas.blit(img, (ox + (c - c0) * cell_size, oy + (r - r0) * cell_size))

    def _fmt_time(self):
        s = int(self.elapsed)
        return f"{s // 60:02d}:{s % 60:02d}"

    # ---- 浮层 ----

    def _draw_toast(self, canvas):
        if self.toast_timer <= 0 or not self.toast:
            return
        f = clamp(self.toast_timer / 1.1, 0.0, 1.0)
        alpha = int(255 * min(1.0, f * 2.2))
        rise = int(26 * (1.0 - f))
        font = get_font(22, bold=True)
        cy = BOARD_Y + int(BOARD_H * 0.30) - rise
        draw_text(canvas, self.toast, font, C_TEXT, (BOARD_X + BOARD_W // 2, cy),
                  "center", alpha=alpha)

    def _draw_flash(self, canvas):
        a = int(46 * self.flash)
        if a <= 0:
            return
        layer = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        layer.fill((255, 255, 255, a))
        canvas.blit(layer, (0, 0))

    def _overlay(self, canvas, alpha=168):
        layer = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        layer.fill((6, 8, 14, alpha))
        canvas.blit(layer, (0, 0))

    def _draw_menu(self, canvas):
        self._overlay(canvas, 178)
        cx = CANVAS_W // 2
        draw_text(canvas, "俄罗斯方块", get_font(46, bold=True), C_TEXT, (cx, 240), "center")
        draw_text(canvas, "T E T R I S", get_font(16, bold=True), C_ACCENT, (cx, 288), "center")

        parts = ("← →  左右移动", "↑ / X  顺时针旋转     Z  逆时针旋转",
                 "↓  软降     空格  硬降", "C  暂存      P / ESC  暂停",
                 "R  重新开始      M  静音")
        for i, t in enumerate(parts):
            draw_text(canvas, t, get_font(15), C_TEXT_DIM, (cx, 372 + i * 26), "center")

        pulse = 0.55 + 0.45 * math.sin(pygame.time.get_ticks() / 380.0)
        col = mix(C_TEXT_DIM, C_ACCENT, pulse)
        draw_text(canvas, "按 Enter 开始", get_font(20, bold=True), col, (cx, 540), "center")

        if self.best:
            draw_text(canvas, f"最高分  {self.best}", get_font(14), C_TEXT_FAINT, (cx, 586), "center")
        if not self.sfx.ok:
            draw_text(canvas, "（未检测到音频设备 / numpy，已静音运行）",
                      get_font(12), C_TEXT_FAINT, (cx, CANVAS_H - 44), "center")

    def _draw_pause(self, canvas):
        self._overlay(canvas, 176)
        cx = CANVAS_W // 2
        panel = pygame.Rect(0, 0, 304, 168)
        panel.center = (cx, 336)
        layer = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, (10, 12, 21, 200), layer.get_rect(), border_radius=14)
        canvas.blit(layer, panel.topleft)
        pygame.draw.rect(canvas, C_CARD_EDGE, panel, width=1, border_radius=14)
        draw_text(canvas, "已暂停", get_font(38, bold=True), C_TEXT, (cx, 300), "center")
        draw_text(canvas, "P / ESC  继续", get_font(16), C_TEXT_DIM, (cx, 352), "center")
        draw_text(canvas, "R  重新开始", get_font(16), C_TEXT_DIM, (cx, 382), "center")

    def _draw_over(self, canvas):
        self._overlay(canvas, 182)
        cx = CANVAS_W // 2
        panel = pygame.Rect(0, 0, 372, 402)
        panel.center = (cx, 382)
        layer = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, (10, 12, 21, 206), layer.get_rect(), border_radius=14)
        canvas.blit(layer, panel.topleft)
        pygame.draw.rect(canvas, C_CARD_EDGE, panel, width=1, border_radius=14)

        draw_text(canvas, "游戏结束", get_font(40, bold=True), (255, 138, 148), (cx, 232), "center")
        rows = (("得分", f"{self.score}"),
                ("消行", f"{self.lines}"),
                ("等级", f"{self.level}"),
                ("用时", self._fmt_time()))
        y = 300
        for label, value in rows:
            draw_text(canvas, label, get_font(15), C_TEXT_DIM, (cx - 96, y), "midleft")
            draw_text(canvas, value, get_font(22, bold=True, mono=True), C_TEXT, (cx + 96, y), "midright")
            y += 38
        pygame.draw.line(canvas, C_CARD_EDGE, (cx - 110, y - 12), (cx + 110, y - 12), 1)
        draw_text(canvas, f"最高分  {self.best}", get_font(15), C_WARN, (cx, y + 12), "center")
        pulse = 0.55 + 0.45 * math.sin(pygame.time.get_ticks() / 380.0)
        draw_text(canvas, "按 Enter 再来一局", get_font(20, bold=True),
                  mix(C_TEXT_DIM, C_ACCENT, pulse), (cx, 548), "center")


# ==============================================================
# 7. 应用外壳（窗口 / 缩放 / 主循环）
# ==============================================================

class App:
    def __init__(self, scale=DEFAULT_SCALE, seed=None, frames=None, dummy=False,
                 screenshots=None):
        self.frames_limit = frames
        self.shot_plan = screenshots or []
        self.shot_index = 0
        self.frame = 0

        if dummy:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()

        # 重新初始化后旧 Font 已失效，必须清缓存（不清会在 render 时段错误）
        reset_font_cache()
        pygame.display.set_caption("俄罗斯方块 · Tetris")

        self.win_size = (max(480, int(CANVAS_W * scale)), max(480, int(CANVAS_H * scale)))
        flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(self.win_size, flags)
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H)).convert()
        self.clock = pygame.time.Clock()

        self.sfx = Sfx(True)
        self.game = Game(self.sfx, seed=seed)
        self.view_scale = 1.0
        self.fullscreen = False
        self._recalc_scale()
        self.running = True
        self.auto_keys = None          # 自检用：可注入假按键

    def _recalc_scale(self):
        w, h = self.screen.get_size()
        self.view_scale = min(w / CANVAS_W, h / CANVAS_H)

    def window_to_canvas(self, pos):
        w, h = self.screen.get_size()
        sw = CANVAS_W * self.view_scale
        sh = CANVAS_H * self.view_scale
        ox = (w - sw) * 0.5
        oy = (h - sh) * 0.5
        if self.view_scale <= 0:
            return (0, 0)
        return (int((pos[0] - ox) / self.view_scale), int((pos[1] - oy) / self.view_scale))

    # ---------- 事件 ----------

    def process_events(self):
        events = pygame.event.get()
        for ev in events:
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((max(360, ev.w), max(360, ev.h)),
                                                      pygame.RESIZABLE)
                self._recalc_scale()
            elif ev.type == pygame.KEYDOWN:
                self._on_key(ev.key)

    def _on_key(self, key):
        if key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            else:
                self.screen = pygame.display.set_mode(self.win_size, pygame.RESIZABLE)
            self._recalc_scale()
            return
        if key == pygame.K_m:
            self.sfx.toggle()
            return
        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._zoom(1.12)
            return
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom(1 / 1.12)
            return
        self.game.handle_key(key)

    def _zoom(self, factor):
        self.win_size = (max(360, int(self.win_size[0] * factor)),
                         max(360, int(self.win_size[1] * factor)))
        if not self.fullscreen:
            self.screen = pygame.display.set_mode(self.win_size, pygame.RESIZABLE)
            self._recalc_scale()

    # ---------- 渲染 ----------

    def render(self):
        self.game.draw(self.canvas)

    def present(self):
        dest = self.screen
        w, h = dest.get_size()
        if abs(self.view_scale - 1.0) < 1e-3 and (w, h) == (CANVAS_W, CANVAS_H):
            dest.blit(self.canvas, (0, 0))
        else:
            sw = max(1, int(CANVAS_W * self.view_scale))
            sh = max(1, int(CANVAS_H * self.view_scale))
            scaled = pygame.transform.smoothscale(self.canvas, (sw, sh))
            dest.fill((0, 0, 0))
            dest.blit(scaled, ((w - sw) // 2, (h - sh) // 2))
        pygame.display.flip()

    # ---------- 主循环 ----------

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            self.process_events()
            keys = self.auto_keys if self.auto_keys is not None else pygame.key.get_pressed()
            self.game.update(dt, keys)
            self.render()
            self.present()

            self.frame += 1
            if self.shot_plan and self.shot_index < len(self.shot_plan):
                target, path = self.shot_plan[self.shot_index]
                if self.frame >= target:
                    pygame.image.save(self.canvas, path)
                    print(f"[shot] frame={self.frame} -> {path}")
                    self.shot_index += 1
            if self.frames_limit is not None and self.frame >= self.frames_limit:
                self.running = False
        pygame.quit()


# ==============================================================
# 8. 入口
# ==============================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description="俄罗斯方块 (pygame)")
    ap.add_argument("--version", action="version", version=f"tetris {__version__}")
    ap.add_argument("--scale", type=float, default=DEFAULT_SCALE, help="初始窗口缩放")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--frames", type=int, default=None, help="跑满 N 帧后自动退出")
    ap.add_argument("--dummy", action="store_true", help="使用 dummy 视频/音频驱动")
    args = ap.parse_args(argv)

    app = App(scale=args.scale, seed=args.seed, frames=args.frames, dummy=args.dummy)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
