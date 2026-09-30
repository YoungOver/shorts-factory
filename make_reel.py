"""Сценарий -> вертикальный ролик 1080x1920: озвучка (edge-tts), кадры (PIL), субтитры, склейка (ffmpeg).

python make_reel.py script.txt out.mp4
Каждая строка сценария = отдельная сцена.
"""
import asyncio
import subprocess
import sys
import textwrap
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1080, 1920
VOICE = 'ru-RU-DmitryNeural'
PALETTES = [((20, 24, 60), (120, 60, 220)), ((10, 40, 60), (0, 170, 200)), ((50, 16, 40), (230, 70, 120)),
            ((16, 40, 24), (60, 200, 120)), ((40, 30, 10), (240, 170, 40))]
FONT = 'C:/Windows/Fonts/arialbd.ttf'


def frame(text, idx, total, path):
    c1, c2 = PALETTES[idx % len(PALETTES)]
    img = Image.new('RGB', (W, H), c1)
    d = ImageDraw.Draw(img)
    for y in range(H):  # диагональный градиент
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W * .15, H * .2, W * .95, H * .6), fill=c2)
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), .35)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 92)
    lines = textwrap.wrap(text, 16)
    y = H // 2 - len(lines) * 60
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2 + 4, y + 6), ln, font=f, fill=(0, 0, 0))
        d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255))
        y += 120
    small = ImageFont.truetype(FONT, 38)
    d.text((70, 120), f'{idx + 1:02d} / {total:02d}', font=small, fill=(255, 255, 255))
    bar = int((idx + 1) / total * (W - 140))
    d.rounded_rectangle((70, H - 160, W - 70, H - 148), 6, fill=(255, 255, 255, 60))
    d.rounded_rectangle((70, H - 160, 70 + bar, H - 148), 6, fill=(255, 255, 255))
    img.save(path)


async def tts(text, path):
    await edge_tts.Communicate(text, VOICE, rate='+8%').save(str(path))


def dur(path):
    out = subprocess.run([FF, '-i', str(path)], capture_output=True, text=True).stderr
    h, m, s = out.split('Duration: ')[1].split(',')[0].split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def main(script, out):
    work = Path(out).with_suffix('')
    work.mkdir(exist_ok=True)
    scenes = [s.strip() for s in Path(script).read_text(encoding='utf-8').splitlines() if s.strip()]
    parts = []
    for i, s in enumerate(scenes):
        png, mp3, mp4 = work / f'{i}.png', work / f'{i}.mp3', work / f'{i}.mp4'
        frame(s, i, len(scenes), png)
        asyncio.run(tts(s, mp3))
        d = dur(mp3) + 0.25
        # плавный зум (Ken Burns) + звук сцены
        subprocess.run([FF, '-y', '-loop', '1', '-i', str(png), '-i', str(mp3), '-t', f'{d:.2f}',
                        '-vf', f"zoompan=z='min(zoom+0.0009,1.08)':d={int(d * 30)}:s={W}x{H}:fps=30,format=yuv420p",
                        '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', '-shortest', str(mp4)],
                       capture_output=True, check=True)
        parts.append(mp4)
    lst = work / 'list.txt'
    lst.write_text(''.join(f"file '{p.name}'\n" for p in parts), encoding='utf-8')
    subprocess.run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', str(lst.resolve()), '-c', 'copy', str(Path(out).resolve())],
                   capture_output=True, check=True, cwd=work)
    print(f'{len(scenes)} сцен, {dur(out):.1f} с -> {out}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
