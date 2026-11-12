# Revision B bench bring-up

Use the [schematic](cad/meridian-carrier.kicad_sch), [net map](cad/pad-net-map.csv), and [assembly bill of materials](cad/bill-of-materials.csv) together. Record the board serial, revision, source voltage, current limit, jumper positions, controller and firmware revision with every run.

| Stage | Setup and procedure | Record |
| --- | --- | --- |
| Visual and continuity inspection | Inspect the solder joints, especially U1 and the LED polarity. Check the J1 pin-1 marking and connector orientation. With JP3 removed, check separation among CTRL_3V3, AUX_3V3, and the carrier 3V3 rail. Check that 3V3 is free of a hard short to GND. | Resistance and observations at TP1, TP2, TP11 and TP12. |
| First power | Leave accessories and bus disconnected. Use a current-limited regulated 3.3 V supply at J7 and fit JP3 between pins 2 and 3. Check TP1 against TP2 and confirm TP11 does not rise to the supply rail. Power down before switching sources. Repeat on J1 with pins 1–2 selected and check TP12. | Rail voltage, current after startup, and inactive-source voltage for both cases. |
| RS-485 | Start with JP1 open. Confirm DIR is low during controller reset. Connect a common-ground bench peer over a short twisted pair. Fit termination only at both physical cable ends. Send known frames at the planned baud rate and observe A/B plus DIR during the transmit/receive turn. | Termination setting, baud rate, peak differential waveform, turnaround timing and frame errors. |
| I²C and SPI | Test I²C with JP2 selected only when needed. Start at 100 kHz and measure rise time with all intended devices attached. Exercise SPI with a known peripheral at the intended clock rate and verify chip select timing. | Bus speed, I²C rise time, acknowledgment and SPI transfer evidence. |
| Analog inputs | Apply safe DC steps between ground and the controller’s supported ADC range. Compare raw and filtered points while changing acquisition time. Check channels separately. | Gain, offset, settling and adjacent-channel interaction at the actual sample rate. |
| Load outputs | Start with a current-limited 3.3 V resistive test load and a common ground. Verify the gates remain low at reset and each channel switches independently. Keep the bench load at or below 100 mA per channel during this first qualification. | Gate voltage, drain voltage, current and temperature rise. |

These checks require an assembled board. The CAD evidence covers only the design files. Log observations and escalate unexpected heating, source backfeed or current draw before proceeding.
