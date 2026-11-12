"""Clearance-aware, deterministic grid routing with full-stack plated vias."""
from collections import defaultdict
from dataclasses import asdict
from heapq import heappop, heappush
from itertools import count
from math import ceil
import json
from pathlib import Path

from board import CLEARANCE, GRID, H, MOUNTING, NETS, PADS, PARTS, SIGNAL_WIDTH, VIA_DIA, W

TRACK_GUARD = ceil((SIGNAL_WIDTH + CLEARANCE) / GRID)
VIA_TRACK_GUARD = ceil((VIA_DIA/2 + SIGNAL_WIDTH/2 + CLEARANCE) / GRID)
VIA_VIA_GUARD = ceil((VIA_DIA + CLEARANCE) / GRID)
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
    return ceil((pad.width/2+extra)/GRID), ceil((pad.height/2+extra)/GRID)

class Router:
    def __init__(self):
        self.tracks = defaultdict(set)
        self.vias = defaultdict(set)
        self.segments = []

    def obstacles(self, net):
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
            rx, ry = pad_halo(pad, SIGNAL_WIDTH/2+CLEARANCE)
            for layer in pad.layers:
                rect(track[layer], pad.x, pad.y, rx, ry)
            if pad.ref == "J1":
                direction = -1 if pad.pin % 2 else 1
                rect(track[3],pad.x+direction*10,pad.y,8,2)
        for other, points in self.tracks.items():
            if other == net:
                continue
            for x, y, z in points:
                rect(track[z], x, y, TRACK_GUARD, TRACK_GUARD)
                rect(via, x, y, VIA_TRACK_GUARD, VIA_TRACK_GUARD)
        for other, points in self.vias.items():
            for x, y in points:
                rect(via, x, y, VIA_VIA_GUARD, VIA_VIA_GUARD)
                if other != net:
                    for mask in track:
                        rect(mask, x, y, VIA_TRACK_GUARD, VIA_TRACK_GUARD)
        return track, via

    def find(self, start, goal, net, masks):
        track, via = masks
        internal = {"GND": 1, "3V3": 2}.get(net)
        available = (0, 1, 2, 3)
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
        raise RuntimeError(f"Could not route {net}: {start.ref}.{start.pin} to {goal.ref}.{goal.pin}")

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
        priority = ["RS_A", "RS_B", "UART_RX", "UART_TX", "RS_DIR", "OUT0", "OUT1",
                    "SPI_MISO", "SPI_MOSI", "SPI_SCK", "SPI_CS0", "GND", "3V3"]
        order = priority + sorted(set(NETS)-set(priority), key=lambda n: (-len(NETS[n]), n))
        for net in order:
            head, *pending = NETS[net]
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

if __name__ == "__main__":
    path = Path(__file__).parent/"layout.json"
    path.write_text(json.dumps(Router().run(), indent=2)+"\n", encoding="utf-8")
