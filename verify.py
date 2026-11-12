"""Independent vector clearance and connectivity checks for the generated layout."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from shapely import LineString, Point, Polygon, STRtree, box
from board import CLEARANCE, GRID, H, LAYER_NAMES, SIGNAL_WIDTH, POWER_WIDTH, VIA_DIA, VIA_DRILL, W, track_width

ROOT = Path(__file__).parent
EDGE = [(12, 0), (W-12, 0), (W, 12), (W, H-12),
        (W-12, H), (12, H), (0, H-12), (0, 12)]

def mm(x, y):
    return x*GRID, y*GRID

def inspect(layout):
    outline = Polygon([mm(x,y) for x,y in EDGE])
    clear_area = outline.buffer(-.50)
    layers = defaultdict(list)
    all_ids = defaultdict(set)
    pad_ids = defaultdict(set)
    drills = []
    errors = []
    track_count = Counter()
    via_count = Counter()
    def add(key, net, shape, sides, pad=False):
        all_ids[net].add(key)
        if pad:
            pad_ids[net].add(key)
        if not clear_area.covers(shape):
            errors.append(f"Copper to edge: {key}")
        for side in sides:
            layers[side].append((key, net, shape))

    for part in layout["parts"]:
        for p in part["pads"]:
            x, y = mm(p["x"],p["y"])
            radius_x, radius_y = p["width"]/2,p["height"]/2
            key = f'{p["ref"]}.{p["pin"]}'
            if p["drill"]:
                geo = Point(x,y).buffer(radius_x)
                drills.append((key,Point(x,y).buffer(p["drill"]/2)))
                sides = range(4)
            else:
                geo = box(x-radius_x,y-radius_y,x+radius_x,y+radius_y)
                sides = (0,)
            add(key,p["net"],geo,sides,pad=True)
    for i,(net,start,end) in enumerate(layout["traces"]):
        a,b = mm(*start[:2]),mm(*end[:2])
        if a == b or start[2] != end[2]:
            errors.append(f"Degenerate segment {i}")
            continue
        track_count[LAYER_NAMES[start[2]]] += 1
        add(f"Track {i}",net,LineString([a,b]).buffer(track_width(net)/2),[start[2]])
    for i,(net,x,y) in enumerate(layout["vias"]):
        point = Point(*mm(x,y))
        key = f"Via {i}"
        via_count[net] += 1
        drills.append((key,point.buffer(VIA_DRILL/2)))
        add(key,net,point.buffer(VIA_DIA/2),range(4))
    for i,(x,y) in enumerate(layout["mounting"]):
        drills.append((f"Mount {i}",Point(*mm(x,y)).buffer(1.60)))

    for i,(a,ag) in enumerate(drills):
        for b,bg in drills[i+1:]:
            if ag.distance(bg) < .24999:
                errors.append(f"Drill clearance: {a} / {b}")

    parents = {key:key for keys in all_ids.values() for key in keys}
    def root(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for side, items in layers.items():
        shapes = [record[2] for record in items]
        tree = STRtree(shapes)
        for i,(left,net,shape) in enumerate(items):
            for j in tree.query(shape,predicate="dwithin",distance=CLEARANCE+1e-7):
                if j <= i:
                    continue
                right, other, target = items[j]
                if net == other:
                    if shape.intersects(target):
                        parents[root(left)] = root(right)
                elif shape.distance(target) < CLEARANCE-1e-6:
                    errors.append(f"{LAYER_NAMES[side]} clearance: {left} ({net}) / {right} ({other})")
            for key,mount in drills[-len(layout["mounting"]):]:
                if shape.distance(mount) < .49999:
                    errors.append(f"{LAYER_NAMES[side]} mount keepout: {left} / {key}")
    for net, members in all_ids.items():
        groups = {root(key) for key in members}
        if len(groups) != 1:
            endpoints = sorted(pad_ids[net])
            errors.append(f"Disconnected copper on {net}: {len(groups)} islands, pads {endpoints}")
    return {
        "footprints":len(layout["parts"]),
        "electrical_pads":sum(map(len,pad_ids.values())),
        "nets":len(all_ids),
        "copper_clearance_mm":CLEARANCE,
        "copper_to_edge_mm":.50,
        "copper_to_mount_hole_mm":.50,
        "hole_clearance_mm":.25,
        "signal_width_mm":SIGNAL_WIDTH,
        "power_width_mm":POWER_WIDTH,
        "plated_vias":sum(via_count.values()),
        "tracks_by_layer":dict(track_count),
        "errors":errors,
    }

if __name__ == "__main__":
    result = inspect(json.loads((ROOT/"layout.json").read_text(encoding="utf-8")))
    (ROOT/"verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    raise SystemExit(bool(result["errors"]))
