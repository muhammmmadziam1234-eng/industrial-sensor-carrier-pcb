"""Compare KiCad's exported schematic netlist with the source pad map."""

from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

from board import PADS


def netlist_map(path):
    root = ET.parse(path).getroot()
    actual = {}
    for net in root.findall("./nets/net"):
        name = net.attrib["name"].lstrip("/")
        for node in net.findall("node"):
            ref = node.attrib["ref"]
            if ref.startswith("#"):
                continue
            key = (ref, node.attrib["pin"])
            if key in actual:
                raise ValueError(f"{key} occurs on multiple schematic nets")
            actual[key] = name
    return actual


def summarize_report(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    groups = ("violations", "unconnected_items", "schematic_parity")
    violations = [item for field in groups for item in report.get(field, [])]
    for sheet in report.get("sheets", []):
        violations.extend(sheet.get("violations", []))
    errors = sum(item.get("severity") == "error" for item in violations)
    warnings = sum(item.get("severity") == "warning" for item in violations)
    return {"errors": errors, "warnings": warnings, "items": len(violations)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_dir", type=Path, nargs="?", default=Path("reports"))
    args = parser.parse_args()
    report_dir = args.report_dir
    expected = {(p.ref,str(p.pin)):p.net for p in PADS}
    actual = netlist_map(report_dir/"schematic-netlist.xml")
    diff = [
        (key,expected.get(key),actual.get(key)) for key in sorted(expected.keys() | actual.keys())
        if expected.get(key)!=actual.get(key)
    ]
    summary = {
        "schematic_pad_count":len(actual),
        "source_pad_count":len(expected),
        "differing_pad_assignments":len(diff),
        "erc":summarize_report(report_dir/"erc.json"),
        "drc":summarize_report(report_dir/"drc.json"),
    }
    (report_dir/"native-summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
    if diff:
        print(f"Netlist differences: {diff[:12]}")
    return 1 if diff or summary["erc"]["errors"] or summary["drc"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
