"""Independent check of the fabrication package.

The other scripts in this repository check the design from the generator's own model (layout.json). This one never
reads that model. It reads only what leaves the project: the Gerber and drill files in fab/, the placement file, the
bill of materials, the saved KiCad board and the KiCad schematic. Gerbers and drills are read back with a second tool
(gerbonara), the KiCad files with a small s-expression reader, and everything is compared against everything else.

It writes reports/independent-fabrication-check.json and exits with status 1 if any check fails.
"""
import csv
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import gerbonara
from gerbonara import LayerStack

ROOT = Path(__file__).parent
BOARD = ROOT / "cad" / "meridian-carrier.kicad_pcb"
SCHEMATIC = ROOT / "cad" / "meridian-carrier.kicad_sch"
RULES = ROOT / "cad" / "meridian-carrier.kicad_dru"
BOM = ROOT / "cad" / "bill-of-materials.csv"
PLACEMENT = ROOT / "fab" / "top-placement.csv"
REPORT = ROOT / "reports" / "independent-fabrication-check.json"
TOLERANCE = 0.005  # mm


def parse_sexpr(text):
    """Parse a KiCad s-expression file into nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack = [[]]
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif token.startswith('"'):
            stack[-1].append(token[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(token)
    return stack[0]


def children(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def prop(node, name):
    for p in children(node, "property"):
        if len(p) > 2 and p[1] == name:
            return p[2]
    return None


def read_board():
    root = parse_sexpr(BOARD.read_text(encoding="utf-8"))[0]
    footprints = []
    for fp in children(root, "footprint"):
        pads = []
        for pad in children(fp, "pad"):
            net = child(pad, "net")
            drill = child(pad, "drill")
            pads.append({"type": pad[2], "net": net[1] if net and len(net) > 1 else None,
                         "drill": float(drill[1]) if drill and len(drill) > 1 and drill[1] not in ("oval",) else None})
        footprints.append({"ref": prop(fp, "Reference"), "name": fp[1], "layer": child(fp, "layer")[1], "pads": pads})
    segments = [{"layer": child(s, "layer")[1], "width": float(child(s, "width")[1]), "net": child(s, "net")[1]}
                for s in children(root, "segment")]
    vias = [{"drill": float(child(v, "drill")[1]), "net": child(v, "net")[1]} for v in children(root, "via")]
    zones = [{"layer": (child(z, "layer") or child(z, "layers"))[1], "net": child(z, "net")[1]} for z in children(root, "zone")]
    return footprints, segments, vias, zones


def read_schematic_refs():
    root = parse_sexpr(SCHEMATIC.read_text(encoding="utf-8"))[0]
    refs = []
    for sym in children(root, "symbol"):  # placed symbols sit directly under the sheet; library symbols are under lib_symbols
        ref = prop(sym, "Reference")
        if ref and not ref.startswith("#"):
            refs.append(ref)
    return refs


def outline_extent(layer):
    lines = [o for o in layer.objects if type(o).__name__ == "Line"]
    xs = [v for o in lines for v in (o.x1, o.x2)]
    ys = [v for o in lines for v in (o.y1, o.y2)]
    ends = Counter((round(o.x1, 4), round(o.y1, 4)) for o in lines) + Counter((round(o.x2, 4), round(o.y2, 4)) for o in lines)
    closed = all(count == 2 for count in ends.values())
    return round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4), closed, len(lines)


def main():
    warnings.simplefilter("ignore")
    stack = LayerStack.open(ROOT / "fab")
    footprints, segments, vias, zones = read_board()
    checks, measured = [], {}

    def check(name, description, expected, actual, ok=None):
        passed = (expected == actual) if ok is None else ok
        checks.append({"id": name, "description": description, "expected": expected, "actual": actual, "passed": bool(passed)})

    # 1. The Gerber set has the nine layers a four-layer board needs, and a drill file pair.
    layer_names = sorted(f"{side}-{use}" for side, use in stack.graphic_layers)
    expected_layers = sorted(["top-copper", "inner_1-copper", "inner_2-copper", "bottom-copper", "top-mask", "bottom-mask",
                              "top-paste", "top-silk", "mechanical-outline"])
    check("gerber-layers", "Nine Gerber layers are present and readable", expected_layers, layer_names)

    # 2. The outline is one closed loop with the documented board size.
    width, height, closed, edges = outline_extent(stack.outline)
    measured["board_mm"] = [width, height]
    check("outline-closed", "Board outline is one closed loop", True, closed)
    check("outline-size", "Board is 101.60 x 76.20 mm (within 0.005 mm)", [101.6, 76.2], [width, height],
          ok=abs(width - 101.6) <= TOLERANCE and abs(height - 76.2) <= TOLERANCE)

    # 3. Copper tracks read from each Gerber equal the tracks stored in the saved board, layer by layer.
    layer_map = {"top-copper": "F.Cu", "inner_1-copper": "In1.Cu", "inner_2-copper": "In2.Cu", "bottom-copper": "B.Cu"}
    widths = set()
    for key, board_layer in layer_map.items():
        side, use = key.split("-")
        lines = [o for o in stack.graphic_layers[(side, use)].objects if type(o).__name__ == "Line"]
        board_count = sum(1 for s in segments if s["layer"] == board_layer)
        measured.setdefault("tracks", {})[board_layer] = len(lines)
        widths |= {round(o.aperture.diameter, 3) for o in lines}
        check(f"tracks-{board_layer}", f"{board_layer}: tracks in the Gerber equal tracks in the saved board", board_count, len(lines))
    measured["track_widths_mm"] = sorted(widths)

    # 4. Pads, vias and holes agree between Gerber flashes, Excellon files and the board.
    pads = [(fp, p) for fp in footprints for p in fp["pads"]]
    smd = sum(1 for _, p in pads if p["type"] == "smd")
    thru = sum(1 for _, p in pads if p["type"] == "thru_hole")
    mount = sum(1 for _, p in pads if p["type"] == "np_thru_hole")
    electrical = sum(1 for _, p in pads if p["net"])
    measured["pads"] = {"smd": smd, "through_hole": thru, "mounting_hole": mount, "electrical": electrical, "vias": len(vias)}
    flashes = {k: sum(1 for o in stack.graphic_layers[k].objects if type(o).__name__ == "Flash") for k in stack.graphic_layers}
    check("flashes-top-copper", "Top copper flashes = SMD pads + through-hole pads + vias", smd + thru + len(vias), flashes[("top", "copper")])
    for inner in (("inner_1", "copper"), ("inner_2", "copper"), ("bottom", "copper")):
        check(f"flashes-{inner[0]}", f"{inner[0]} flashes = through-hole pads + vias", thru + len(vias), flashes[inner])
    test_lands = [fp for fp in footprints if fp["name"] == "Meridian:TestLand_1p5mm"]
    pasted = sum(1 for fp, p in pads if p["type"] == "smd" and fp["name"] != "Meridian:TestLand_1p5mm")
    check("flashes-top-mask", "Top mask openings = every pad on the board", len(pads), flashes[("top", "mask")])
    check("flashes-top-paste", "Top paste openings = SMD pads of fitted parts (test lands get no paste)", pasted, flashes[("top", "paste")])
    check("flashes-bottom-mask", "Bottom mask openings = through-hole and mounting pads (vias are tented)", thru + mount, flashes[("bottom", "mask")])
    pth = Counter(round(o.tool.diameter, 3) if hasattr(o, "tool") and o.tool else 0 for o in stack.drill_pth.objects)
    npth = Counter(round(o.tool.diameter, 3) if hasattr(o, "tool") and o.tool else 0 for o in stack.drill_npth.objects)
    via_drills = Counter(round(v["drill"], 3) for v in vias)
    thru_drills = Counter(round(p["drill"], 3) for _, p in pads if p["type"] == "thru_hole")
    measured["drills_mm"] = {"plated": {str(k): v for k, v in sorted(pth.items())}, "unplated": {str(k): v for k, v in sorted(npth.items())}}
    check("drill-plated", "Plated drill hits by diameter = via drills + through-hole pad drills", dict(sorted((via_drills + thru_drills).items())), dict(sorted(pth.items())))
    check("drill-unplated", "Unplated drill hits = mounting holes in the board (3.20 mm)", {3.2: mount}, dict(npth))
    check("drill-total", "117 plated and 4 unplated hits", [117, 4], [sum(pth.values()), sum(npth.values())])

    # 5. Parts: bill of materials, placement file, board and schematic list the same references.
    with BOM.open(encoding="utf-8", newline="") as handle:
        bom_rows = list(csv.DictReader(handle))
    bom_refs = [r["Reference"] for r in bom_rows]
    board_refs = sorted(fp["ref"] for fp in footprints if fp["name"] != "Meridian:Mount_M3")
    shunt_rows = [r for r in bom_rows if r["Reference"] == "SH1-SH3"]
    bom_refs = [r for r in bom_refs if r != "SH1-SH3"]
    with PLACEMENT.open(encoding="utf-8", newline="") as handle:
        placement_refs = sorted(r["Ref"] for r in csv.DictReader(handle))
    smd_refs = sorted(fp["ref"] for fp in footprints if any(p["type"] == "smd" for p in fp["pads"]) and fp["name"] != "Meridian:TestLand_1p5mm")
    bare_lands = sorted(r["Reference"] for r in bom_rows if r["Population"] == "No purchased part")
    schematic_refs = sorted(read_schematic_refs())
    measured["parts"] = {"board": len(board_refs), "bom_rows": len(bom_refs), "placement": len(placement_refs), "schematic": len(schematic_refs)}
    check("refs-unique", "Every reference appears once in the bill of materials", [], sorted(r for r, n in Counter(bom_refs).items() if n > 1))
    check("bom-vs-board", "Bill of materials references = components on the board, plus the removable shunts", board_refs, sorted(bom_refs))
    check("bom-shunts", "The one bill-of-materials row that is not a board footprint is the removable shunts SH1-SH3",
          ["Removable shunts"], [r["Value"] for r in shunt_rows])
    check("bom-test-lands", "Rows marked 'No purchased part' are exactly the bare-copper test lands on the board",
          sorted(fp["ref"] for fp in test_lands), bare_lands)
    check("placement-vs-board", "Placement file = every fitted part with SMD pads (all on top; test lands are not placed)", smd_refs, placement_refs)
    check("schematic-vs-board", "Schematic symbols = components on the board", board_refs, schematic_refs)

    # 6. Design rules that can be re-measured from the files alone.
    min_signal = min_power = min_hole = None
    power_nets = set()
    for form in parse_sexpr(RULES.read_text(encoding="utf-8")):
        if form[0] != "rule":
            continue
        constraint, condition = child(form, "constraint"), child(form, "condition")
        value = float(child(constraint, "min")[1].removesuffix("mm")) if child(constraint, "min") else None
        if constraint[1] == "track_width" and condition:
            min_power = value
            power_nets = set(re.findall(r"'(/[A-Za-z0-9_]+)'", condition[1]))
        elif constraint[1] == "track_width":
            min_signal = value
        elif constraint[1] == "hole_size":
            min_hole = value
    measured["rules_mm"] = {"min_signal_track": min_signal, "min_power_track": min_power, "min_via_drill": min_hole,
                            "power_nets": sorted(power_nets)}
    check("rule-track-width", "Every track is at least the signal minimum in the design rules", True,
          min(widths) + 1e-9 >= min_signal)
    thin_power = sorted({s["net"] for s in segments if s["net"] in power_nets and s["width"] + 1e-9 < min_power})
    check("rule-power-width", "Tracks on the power nets named in the design rules meet the power minimum", [], thin_power)
    check("rule-via-drill", "Every via drill meets the hole-size rule", True, min(v["drill"] for v in vias) + 1e-9 >= min_hole)

    result = {"gerbonara": gerbonara.__version__ if hasattr(gerbonara, "__version__") else "unknown",
              "inputs": ["fab/gerbers/*", "fab/drill/*", "fab/top-placement.csv", "cad/bill-of-materials.csv",
                         "cad/meridian-carrier.kicad_pcb", "cad/meridian-carrier.kicad_sch", "cad/meridian-carrier.kicad_dru"],
              "not_used": ["layout.json", "verification.json", "the generator scripts"],
              "measured": measured, "checks": checks, "passed": all(c["passed"] for c in checks)}
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failed = [c for c in checks if not c["passed"]]
    print(f"{len(checks) - len(failed)} of {len(checks)} independent checks pass")
    for c in failed:
        print(f"FAILED {c['id']}: {c['description']}\n  expected {c['expected']}\n  actual   {c['actual']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
