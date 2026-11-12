"""Prove the verifier rejects two representative broken layouts."""
from copy import deepcopy
import json
from pathlib import Path
from verify import inspect

layout=json.loads((Path(__file__).parent/"layout.json").read_text(encoding="utf-8"))
assert inspect(layout)["errors"]==[], "Known-good layout"
short=deepcopy(layout)
pad=next(p for f in short["parts"] for p in f["pads"] if p["net"]=="SPI_CS0")
x,y=pad["x"],pad["y"]
short["traces"].append(["GND",[x-2,y,0],[x+2,y,0]])
assert any("clearance" in error for error in inspect(short)["errors"]), "Shorted pad escaped"
opened=deepcopy(layout)
opened["traces"]=[track for track in opened["traces"] if track[0]!="SPI_CS0"]
assert any("Disconnected copper on SPI_CS0" in error for error in inspect(opened)["errors"]), "Open net escaped"
print("Three verification probes passed: reference geometry, deliberate short, deliberate open.")
