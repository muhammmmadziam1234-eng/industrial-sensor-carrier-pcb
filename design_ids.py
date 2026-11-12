"""Stable identifiers shared by the schematic and board exporters."""

from uuid import NAMESPACE_URL, uuid5


def design_uuid(label):
    return str(uuid5(NAMESPACE_URL, f"meridian-carrier/{label}"))


ROOT_UUID = design_uuid("schematic")
PROJECT = "meridian-carrier"


def footprint_name(part):
    package = part["package"]
    if package == "1.5 mm test land":
        return "TestLand_1p5mm"
    if package == "SOIC-8 3.9 mm":
        return "SOIC_8_3p9x4p9mm"
    if package == "SOT-23":
        return "SOT_23"
    if package == "2.54 mm 2x12":
        return "Header_2x12_P2p54mm"
    pins = part["pads"]
    axis = "V" if pins[0]["x"] == pins[-1]["x"] else "H"
    if package.startswith("2.54 mm"):
        return f"Header_1x{len(pins):02d}_{axis}_P2p54mm"
    return f"Chip_{package}_{axis}"


def footprint_id(part):
    return f"Meridian:{footprint_name(part)}"
