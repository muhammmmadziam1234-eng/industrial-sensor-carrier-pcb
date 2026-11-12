"""Independent clearance and connectivity model of the two dedicated copper pours."""

import json
from pathlib import Path
from shapely import Point, Polygon, box, union_all
from board import GRID, PLANES, VIA_DIA
from verify import EDGE

PLANE_CLEARANCE = .35
EDGE_CLEARANCE = .55
MOUNT_CLEARANCE = .60

def xy(x, y):
    return x*GRID, y*GRID

def pad_polygon(p):
    x,y = xy(p["x"],p["y"])
    a,b=p["width"]/2,p["height"]/2
    if p["drill"]:
        return Point(x,y).buffer(a,quad_segs=16)
    return box(x-a,y-b,x+a,y+b)

def model(layout):
    assert all(a[2] not in PLANES or PLANES[a[2]] == net for net,a,b in layout['traces']), 'Foreign trace on a dedicated plane layer'
    board = Polygon([xy(x,y) for x,y in EDGE])
    envelope = board.buffer(-EDGE_CLEARANCE,join_style="mitre")
    mounts = [Point(*xy(x,y)).buffer(1.60+MOUNT_CLEARANCE,quad_segs=16)
              for x,y in layout["mounting"]]
    metal = [(f'{pad["ref"]}.{pad["pin"]}',pad["net"],pad_polygon(pad))
             for item in layout["parts"] for pad in item["pads"] if pad["drill"]]
    metal += [(f"via {i}",net,Point(*xy(x,y)).buffer(VIA_DIA/2,quad_segs=16))
              for i,(net,x,y) in enumerate(layout["vias"])]
    planes, summary = {}, {}
    for layer, net in PLANES.items():
        foreign = [shape.buffer(PLANE_CLEARANCE,quad_segs=12)
                   for _,other,shape in metal if other!=net]
        geometry = envelope.difference(union_all([*mounts,*foreign]))
        islands = [geometry] if geometry.geom_type=="Polygon" else list(geometry.geoms)
        assert len(islands)==1, f"{net} plane has {len(islands)} copper islands"
        neck = geometry.buffer(-.15)
        sections = list(neck.geoms) if neck.geom_type=="MultiPolygon" else [neck]
        continuous = max(sections, key=lambda section:section.area)
        retained = continuous.buffer(.15).intersection(geometry)
        assert not retained.is_empty and retained.geom_type=="Polygon", f"{net} plane loses its main pour"
        trim_area = geometry.area-retained.area
        assert trim_area < board.area*.005, f"{net} plane lost {trim_area:.2f} mm2 while removing narrow pockets"
        geometry = retained
        assert all(geometry.intersection(shape).area>.05 for _,other,shape in metal if other==net), net
        planes[layer] = geometry
        summary[net] = {
            "layer": layer+1,
            "model_clearance_mm": PLANE_CLEARANCE,
            "copper_coverage_percent": round(100*geometry.area/board.area,2),
            "plated_connections": sum(other==net for _,other,_ in metal),
            "islands": len(islands),
            "continuous_core_inset_mm": .15,
            "trimmed_narrow_copper_mm2": round(trim_area,3),
        }
    return planes,summary


if __name__ == "__main__":
    root=Path(__file__).parent
    layout=json.loads((root/"layout.json").read_text(encoding="utf-8"))
    _,summary=model(layout)
    (root/"plane-verification.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
