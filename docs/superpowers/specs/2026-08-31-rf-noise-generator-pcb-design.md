# 50 MHz–3 GHz Four-Output Battery Noise Generator PCB Design

## Status

This specification freezes the first-prototype architecture selected by the user: option A, a low-cost 50 MHz–3 GHz, four-output laboratory noise generator powered by a two-cell 2S lithium-ion pack. It authorizes local design work but does not authorize purchasing, ordering, or transmitting outside a shielded enclosure.

## User-Facing Summary

The board produces a weak broadband random RF signal, amplifies it twice, reduces it by a selectable resistor attenuator, and divides it into four nominally 50-ohm SMA outputs. It runs from two matched 18650 or two matched 21700 cells connected in series. An external 15 V source has priority while connected: it powers the RF section and charges the battery on separate branches. Removing external power automatically returns the RF section to battery operation.

The user is expected to assemble specialist RF parts, connect a documented battery/BMS harness, and perform basic measurements, but is not expected to make circuit-design decisions.

The first PCB is an engineering prototype. Its component values, DC operating points, impedance geometry, and manufacturing files can be calculated and checked before fabrication. Its absolute noise level and spectral flatness cannot be guaranteed until the avalanche transistor and assembled PCB are measured.

## Safety and Use Boundary

- Use only inside a shielded room or fully enclosed RF shield box.
- During assembly and bench tests, terminate all four outputs with 50-ohm loads.
- Do not connect antennas in an open room or outdoors.
- Use two cells of the same manufacturer, model, capacity, age, and initial state of charge. Do not mix 18650 and 21700 cells.
- Never bypass the 2S BMS, cell-balancing connections, pack fuse, or keyed battery connector.
- Assemble and verify the BMS harness before inserting cells. Do not solder directly to bare lithium-ion cells; use a suitable holder or a professionally tab-welded pack.
- Apply power through the dedicated current-limited 12 V RF-rail test input during initial RF bring-up, before connecting the battery or charger.
- The board silkscreen shall state `SHIELDED-ROOM USE ONLY` and `TERMINATE UNUSED PORTS 50R`.
- No external high-power amplifier is part of this design.

## Acceptance Boundary

### Pre-Fabrication Acceptance

- Editable schematic and PCB source files exist.
- Electrical-rule and design-rule checks pass in the selected EDA tool.
- Calculations cover MMIC bias, resistor dissipation, attenuator matching, four-way splitter matching, and estimated 50-ohm transmission-line geometry.
- Gerbers, drills, BOM, and CPL conform to JLCPCB file-format requirements.
- All unverified RF claims are marked as estimates or prototype measurements.
- The power system has documented no-backfeed behavior, external-power priority, battery under-voltage protection, and separate charge and load current paths.
- The charger cannot see normal RF-board load current as battery charge current while external power is present.

### Prototype Measurement Targets

- Intended usable band: 50 MHz–3 GHz.
- Target spectral flatness after calibration: within a 10 dB peak-to-peak window, equivalent to a nominal ±5 dB target.
- All four ports show broadband noise above the spectrum-analyzer noise floor when measured with suitable RBW and external attenuation.
- Port-to-port noise-power difference target: no more than 2 dB with identical 50-ohm terminations.
- Intended calibrated total power per output: between -30 dBm and -10 dBm over the full band.
- Do not connect antennas if any port measures above -10 dBm integrated power until additional fixed attenuation is installed.
- No persistent narrow spectral line more than 10 dB above the local noise baseline; such a line is treated as oscillation or power-supply contamination.
- Automatic external-to-battery and battery-to-external transfer does not create a sustained over-voltage or reverse-current condition.
- Conducted RF acceptance measurements are performed in battery-only quiet mode with the external 15 V source unplugged.

The targets above are prototype acceptance goals, not pre-fabrication guarantees.

## System Architecture

```text
 external 15 V DC --------------------------+
       |                                     |
       +-- TP5100 2S charger --> 2S BMS --> matched 2S cells
       |
       +-- L78M12 clean 12 V ----+
                                  | external-power-priority relay
 2S BMS protected output          | and battery-boost interlock
       |                          v
       +-- MT3608 12 V boost --> source selector --> RF enable
                                                      |
                                           staged supply filtering
                                               |             |
                                          source bias   isolated MMIC branches

MMBT3904 reverse-BE noise source
          |
      DC block
          |
      ERA-3SM+ U1
          |
      DC block
          |
 configurable 50-ohm pi attenuator
          |
      ERA-3SM+ U2
          |
      DC block
          |
  five-arm resistive 1-to-4 divider
     |          |          |          |
   SMA1       SMA2       SMA3       SMA4
```

An unpopulated calibration-input SMA footprint is provided before U1. A mutually exclusive solder-link arrangement selects either the avalanche source or the calibration input. This permits conducted VNA testing without changing the four output connectors.

The BMS, charger, boost converter, source selector, and RF filter are separate functions. A board sold as a “2S protection board” is not treated as a charger or as a load-sharing controller.

## Noise Source

### Device and Topology

- Q1 is an MMBT3904 in SOT-23.
- The collector is left electrically unconnected.
- The base is connected to RF ground with the shortest practical path and a nearby ground via.
- The emitter is reverse-biased from the filtered 12 V rail through a replaceable bias resistor.
- Noise is extracted from the emitter through a series RF DC-block capacitor into the 50-ohm U1 input.

### Bias Provision

- Default source resistor: 10.0 kohm, 1%, 0603.
- Alternate documented values: 6.81 kohm and 15.0 kohm.
- With an approximate 6–8 V reverse-BE breakdown, these values provide a practical sub-milliampere experiment range from a 12 V rail.
- The board provides one source-bias voltage test point and no user-accessible RF-frequency potentiometer.
- The schematic and assembly guide state that Q1 operates outside a data-sheet-guaranteed normal mode and may need sample selection.

The design does not derive a guaranteed output noise density from the MMBT3904 data sheet. Absolute level, temperature drift, and flatness are measured properties.

## MMIC Gain Chain

### Amplifiers

- U1 and U2 are Mini-Circuits ERA-3SM+ in the WW107 package.
- Recommended operating current is 35 mA per device.
- Typical device voltage is approximately 3.2 V.
- The manufacturer specifies operation through 3 GHz and lists typical gain near 18.7 dB.
- Nominal two-stage small-signal gain before pads and divider is approximately 37 dB; the actual frequency-dependent value shall be calculated from manufacturer S-parameters.

### Bias

- Supply voltage: 12 V nominal.
- Nominal bias resistance per MMIC: 249 ohm, 1%.
- Each 249-ohm function is implemented as two 499-ohm, 1%, 1206 resistors in parallel.
- At 35 mA, total bias-resistor dissipation is approximately 0.31 W; each 499-ohm resistor dissipates approximately 0.153 W, below a 0.25 W rating but above ordinary 0805 design comfort.
- Each amplifier has a separate filtered bias branch and separate current-measurement link.

### Broadband Bias Strategy

The first prototype feeds the MMIC output/bias pin through the required bias resistance without populating a narrowband series RF choke. This intentionally accepts approximately 1 dB of additional loading to avoid a low-cost inductor resonance inside the 50 MHz–3 GHz band.

Each bias path includes an optional series-choke footprint and bypass footprint for later experiments. The default BOM marks the choke as not populated. The DC supply before each bias resistor uses a ferrite-bead pi filter with local bulk, mid-band, and high-frequency bypass capacitors.

## Coupling and Bypass Capacitors

- RF coupling positions use C0G/NP0 capacitors in 0402 or smaller footprints.
- The initial assembly value is 100 pF.
- The PCB includes a compact alternative pad arrangement that permits a characterized broadband capacitor to replace the generic 100 pF part without rerouting.
- The design calculation shall evaluate series reactance at 50 MHz and package parasitics at 3 GHz.
- Different capacitor values are not blindly paralleled across the RF path because anti-resonance can create a spectral notch.
- Supply bypass values are staged as 10 uF, 1 uF, 100 nF, and 1 nF, with the smallest package closest to the relevant bias node.

## Configurable Pi Attenuator

The interstage attenuator uses three 0402 thin-film resistors: two shunt arms and one series arm. Values are changed by soldering a complete matched set; the board does not use a mechanical potentiometer or a long multi-position switch in the RF path.

| Nominal attenuation | Input/output shunt | Series arm | Initial E96 population |
|---:|---:|---:|---:|
| 6 dB | 150.5 ohm | 37.4 ohm | 150 ohm / 37.4 ohm |
| 10 dB | 96.2 ohm | 71.2 ohm | 96.5 ohm / 71.5 ohm |
| 15 dB | 71.6 ohm | 136.1 ohm | 71.5 ohm / 137 ohm |
| 20 dB | 61.1 ohm | 247.5 ohm | 61.9 ohm / 249 ohm |

The default prototype population is 10 dB. The assembly guide explains how to replace all three resistors as one set.

## Four-Way Output Divider

The first prototype uses a five-port resistive star:

- One 30.1-ohm 0402 resistor from U2 output to the star center.
- Four identical 30.1-ohm 0402 resistors from the star center to the four SMA transmission lines.
- All five resistors are placed symmetrically with minimal center-node copper area.
- With all other ports terminated in 50 ohms, every port is nominally matched to 50 ohms.
- Ideal amplitude transmission from input to each output is 0.4, corresponding to approximately 7.96 dB insertion loss.
- Output-to-output isolation is also only approximately 7.96 dB; this is an accepted low-cost tradeoff.

Unused outputs must remain terminated. A later four-buffer revision is outside the first-prototype scope.

## Battery, Charging, and Power Control

### Battery Pack and Protection

- Battery: two matched 18650 cells or two matched 21700 cells in 2S series, 7.4 V nominal and 8.4 V fully charged.
- The pack uses a common-port 2S balancing BMS with `B+`, `BM`, `B-`, `P+`, and `P-` connections and at least a 2 A continuous-current rating.
- The BMS is mounted with the external battery holder or tab-welded pack. Only its protected `P+` and `P-` output reaches the main PCB through a keyed, polarized connector.
- A replaceable 1 A pack fuse is placed in series with `P+`. The expected operating current is below 0.3 A, so this fuse protects wiring and fault conditions without nuisance opening.
- The BMS must provide per-cell over-charge, over-discharge, and over-current protection plus passive balancing. Marketing current ratings are not accepted without a traceable data sheet or incoming inspection.

### External Input and Charger

- External input: regulated 15 V DC, at least 1 A, through a keyed connector with a resettable fuse, reverse-polarity MOSFET, and transient suppression.
- USB-C is supported by an external, enclosed PD trigger module fixed to 15 V. The first RF prototype does not integrate an undocumented PD trigger circuit. A normal 5 V USB source is not sufficient for the selected two-cell buck charger.
- Charger: replaceable TP5100-based module configured for 2S/8.4 V CC/CV charging and 0.5 A charge current.
- Charger output connects to the protected BMS `P+` and `P-` nodes, not directly to individual cells.
- The charger module is physically separated from the RF chain and may be enclosed by a grounded shield partition.

### External-Power Priority and Battery Boost

- The 15 V input feeds an L78M12 regulator that creates the external 12 V RF source. At an estimated 75 mA RF load, the regulator dissipates approximately 0.23 W from load current; allowing for regulator quiescent current gives approximately 0.32 W total dissipation. The package therefore uses an adequate copper heat-spreading area.
- The protected 2S pack feeds an MT3608 boost stage set to 12.0 V. Initial feedback values are 191 kohm upper and 10.0 kohm lower, giving approximately 12.06 V from a nominal 0.6 V reference.
- A break-before-make SPDT relay selects the external regulated 12 V whenever external power is present and selects the battery boost output when external power is absent. A flyback diode is fitted across the relay coil.
- External-input detection also forces the MT3608 enable pin low through a transistor. The boost stage is therefore off while the external source powers the RF section, preventing battery discharge and keeping load current out of the charger-termination decision.
- Source transfer may create a brief interruption; uninterrupted RF output during cable insertion or removal is not an acceptance requirement.
- The selected 12 V source passes through a ferrite-bead/LC pi filter and then the RF enable switch before reaching Q1 and the two independent MMIC bias filters.
- An optional direct 12 V test input, isolated by a normally open solder link, is provided only for current-limited bring-up with the battery and external 15 V source disconnected.

### Operating Modes

| Mode | RF source | Battery charger | Battery boost | Intended use |
|---|---|---|---|---|
| External 15 V connected | L78M12 branch | Enabled | Disabled | Charging plus functional RF operation |
| External power absent | 2S pack through MT3608 | Off | Enabled | Normal battery operation and precision spectrum measurements |
| RF enable off, 15 V connected | RF section off | Enabled | Disabled | Preferred charging-only mode |

Battery-only operation is the RF “quiet mode.” Charge-and-run operation is useful for long bench sessions, but its spectrum must not be used as the final flatness or spur measurement because the adapter and charger can introduce discrete interference.

### Power Budget and Indication

- Expected RF-section current at 12 V is approximately 75 mA including Q1 and a low-current indicator, or approximately 0.9 W.
- At a 6.0 V protected-pack lower limit and 80% boost efficiency, estimated pack current is approximately 0.19 A; the 2 A BMS rating therefore has ample normal-operation margin.
- A 15 V, 1 A external source has sufficient margin to supply the 0.5 A battery charger, RF load, relay, and conversion loss simultaneously.
- Allowing for converter loss and practical capacity derating, two 3000 mAh 18650 cells are expected to provide roughly 15–18 hours, while two 5000 mAh 21700 cells are expected to provide roughly 25–30 hours. These are planning estimates, not guaranteed runtimes.
- One LED indicates external input, one indicates RF enable, and the charger module retains its own charge/full indicators.
- Test points expose external 15 V, protected pack voltage, boost 12 V, selected 12 V, filtered RF rail, Q1 source-bias voltage, and both MMIC output/bias voltages.

## PCB Construction

### Mechanical

- Board outline target: 100 mm by 70 mm, remaining within JLCPCB's common 100 mm by 100 mm prototype envelope.
- Four M3 mounting holes near the corners, isolated from RF traces.
- Four output SMA female edge-launch connectors on one 100 mm edge.
- One unpopulated calibration-input SMA footprint on the opposite edge.
- External 15 V input, protected battery connector, charger-module headers, relay, boost converter, and enable switch remain in a power compartment on the DC side, away from the output divider.
- The external two-cell holder/BMS assembly is not mounted on the RF PCB. This keeps cell mass and user-accessible pack wiring away from the SMA edge and RF reference plane.
- A standard metal shield-can footprint covers Q1, U1, the attenuator, and U2.
- A grounded shield partition separates the boost/charger compartment from the RF compartment.

### JLCPCB Stackup

- Four-layer FR-4.
- Finished thickness: 1.6 mm.
- Stackup: JLC04161H-7628.
- Outer copper: 1 oz.
- Inner copper: 0.5 oz.
- L1-to-L2 prepreg: 7628, nominal 0.2104 mm, dielectric constant published by JLCPCB as approximately 4.4.
- Surface finish: ENIG.
- Green solder mask and white silkscreen.
- Controlled impedance option selected at order time.

### Layer Use

- L1: RF components, grounded coplanar waveguide, short DC component connections, and ground pour.
- L2: uninterrupted RF reference ground.
- L3: filtered DC islands; boost switching nodes are confined to the power compartment and never routed under the RF chain.
- L4: ground plane and low-frequency power routing. Charger and converter return currents join RF ground at one controlled power-entry star region rather than flowing through the RF reference path.

### RF Layout Rules

- Use 50-ohm grounded coplanar waveguide on L1 referenced to L2.
- Compute final trace width and coplanar gap from the frozen JLCPCB stackup; do not copy a generic internet width.
- Keep every RF route short and free of 90-degree corners.
- Use ground-via fences at no more than 2 mm pitch along RF paths and at no more than 1.5 mm pitch around amplifier compartments.
- Place at least two direct ground vias adjacent to each MMIC ground lead.
- Do not use thermal relief on MMIC RF-ground connections.
- Keep the Q1 avalanche loop physically small and isolated from the output divider.
- Keep the U2 output and four-way star geometrically symmetric.
- Route each SMA launch identically and tune the launch geometry to the selected connector footprint.
- Avoid RF stubs; unpopulated calibration links shall be physically short and mutually exclusive.
- Keep the MT3608 switch node, inductor, diode, relay coil, charger module, and their current loops as far as practical from Q1 and U1.
- Do not cut or slot the L2 reference ground under RF transmission lines. Power-noise control uses placement, current-loop control, filters, and partitions rather than breaking the RF return plane.

## Assembly Strategy

### JLCPCB-Eligible Assembly

Ordinary resistors, capacitors, ferrite beads, protection parts, LED, and other stocked standard SMD parts may be assigned LCSC part numbers and included in the CPL.

### Hand Installation

- ERA-3SM+ U1 and U2.
- MMBT3904 Q1, because sample substitution may be needed.
- SMA connectors.
- Enable switch, power connectors, relay, shield can, and measurement links when not economical for JLCPCB assembly.
- TP5100 2S charger module, external USB-C PD trigger module, 2S balancing BMS, battery holder or tab-welded pack, pack fuse, and keyed harness.

The BOM contains an `Assembly` column with `JLCPCB`, `HAND`, or `DNP`. The CPL contains only parts intended for automated placement.

## Design Deliverables

- `rf-noise-generator.kicad_pro`
- `rf-noise-generator.kicad_sch`
- `rf-noise-generator.kicad_pcb`
- Custom symbols and footprints stored inside the project directory.
- Schematic PDF.
- PCB front/back renders and 3D screenshots.
- RS-274X Gerber archive with four copper layers, masks, silkscreens, paste layers, and board outline.
- Excellon plated and non-plated drill files plus drill map.
- JLCPCB-format BOM with manufacturer and LCSC identifiers.
- JLCPCB-format CPL with designator, X, Y, rotation, and layer.
- Human-readable full BOM including hand-installed and DNP parts.
- Fabrication README containing exact JLCPCB order selections.
- Beginner assembly guide and staged test procedure.
- Battery-pack/BMS wiring diagram that separately identifies `B+`, `BM`, `B-`, `P+`, and `P-`.
- Calculation report for bias, attenuation, splitter, impedance geometry, expected gain budget, regulator heating, boost current, and battery runtime.
- Charge-and-run validation record covering external priority, boost disable, no backfeed, charge termination, and automatic transfer.
- ERC, DRC, and Gerber-review reports.

## Verification Workflow

### Automated and File-Level Checks

1. Validate attenuator resistor calculations against 50-ohm two-port equations.
2. Validate the five-arm divider input and output impedance with all unused ports terminated.
3. Validate MMIC bias current and resistor power over 11.4–12.6 V supply tolerance.
4. Validate the 15 V input budget, L78M12 junction-temperature margin, 2S boost current, boost feedback, relay states, boost-disable logic, pack fuse, and no-backfeed paths.
5. Calculate CPWG geometry using the frozen JLCPCB stackup and cross-check against JLCPCB's calculator before release.
6. Run schematic ERC.
7. Run PCB DRC, refill zones, and rerun DRC.
8. Export Gerbers and drills in millimetres and inspect every layer in an independent Gerber viewer.
9. Validate BOM and CPL required columns and check that no DNP part appears in the automated-placement list.

### Beginner Prototype Test Sequence

1. Inspect component orientation and solder bridges without power.
2. Leave the cells, BMS, charger module, and external 15 V source disconnected. Measure resistance from the RF 12 V rail to ground and check for a hard short.
3. Fit 50-ohm loads to all four outputs.
4. Feed the isolated RF-rail test input from a laboratory supply set to 12 V and a 100 mA current limit.
5. Enable RF and immediately disable it if current reaches the limit.
6. Measure the filtered rail and both MMIC bias pins; each MMIC bias pin should be near its documented 3.0–3.4 V range.
7. Measure Q1 emitter voltage and record it rather than adjusting by assumption.
8. Disconnect the laboratory supply. Verify BMS wiring and each cell voltage independently before connecting the protected pack to the board.
9. Test battery-only operation, boost output, low-voltage cutoff behavior with a battery simulator or controlled supply, and RF enable before connecting a charger.
10. Connect the 15 V source without cells and verify external 12 V selection and boost disable. Then connect the protected pack and verify no reverse current into the pack with the charger module still disconnected.
11. Connect the TP5100 module, verify 2S/8.4 V configuration and 0.5 A current setting, then record charging, full-charge termination, relay transfer, and connector temperatures under charge-and-run operation.
12. Unplug external 15 V for battery-only quiet mode. Connect one output to a spectrum analyzer through a 20 dB external attenuator; leave the other three terminated.
13. Confirm broadband noise and check for narrow oscillation peaks before removing external attenuation. Repeat once in charge-and-run mode to identify charger or adapter spurs, but do not use that result as the RF acceptance trace.
14. Measure all four ports using identical analyzer settings.
15. Use the unpopulated calibration input and mutually exclusive source link for conducted gain and return-loss testing with a VNA.
16. Only after recorded conducted measurements meet the power boundary may the board be used with antennas inside the shielded room.

## Known Limitations

- MMBT3904 avalanche operation is not a guaranteed normal operating mode.
- A generic FR-4 prototype has dielectric and loss variation; controlled impedance reduces but does not eliminate it.
- The resistive divider has low inter-output isolation.
- The no-choke MMIC bias strategy sacrifices roughly 1 dB per stage for broadband simplicity and lower resonance risk.
- Absolute noise density and ±5 dB flatness require prototype measurement and may require changing Q1, the source resistor, coupling capacitors, or equalization.
- TP5100, MT3608, and low-cost 2S BMS modules vary among suppliers; the procurement list must freeze photographs, pinout, dimensions, configuration links, and incoming-inspection steps for the selected modules.
- Charge-and-run mode is convenient but is not guaranteed spur-free. Battery-only operation is required for final RF characterization.
- The relay transfer briefly interrupts the RF rail when external power is inserted or removed.
- A successful ERC/DRC result does not prove RF performance.

## References

- Mini-Circuits, ERA-3SM+ product data and recommended 35 mA operation: <https://www.minicircuits.com/WebStore/dashboard.html?model=ERA-3SM%2B>
- Mini-Circuits, constant-current MMIC bias guidance: <https://www.minicircuits.com/appdoc/AN60-010.html>
- onsemi, 2N3904 family data sheet and reverse-BE rating: <https://www.onsemi.com/pdf/datasheet/2n3904-d.pdf>
- TOPPOWER, TP5100 one-/two-cell switching charger product information: <https://www.toppwr.com/eproduct/view.php?id=482>
- STMicroelectronics, L78M medium-current positive regulator product information: <https://www.st.com/en/power-management/l78m.html>
- Analog Devices, load sharing and charger-termination discussion in the LTC4056 data sheet: <https://www.analog.com/media/en/technical-documentation/data-sheets/405642f.pdf>
- JLCPCB, current controlled-impedance stackups: <https://jlcpcb.com/impedance>
- JLCPCB, impedance calculator: <https://jlcpcb.com/pcb-impedance-calculator>
- JLCPCB, Gerber preparation: <https://jlcpcb.com/help/article/gerber-files-preparation>
- JLCPCB, BOM and CPL requirements: <https://jlcpcb.com/help/article/how-to-generate-the-bom-and-centroid-file-from-kicad>
