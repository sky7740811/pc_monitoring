"""Create a high-quality modern icon for PC Monitor."""
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 512
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pc-monitor.ico')


def create_icon():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded square base
    margin = 24
    rect = (margin, margin, SIZE - margin, SIZE - margin)
    draw.rounded_rectangle(rect, radius=60, fill=(10, 14, 23, 255))

    # Gradient overlay (subtle cyan glow at top)
    for y in range(SIZE // 2):
        alpha = int(28 * (1 - y / (SIZE // 2)))
        draw.line([(margin + 6, y + margin + 6), (SIZE - margin - 6, y + margin + 6)],
                  fill=(0, 200, 255, alpha))

    # Border glow
    draw.rounded_rectangle(rect, radius=60, outline=(0, 200, 255, 40), width=3)

    # Center circle (stylized CPU/GPU die)
    cx, cy = SIZE // 2, SIZE // 2 - 12
    outer_r = 160
    draw.ellipse([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
                 outline=(0, 212, 255, 180), width=5)

    # Inner circle
    inner_r = 120
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                 fill=(0, 212, 255, 25), outline=(0, 212, 255, 100), width=3)

    # Hexagonal grid pattern (tech/cpu feel)
    import math
    for ring in range(1, 4):
        n = ring * 6
        for i in range(n):
            angle = i * 2 * math.pi / n - math.pi / 2
            r = 50 + ring * 30
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            dot_r = 4 + (3 - ring)
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r],
                         fill=(0, 212, 255, 180 - ring * 30))

    # Connecting lines (like circuits)
    for i in range(6):
        angle = i * 2 * math.pi / 6
        px1 = cx + 50 * math.cos(angle)
        py1 = cy + 50 * math.sin(angle)
        px2 = cx + 140 * math.cos(angle)
        py2 = cy + 140 * math.sin(angle)
        draw.line([(px1, py1), (px2, py2)], fill=(0, 212, 255, 60), width=2)

    # Wave lines at bottom (monitoring chart feel)
    wave_y = cy + outer_r + 36
    colors = [(0, 212, 255, 160), (124, 58, 237, 120), (255, 107, 53, 90)]
    for wi, (rc, gc, bc, ac) in enumerate(colors):
        pts = []
        for x in range(cx - 80, cx + 81, 6):
            rel = (x - (cx - 80)) / 160
            y = wave_y + wi * 18 + 20 + math.sin(rel * 5 + wi * 1.8) * 12 + math.sin(rel * 8 + wi * 0.6) * 6
            pts.append((x, int(y)))
        if len(pts) > 1:
            draw.line(pts, fill=(rc, gc, bc, ac), width=3)

    # "PC" text
    try:
        font_big = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 120)
        font_small = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 32)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((cx, cy - 8), 'PC', fill=(232, 236, 244, 235), font=font_big, anchor='mm')
    draw.text((cx, cy + 46), 'MONITOR', fill=(0, 212, 255, 130), font=font_small, anchor='mm')

    # Save as ICO with multiple resolutions
    img_256 = img.resize((256, 256), Image.LANCZOS)
    img_128 = img.resize((128, 128), Image.LANCZOS)
    img_96 = img.resize((96, 96), Image.LANCZOS)
    img_64 = img.resize((64, 64), Image.LANCZOS)
    img_48 = img.resize((48, 48), Image.LANCZOS)
    img_32 = img.resize((32, 32), Image.LANCZOS)

    img_256.save(OUT, format='ICO', sizes=[(256, 256), (128, 128),
                                            (96, 96), (64, 64), (48, 48), (32, 32)])
    print(f'Icon saved: {OUT}')
    print(f'Sizes: 256,128,96,64,48,32')


if __name__ == '__main__':
    create_icon()
