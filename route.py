"""Clearance-aware, deterministic grid routing with full-stack plated vias."""
from collections import defaultdict
from dataclasses import asdict, replace
from heapq import heappop, heappush
from itertools import count
from math import floor
import json
from pathlib import Path

from board import CLEARANCE, GRID, H, MOUNTING, NETS, PADS, PARTS, VIA_DIA, W, track_width

VIA_VIA_GUARD = floor((VIA_DIA + CLEARANCE) / GRID)
STRIDE = W + 1

def rect(mask, x, y, rx, ry):
    low_x, high_x = max(0, x-rx), min(W, x+rx)
    if low_x > high_x:
        return
    row = b"\x01" * (high_x-low_x+1)
    for py in range(max(0, y-ry), min(H, y+ry)+1):
        start = py*STRIDE+low_x
        mask[start:start+len(row)] = row

def pad_halo(pad, extra):
    return floor((pad.width/2+extra)/GRID), floor((pad.height/2+extra)/GRID)

class Router:
    def __init__(self):
        self.tracks = defaultdict(set)
        self.vias = defaultdict(set)
        self.segments = []
        self.escape = self.breakout_connectors()

    def breakout_connectors(self):
        """Reserve a short bottom-layer escape for the densest headers."""
        result = {}
        for pad in PADS:
            if pad.ref == "J1":
                steps = -24 if pad.pin % 2 else 24
            elif pad.ref == "J3":
                steps = -21
            else:
                continue
            direction = 1 if steps > 0 else -1
            end = pad.x + steps
            path = [(x,pad.y,3) for x in range(pad.x,end+direction,direction)]
            self.save_path(pad.net,path)
            self.vias[pad.net].add((end,pad.y))
            result[(pad.ref,pad.pin)] = replace(pad,x=end,width=VIA_DIA,height=VIA_DIA,drill=.30)
        return result

    def obstacles(self, net):
        width = track_width(net)
        track = [bytearray((W+1)*(H+1)) for _ in range(4)]
        via = bytearray((W+1)*(H+1))
        for x, y in MOUNTING:
            for mask in [*track, via]:
                rect(mask, x, y, 12, 12)
        for pad in PADS:
            # Reserve a drill-free halo for assembly and to prevent via-in-pad.
            vrx, vry = pad_halo(pad, VIA_DIA/2+CLEARANCE)
            rect(via, pad.x, pad.y, vrx, vry)
            if pad.net == net:
                continue
            rx, ry = pad_halo(pad, width/2+CLEARANCE)
            for layer in pad.layers:
                rect(track[layer], pad.x, pad.y, rx, ry)

        for other, points in self.tracks.items():
            if other == net:
                continue
            track_guard = floor(((width+track_width(other))/2+CLEARANCE)/GRID)
            drill_guard = floor((VIA_DIA/2+track_width(other)/2+CLEARANCE)/GRID)
            for x, y, z in points:
                rect(track[z], x, y, track_guard, track_guard)
                rect(via, x, y, drill_guard, drill_guard)
        for other, points in self.vias.items():
            for x, y in points:
                rect(via, x, y, VIA_VIA_GUARD, VIA_VIA_GUARD)
                if other != net:
                    for mask in track:
                        guard = floor((VIA_DIA/2+width/2+CLEARANCE)/GRID)
                        rect(mask, x, y, guard, guard)
        return track, via

    def find(self, start, goal, net, masks):
        track, via = masks
        internal = {"GND": 1, "3V3": 2}.get(net)
        available = (0, internal, 3) if internal else (0, 3)
        starts = [(start.x, start.y, z) for z in start.layers if z in available]
        goals = {(goal.x, goal.y, z) for z in goal.layers if z in available}
        order = count()
        def heuristic(x, y, z):
            layer_cost = 0 if (goal.drill or z == 0) else 12
            return 1.16 * (abs(goal.x-x)+abs(goal.y-y)) + layer_cost
        heap = []
        distance, parent = {}, {}
        for node in starts:
            distance[node] = 0
            parent[node] = None
            heappush(heap, (heuristic(*node), 0, next(order), node))
        while heap:
            _, cost, _, node = heappop(heap)
            if cost != distance[node]:
                continue
            if node in goals:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                return path[::-1]
            x, y, z = node
            transitions = []
            for dx, dy in ((1,0), (0,1), (-1,0), (0,-1)):
                a, b = x+dx, y+dy
                if not (7 <= a <= W-7 and 7 <= b <= H-7):
                    continue
                if track[z][b*STRIDE+a]:
                    continue
                # Orthogonal layer preference limits long parallel runs.
                penalty = .18 if ((z in (0, 2) and dy) or (z in (1, 3) and dx)) else 0
                if internal and z != internal:
                    penalty += .45
                if not internal and z in (1,2):
                    penalty += .65
                transitions.append(((a, b, z), 1+penalty))
            if not via[y*STRIDE+x] or (x, y) in self.vias[net]:
                for nz in available:
                    if nz != z and not track[nz][y*STRIDE+x]:
                        transitions.append(((x, y, nz), 19))
            for target, delta in transitions:
                score = cost+delta
                if score < distance.get(target, float("inf")):
                    distance[target] = score
                    parent[target] = node
                    heappush(heap, (score+heuristic(*target), score, next(order), target))
        raise RuntimeError(f"Could not route {net}: {start.ref}.{start.pin} to {goal.ref}.{goal.pin}; visited {len(distance)} nodes")

    def save_path(self, net, path):
        self.tracks[net].update(path)
        previous = path[0]
        begin = previous
        prior_direction = None
        for node in path[1:]:
            if node[2] != previous[2]:
                if begin != previous:
                    self.segments.append((net, begin, previous))
                self.vias[net].add(node[:2])
                begin = node
                prior_direction = None
            else:
                direction = (node[0]-previous[0], node[1]-previous[1])
                if prior_direction is not None and direction != prior_direction:
                    self.segments.append((net, begin, previous))
                    begin = previous
                prior_direction = direction
            previous = node
        if begin != previous:
            self.segments.append((net, begin, previous))

    def run(self):
        priority = ["CTRL_3V3", "AUX_3V3", "SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS0", "RS_A", "RS_B", "UART_RX", "UART_TX", "RS_DIR",
                    "OUT0", "OUT1", "GND", "3V3"]
        order = priority + sorted(set(NETS)-set(priority), key=lambda n: (-len(NETS[n]), n))
        for net in order:
            head, *pending = [self.escape.get((pad.ref,pad.pin),pad) for pad in NETS[net]]
            connected = [head]
            while pending:
                source, target = min(
                    ((a, b) for a in connected for b in pending),
                    key=lambda p: abs(p[0].x-p[1].x)+abs(p[0].y-p[1].y),
                )
                self.save_path(net, self.find(source, target, net, self.obstacles(net)))
                connected.append(target)
                pending.remove(target)
            print(f"Routed {net}: {len(connected)} pads", flush=True)
        return {
            "grid_mm": GRID, "width": W, "height": H,
            "parts": [asdict(part) for part in PARTS],
            "mounting": MOUNTING,
            "traces": self.segments,
            "vias": [(net, x, y) for net, coords in sorted(self.vias.items()) for x, y in sorted(coords)],
        }

def remove_dangling_vias(layout):
    """Keep vias serving a layer transition or an inner plane connection."""
    touched = defaultdict(set)
    for net,a,b in layout["traces"]:
        layer=a[2]
        if a[0]==b[0]:
            for y in range(min(a[1],b[1]),max(a[1],b[1])+1):
                touched[(net,a[0],y)].add(layer)
        else:
            for x in range(min(a[0],b[0]),max(a[0],b[0])+1):
                touched[(net,x,a[1])].add(layer)
    planes = {"GND":1,"3V3":2}
    kept=[]
    for net,x,y in layout["vias"]:
        layers=touched[(net,x,y)].copy()
        if net in planes and layers:
            layers.add(planes[net])
        if len(layers)>1:
            kept.append((net,x,y))
    layout["vias"]=kept
    return layout


if __name__ == "__main__":
    path = Path(__file__).parent/"layout.json"
    layout=remove_dangling_vias(Router().run())
    path.write_text(json.dumps(layout, indent=2)+"\n", encoding="utf-8")
