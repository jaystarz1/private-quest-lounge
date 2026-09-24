"""Original 1940s-inspired Paris poster art and woven gingham scene textures."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random
ROOT = Path(__file__).parent / 'art'
FONTS = Path('/System/Library/Fonts/Supplemental')
def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ('Arial Narrow Bold.ttf' if bold else 'Georgia.ttf')), size)
def title(draw, text, y, size, color, bold=False):
    draw.text((360,y), text, font=font(size,bold), fill=color, anchor='mt')
cream='#eadbb8'; ink='#233b38'; red='#a13b30'; gold='#c39148'
for year in (1946,1948):
    im=Image.new('RGB',(720,1024),cream); d=ImageDraw.Draw(im)
    d.rectangle((28,28,692,996),outline=ink,width=4)
    title(d,'PARIS',63,132,ink,True)
    title(d,'LE CAFÉ DU PARC' if year==1948 else 'LES SOIRS DE PARIS',220,30,red,True)
    d.ellipse((140,310,580,750),fill=gold if year==1946 else '#b8674e')
    if year==1946:
        # Screenprint-like Eiffel silhouette, river and a distant roofline.
        d.polygon([(350,294),(370,294),(387,463),(426,630),(498,792),(419,792),(382,682),(338,682),(301,792),(222,792),(294,630),(333,463)],fill=ink)
        d.line((360,271,360,320),fill=ink,width=6)
        for y,x0,x1 in [(474,320,400),(628,287,433),(679,263,457)]:d.rectangle((x0,y,x1,y+12),fill=cream)
        d.ellipse((323,718,397,832),fill=cream)
        for x,h in [(67,57),(111,81),(161,52),(526,74),(572,91),(620,55)]:
            d.rectangle((x,784-h,x+35,807),fill=red)
        d.line((67,827,653,827),fill=ink,width=4)
    else:
        d.ellipse((185,684,535,752),fill=ink)
        d.ellipse((200,690,520,728),fill=cream)
        d.ellipse((457,514,563,638),outline=ink,width=22)
        d.rounded_rectangle((217,498,481,705),radius=70,fill=cream,outline=ink,width=10)
        d.ellipse((218,475,482,547),fill=ink)
        d.arc((265,326,351,494),95,275,fill=cream,width=10)
        d.arc((360,297,446,476),95,275,fill=cream,width=10)
        title(d,'CAFÉ • CROISSANTS',792,33,ink,True)
    title(d,'PROMENADE AU BORD DE LA SEINE' if year==1946 else 'UN RENDEZ-VOUS À PARIS',866,25,ink)
    title(d,str(year),920,33,red)
    rng=random.Random(year)
    px=im.load()
    for y in range(1024):
        for x in range(720):
            v=rng.randint(-7,7)
            px[x,y]=tuple(max(0,min(255,c+v)) for c in px[x,y])
    im.save(ROOT/f'paris-{year}.png')
im=Image.new('RGB',(512,512)); pix=im.load()
for y in range(512):
    for x in range(512):
        n=(x//32)%2+(y//32)%2
        rgb=((243,231,208),(210,141,133),(163,48,49))[n]
        weave=3 if (x+y)%4<2 else -3
        pix[x,y]=tuple(c+weave for c in rgb)
im.save(ROOT/'gingham.png')
