# Interface and assembly notes

The controller at J1 supplies logic and peripheral power from a regulated 3.3 V rail. J7 is an alternative feed for bench work. Connect one regulated source and verify the common ground before adding peripherals.

| J1 pin | Odd column | J1 pin | Even column |
| ---: | --- | ---: | --- |
| 1 | 3V3 | 2 | GND |
| 3 | SPI_SCK | 4 | SPI_MOSI |
| 5 | SPI_MISO | 6 | SPI_CS0 |
| 7 | UART_TX | 8 | UART_RX |
| 9 | RS_DIR | 10 | I2C_SDA |
| 11 | I2C_SCL | 12 | ADC0 |
| 13 | ADC1 | 14 | OUT0 |
| 15 | OUT1 | 16 | LED0 |
| 17 | LED1 | 18 | RESET_N |
| 19 | GPIO0 | 20 | GPIO1 |
| 21 | GPIO2 | 22 | GPIO3 |
| 23 | GND | 24 | 3V3 |

| Block | Design detail | Bench review |
| --- | --- | --- |
| RS-485 | R1 pulls RS_DIR low. It drives both DE and active-low RE. R2 and JP1 provide switchable 120 Ω across A/B. | Confirm receiver mode at reset, termination at the cable ends and A/B polarity at both devices. |
| I²C | R3 and R4 connect to the pull-up rail when JP2 is fitted. | Fit JP2 only after accounting for the other pull-ups and checking rise times. |
| ADC | R5/C5 and R6/C6 each give a nominal 1.59 kHz first-order low-pass corner. | Check source impedance, ADC acquisition time and input amplitude. |
| Open-drain | 100 Ω gate resistors and 100 kΩ pull-downs. Loads connect to their own limited source and a common ground. | Verify both channels start off and use a current-limited resistive bench load. External inductive loads need suitable suppression. |
| Power | C3/C4 are placed near J7. C1/C2 sit beside the transceiver supply. | Power up under current limit and check 3V3 at TP1, then check it during bus activity. |

All capacitors and resistors require part-level selection before procurement. The coordinate table includes drill diameters and uses the DXF origin. A real board release needs an independent schematic-to-layout review, connector and footprint confirmation, full fabrication DRC, signal integrity review and physical bench measurements.
