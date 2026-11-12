"""Assembly selections and sourcing fields for the Revision B handoff."""

TDK = "https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no="
PASSIVES = {
    "100 nF": ("TDK", "C1608X7R1E104K080AA", "0603 X7R, 25 V, ±10%"),
    "4.7 uF": ("TDK", "C2012X5R1E475K125AB", "0805 X5R, 25 V, ±10%"),
    "22 uF": ("TDK", "C2012X5R1A226M125AB", "0805 X5R, 10 V, ±20%"),
}
RESISTORS = {
    "10 k":"10KL", "120 ohm":"120RL", "4.7 k":"4K7L",
    "1 k":"1KL", "100 ohm":"100RL", "100 k":"100KL", "680 ohm":"680RL",
}
FIXED = {
    "THVD1410DR": ("Texas Instruments","THVD1410DR","SOIC D, half-duplex transceiver","https://www.ti.com/product/THVD1410/part-details/THVD1410DR"),
    "AO3400A": ("Alpha & Omega Semiconductor","AO3400A","SOT-23, gate/source/drain pins 1/2/3","https://www.aosmd.com/sites/default/files/res/data_sheets/AO3400A.pdf"),
    "Green LED": ("Lite-On","LTST-C190KGKT","0603 green, pin 1 cathode","https://optoelectronics.liteon.com/upload/download/DS22-2000-074/LTST-C190KGKT.PDF"),
}

def selection(part):
    ref,value,package = part["ref"],part["value"],part["package"]
    if value in FIXED:
        return (*FIXED[value], "Fit")
    if value in PASSIVES:
        manufacturer,mpn,notes = PASSIVES[value]
        return manufacturer,mpn,notes,TDK+mpn,"Fit"
    if ref.startswith("R"):
        mpn = f"RC{package}FR-07{RESISTORS[value]}"
        return "Yageo",mpn,"1% thick-film resistor","https://www.yageo.com/en/Product/Index/rchip", "Fit"
    if ref.startswith("J"):
        count = 12 if ref=="J1" else len(part["pads"])
        suffix = "D" if ref=="J1" else "S"
        mpn = f"TSW-{100+count}-07-L-{suffix}"
        return "Samtec",mpn,"Vertical 2.54 mm header; review mating connector",f"https://www.samtec.com/products/{mpn.lower()}","Fit"
    if ref.startswith("TP"):
        return "","","Bare copper test land","","No purchased part"
    raise ValueError(f"No purchasing selection for {ref}")
