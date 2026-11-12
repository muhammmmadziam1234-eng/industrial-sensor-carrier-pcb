"""Export the verified geometry to millimetre DXF, KiCad and assembly tables."""
import csv
from collections import Counter
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import ezdxf
from kiutils.board import Board
from kiutils.items.brditems import Segment, Via
from board import GRID, H, LAYER_NAMES, PLANES, VIA_DIA, VIA_DRILL, W, track_width
from design_ids import PROJECT, ROOT_UUID, design_uuid, footprint_id, footprint_name
from planes import model, PLANE_CLEARANCE
from procurement import selection
from verify import EDGE

ROOT = Path(__file__).parent
OUT = ROOT/"cad"
DXF_LAYERS = ("L1_FRONT_SIGNAL", "L2_GROUND_ROUTE", "L3_SUPPLY_ROUTE", "L4_BACK_SIGNAL")

def dxy(x, y):
    return (x*GRID, (H-y)*GRID)

def xy(x, y):
    return f"{x*GRID:.4f} {y*GRID:.4f}"

def quote(s):
    return json.dumps(str(s),ensure_ascii=False)

def net_name(net):
    return quote("/"+net)


def stamp(label):
    return f"(tstamp {uuid5(NAMESPACE_URL,'meridian-carrier/'+str(label))})"

def pad_bounds(pad):
    x, y = dxy(pad["x"],pad["y"])
    r, s = pad["width"]/2,pad["height"]/2
    return [(x-r,y-s),(x+r,y-s),(x+r,y+s),(x-r,y+s)]

def trace_key(layer, start, end, width):
    endpoints = tuple(sorted(tuple(round(n,4) for n in point) for point in (start,end)))
    return layer, endpoints, round(width,4)

def dxf(layout):
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name,color in [*zip(DXF_LAYERS,(30,92,151,210)), ("EDGE_CUTS",7), ("L2_GND_POUR",94), ("L3_3V3_POUR",154),
        ("PLATED_PAD",2),("SMD_LANDS",34),("VIA_ANNULUS",151),("PLATED_DRILL",7),
        ("MOUNTING_NPTH",1),("COMPONENT_OUTLINES",8),("REFERENCE_LABELS",7),("DIMENSIONS",6)]:
        doc.layers.new(name,dxfattribs={"color":color})
    m = doc.modelspace()
    def text(value, at, height, layer):
        m.add_text(value,dxfattribs={"layer":layer,"height":height}).set_placement(at)
    m.add_lwpolyline([dxy(x,y) for x,y in EDGE],close=True,dxfattribs={"layer":"EDGE_CUTS"})
    for i, (net,a,b) in enumerate(layout["traces"]):
        m.add_lwpolyline([dxy(*a[:2]),dxy(*b[:2])],
            dxfattribs={"layer":DXF_LAYERS[a[2]],"const_width":track_width(net)})
    plane_geometry, _ = model(layout)
    for layer, polygon in plane_geometry.items():
        name = {1:"L2_GND_POUR",2:"L3_3V3_POUR"}[layer]
        hatch = m.add_hatch(dxfattribs={"layer":name,"color":256})
        hatch.paths.add_polyline_path([(x,H*GRID-y) for x,y in polygon.exterior.coords[:-1]], is_closed=True, flags=1)
        for hole in polygon.interiors:
            hatch.paths.add_polyline_path([(x,H*GRID-y) for x,y in hole.coords[:-1]], is_closed=True, flags=0)
    for net,x,y in layout["vias"]:
        m.add_circle(dxy(x,y),VIA_DIA/2,dxfattribs={"layer":"VIA_ANNULUS"})
        m.add_circle(dxy(x,y),VIA_DRILL/2,dxfattribs={"layer":"PLATED_DRILL"})
    for part in layout["parts"]:
        points = []
        for p in part["pads"]:
            a = dxy(p["x"],p["y"])
            points.extend(pad_bounds(p))
            if p["drill"]:
                m.add_circle(a,p["width"]/2,dxfattribs={"layer":"PLATED_PAD"})
                m.add_circle(a,p["drill"]/2,dxfattribs={"layer":"PLATED_DRILL"})
            else:
                m.add_lwpolyline(pad_bounds(p),close=True,dxfattribs={"layer":"SMD_LANDS"})
        left,right = min(x for x,y in points)-.5,max(x for x,y in points)+.5
        bottom,top = min(y for x,y in points)-.5,max(y for x,y in points)+.5
        m.add_lwpolyline([(left,bottom),(right,bottom),(right,top),(left,top)],close=True,
                        dxfattribs={"layer":"COMPONENT_OUTLINES"})
        text(part["ref"],(left,top+.28),.80,"REFERENCE_LABELS")
    for x,y in layout["mounting"]:
        m.add_circle(dxy(x,y),1.6,dxfattribs={"layer":"MOUNTING_NPTH"})
    for base,p1,p2,angle in [((0,-5),(0,0),(W*GRID,0),0),((-5,0),(0,0),(0,H*GRID),90)]:
        dim = m.add_linear_dim(base=base,p1=p1,p2=p2,angle=angle,
            override={"dimtxt":1.8,"dimasz":1.1},dxfattribs={"layer":"DIMENSIONS"})
        dim.render()
    text("MERIDIAN / INDUSTRIAL SENSOR CARRIER   |   1:1   |   mm", (0,H*GRID+4),1.7,"REFERENCE_LABELS")
    path = OUT/"meridian-carrier.dxf"
    doc.saveas(path)
    verified = ezdxf.readfile(path)
    audit = verified.audit()
    assert not audit.errors and not audit.fixes, "DXF audit found malformed objects"
    assert verified.units == ezdxf.units.MM
    tracks = [e for e in verified.modelspace() if e.dxf.layer in DXF_LAYERS]
    expected = Counter(trace_key(DXF_LAYERS[a[2]],dxy(*a[:2]),dxy(*b[:2]),track_width(net))
                       for net,a,b in layout["traces"])
    actual = Counter(trace_key(e.dxf.layer,*list(e.get_points("xy")),e.dxf.const_width)
                     for e in tracks)
    assert actual == expected, "DXF changed track geometry"
    assert len(verified.modelspace().query('CIRCLE[layer=="MOUNTING_NPTH"]')) == len(layout["mounting"])
    return {"dxf_version":verified.dxfversion,"dxf_model_entities":len(verified.modelspace()),"dxf_audit_errors":0,"dxf_plane_hatches":len(verified.modelspace().query("HATCH"))}

def footprint(part, nets=None):
    name,ref=footprint_name(part),part["ref"]
    origin_x,origin_y=part["x"],part["y"]
    if ref=="U1":
        # Centre the SOIC origin between its outer pin rows for assembly placement.
        origin_y=(min(p["y"] for p in part["pads"])+max(p["y"] for p in part["pads"]))/2
    through=any(p["drill"] for p in part["pads"])
    board_instance = nets is not None
    if board_instance:
        path = f'/{ROOT_UUID}/{design_uuid(ref+"/instance")}'
        out=[f'  (footprint {quote(footprint_id(part))} (layer "F.Cu") {stamp(ref)}',
             f'    (at {xy(origin_x,origin_y)}) (path {quote(path)})']
    else:
        out=[f'  (footprint {quote(name)} (version 20221018) (generator meridian_export) (layer "F.Cu")']
    kind = "through_hole" if through else "smd"
    attributes = " exclude_from_bom exclude_from_pos_files" if ref.startswith("TP") else ""
    out.append(f"    (attr {kind}{attributes})")
    xmin=min((p["x"]-origin_x)*GRID-p["width"]/2 for p in part["pads"])-.5
    xmax=max((p["x"]-origin_x)*GRID+p["width"]/2 for p in part["pads"])+.5
    ymin=min((p["y"]-origin_y)*GRID-p["height"]/2 for p in part["pads"])-.5
    ymax=max((p["y"]-origin_y)*GRID+p["height"]/2 for p in part["pads"])+.5
    reference_y = ymin - (1.25 if through else .50)
    out += [
        f'    (fp_text reference {quote(ref if board_instance else "REF**")} (at 0 {reference_y:.3f}) (layer "F.SilkS") (effects (font (size 0.85 0.85) (thickness 0.12))) {stamp(ref+"-ref")})',
        f'    (fp_text value {quote(part["value"] if board_instance else name)} (at 0 0) (layer "F.Fab") hide (effects (font (size 0.7 0.7) (thickness 0.12))) {stamp(ref+"-val")})',
        f'    (fp_rect (start {xmin:.3f} {ymin:.3f}) (end {xmax:.3f} {ymax:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "F.Fab") {stamp(ref+"-fab")})',
        f'    (fp_rect (start {xmin-.15:.3f} {ymin-.15:.3f}) (end {xmax+.15:.3f} {ymax+.15:.3f}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") {stamp(ref+"-courtyard")})',
    ]
    if through:
        out.append(f'    (fp_line (start -0.9 {ymin:.3f}) (end 0.9 {ymin:.3f}) (stroke (width 0.15) (type default)) (layer "F.SilkS") {stamp(ref+"-pin1")})')
    for p in part["pads"]:
        dx,dy=p["x"]-origin_x,p["y"]-origin_y
        drill=f'(drill {p["drill"]}) (layers "*.Cu" "*.Mask")' if p["drill"] else (
            '(layers "F.Cu" "F.Mask")' if ref.startswith("TP") else '(layers "F.Cu" "F.Paste" "F.Mask")'
        )
        kind="thru_hole circle" if p["drill"] else "smd rect"
        assigned = f'(net {nets[p["net"]]} {net_name(p["net"])})' if board_instance else ""
        out.append(f'    (pad "{p["pin"]}" {kind} (at {xy(dx,dy)}) (size {p["width"]} {p["height"]}) {drill} {assigned} {stamp(ref+"-pad-"+str(p["pin"]))})')
    out.append("  )")
    return out

def mounting_footprint(ref="REF**", position=None):
    if position is None:
        start = '(footprint "Mount_M3" (version 20221018) (generator meridian_export) (layer "F.Cu")'
    else:
        start = f'(footprint "Meridian:Mount_M3" (layer "F.Cu") {stamp(ref)} (at {xy(*position)})'
    return [
        start + ' (attr board_only exclude_from_pos_files exclude_from_bom)',
        f'  (fp_text reference {quote(ref)} (at 0 -2.9) (layer "F.SilkS") (effects (font (size 0.85 0.85) (thickness 0.12))) {stamp(ref+"-mount-ref")})',
        f'  (fp_circle (center 0 0) (end 2.25 0) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd") {stamp(ref+"-mount-courtyard")})',
        f'  (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask") {stamp(ref+"-mount-hole")})',
        ')',
    ]


def kicad(layout):
    nets = {net:i for i,net in enumerate(sorted({p["net"] for f in layout["parts"] for p in f["pads"]}),1)}
    out=['(kicad_pcb (version 20221018) (generator meridian_export)',
         '  (general (thickness 1.6)) (paper "A4")',
         '  (layers (0 "F.Cu" signal) (1 "In1.Cu" power) (2 "In2.Cu" power) (31 "B.Cu" signal)',
         '    (35 "F.Paste" user) (37 "F.SilkS" user "F.Silkscreen") (38 "B.Mask" user) (39 "F.Mask" user)',
         '    (44 "Edge.Cuts" user) (47 "F.CrtYd" user "F.Courtyard") (49 "F.Fab" user))',
         '  (setup (pad_to_mask_clearance 0))', '  (net 0 "")']
    out += [f'  (net {i} {net_name(net)})' for net,i in nets.items()]
    for item in layout["parts"]:
        out.extend(footprint(item,nets))
    for i,(x,y) in enumerate(layout["mounting"],1):
        out.extend(mounting_footprint(f"H{i}",(x,y)))
    for i,(a,b) in enumerate(zip(EDGE,EDGE[1:]+EDGE[:1])):
        out.append(f'  (gr_line (start {xy(*a)}) (end {xy(*b)}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") {stamp("edge"+str(i))})')
    for i,(net,a,b) in enumerate(layout["traces"]):
        out.append(f'  (segment (start {xy(*a[:2])}) (end {xy(*b[:2])}) (width {track_width(net)}) (layer "{LAYER_NAMES[a[2]]}") (net {nets[net]}) {stamp("seg"+str(i))})')
    for i,(net,x,y) in enumerate(layout["vias"]):
        out.append(f'  (via (at {xy(x,y)}) (size {VIA_DIA}) (drill {VIA_DRILL}) (layers "F.Cu" "B.Cu") (net {nets[net]}) {stamp("via"+str(i))})')
    coords = " ".join(f"(xy {xy(x,y)})" for x,y in EDGE)
    for layer,net in PLANES.items():
        out += [
            f'  (zone (net {nets[net]}) (net_name {net_name(net)}) (layer "{LAYER_NAMES[layer]}") {stamp("plane-"+net)}',
            f'    (hatch edge 0.5) (connect_pads (clearance {PLANE_CLEARANCE})) (min_thickness 0.25)',
            '    (fill yes (thermal_gap 0.35) (thermal_bridge_width 0.40))',
            f'    (polygon (pts {coords}))',
            '  )',
        ]
    out.append(")")
    path=OUT/"meridian-carrier.kicad_pcb"
    path.write_text("\n".join(out)+"\n",encoding="utf-8")
    parsed=Board.from_file(str(path))
    assert len(parsed.footprints)==len(layout["parts"])+len(layout["mounting"])
    assert len(parsed.nets)==len(nets)+1
    def position(point):
        return point.X,point.Y
    expected = Counter((nets[net],trace_key(LAYER_NAMES[a[2]],(a[0]*GRID,a[1]*GRID),
                        (b[0]*GRID,b[1]*GRID),track_width(net))) for net,a,b in layout["traces"])
    actual = Counter((item.net,trace_key(item.layer,position(item.start),position(item.end),item.width))
                     for item in parsed.traceItems if isinstance(item,Segment))
    assert actual == expected, "KiCad export changed tracks or their net assignments"
    assert sum(isinstance(item,Via) for item in parsed.traceItems)==len(layout["vias"])
    return {"kicad_readback_footprints":len(parsed.footprints),"kicad_readback_track_items":len(parsed.traceItems)}

def export_footprint_library(layout):
    library=OUT/"Meridian.pretty"
    library.mkdir(exist_ok=True)
    unique={footprint_name(part):part for part in layout["parts"]}
    for name,part in unique.items():
        (library/(name+".kicad_mod")).write_text("\n".join(footprint(part))+"\n",encoding="utf-8")
    (library/"Mount_M3.kicad_mod").write_text("\n".join(mounting_footprint())+"\n",encoding="utf-8")
    (OUT/"fp-lib-table").write_text(
        '(fp_lib_table (version 7) (lib (name "Meridian") (type "KiCad") '
        '(uri "$'+'{KIPRJMOD}/Meridian.pretty") (options "") (descr "Carrier footprints")))\n',
        encoding="utf-8",
    )

def tables(layout):
    with (OUT/"bill-of-materials.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle)
        writer.writerow(("Reference","Value","Package or connector pitch","Manufacturer","Part number","Assembly note","Source","Population"))
        for f in layout["parts"]:
            writer.writerow((f["ref"],f["value"],f["package"],*selection(f)))
        writer.writerow(("SH1-SH3","Removable shunts","2.54 mm","","","One source shunt is required. Fit the other two only as needed.","","Install by configuration"))
    with (OUT/"pad-net-map.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle)
        writer.writerow(("Reference","Pad","Net","CAD x mm","CAD y mm","Drill mm"))
        for f in layout["parts"]:
            for p in f["pads"]:
                x,y=dxy(p["x"],p["y"])
                writer.writerow((f["ref"],p["pin"],p["net"],f"{x:.3f}",f"{y:.3f}",p["drill"]))

if __name__=="__main__":
    layout=json.loads((ROOT/"layout.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    status={**dxf(layout),**kicad(layout)}
    export_footprint_library(layout)
    tables(layout)
    (OUT/"export-checks.json").write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(status,indent=2))
