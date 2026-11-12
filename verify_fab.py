"""Check the fabrication and assembly exports against the routed design."""

from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).parent
FAB = ROOT/"fab"


def drill_hits(path):
    data = path.read_text(encoding="ascii")
    assert "M48" in data and "M30" in data and "METRIC" in data, path.name
    return len(re.findall(r"(?m)^X[-+\d.]+Y[-+\d.]+",data))


def main():
    layout=json.loads((ROOT/"layout.json").read_text(encoding="utf-8"))
    layer_files=sorted(path for path in (FAB/"gerbers").iterdir()
                       if path.is_file() and path.suffix != ".gbrjob")
    functions={}
    for path in layer_files:
        content=path.read_text(encoding="utf-8")
        match=re.search(r"%TF\.FileFunction,([^*]+)\*%",content)
        assert match and "M02*" in content, path.name
        functions[path.name]=match.group(1)
    counts=Counter(value.split(",")[0].lower() for value in functions.values())
    assert counts==Counter(copper=4,soldermask=2,legend=1,profile=1,paste=1), counts
    copper_layers={value.split(",")[1] for value in functions.values() if value.startswith("Copper,")}
    assert copper_layers=={"L1","L2","L3","L4"},copper_layers
    plated=next(path for path in (FAB/"drill").glob("*-PTH.drl"))
    nonplated=next(path for path in (FAB/"drill").glob("*-NPTH.drl"))
    expected_pth=sum(bool(p["drill"]) for part in layout["parts"] for p in part["pads"])+len(layout["vias"])
    assert drill_hits(plated)==expected_pth, plated.name
    assert drill_hits(nonplated)==len(layout["mounting"]), nonplated.name

    with (FAB/"top-placement.csv").open(encoding="utf-8",newline="") as handle:
        placements={row["Ref"] for row in csv.DictReader(handle)}
    expected_smd={part["ref"] for part in layout["parts"] if not part["ref"].startswith("TP") and not any(p["drill"] for p in part["pads"])}
    assert placements==expected_smd,(placements,expected_smd)
    test_netlist=FAB/"meridian-carrier.d356"
    assert test_netlist.read_text(encoding="ascii").count("\n")>len(layout["parts"])

    deliverables=sorted(path for path in FAB.rglob("*") if path.is_file() and path.name not in {"README.md","manifest.sha256"})
    manifest="".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(FAB).as_posix()}\n"
                     for path in deliverables)
    (FAB/"manifest.sha256").write_bytes(manifest.encode("ascii"))
    result={"gerber_functions":functions,"plated_drill_hits":expected_pth,
            "nonplated_drill_hits":len(layout["mounting"]),"top_smd_placements":len(placements),
            "export_hashes":len(deliverables)}
    (ROOT/"reports"/"fabrication-summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
