"""SwipePads weekly digest cover v2 — gradient title, cyan glow, finger-pad motif."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1200, 630
BG = (9, 10, 18)
INK = (245, 246, 252)
MUTED = (245, 246, 252, 150)
CYAN = (15, 236, 255)
CYAN2 = (142, 215, 255)

F = "C:/Windows/Fonts/"
def font(name, size):
    for f in name:
        try: return ImageFont.truetype(F + f, size)
        except OSError: pass
    return ImageFont.truetype(F + "arialbd.ttf", size)

f_kicker = font(["bahnschrift.ttf", "segoeuib.ttf"], 30)
f_title  = font(["segoeuib.ttf"], 108)
f_date   = font(["segoeui.ttf", "arial.ttf"], 32)
f_pill   = font(["segoeuib.ttf"], 25)
f_foot   = font(["segoeuib.ttf"], 24)

img = Image.new("RGB", (W, H), BG)

# --- cyan radial glow top-right (blurred) ---
glow = Image.new("RGB", (W, H), BG)
gd = ImageDraw.Draw(glow)
gd.ellipse([W-420, -260, W+260, 300], fill=(13, 60, 84))
gd.ellipse([W-300, -160, W+120, 180], fill=(16, 96, 122))
glow = glow.filter(ImageFilter.GaussianBlur(90))
img = Image.blend(img, glow, 0.85)
d = ImageDraw.Draw(img, "RGBA")

# --- finger-pad motif (4 glowing rings, right side) ---
pads = [(985, 300, 46), (1068, 218, 34), (1075, 386, 30), (930, 175, 24)]
halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(halo)
for x, y, r in pads:
    hd.ellipse([x-r-18, y-r-18, x+r+18, y+r+18], fill=(15, 236, 255, 70))
halo = halo.filter(ImageFilter.GaussianBlur(22))
img.paste(halo, (0, 0), halo)
d = ImageDraw.Draw(img, "RGBA")
for i, (x, y, r) in enumerate(pads):
    d.ellipse([x-r, y-r, x+r, y+r], outline=CYAN, width=4)
    d.ellipse([x-r+12, y-r+12, x+r-12, y+r-12], fill=(15, 236, 255, 210) if i == 0 else (26, 26, 37, 235))
# connecting hairlines
d.line([pads[0][0], pads[0][1], pads[1][0], pads[1][1]], fill=(15, 236, 255, 60), width=2)
d.line([pads[0][0], pads[0][1], pads[2][0], pads[2][1]], fill=(15, 236, 255, 60), width=2)
d.line([pads[1][0], pads[1][1], pads[3][0], pads[3][1]], fill=(15, 236, 255, 60), width=2)

# --- kicker ---
d.ellipse([80, 92, 98, 110], fill=CYAN)
d.text((118, 84), "THIS WEEK IN", font=f_kicker, fill=CYAN2)

# --- gradient title (mask technique) ---
title = "MOBILE\nGAMING"
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
md.multiline_text((76, 140), title, font=f_title, fill=255, spacing=6)
grad = Image.new("RGB", (W, H))
gdr = ImageDraw.Draw(grad)
for x in range(W):
    t = x / W
    c = tuple(int(a + (b - a) * t) for a, b in zip((142, 215, 255), (15, 236, 255)))
    gdr.line([(x, 0), (x, H)], fill=c)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img, "RGBA")

# --- date ---
d.text((80, 420), "July 9, 2026", font=f_date, fill=MUTED)
d.text((262, 420), "·  issue #1", font=f_date, fill=(15, 236, 255, 190))

# --- pills ---
pills = ["NARUTO × PUBG", "PERSONA 5 × CODM", "CR: NO MORE LEVELS"]
x, y = 80, 486
for p in pills:
    w = d.textlength(p, font=f_pill)
    d.rounded_rectangle([x, y, x+w+44, y+52], radius=26, fill=(26, 26, 37, 230), outline=(15, 236, 255, 120), width=2)
    d.text((x+22, y+13), p, font=f_pill, fill=INK)
    x += w + 60

# --- footer ---
d.text((80, 574), "SWIPEPADS WEEKLY", font=f_foot, fill=(15, 236, 255, 200))
d.text((342, 574), "outplay.game", font=f_foot, fill=MUTED)

img.save(r"C:\Claude\projects\swipe-pads\blog\2026-07-09-cover.png", "PNG")
print("saved v2", img.size)
