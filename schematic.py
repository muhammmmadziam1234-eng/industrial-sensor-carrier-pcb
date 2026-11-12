"""Generate the review schematic from the same pin map used for the board."""

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from xml.sax.saxutils import escape

from board import PARTS
from design_ids import PROJECT, ROOT_UUID, design_uuid, footprint_id


OUT = Path(__file__).parent / "cad"
STEP = 1.27

@dataclass(frozen=True)
class Pin:
    number: int
    name: str
    x: int
    y: int
    angle: int
    kind: str = "passive"

@dataclass
class Symbol:
    name: str
    prefix: str
    pins: list
    graphic: str
    names: bool = False


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def units(value):
    return f"{value*STEP:.2f}"


def xy(x, y):
    return f"{units(x)} {units(y)}"


def effects(size=1.27, extra=""):
    return f"(effects (font (size {size} {size})) {extra})"


def uuid(label):
    return f"(uuid {q(design_uuid(label))})"


def body(x1, y1, x2, y2):
    return (f"(rectangle (start {xy(x1,y1)}) (end {xy(x2,y2)}) "
            "(stroke (width 0.254) (type default)) (fill (type background)))")


def line(*points):
    coords = " ".join(f"(xy {xy(x,y)})" for x, y in points)
    return f"(polyline (pts {coords}) (stroke (width 0.254) (type default)) (fill (type none)))"


def drawing(part):
    ref = part.ref
    if ref == "U1":
        names = ("R", "~{RE}", "DE", "D", "GND", "A", "B", "VCC")
        kinds = ("output", "input", "input", "input", "power_in", "bidirectional", "bidirectional", "power_in")
        positions = [(-10,3,0),(-10,1,0),(-10,-1,0),(-10,-3,0),
                     (10,-3,180),(10,-1,180),(10,1,180),(10,3,180)]
        pins = [Pin(i+1,name,*pos,kind) for i,(name,pos,kind) in enumerate(zip(names,positions,kinds))]
        return Symbol("THVD1410","U",pins,body(-7,5,7,-5),True)
    if ref.startswith("Q"):
        pins = [Pin(1,"G",-7,0,0),Pin(2,"S",7,-2,180),Pin(3,"D",7,2,180)]
        graphic = " ".join((line((-4,0),(-2,0)),line((-2,-3),(-2,3)),
                            line((0,-3),(0,3)),line((0,2),(4,2)),line((0,-2),(4,-2)),
                            line((3,-1),(1,0),(3,1),(3,-1))))
        return Symbol("NMOS_GSD","Q",pins,graphic)
    if ref.startswith("TP"):
        graphic = "(circle (center 0 0) (radius 1.0) (stroke (width 0.254) (type default)) (fill (type none)))"
        return Symbol("TestPoint","TP",[Pin(1,"TP",-3,0,0)],graphic)
    if ref.startswith("J"):
        count = len(part.pads)
        name = "Controller_2x12" if ref == "J1" else f"Connector_{count}"
        pins = []
        for index in range(count):
            if ref == "J1":
                left = index % 2 == 0
                pins.append(Pin(index+1,str(index+1),-7 if left else 7,11-2*(index//2),0 if left else 180))
            else:
                pins.append(Pin(index+1,str(index+1),-5,count-1-2*index,0))
        tall = 12 if ref == "J1" else count
        return Symbol(name,"J",pins,body(-4 if ref == "J1" else -2,tall,4 if ref == "J1" else 2,-tall),True)
    pins = [Pin(1,"1",-5,0,0),Pin(2,"2",5,0,180)]
    if ref.startswith("R"):
        return Symbol("Resistor","R",pins,body(-2,1,2,-1))
    if ref.startswith("C"):
        graphic = " ".join((line((-2,0),(-1,0)),line((1,0),(2,0)),
                            line((-1,-2),(-1,2)),line((1,-2),(1,2))))
        return Symbol("Capacitor","C",pins,graphic)
    if ref.startswith("D"):
        graphic = " ".join((line((-2,0),(-1,0)),line((1,0),(2,0)),
                            line((-1,-2),(-1,2)),line((1,-2),(-1,0),(1,2),(1,-2))))
        return Symbol("LED_KA","D",pins,graphic)
    raise ValueError(f"No symbol for {ref}")


def library_symbol(symbol, embedded):
    name = symbol.name
    pin_settings = "(pin_names (offset 0.45))" if symbol.names else "(pin_names hide)"
    in_bom = "no" if symbol.prefix == "TP" else "yes"
    output = [f"(symbol {q('Meridian:'+name if embedded else name)} {pin_settings}",
              f"(in_bom {in_bom}) (on_board yes)",
              f'(property "Reference" {q(symbol.prefix)} (at 0 7.62 0) {effects()})',
              f'(property "Value" {q(name)} (at 0 5.08 0) {effects()})',
              f'(property "Footprint" "" (at 0 0 0) {effects(extra="(hide yes)")})',
              f'(property "Datasheet" "" (at 0 0 0) {effects(extra="(hide yes)")})',
              f'(symbol {q(name+"_0_1")} {symbol.graphic})',
              f'(symbol {q(name+"_1_1")}']
    for pin in symbol.pins:
        output.append(f'(pin {pin.kind} line (at {xy(pin.x,pin.y)} {pin.angle}) (length {units(3)}) '
                      f'(name {q(pin.name)} {effects(0.9)}) (number {q(pin.number)} {effects(0.9)}))')
    output += [")",")"]
    return "\n".join(output)


LOCATIONS = {
    "J1": (56,71), "J2": (56,108), "J3": (56,133), "J4": (56,160),
    "J5": (56,186), "J6": (56,210), "J7": (56,235), "J8": (56,264),
    "U1": (195,75), "R1": (137,92), "R2": (246,91), "JP1": (245,110),
    "C1": (194,111), "C2": (194,128), "JP3": (175,177),
    "C3": (175,201), "C4": (175,219), "JP2": (319,64),
    "R3": (319,87), "R4": (319,103),
    "R5": (319,135), "R6": (382,135), "C5": (338,151), "C6": (401,151),
    "R7": (303,208), "R8": (303,228), "Q1": (352,208),
    "R9": (303,255), "R10": (303,275), "Q2": (352,255),
    "R11": (408,208), "D1": (440,208), "R12": (408,255), "D2": (440,255),
}
for idx in range(1,13):
    LOCATIONS[f"TP{idx}"] = (115 + (idx-1)%3*49, 249 + (idx-1)//3*14)


ROTATIONS = {"C5":270,"C6":270,"D1":180,"D2":180}
EXPLICIT_PINS = {
    ("R3",2),("R4",2),("R5",2),("C5",1),("R6",2),("C6",1),
    ("R11",2),("D1",2),("R12",2),("D2",2),
}


def rotated(x,y,angle):
    return {0:(x,y),90:(y,-x),180:(-x,-y),270:(-y,x)}[angle]


def wire(tag,a,b):
    return f'(wire (pts (xy {xy(*a)}) (xy {xy(*b)})) (stroke (width 0) (type default)) {uuid(tag+"/wire")})'


def label(tag,net,at,west=False):
    angle,justify=(180,"right") if west else (0,"left")
    return f'(label {q(net)} (at {xy(*at)} {angle}) {effects(1.12,f"(justify {justify} bottom)")} {uuid(tag+"/label")})'


def junction(tag,at):
    return f'(junction (at {xy(*at)}) (diameter 0) (color 0 0 0 0) {uuid(tag+"/junction")})'


def label_and_wire(ref, pin, net, x, y):
    rotation=ROTATIONS.get(ref,0)
    px,py=rotated(pin.x,-pin.y,rotation)
    dx,dy=rotated(*{0:(-1,0),180:(1,0),90:(0,1),270:(0,-1)}[pin.angle],rotation)
    start=(x+px,y+py)
    end=(start[0]+4*dx,start[1]+4*dy)
    tag=f"{ref}.{pin.number}"
    return [wire(tag,start,end),label(tag,net,end,west=dx<0)]


def explicit_wires():
    lines=[]
    for index,(x,y) in enumerate(((338,135),(401,135))):
        tag=f"adc-branch-{index}"
        node=(x,y)
        end=(x+10,y)
        lines.extend([
            wire(tag+"-in",(x-14,y),node),
            wire(tag+"-out",node,end),
            wire(tag+"-cap",node,(x,146)),
            junction(tag,node),
            label(tag,f"ADC{index}",end),
        ])
    lines.extend([
        wire("i2c-pullup-top",(324,87),(343,87)),
        wire("i2c-pullup-spine",(343,87),(343,103)),
        wire("i2c-pullup-bottom",(324,103),(343,103)),
        label("i2c-pullup","I2C_PULLUP",(343,87)),
    ])
    for index,y in enumerate((208,255)):
        tag=f"indicator-{index}"
        lines.extend([wire(tag+"-in",(413,y),(424,y)),wire(tag+"-out",(424,y),(435,y)),
                      label(tag,f"LED_AN{index}",(424,y))])
    return lines


def instance(part, symbol, x, y):
    ref=part.ref
    in_bom = "no" if ref.startswith("TP") else "yes"
    offset = max(pin.y for pin in symbol.pins) + 4
    props = [
        f'(property "Reference" {q(ref)} (at {xy(x,y-offset)} 0) {effects(1.27)})',
        f'(property "Value" {q(part.value)} (at {xy(x,y-offset+2)} 0) {effects(1.12)})',
        f'(property "Footprint" {q(footprint_id(asdict(part)))} (at {xy(x,y)} 0) {effects(extra="(hide yes)")})',
    ]
    return [f'(symbol (lib_id {q("Meridian:"+symbol.name)}) (at {xy(x,y)} {ROTATIONS.get(ref,0)}) (unit 1)',
            f'(in_bom {in_bom}) (on_board yes) (dnp no) {uuid(ref+"/instance")}',
            *props,
            *[f'(pin {q(pin.number)} {uuid(ref+"."+str(pin.number)+"/pin")})' for pin in symbol.pins],
            f'(instances (project {q(PROJECT)} (path {q("/"+ROOT_UUID)} (reference {q(ref)}) (unit 1))))',
            ')']


def flag_library(embedded):
    return f"""(symbol {q("Meridian:RailFlag" if embedded else "RailFlag")} (pin_names hide) (pin_numbers hide)
      (in_bom no) (on_board no)
      (property "Reference" "#FLG" (at 0 5.08 0) {effects(extra="(hide yes)")})
      (property "Value" "Rail source" (at 0 2.54 0) {effects(1.0)})
      (symbol "RailFlag_0_1" {line((0,0),(0,1),(-1,2),(0,3),(1,2),(0,1))})
      (symbol "RailFlag_1_1"
        (pin power_out line (at 0 0 90) (length 0)
          (name "~" {effects(1.0)}) (number "1" {effects(1.0)}))))"""


def flag(index, net, x, y):
    ref=f"#FLG{index:02d}"
    return [
        *label_and_wire(ref,Pin(1,net,0,0,0),net,x,y),
        f'''(symbol (lib_id "Meridian:RailFlag") (at {xy(x,y)} 0) (unit 1)
         (in_bom no) (on_board no) (dnp no) {uuid(ref+"/instance")}
         (property "Reference" {q(ref)} (at {xy(x,y-5)} 0) {effects(extra="(hide yes)")})
         (property "Value" "Rail source" (at {xy(x,y-4)} 0) {effects(1.0)})
         (pin "1" {uuid(ref+"/pin")})
         (instances (project {q(PROJECT)} (path {q("/"+ROOT_UUID)} (reference {q(ref)}) (unit 1)))))'''
    ]


def note(label, x, y, size):
    return f'(text {q(label)} (at {xy(x,y)} 0) {effects(size,"(justify left)")} {uuid("note/"+label)})'


def export_schematic():
    OUT.mkdir(exist_ok=True)
    parts = {p.ref:p for p in PARTS}
    assert set(LOCATIONS) == set(parts), "Every board part must appear on the schematic"
    symbols = {ref:drawing(part) for ref,part in parts.items()}
    library = {symbol.name:symbol for symbol in symbols.values()}
    lines = ['(kicad_sch (version 20250114) (generator eeschema)',
             f'(uuid {q(ROOT_UUID)}) (paper "A2")',
             '(title_block (title "Meridian industrial sensor carrier") (rev "B") (comment 1 "3.3 V bench integration"))',
             '(lib_symbols',*[library_symbol(symbol,True) for symbol in library.values()],flag_library(True),')',
             note("HOST AND FIELD CONNECTORS",23,42,3),
             note("RS-485 INTERFACE",124,42,3),
             note("POWER SOURCE AND BYPASS",124,151,3),
             note("TEST ACCESS",100,235,3),
             note("I2C PULL-UPS",284,42,3),
             note("ANALOG INPUTS",284,111,3),
             note("LOW-SIDE OUTPUTS AND INDICATORS",275,183,3),
             note("Fit one shunt on JP3. Centre pin feeds the carrier rail.",127,194,1.4),
             note("Enable JP1 at a cable end only. JP2 connects the I2C pull-ups.",123,137,1.4),
             note("All net labels with the same name are connected on this sheet.",23,298,1.5),
             note("Nominal 3.3 V logic. Review grounding and power limits before connecting external equipment.",23,306,1.5)]
    for ref, (x,y) in LOCATIONS.items():
        part=parts[ref]
        symbol=symbols[ref]
        assert len(part.pads)==len(symbol.pins), ref
        for pad,pin in zip(part.pads,symbol.pins):
            assert pad.pin==pin.number, ref
            if (ref,pin.number) not in EXPLICIT_PINS:
                lines.extend(label_and_wire(ref,pin,pad.net,x,y))
        lines.extend(instance(part,symbol,x,y))
    lines.extend(explicit_wires())
    for index,net in enumerate(("GND","3V3","CTRL_3V3","AUX_3V3"),1):
        lines.extend(flag(index,net,238,168+index*12))
    lines += ['(sheet_instances (path "/" (page "1")))',')']
    (OUT/f"{PROJECT}.kicad_sch").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (OUT/"Meridian.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20231120) (generator kicad_symbol_editor)\n'
        +"\n".join(library_symbol(symbol,False) for symbol in library.values())
        +"\n"+flag_library(False)+"\n)\n",encoding="utf-8")
    (OUT/"sym-lib-table").write_text(
        '(sym_lib_table (version 7) (lib (name "Meridian") (type "KiCad") (uri "${KIPRJMOD}/Meridian.kicad_sym") (options "") (descr "Carrier symbols")))\n',
        encoding="utf-8")


if __name__=="__main__":
    export_schematic()
