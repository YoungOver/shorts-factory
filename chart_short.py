"""Вертикальный шортс 1080x1920: хук сверху, график рисуется слева направо, цена и процент догоняют линию.

python chart_short.py out.mp4 [--title "..."] [--seed N]
Данные — синтетические (случайное блуждание), в реальной работе подставляется выгрузка котировок.
"""
import argparse
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BG = (10, 12, 18)
UP, DOWN = (34, 214, 130), (255, 84, 84)
FB = 'C:/Windows/Fonts/arialbd.ttf'
FR = 'C:/Windows/Fonts/arial.ttf'


def series(seed, n=240):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0016, 0.012, n)
    steps[n // 2:n // 2 + 12] -= 0.02  # просадка посередине — драматургия
    return 100 * np.exp(np.cumsum(steps))


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def render(out, title, seed, dur=14.0):
    y = series(seed)
    n_frames = int(dur * FPS)
    draw_frames = int(n_frames * 0.78)
    ch = (80, 620, W - 80, 1500)  # область графика
    lo, hi = y.min(), y.max()
    pad = (hi - lo) * 0.12
    lo, hi = lo - pad, hi + pad
    px = lambda i: ch[0] + (ch[2] - ch[0]) * i / (len(y) - 1)
    py = lambda v: ch[3] - (ch[3] - ch[1]) * (v - lo) / (hi - lo)
    pts = [(px(i), py(v)) for i, v in enumerate(y)]

    f_hook = ImageFont.truetype(FB, 84)
    f_big = ImageFont.truetype(FB, 120)
    f_mid = ImageFont.truetype(FB, 46)
    f_sm = ImageFont.truetype(FR, 34)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen([ff, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '20', str(out)],
                            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    base = Image.new('RGB', (W, H), BG)
    bd = ImageDraw.Draw(base)
    for gy in np.linspace(ch[1], ch[3], 6):  # сетка
        bd.line([(ch[0], gy), (ch[2], gy)], fill=(32, 36, 48), width=2)
        val = lo + (hi - lo) * (ch[3] - gy) / (ch[3] - ch[1])
        bd.text((ch[2] - 4, gy - 40), f'{val:.0f}', font=f_sm, fill=(90, 96, 112), anchor='ra')
    title = title.format(chg=f'{(y[-1] / y[0] - 1) * 100:+.0f}%')
    lines = wrap(bd, title, f_hook, W - 160)
    for k, ln in enumerate(lines):
        bd.text((80, 150 + k * 100), ln, font=f_hook, fill=(255, 255, 255))
    bd.text((80, H - 105), '@your_channel', font=f_mid, fill=(120, 126, 142))
    bd.rounded_rectangle((W - 250, H - 125, W - 80, H - 55), 18, outline=(120, 126, 142), width=3)
    bd.text((W - 165, H - 90), 'LOGO', font=f_mid, fill=(120, 126, 142), anchor='mm')

    for fr in range(n_frames):
        t = min(1.0, fr / draw_frames)
        t = 1 - (1 - t) ** 2.2  # ease-out
        m = max(2, int(t * (len(y) - 1)) + 1)
        cur = y[m - 1]
        chg = (cur / y[0] - 1) * 100
        col = UP if chg >= 0 else DOWN
        img = base.copy()
        seg = pts[:m]
        # заливка под линией
        poly = Image.new('L', (W, H), 0)
        ImageDraw.Draw(poly).polygon(seg + [(seg[-1][0], ch[3]), (seg[0][0], ch[3])], fill=70)
        img.paste(Image.new('RGB', (W, H), col), (0, 0), poly.filter(ImageFilter.GaussianBlur(30)))
        # свечение и линия
        glow = Image.new('RGB', (W, H), (0, 0, 0))
        ImageDraw.Draw(glow).line(seg, fill=col, width=18, joint='curve')
        img.paste(col, (0, 0), glow.convert('L').filter(ImageFilter.GaussianBlur(16)).point(lambda v: v * 0.55))
        d = ImageDraw.Draw(img)
        d.line(seg, fill=col, width=7, joint='curve')
        x, yy = seg[-1]
        d.ellipse((x - 16, yy - 16, x + 16, yy + 16), fill=(255, 255, 255))
        d.ellipse((x - 9, yy - 9, x + 9, yy + 9), fill=col)
        # счётчик
        d.text((80, 1530), f'{cur:,.2f}'.replace(',', ' '), font=f_big, fill=(255, 255, 255))
        d.rounded_rectangle((80, 1680, 380, 1760), 22, fill=col)
        d.text((230, 1720), f'{chg:+.1f}%', font=f_mid, fill=BG, anchor='mm')
        if fr > draw_frames:  # финальный акцент
            a = min(1.0, (fr - draw_frames) / 12)
            r = int(28 + 40 * a)
            d.ellipse((x - r, yy - r, x + r, yy + r), outline=col, width=4)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()
    print('ok', out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--title', default='Этот график за год сделал {chg}. Смотри, что было в середине')
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    render(Path(a.out), a.title, a.seed)
