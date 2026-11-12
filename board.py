"""Source netlist and component placement for the Meridian I/O carrier."""
from dataclasses import dataclass
from collections import defaultdict

GRID = 0.254
W, H = 400, 300
MOUNTING = [(21, 21), (379, 21), (21, 279), (379, 279)]
LAYER_NAMES = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
SIGNAL_WIDTH = .254
POWER_WIDTH = .508
POWER_NETS = frozenset({'3V3', 'CTRL_3V3', 'AUX_3V3', 'GND', 'LOAD0', 'LOAD1'})
PLANES = {1: 'GND', 2: '3V3'}


def track_width(net):
    return POWER_WIDTH if net in POWER_NETS else SIGNAL_WIDTH

CLEARANCE = .254
VIA_DIA = .70
VIA_DRILL = .30

@dataclass(frozen=True)
class Pad:
    ref: str
    pin: int
    net: str
    x: int
    y: int
    width: float
    height: float
    drill: float = 0

    @property
    def layers(self):
        return range(4) if self.drill else (0,)

@dataclass
class Part:
    ref: str
    value: str
    package: str
    x: int
    y: int
    pads: list

PARTS = []

def part(ref, value, package, x, y, specs, size, drill=0):
    pads = [Pad(ref, i + 1, net, x + dx, y + dy, *size, drill)
            for i, (dx, dy, net) in enumerate(specs)]
    PARTS.append(Part(ref, value, package, x, y, pads))

def header(ref, value, x, y, nets, horizontal=False):
    coords = [(10*i, 0, net) if horizontal else (0, 10*i, net)
              for i, net in enumerate(nets)]
    part(ref, value, f"2.54 mm 1x{len(nets)}", x, y, coords, (1.75, 1.75), 1.05)

def two(ref, value, package, x, y, a, b, vertical=False):
    pitch = 3 if package == "0603" else 4
    offsets = [(0, -pitch, a), (0, pitch, b)] if vertical else [(-pitch, 0, a), (pitch, 0, b)]
    size = (.95, .90) if package == "0603" else (1.18, 1.25)
    if vertical:
        size = size[::-1]
    part(ref, value, package, x, y, offsets, size)

controller = [
    "CTRL_3V3", "GND", "SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS0",
    "UART_TX", "UART_RX", "RS_DIR", "I2C_SDA", "I2C_SCL", "ADC0",
    "ADC1", "OUT0", "OUT1", "LED0", "LED1", "RESET_N",
    "GPIO0", "GPIO1", "GPIO2", "GPIO3", "GND", "CTRL_3V3",
]
part("J1", "Controller interface", "2.54 mm 2x12", 152, 83,
     [(10*(i % 2), 10*(i//2), net) for i, net in enumerate(controller)],
     (1.75, 1.75), 1.05)

header("J2", "RS-485 bus", 366, 54, ["RS_B", "RS_A", "GND"])
header("J3", "SPI expansion", 366, 99, ["3V3", "GND", "SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS0"])
header("J4", "I2C expansion", 366, 171, ["3V3", "GND", "I2C_SDA", "I2C_SCL"])
header("J5", "Analog inputs", 366, 226, ["ADC0_RAW", "ADC1_RAW", "GND"])
header("J6", "Open-drain outputs", 45, 216, ["LOAD0", "LOAD1", "GND"])
header("J7", "Auxiliary 3.3 V input", 44, 55, ["AUX_3V3", "GND"])
header("J8", "GPIO expansion", 44, 92, ["GPIO0", "GPIO1", "GPIO2", "GPIO3", "RESET_N", "GND"])
header("JP1", "RS-485 termination enable", 342, 86, ["TERM_SW", "RS_B"], True)
header("JP2", "I2C pull-up enable", 323, 198, ["3V3", "I2C_PULLUP"], True)
header("JP3", "3.3 V source select", 72, 41, ["CTRL_3V3", "3V3", "AUX_3V3"], True)

part("U1", "THVD1410DR", "SOIC-8 3.9 mm", 298, 58,
     [(-10, -8, "UART_RX"), (-10, -3, "RS_DIR"), (-10, 2, "RS_DIR"), (-10, 7, "UART_TX"),
      (10, 7, "GND"), (10, 2, "RS_A"), (10, -3, "RS_B"), (10, -8, "3V3")],
     (1.76, .65))
two("R1", "10 k", "0603", 260, 58, "RS_DIR", "GND")
two("R2", "120 ohm", "0805", 342, 66, "RS_A", "TERM_SW", True)
two("C1", "100 nF", "0603", 313, 40, "3V3", "GND")
two("C2", "4.7 uF", "0805", 332, 40, "3V3", "GND")
two("C3", "22 uF", "0805", 76, 59, "3V3", "GND")
two("C4", "100 nF", "0603", 96, 59, "3V3", "GND")
two("R3", "4.7 k", "0603", 305, 176, "I2C_SDA", "I2C_PULLUP")
two("R4", "4.7 k", "0603", 305, 188, "I2C_SCL", "I2C_PULLUP")
two("R5", "1 k", "0603", 309, 221, "ADC0_RAW", "ADC0")
two("R6", "1 k", "0603", 309, 238, "ADC1_RAW", "ADC1")
two("C5", "100 nF", "0603", 284, 221, "ADC0", "GND", True)
two("C6", "100 nF", "0603", 284, 240, "ADC1", "GND", True)

for i, y in enumerate((210, 242)):
    gate = f"GATE{i}"
    part(f"Q{i+1}", "AO3400A", "SOT-23", 92, y,
         [(-4, 4, gate), (4, 4, "GND"), (0, -4, f"LOAD{i}")], (.87, 1.00))
    two(f"R{7 + i*2}", "100 ohm", "0603", 122, y - 5, f"OUT{i}", gate)
    two(f"R{8 + i*2}", "100 k", "0603", 122, y + 9, gate, "GND")
    two(f"R{11 + i}", "680 ohm", "0603", 211 + 39*i, 250, f"LED{i}", f"LED_AN{i}")
    two(f"D{i+1}", "Green LED", "0603", 211 + 39*i, 268, "GND", f"LED_AN{i}")

for i, (net, x, y) in enumerate([
    ("3V3", 119, 42), ("GND", 137, 42), ("UART_TX", 241, 84),
    ("UART_RX", 259, 84), ("RS_DIR", 277, 84), ("I2C_SDA", 269, 177),
    ("I2C_SCL", 269, 190), ("ADC0", 260, 221), ("ADC1", 260, 240),
    ("RESET_N", 87, 158), ("CTRL_3V3", 125, 64), ("AUX_3V3", 59, 42),
], 1):
    part(f"TP{i}", net, "1.5 mm test land", x, y, [(0, 0, net)], (1.5, 1.5))

PADS = [pad for item in PARTS for pad in item.pads]
NETS = defaultdict(list)
for pad in PADS:
    NETS[pad.net].append(pad)

if __name__ == "__main__":
    print(f"{len(PARTS)} footprints, {len(PADS)} pads, {len(NETS)} nets")
    print("Nets with fewer than two pads:", [net for net, pads in NETS.items() if len(pads) < 2])
