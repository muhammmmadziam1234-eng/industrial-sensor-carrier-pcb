# Revision B interface and assembly notes

Meridian uses regulated 3.3 V power. JP3 selects one source: pins 1–2 select the controller supply on J1, pins 2–3 select the auxiliary input at J7, and a removed shunt disconnects both sources from the carrier rail. Power off before changing the shunt.

| J1 pin | Signal | J1 pin | Signal |
| ---: | --- | ---: | --- |
| 1 | CTRL_3V3 | 2 | SPI_SCK |
| 3 | GND | 4 | SPI_MOSI |
| 5 | OUT0 | 6 | SPI_MISO |
| 7 | OUT1 | 8 | SPI_CS0 |
| 9 | LED0 | 10 | UART_TX |
| 11 | LED1 | 12 | UART_RX |
| 13 | RESET_N | 14 | RS_DIR |
| 15 | GPIO0 | 16 | I2C_SDA |
| 17 | GPIO1 | 18 | I2C_SCL |
| 19 | GPIO2 | 20 | ADC0 |
| 21 | GPIO3 | 22 | ADC1 |
| 23 | CTRL_3V3 | 24 | GND |

| Reference | Pins in numerical order | Assembly or hookup note |
| --- | --- | --- |
| J2 | RS_B, RS_A, GND | Use a common-ground bench peer. Confirm A/B polarity from the peer’s documentation. |
| J3 | 3V3, GND, SPI_SCK, SPI_MOSI, SPI_MISO, SPI_CS0 | Check the peripheral mode and clock rate. |
| J4 | 3V3, GND, I2C_SDA, I2C_SCL | Install JP2 only if the assembled bus needs the onboard pull-ups. |
| J5 | ADC0_RAW, ADC1_RAW, GND | Input range is set by the attached controller and is limited to the bench interface envelope. |
| J6 | LOAD0, LOAD1, GND | Open-drain outputs. Use an external current-limited load supply and a shared ground. |
| J7 | AUX_3V3, GND | Regulated auxiliary input. Select it with JP3 pins 2–3. |
| J8 | GPIO0, GPIO1, GPIO2, GPIO3, RESET_N, GND | 3.3 V signals through from the controller. |
| JP1 | TERM_SW, RS_B | One shunt enables the 120 Ω resistor. Enable at the cable end only. |
| JP2 | 3V3, I2C_PULLUP | One shunt enables both pull-ups. |
| JP3 | CTRL_3V3, 3V3, AUX_3V3 | Use one shunt in one position. |
| D1, D2 | Cathode, anode | Pad 1 is GND. Verify the package polarity at assembly. |

TP1 and TP2 expose the carrier rail and ground. TP3–TP5 cover UART TX, UART RX and DIR. TP6 and TP7 expose I²C. TP8 and TP9 expose the filtered analog inputs. TP10 is reset, TP11 is controller power, and TP12 is auxiliary power.

The [CAD pad map](cad/pad-net-map.csv) uses the lower-left DXF origin. The [engineering basis](engineering-basis.md) and [bring-up plan](bring-up.md) record assumptions and expected review evidence.
