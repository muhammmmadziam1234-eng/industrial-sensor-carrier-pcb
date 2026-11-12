"""Read back the KiCad board-only STEP and compare its mounting geometry to Excellon."""

import argparse
import json
import re
from pathlib import Path

from board import GRID, H, MOUNTING, W

ROOT = Path(__file__).resolve().parent
STEP = ROOT / "cad" / "meridian-carrier-board.step"
DRILL = ROOT / "fab" / "drill" / "meridian-carrier-NPTH.drl"
EXPECTED_MOUNT_DIAMETER = 3.2


def parse_step(step_path):
    source = step_path.read_text(encoding="ascii")
    if not source.startswith("ISO-10303-21;") or "SI_UNIT(.MILLI.,.METRE.)" not in source:
        raise ValueError("Expected a millimetre STEP exchange file")
    entities = dict(re.findall(r"#(\d+)\s*=\s*(.+?);", source, flags=re.S))
    if sum(entity.startswith("MANIFOLD_SOLID_BREP(") for entity in entities.values()) != 1:
        raise ValueError("Expected one board solid")

    def point(reference):
        match = re.fullmatch(r"CARTESIAN_POINT\('[^']*',\s*\(([^)]+)\)\)", entities[reference])
        if match is None:
            raise ValueError(f"Invalid point #{reference}")
        return tuple(float(axis) for axis in match[1].split(","))

    vertices = []
    mounting = set()
    for entity in entities.values():
        vertex = re.fullmatch(r"VERTEX_POINT\('[^']*',\s*#(\d+)\)", entity)
        if vertex:
            vertices.append(point(vertex[1]))
        cylinder = re.fullmatch(r"CYLINDRICAL_SURFACE\('[^']*',\s*#(\d+),\s*([^\s)]+)\)", entity)
        if cylinder and abs(float(cylinder[2]) * 2 - EXPECTED_MOUNT_DIAMETER) < 1e-6:
            axis = re.fullmatch(r"AXIS2_PLACEMENT_3D\('[^']*',\s*#(\d+),.*\)", entities[cylinder[1]], re.S)
            if axis is None:
                raise ValueError("Mounting bore has no axis placement")
            mounting.add(tuple(round(value, 3) for value in point(axis[1])[:2]))
    if not vertices:
        raise ValueError("Board solid contains no vertices")
    return vertices, mounting


def verify(step_path, drill_path):
    vertices, step_mounting = parse_step(step_path)
    extent = [round(max(v[i] for v in vertices) - min(v[i] for v in vertices), 3) for i in range(3)]
    expected_xy = [round(axis * GRID, 3) for axis in (W, H)]
    if extent[:2] != expected_xy:
        raise ValueError(f"STEP outline is {extent[:2]} mm, expected {expected_xy} mm")

    drill = drill_path.read_text(encoding="ascii")
    hits = [
        (round(float(x), 3), round(float(y), 3))
        for x, y in re.findall(r"^X([-+0-9.]+)Y([-+0-9.]+)$", drill, flags=re.M)
    ]
    tools = [float(diameter) for diameter in re.findall(r"^T\d+C([0-9.]+)$", drill, flags=re.M)]
    expected_mounting = {(round(x * GRID, 3), round(-y * GRID, 3)) for x, y in MOUNTING}
    if (
        tools != [EXPECTED_MOUNT_DIAMETER]
        or len(hits) != len(expected_mounting)
        or set(hits) != expected_mounting
        or step_mounting != expected_mounting
    ):
        raise ValueError(f"Mounting geometry mismatch: STEP={sorted(step_mounting)}, Excellon={hits}")
    return {
        "board_outline_xy_mm": extent[:2],
        "step_solid_z_span_mm": extent[2],
        "mounting_bore_diameter_mm": EXPECTED_MOUNT_DIAMETER,
        "step_and_excellon_mounting_centers_mm": sorted(step_mounting),
        "coordinate_origin": "KiCad board origin, X right and Y up in STEP",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, default=STEP)
    parser.add_argument("--drill", type=Path, default=DRILL)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(verify(args.step, args.drill), indent=2) + "\n"
    if args.report:
        args.report.write_bytes(rendered.encode("utf-8"))
    print(rendered, end="")


if __name__ == "__main__":
    main()
