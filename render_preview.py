"""Render an inspection sheet from the routed board, with one panel per copper layer."""
from collections import Counter
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
from board import VIA_DIA, VIA_DRILL
from verify import EDGE

ROOT=Path(__file__).parent
PALETTE = ("#f5aa66","#a8db96","#6bcddf","#c9a8fc")
TITLES=("Front copper","Inner 1 / ground priority","Inner 2 / supply priority","Back copper")
SCALE=1.13
BG="#142123"
INK="#f4f4e9"
SUB="#acbfbd"

def font(size,bold=False,mono=False):
    options = ["consola.ttf", "DejaVuSansMono.ttf"] if mono else [
        "seguisb.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in options:
        try:
            return ImageFont.truetype(path,size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)

def dot(draw, center, radius, fill, outline=None):
    x,y=center
    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=fill,outline=outline,width=1)

def panel(draw, layout, ox, oy, layer):
    color=PALETTE[layer]
    fx=lambda x,y:(ox+54+x*SCALE,oy+65+y*SCALE)
    draw.rounded_rectangle((ox,oy,ox+560,oy+428),radius=14,fill="#1c2d2e",outline="#3d5351",width=1)
    draw.text((ox+22,oy+13),f"L{layer+1}   {TITLES[layer]}",font=font(21,bold=True),fill=INK)
    draw.polygon([fx(x,y) for x,y in EDGE],fill="#263f3b",outline="#74928b",width=2)
    for x in range(20,400,20):
        draw.line([fx(x,13),fx(x,287)],fill="#2d4743")
    for y in range(20,300,20):
        draw.line([fx(13,y),fx(387,y)],fill="#2d4743")
    tracks=0
    for net,a,b in layout["traces"]:
        if a[2]!=layer:
            continue
        tracks+=1
        draw.line([fx(*a[:2]),fx(*b[:2])],fill=color,width=2)
    for net,x,y in layout["vias"]:
        dot(draw,fx(x,y),VIA_DIA/.254*SCALE/2,color)
        dot(draw,fx(x,y),max(1,VIA_DRILL/.254*SCALE/2),"#273c39")
    for item in layout["parts"]:
        for p in item["pads"]:
            center=fx(p["x"],p["y"])
            if p["drill"]:
                dot(draw,center,3.65,"#dfce94")
                dot(draw,center,1.9,"#20302d")
            elif layer==0:
                x,y=center
                rx,ry=p["width"]/.254*SCALE/2,p["height"]/.254*SCALE/2
                draw.rectangle((x-rx,y-ry,x+rx,y+ry),fill="#dfce94")
        if layer==0 and (item["ref"].startswith(("J","U","Q")) or item["ref"] in {"R2","TP1","TP2"}):
            x,y=fx(item["x"],item["y"])
            draw.text((x+7,y-13),item["ref"],font=font(11,mono=True),fill="#f8e7b3",stroke_width=1,stroke_fill="#263f3b")
    for x,y in layout["mounting"]:
        dot(draw,fx(x,y),7.1,"#142123","#b7c6be")
    draw.text((ox+20,oy+408),f"{tracks} copper segments",font=font(13,mono=True),fill=SUB)

def render(layout, result):
    image=Image.new("RGB",(1220,1080),BG)
    draw=ImageDraw.Draw(image)
    draw.text((42,31),"Meridian I/O carrier",font=font(48,bold=True),fill=INK)
    draw.text((45,92),"Four-layer PCB layout  /  101.60 × 76.20 mm  /  millimetre model",font=font(21),fill=SUB)
    for index,(x,y) in enumerate(((42,146),(618,146),(42,588),(618,588))):
        panel(draw,layout,x,y,index)
    draw.text((44,1038),
        f'{result["nets"]} nets   /   {result["electrical_pads"]} electrical pads   /   {result["plated_vias"]} plated vias   /   {len(result["errors"])} geometry violations',
        font=font(16,mono=True),fill=SUB)
    (ROOT/"media").mkdir(exist_ok=True)
    image.save(ROOT/"media"/"four-layer-inspection.png",optimize=True)

if __name__=="__main__":
    render(json.loads((ROOT/"layout.json").read_text(encoding="utf-8")),
           json.loads((ROOT/"verification.json").read_text(encoding="utf-8")))
