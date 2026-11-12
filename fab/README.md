# Prototype fabrication package

Reference stack, top to bottom: F.Cu signal and power traces, In1.Cu ground, In2.Cu 3.3 V, B.Cu signal and power traces. Request 1.60 mm nominal FR-4 and confirm available outer and inner copper weights with the fabricator before ordering. The plan uses standard plated through vias, separate plated and nonplated drills, and a 101.60 × 76.20 mm chamfered profile. Mounting holes are 3.20 mm nonplated.

Use the checked KiCad board and drill outputs as the manufacturing source. The DXF is the mechanical and copper-intent exchange drawing. In the fabricator preview, inspect all four copper layers, solder mask, plated and nonplated drill sets, and the routed outline. Confirm the four corner holes stay nonplated and that the two inner zones appear on their intended layers. Review component land patterns and tolerances against the selected parts, and confirm the jumper and connector orientation before assembly.

## Files for the review

- [Gerbers](gerbers) include four copper layers, both solder masks, top legend, top paste and outline.
- [Drill files and maps](drill) separate plated and nonplated holes.
- [Top placement CSV](top-placement.csv) contains fitted SMD locations. Connectors are through-hole and use the assembly pin map. Test lands receive no paste or placement.
- [IPC-D-356 netlist](meridian-carrier.d356) provides the electrical test reference.
- [SHA-256 manifest](manifest.sha256) identifies the exported file bytes.

## Reproduce with KiCad 10

Use the project root as the working directory and create the `reports`, `fab/gerbers`, and `fab/drill` directories if they do not exist. Run the following checks after rebuilding the source files. The board must contain up-to-date fills before plotting.

~~~sh
kicad-cli sch erc --format json --severity-all --exit-code-violations --output reports/erc.json cad/meridian-carrier.kicad_sch
kicad-cli sch export netlist --format kicadxml --output reports/schematic-netlist.xml cad/meridian-carrier.kicad_sch
kicad-cli sch export pdf --output reports/meridian-schematic.pdf cad/meridian-carrier.kicad_sch
kicad-cli pcb drc --format json --severity-all --schematic-parity --refill-zones --save-board --exit-code-violations --output reports/drc.json cad/meridian-carrier.kicad_pcb
python verify_native.py
kicad-cli pcb export gerbers --check-zones --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,Edge.Cuts,F.Paste --output fab/gerbers/ cad/meridian-carrier.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-separate-th --excellon-units mm --generate-map --map-format pdf --output fab/drill/ cad/meridian-carrier.kicad_pcb
kicad-cli pcb export pos --side front --format csv --units mm --smd-only --output fab/top-placement.csv cad/meridian-carrier.kicad_pcb
kicad-cli pcb export ipcd356 --output fab/meridian-carrier.d356 cad/meridian-carrier.kicad_pcb
python verify_fab.py
~~~

## Mechanical exchange and board image

Export and check the board-only STEP after a CAD change. Enclosure mounting geometry uses the same origin as the nonplated Excellon file. Use the schematic, parts list and supplier drawings for populated clearance.

~~~sh
kicad-cli pcb export step --board-only --no-components --force --output cad/meridian-carrier-board.step cad/meridian-carrier.kicad_pcb
python verify_mechanical.py --report reports/mechanical-summary.json
kicad-cli pcb render --width 1660 --height 1080 --side top --rotate 31,0,24 --zoom 0.93 --quality high --background transparent --output media/meridian-board-render.png cad/meridian-carrier.kicad_pcb
~~~
