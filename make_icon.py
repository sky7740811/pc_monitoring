"""Modern flat icon for PC Monitor — borderless, 256px primary."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os, math

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pc-monitor.ico')
S = 512

def draw_icon(size):
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    s = size / S  # scale factor

    cx, cy = size//2, size//2 - int(14*s)

    # Glow circle behind the icon
    r_glow = int(180*s)
    glow = Image.new('RGBA', (size,size), (0,0,0,0))
    gdraw = ImageDraw.Draw(glow)
    for rr in range(r_glow, 0, -1):
        a = int(12 * (1 - rr/r_glow))
        gdraw.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], fill=(0,212,255,a))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(20*s)))
    img = Image.alpha_composite(img, glow)

    # Outer ring
    or_ = int(150*s)
    draw.ellipse([cx-or_, cy-or_, cx+or_, cy+or_], outline=(0,212,255,int(140*s)), width=max(1,int(4*s)))

    # Inner ring
    ir_ = int(110*s)
    draw.ellipse([cx-ir_, cy-ir_, cx+ir_, cy+ir_], fill=(0,212,255,int(15*s)), outline=(0,212,255,int(70*s)), width=max(1,int(2*s)))

    # Dot grid (CPU cores)
    for ring in range(1, 5):
        n = ring * 6
        for i in range(n):
            angle = i * 2*math.pi/n
            r = int((40 + ring*22)*s)
            px, py = int(cx + r*math.cos(angle)), int(cy + r*math.sin(angle))
            ds = max(2, int((5-ring)*s))
            draw.ellipse([px-ds, py-ds, px+ds, py+ds], fill=(0,200,255,max(80, 200-ring*35)))

    # Connecting lines
    for i in range(6):
        a = i * 2*math.pi/6
        p1 = (cx + int(45*s*math.cos(a)), cy + int(45*s*math.sin(a)))
        p2 = (cx + int(130*s*math.cos(a)), cy + int(130*s*math.sin(a)))
        draw.line([p1, p2], fill=(0,212,255,int(40*s)), width=max(1,int(2*s)))

    # Wave lines (monitoring)
    wy = cy + int(165*s)
    colors = [(0,212,255,160), (124,58,237,120), (255,107,53,90)]
    for wi, c in enumerate(colors):
        pts = []
        ww = int(90*s)
        for x in range(cx-ww, cx+ww+1, max(1,int(4*s))):
            rel = (x - (cx-ww)) / (ww*2)
            yv = wy + wi*int(18*s) + int(18*s) + math.sin(rel*5 + wi*1.8)*int(12*s) + math.sin(rel*8 + wi*0.6)*int(6*s)
            pts.append((x, int(yv)))
        if len(pts) > 1:
            draw.line(pts, fill=c, width=max(1,int(3*s)))

    # Text
    if size >= 64:
        try:
            fb = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', max(24, int(100*s)))
            fs = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', max(10, int(28*s)))
        except:
            fb = fs = ImageFont.load_default()
        draw.text((cx, cy - int(6*s)), 'PC', fill=(232,236,244,220), font=fb, anchor='mm')
        draw.text((cx, cy + int(46*s)), 'MONITOR', fill=(0,212,255,int(100*s)), font=fs, anchor='mm')

    return img


img_256 = draw_icon(256)
img_128 = draw_icon(128)
img_96  = draw_icon(96)
img_64  = draw_icon(64)
img_48  = draw_icon(48)
img_32  = draw_icon(32)
img_16  = draw_icon(16)

img_256.save(OUT, format='ICO', sizes=[(256,256),(128,128),(96,96),(64,64),(48,48),(32,32),(16,16)])
print(f'Saved: {OUT}')
print('Sizes: 256,128,96,64,48,32,16')
