"""Instagram Reels renderer: Сура 96 «Сгусток» (Аль-Алак), поэтический перевод.

Usage: python3 render.py <fonts_dir> <out_dir> [--preview]
Produces sura96_reels.mp4 (1080x1920, 30 fps) and cover.png.
"""
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
PREVIEW = "--preview" in sys.argv
OUT.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1080, 1920, 30
MARGIN = 96                     # side margin for text
TEXT_CY = 930                   # vertical centre of text block (Reels safe zone)

GOLD = (226, 189, 120)
GOLD_SOFT = (196, 163, 104)
CREAM = (246, 238, 222)
MUTED = (170, 186, 180)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


F_VERSE = font("lora-500-normal.ttf", 64)
F_TITLE = font("cormorant-garamond-600-normal.ttf", 92)
F_TITLE_IT = font("cormorant-garamond-500-italic.ttf", 64)
F_SMALL = font("montserrat-500-normal.ttf", 30)
F_SMALL_B = font("montserrat-600-normal.ttf", 34)
F_ARAB_BIG = ImageFont.truetype(str(FONTS / "amiri-700.ttf"), 250, layout_engine=ImageFont.Layout.RAQM)
F_SAW = ImageFont.truetype(str(FONTS / "amiri-700.ttf"), 46, layout_engine=ImageFont.Layout.RAQM)
F_ARAB = ImageFont.truetype(str(FONTS / "amiri-700.ttf"), 92, layout_engine=ImageFont.Layout.RAQM)

# ---------------------------------------------------------------- text ----
COUPLETS = [
    ("Читай во имя Бога, Владыки твоего,",
     "Кто создал человека, Кто сотворил его"),
    ("Из кровяного сгустка и дал увидеть свет.",
     "Читай! Щедротам Божьим конца и меры нет."),
    ("Господь письмом высоким не знавших научил,",
     "Он человеку знанье сокрытого вручил."),
    ("Но человек, увидя, что вдруг богатым стал —",
     "Уже и возгордился, вознесся и восстал!"),
    ("Ужели непонятно строптивому уму,",
     "Что к Богу возвратиться назначено ему?"),
    ("Видал ли ты такого, кто зычно, как труба,",
     "Осмеивал молитву склоненного раба?"),
    ("Видал ли, чтоб насмешник ступил на правый путь",
     "И к страху перед Богом повелевал прильнуть?"),
    ("Винил во лжи — видал ты? — и отвернуться смог.",
     "Ужели он не ведал, что все увидит Бог?"),
    ("Да! Если он в смиреньи не преклонит лица,",
     "За волосы Мы схватим греховного лжеца!"),
    ("Мы стражею ударим по всем его друзьям!",
     "Не подчинись безумцу, а приближайся к Нам!"),
]

# words painted gold (compared without punctuation, lower-case)
HIGHLIGHT = {
    "читай", "бога", "владыки", "создал", "сотворил", "свет", "щедротам",
    "господь", "научил", "знанье", "возгордился", "богу", "возвратиться",
    "молитву", "правый", "путь", "богом", "увидит", "бог", "смиреньи",
    "приближайся", "нам",
}

PUNCT = ",.!?:;—«»()"


def clean(w):
    return w.strip(PUNCT).lower()


def wrap(text, fnt, max_w):
    """Split a poetic line into at most two balanced rows, preferring a
    break after punctuation (the natural caesura)."""
    words = text.split()
    if fnt.getlength(text) <= max_w:
        return [words]
    best, best_score = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = fnt.getlength(a), fnt.getlength(b)
        if max(wa, wb) > max_w:
            continue
        score = abs(wa - wb)
        if words[i - 1][-1] in ",;:!?—" or words[i] == "—":
            score -= 220
        if best_score is None or score < best_score:
            best, best_score = i, score
    if best is None:
        best = len(words) // 2
    return [words[:best], words[best:]]


# ------------------------------------------------------------- easing ----
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


# --------------------------------------------------------- background ----
def make_pattern(size=240):
    """Faint 8-pointed-star lattice (khatam) tile."""
    img = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(img)
    c = size / 2
    for cx, cy in [(c, c), (0, 0), (size, 0), (0, size), (size, size)]:
        r = size * 0.30
        for rot in (0, 45):
            pts = []
            for k in range(4):
                a = math.radians(rot + 90 * k + 45)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            d.polygon(pts, outline=255, width=2)
        d.ellipse([cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42], outline=255, width=2)
    d.line([(0, c), (size, c)], fill=110, width=1)
    d.line([(c, 0), (c, size)], fill=110, width=1)
    return np.asarray(img, dtype=np.float32) / 255.0


PAT_TILE = make_pattern()
PT = PAT_TILE.shape[0]
PATTERN = np.tile(PAT_TILE, (H // PT + 3, W // PT + 3))

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
# vertical gradient: deep teal-emerald -> near black
g = yy / H
BASE = np.stack([
    10 + 6 * (1 - g),
    30 + 18 * (1 - g),
    34 + 14 * (1 - g),
], axis=-1)
# vignette
dx, dy = (xx - W / 2) / (W / 2), (yy - H * 0.48) / (H / 2)
VIGNETTE = np.clip(1.0 - 0.55 * (dx * dx * 0.7 + dy * dy), 0.25, 1.0)[..., None]
# pattern visibility mask: strongest at top/bottom, gentle behind text
PAT_MASK = (0.35 + 0.65 * np.clip(np.abs(yy - TEXT_CY) / 700.0, 0, 1)) * 0.075

GLOW_R = 900
gy, gx = np.mgrid[-GLOW_R:GLOW_R, -GLOW_R:GLOW_R].astype(np.float32)
GLOW = np.exp(-(gx * gx + gy * gy) / (2 * (GLOW_R * 0.42) ** 2))

random.seed(7)
PARTICLES = [dict(x=random.uniform(0, W), y=random.uniform(0, H),
                  r=random.uniform(1.2, 3.2), sp=random.uniform(8, 26),
                  ph=random.uniform(0, 6.28), a=random.uniform(0.25, 0.7))
             for _ in range(46)]


def background(t, pulse=0.0):
    img = BASE.copy()
    # slowly drifting pattern
    ox = int(t * 6) % PT
    oy = int(t * 14) % PT
    pat = PATTERN[oy:oy + H, ox:ox + W]
    img += (pat * PAT_MASK)[..., None] * np.array(GOLD, np.float32)
    # warm drifting glow
    cx = int(W / 2 + 160 * math.sin(t * 0.21))
    cy = int(TEXT_CY - 120 + 140 * math.sin(t * 0.13 + 1.0))
    x0, y0 = cx - GLOW_R, cy - GLOW_R
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(W - dx0, 2 * GLOW_R - sx0)
    h = min(H - dy0, 2 * GLOW_R - sy0)
    strength = 0.16 + 0.05 * math.sin(t * 0.8) + 0.12 * pulse
    img[dy0:dy0 + h, dx0:dx0 + w] += (GLOW[sy0:sy0 + h, sx0:sx0 + w] * strength)[..., None] * np.array((200, 150, 80), np.float32)
    img *= VIGNETTE
    frame = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # dust particles
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for p in PARTICLES:
        y = (p["y"] - t * p["sp"]) % H
        x = p["x"] + 14 * math.sin(t * 0.5 + p["ph"])
        a = int(255 * p["a"] * (0.55 + 0.45 * math.sin(t * 1.3 + p["ph"])))
        r = p["r"]
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD + (a,))
    return Image.alpha_composite(frame, layer)


# ----------------------------------------------------------- drawing ----
def text_w(s, f):
    return f.getlength(s)


def draw_center(layer, y, s, f, color, alpha, dy=0.0, anchor="mm"):
    if alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    d.text((W / 2, y + dy), s, font=f, fill=color + (int(255 * clamp(alpha)),), anchor=anchor)


def ornament(layer, y, alpha, width=260):
    """Thin gold divider with a diamond in the middle."""
    if alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    a = int(220 * clamp(alpha))
    half = width / 2 * ease_out(alpha)
    d.line([(W / 2 - half, y), (W / 2 - 18, y)], fill=GOLD + (a,), width=2)
    d.line([(W / 2 + 18, y), (W / 2 + half, y)], fill=GOLD + (a,), width=2)
    s = 9
    d.polygon([(W / 2, y - s), (W / 2 + s, y), (W / 2, y + s), (W / 2 - s, y)], outline=GOLD + (a,), width=2)


def shadowed(base, layer, radius=14, strength=0.85):
    """Composite layer over base with a soft dark halo for readability."""
    alpha = layer.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return base
    pad = radius * 3
    box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(W, bbox[2] + pad), min(H, bbox[3] + pad))
    sh_a = alpha.crop(box).filter(ImageFilter.GaussianBlur(radius))
    sh_a = sh_a.point(lambda v: int(v * strength))
    shadow = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (2, 10, 12, 0))
    shadow.putalpha(sh_a)
    base.alpha_composite(shadow, (box[0], box[1]))
    base.alpha_composite(layer)
    return base


# ----------------------------------------------------------- layout ----
LINE_H = 84          # visual line height
STANZA_GAP = 46      # extra gap between the two poetic lines


def layout_couplet(c):
    """Return list of (y, [(word, x, highlighted)], line_index, poetic_line)."""
    rows = []
    for pi, line in enumerate(c):
        for ws in wrap(line, F_VERSE, W - 2 * MARGIN):
            rows.append((pi, ws))
    total = len(rows) * LINE_H + STANZA_GAP
    y = TEXT_CY - total / 2 + LINE_H / 2
    out, prev_pi = [], 0
    space = F_VERSE.getlength(" ")
    for ri, (pi, ws) in enumerate(rows):
        if pi != prev_pi:
            y += STANZA_GAP
            prev_pi = pi
        lw = sum(F_VERSE.getlength(w) for w in ws) + space * (len(ws) - 1)
        x = W / 2 - lw / 2
        placed = []
        for w in ws:
            placed.append((w, x, clean(w) in HIGHLIGHT))
            x += F_VERSE.getlength(w) + space
        out.append((y, placed, ri, pi))
        y += LINE_H
    return out


LAYOUTS = [layout_couplet(c) for c in COUPLETS]


def draw_couplet(layer, lay, lt, dur):
    """lt: local time inside the card; dur: total card duration."""
    d = ImageDraw.Draw(layer)
    out_a = 1 - ease_in_out((lt - (dur - 0.55)) / 0.55)
    out_dy = -40 * ease_in_out((lt - (dur - 0.55)) / 0.55)
    wi = 0
    for y, placed, ri, pi in lay:
        for w, x, hl in placed:
            start = 0.15 + pi * 0.9 + wi * 0.075
            p = ease_out((lt - start) / 0.5)
            wi += 1
            a = p * out_a
            if a <= 0:
                continue
            col = GOLD if hl else CREAM
            d.text((x, y + (1 - p) * 26 + out_dy), w, font=F_VERSE, fill=col + (int(255 * a),), anchor="lm")


def draw_header(layer, idx, n, t_in, progress):
    a = ease_out(t_in / 0.8)
    if a <= 0:
        return
    d = ImageDraw.Draw(layer)
    # progress bar
    y = 238
    x0, x1 = MARGIN, W - MARGIN
    d.rounded_rectangle([x0, y - 3, x1, y + 3], radius=3, fill=(255, 255, 255, int(40 * a)))
    xe = x0 + (x1 - x0) * clamp(progress)
    if xe > x0 + 6:
        d.rounded_rectangle([x0, y - 3, xe, y + 3], radius=3, fill=GOLD + (int(230 * a),))
    d.text((x0, y + 44), "СУРА 96 · СГУСТОК", font=F_SMALL, fill=MUTED + (int(230 * a),), anchor="lm")
    if idx is not None:
        d.text((x1, y + 44), f"{idx} / {n}", font=F_SMALL_B, fill=GOLD + (int(240 * a),), anchor="rm")


# ------------------------------------------------------------ timeline ----
INTRO = 4.2
BISM = 4.3
OUTRO = 5.0
FINAL_EXTRA = 1.6


def card_dur(c):
    words = len(" ".join(c).split())
    return round(3.0 + 0.2 * words, 2)


DURS = [card_dur(c) for c in COUPLETS]
DURS[-1] += FINAL_EXTRA
STARTS = []
acc = INTRO + BISM
for dd in DURS:
    STARTS.append(acc)
    acc += dd
CONTENT_END = acc
TOTAL = CONTENT_END + OUTRO


def render(t):
    pulse = 0.0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    if t < INTRO:
        lt = t
        fade_out = 1 - ease_in_out((lt - (INTRO - 0.6)) / 0.6)
        pulse = ease_out(lt / 1.5) * fade_out
        # big Arabic "Iqra"
        a = ease_out((lt - 0.1) / 1.1) * fade_out
        sc = 0.92 + 0.08 * ease_out(lt / 2.0)
        if a > 0:
            tmp = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((W / 2, 260), "اقْرَأْ", font=F_ARAB_BIG, fill=GOLD + (int(255 * a),), anchor="mm")
            tmp = tmp.resize((int(W * sc), int(520 * sc)), Image.LANCZOS)
            layer.alpha_composite(tmp, (int((W - W * sc) / 2), int(690 - 260 * sc)))
        draw_center(layer, 930, "«Читай!»", F_TITLE_IT, CREAM, ease_out((lt - 0.7) / 0.8) * fade_out)
        ornament(layer, 1020, ease_out((lt - 1.0) / 0.9) * fade_out)
        a2 = ease_out((lt - 1.4) / 0.8) * fade_out
        draw_center(layer, 1095, "Первые слова Откровения,", F_SMALL_B, CREAM, a2, dy=(1 - a2) * 20)
        txt = "ниспосланные Пророку "
        tw = F_SMALL_B.getlength(txt) + F_SAW.getlength("ﷺ")
        if a2 > 0:
            dl = ImageDraw.Draw(layer)
            x0 = W / 2 - tw / 2
            yb = 1145 + (1 - a2) * 20
            dl.text((x0, yb), txt, font=F_SMALL_B, fill=CREAM + (int(255 * a2),), anchor="lm")
            dl.text((x0 + F_SMALL_B.getlength(txt), yb + 4), "ﷺ", font=F_SAW, fill=GOLD + (int(255 * a2),), anchor="lm")
        a3 = ease_out((lt - 2.0) / 0.8) * fade_out
        draw_center(layer, 1235, "СУРА 96 · «СГУСТОК»", F_SMALL, GOLD_SOFT, a3)

    elif t < INTRO + BISM:
        lt = t - INTRO
        fo = 1 - ease_in_out((lt - (BISM - 0.6)) / 0.6)
        a = ease_out(lt / 1.0) * fo
        draw_center(layer, 760, "بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", F_ARAB, GOLD, a, dy=(1 - a) * 24)
        ornament(layer, 880, ease_out((lt - 0.5) / 0.9) * fo, width=320)
        b = ease_out((lt - 0.9) / 0.9) * fo
        draw_center(layer, 975, "Во имя милосердного", F_TITLE, CREAM, b, dy=(1 - b) * 24)
        c = ease_out((lt - 1.3) / 0.9) * fo
        draw_center(layer, 1075, "милостивого Бога", F_TITLE, CREAM, c, dy=(1 - c) * 24)
        pulse = 0.5 * a

    elif t < CONTENT_END:
        for i, (s, dd) in enumerate(zip(STARTS, DURS)):
            if s <= t < s + dd:
                lt = t - s
                draw_couplet(layer, LAYOUTS[i], lt, dd)
                head_in = t - (INTRO + BISM)
                prog = (t - INTRO - BISM) / (CONTENT_END - INTRO - BISM)
                hdr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                draw_header(hdr, i + 1, len(COUPLETS), head_in, prog)
                fade_hdr = 1 - ease_in_out((t - (CONTENT_END - 0.5)) / 0.5)
                if fade_hdr < 1:
                    hdr.putalpha(hdr.getchannel("A").point(lambda v: int(v * fade_hdr)))
                layer.alpha_composite(hdr)
                if i == len(COUPLETS) - 1:
                    pulse = 0.6 * ease_out((lt - 1.2) / 1.5)
                break
    else:
        lt = t - CONTENT_END
        a = ease_out(lt / 0.9)
        ornament(layer, 700, a, width=360)
        draw_center(layer, 800, "Сура 96 · «Сгусток»", F_TITLE, CREAM, a, dy=(1 - a) * 20)
        b = ease_out((lt - 0.5) / 0.8)
        draw_center(layer, 890, "Поэтический перевод", F_TITLE_IT, GOLD, b)
        ornament(layer, 975, b, width=360)
        c = ease_out((lt - 1.1) / 0.8)
        draw_center(layer, 1080, "Сохрани, чтобы перечитать", F_SMALL_B, CREAM, c, dy=(1 - c) * 18)
        d_ = ease_out((lt - 1.5) / 0.8)
        draw_center(layer, 1135, "Подпишись — следующая сура скоро", F_SMALL_B, CREAM, d_, dy=(1 - d_) * 18)
        pulse = 0.4 * a
        # fade to the opening colour for a smooth loop
        end_f = ease_in_out((lt - (OUTRO - 0.6)) / 0.6)
        if end_f > 0:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * (1 - end_f))))

    frame = background(t, pulse)
    return shadowed(frame, layer).convert("RGB")


def main():
    if PREVIEW:
        times = [1.5, 3.2, INTRO + 2.5] + [s + dd * 0.7 for s, dd in zip(STARTS, DURS)] + [CONTENT_END + 2.6]
        for k, t in enumerate(times):
            render(t).save(OUT / f"preview_{k:02d}.png")
        print("total", TOTAL)
        return
    render(INTRO + BISM + DURS[0] * 0.75).save(OUT / "cover.png")
    n = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", str(OUT / "sura96_reels.mp4")]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(render(f / FPS).tobytes())
        if f % 300 == 0:
            print(f"{f}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    print("done", TOTAL, "s")


if __name__ == "__main__":
    main()
