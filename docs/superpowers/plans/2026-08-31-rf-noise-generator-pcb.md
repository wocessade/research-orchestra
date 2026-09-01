# RF Noise Generator PCB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an editable, reviewable, JLCPCB-ready first-prototype package for a battery-powered 50 MHz–3 GHz four-output laboratory white-noise generator.

**Architecture:** A reverse-base-emitter MMBT3904 avalanche source feeds two ERA-3SM+ gain stages with a configurable 50-ohm pi attenuator between them and a five-arm resistive four-way divider at the output. A protected 2S lithium-ion pack is boosted to 12 V for battery operation; an external 15 V input has priority, powers the RF rail through an L78M12, charges the pack through a TP5100 module, and disables the battery boost. The PCB is a four-layer 100 mm by 70 mm controlled-impedance design with RF and switching-power compartments.

**Tech Stack:** KiCad 10 project files and CLI; Python 3.11 standard library plus `pytest`; JLCPCB JLC04161H-7628 four-layer stackup; RS-274X Gerber, Excellon drill, CSV BOM, and CSV CPL outputs.

**Spec:** `docs/superpowers/specs/2026-08-31-rf-noise-generator-pcb-design.md`

## Global Constraints

- Use and test the RF outputs only inside a shielded room or fully enclosed RF shield box.
- Usable-band target is 50 MHz–3 GHz; DC–50 MHz operation is not an acceptance requirement.
- Per-output calibrated integrated power target is -30 dBm to -10 dBm, with all unused outputs terminated in 50 ohms.
- Use two matched 18650 or two matched 21700 cells in 2S series through a balancing 2S BMS and a 1 A pack fuse.
- External input is regulated 15 V at 1 A or greater; ordinary 5 V USB is not a valid charger input.
- Final RF acceptance measurements use battery-only quiet mode with external 15 V unplugged.
- PCB stackup is JLCPCB JLC04161H-7628, four layers, 1.6 mm, 1 oz outer copper, 0.5 oz inner copper, and ENIG.
- Preserve unrelated files in the shared worktree.
- Do not purchase parts, submit an order, push, or create a Git commit without explicit user authorization.
- Do not claim ERC, DRC, Gerber review, charge safety, or 3 GHz RF performance without the corresponding recorded evidence.

## File Map

```text
rf-noise-generator/
├── README.md                              project entry point and status
├── requirements-dev.txt                  pytest version floor
├── hardware/
│   ├── rf-noise-generator.kicad_pro       KiCad project configuration
│   ├── rf-noise-generator.kicad_sch       hierarchical top-level schematic
│   ├── rf-source.kicad_sch                avalanche source and calibration input
│   ├── gain-chain.kicad_sch               two MMIC stages and pi attenuator
│   ├── output-divider.kicad_sch            resistive four-way divider and SMA ports
│   ├── power-system.kicad_sch              15 V, charger, 2S pack, boost, relay, filters
│   ├── rf-noise-generator.kicad_pcb        four-layer board layout
│   ├── sym-lib-table                       project symbol-library mapping
│   ├── fp-lib-table                        project footprint-library mapping
│   ├── lib/
│   │   ├── rf-noise-generator.kicad_sym    custom symbols with verified pin numbers
│   │   └── rf-noise-generator.pretty/
│   │       ├── ERA-3SM_WW107.kicad_mod
│   │       ├── SMA_EDGE_1P6MM.kicad_mod
│   │       ├── TP5100_MODULE_2S.kicad_mod
│   │       ├── BATT_KEYED_2PIN.kicad_mod
│   │       └── SHIELD_CAN_40X30.kicad_mod
│   └── fabrication/                        generated manufacturing output only
├── config/
│   ├── components.csv                      frozen manufacturer parts and assembly class
│   ├── attenuator-options.csv              complete 6/10/15/20 dB resistor sets
│   └── fabrication.json                    stackup and JLCPCB order selections
├── scripts/
│   ├── design_model.py                     electrical calculations
│   ├── validate_components.py              BOM completeness and duplicate checks
│   ├── validate_kicad.py                    symbols, footprints, nets, and board rules
│   ├── export_fabrication.py                Gerber, drill, BOM, and CPL orchestration
│   └── inspect_outputs.py                   archive and layer completeness checks
├── tests/
│   ├── test_design_model.py
│   ├── test_components.py
│   ├── test_kicad_structure.py
│   └── test_fabrication_outputs.py
└── docs/
    ├── calculations.md                      reviewed numeric design report
    ├── battery-wiring.md                    BMS and pack connection diagram
    ├── assembly-and-test.md                 beginner-safe staged instructions
    ├── fabrication-readme.md                exact JLCPCB selections
    └── verification-report.md               evidence and unresolved physical gates
```

---

### Task 1: Create the Isolated Project and Verification Harness

**Files:**

- Create: `rf-noise-generator/README.md`
- Create: `rf-noise-generator/requirements-dev.txt`
- Create: `rf-noise-generator/tests/test_project_structure.py`
- Create: directories shown in the file map
- Modify: `.tasks/active/051_rf-noise-generator-pcb/STATE.md`

**Interfaces:**

- Consumes: approved design specification.
- Produces: isolated project root and one repeatable `pytest` command used by every later task.

- [ ] **Step 1: Write the project-structure test**

```python
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_required_project_directories_exist():
    for relative in ("hardware/lib/rf-noise-generator.pretty", "config", "scripts", "docs"):
        assert (ROOT / relative).is_dir(), relative
```

- [ ] **Step 2: Run the test and verify the initial failure**

Run: `py -m pytest rf-noise-generator/tests/test_project_structure.py -v`

Expected: failure naming the first absent directory.

- [ ] **Step 3: Create the directory tree, README, and dependency file**

`requirements-dev.txt` contains `pytest>=8.3,<9`. `README.md` links the approved specification, states `SHIELDED-ROOM USE ONLY`, and records KiCad as required for authoritative fabrication export.

- [ ] **Step 4: Run the structure test**

Run: `py -m pytest rf-noise-generator/tests/test_project_structure.py -v`

Expected: one passing test.

- [ ] **Step 5: Record the checkpoint**

Append a valid NDJSON record to `.tasks/active/051_rf-noise-generator-pcb/RUNLOG.ndjson`. Do not commit until the user authorizes commits.

### Task 2: Freeze Components and Module Interfaces

**Files:**

- Create: `rf-noise-generator/config/components.csv`
- Create: `rf-noise-generator/config/attenuator-options.csv`
- Create: `rf-noise-generator/scripts/validate_components.py`
- Create: `rf-noise-generator/tests/test_components.py`
- Create: `rf-noise-generator/docs/battery-wiring.md`

**Interfaces:**

- Consumes: approved topology and current supplier documentation.
- Produces: CSV rows with `Designator,Value,Description,Manufacturer,MPN,LCSC,Footprint,Assembly,Datasheet,Notes`; module connector definitions used by the schematic and PCB.

- [ ] **Step 1: Write failing component-manifest tests**

```python
from pathlib import Path
from scripts.validate_components import load_components, validate_components


ROOT = Path(__file__).parents[1]


def test_required_designators_and_fields_are_frozen():
    rows = load_components(ROOT / "config/components.csv")
    errors = validate_components(rows)
    assert not errors
    designators = {row["Designator"] for row in rows}
    assert {"Q1", "U1", "U2", "U3", "U4", "K1", "J1", "J2", "J3", "J4"} <= designators
```

- [ ] **Step 2: Run the test and verify it fails on missing files**

Run: `py -m pytest rf-noise-generator/tests/test_components.py -v`

Expected: import or file-not-found failure.

- [ ] **Step 3: Implement manifest validation**

`validate_components.py` rejects empty MPN, footprint, assembly class, or datasheet fields; permits an empty LCSC field only when `Assembly` is `HAND` or `DNP`; and rejects duplicate designators.

- [ ] **Step 4: Populate the frozen functional parts**

Use MMBT3904 for Q1, ERA-3SM+ for U1/U2, the current ST order code L78M12CDT-TR for U3, MT3608 for U4, a 12 V break-before-make SPDT relay for K1, 100 pF C0G RF coupling capacitors, two parallel 499 ohm 1206 resistors per MMIC bias, and 30.1 ohm 0402 thin-film divider resistors. Record the exact selected relay, SMA, connectors, ferrite beads, inductor, Schottky diode, MOSFET, TVS, and module pinouts from traceable data sheets before marking their rows complete.

- [ ] **Step 5: Populate attenuator options**

```csv
Attenuation_dB,Shunt1_ohm,Series_ohm,Shunt2_ohm,Population
6,150,37.4,150,OPTION
10,96.5,71.5,96.5,DEFAULT
15,71.5,137,71.5,OPTION
20,61.9,249,61.9,OPTION
```

- [ ] **Step 6: Document battery and module wiring**

The diagram must show cell junction to `BM`, pack extremes to `B-`/`B+`, and all charger/load connections to `P-`/`P+`. It must also state that the keyed main-board battery connector receives only protected `P+` and `P-`.

- [ ] **Step 7: Run component tests**

Run: `py -m pytest rf-noise-generator/tests/test_components.py -v`

Expected: all tests pass and the validator prints zero errors.

### Task 3: Implement and Verify the Electrical Design Model

**Files:**

- Create: `rf-noise-generator/scripts/design_model.py`
- Create: `rf-noise-generator/tests/test_design_model.py`
- Create: `rf-noise-generator/docs/calculations.md`

**Interfaces:**

- Consumes: component manifest and attenuator table.
- Produces: `pi_pad(z0_ohm: float, attenuation_db: float) -> tuple[float, float]`, `star_divider(z0_ohm: float, outputs: int) -> tuple[float, float]`, `mmic_bias(supply_v: float, device_v: float, resistance_ohm: float) -> tuple[float, float]`, `boost_output(vref_v: float, upper_ohm: float, lower_ohm: float) -> float`, and `power_budget() -> dict[str, float]`.

- [ ] **Step 1: Write failing numeric tests**

```python
import pytest
from scripts.design_model import boost_output, mmic_bias, pi_pad, power_budget, star_divider


def test_ten_db_pi_pad():
    shunt, series = pi_pad(50.0, 10.0)
    assert shunt == pytest.approx(96.25, rel=0.002)
    assert series == pytest.approx(71.15, rel=0.002)


def test_four_way_star():
    arm, loss_db = star_divider(50.0, 4)
    assert arm == pytest.approx(30.0)
    assert loss_db == pytest.approx(7.9588, abs=0.001)


def test_power_values():
    current, total_power = mmic_bias(12.0, 3.2, 249.5)
    assert current == pytest.approx(0.03527, rel=0.01)
    assert total_power == pytest.approx(0.310, rel=0.03)
    assert boost_output(0.6, 191_000, 10_000) == pytest.approx(12.06)
    assert power_budget()["pack_current_at_6v_80pct_a"] == pytest.approx(0.1875)
```

- [ ] **Step 2: Run the tests and verify missing-function failures**

Run: `py -m pytest rf-noise-generator/tests/test_design_model.py -v`

Expected: import failures for the declared calculation functions.

- [ ] **Step 3: Implement the equations with input validation**

Use the symmetrical 50-ohm pi-pad equations and `Rarm = Z0 × (N - 1) / (N + 1)` for the matched star. Reject non-positive impedance, fewer than two outputs, attenuation at or below 0 dB, and a non-positive feedback lower resistor.

- [ ] **Step 4: Generate the calculation report**

Record the ideal and populated attenuator values, 7.9588 dB divider loss, 35 mA nominal MMIC bias, 0.31 W bias-resistor pair dissipation, 12.06 V boost setpoint, 0.315 W L78M12 estimate, 0.1875 A worst-case pack-current estimate, and 15–18/25–30 hour runtime planning ranges.

- [ ] **Step 5: Run the calculation tests**

Run: `py -m pytest rf-noise-generator/tests/test_design_model.py -v`

Expected: all numeric and invalid-input tests pass.

### Task 4: Create and Validate KiCad Libraries

**Files:**

- Create: `rf-noise-generator/hardware/sym-lib-table`
- Create: `rf-noise-generator/hardware/fp-lib-table`
- Create: `rf-noise-generator/hardware/lib/rf-noise-generator.kicad_sym`
- Create: the five `.kicad_mod` files listed in the file map
- Create: `rf-noise-generator/scripts/validate_kicad.py`
- Create: `rf-noise-generator/tests/test_kicad_structure.py`

**Interfaces:**

- Consumes: frozen MPNs, module photographs/dimensions, and manufacturer land-pattern data.
- Produces: project-local KiCad symbol and footprint identifiers referenced verbatim by all schematic sheets.

- [ ] **Step 1: Write failing library checks**

```python
from pathlib import Path
from scripts.validate_kicad import inspect_library_files


ROOT = Path(__file__).parents[1]


def test_custom_library_contains_required_footprints():
    report = inspect_library_files(ROOT / "hardware")
    assert report.missing == []
    assert report.duplicate_pad_numbers == []
```

- [ ] **Step 2: Run the test and verify the missing-library failure**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

Expected: failure listing each missing library file.

- [ ] **Step 3: Create symbols and footprints from primary drawings**

ERA-3SM+ pad numbers must match Mini-Circuits WW107 documentation. SMA ground pads and edge position must match the selected 1.6 mm connector. TP5100 module pads must include input positive/negative and output positive/negative labels. The shield-can courtyard and keepout must prevent interference with Q1, U1, attenuator, and U2.

- [ ] **Step 4: Add dimensional assertions**

The validator checks pad-number uniqueness, positive courtyard size, exact footprint names, presence of fabrication/source URLs in properties, and a board-edge anchor in the SMA footprint.

- [ ] **Step 5: Run library checks and KiCad syntax checks**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

When KiCad is installed, also run: `kicad-cli create-project --help` and `kicad-cli --version`, recording the exact version in `docs/verification-report.md` before opening or converting files.

Expected: Python checks pass; KiCad version is 10.x.

### Task 5: Draw the RF and Power Schematics

**Files:**

- Create: `rf-noise-generator/hardware/rf-noise-generator.kicad_pro`
- Create: `rf-noise-generator/hardware/rf-noise-generator.kicad_sch`
- Create: `rf-noise-generator/hardware/rf-source.kicad_sch`
- Create: `rf-noise-generator/hardware/gain-chain.kicad_sch`
- Create: `rf-noise-generator/hardware/output-divider.kicad_sch`
- Create: `rf-noise-generator/hardware/power-system.kicad_sch`
- Modify: `rf-noise-generator/tests/test_kicad_structure.py`

**Interfaces:**

- Consumes: validated project libraries and component manifest.
- Produces: named nets `RF_NOISE_RAW`, `RF_U1_OUT`, `RF_PAD_OUT`, `RF_U2_OUT`, `RF_STAR`, `EXT_15V`, `PACK_PROTECTED`, `BOOST_12V`, `EXT_12V`, `SELECTED_12V`, and `RF_12V_FILTERED`.

- [ ] **Step 1: Add failing schematic-content tests**

The test loads the schematic text and asserts that all named nets, Q1/U1/U2/U3/U4/K1, four output SMA references, three attenuator resistors, five divider resistors, boost enable transistor, relay flyback diode, 1 A pack fuse, and normally open direct-test link are present exactly once where appropriate.

- [ ] **Step 2: Run the schematic test and verify it fails**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

Expected: failure listing absent schematic sheets or required nets.

- [ ] **Step 3: Draw the RF sheets**

Implement Q1 with collector unconnected, base at RF ground, emitter fed by 10.0 kohm and coupled by 100 pF. Implement U1/U2 with two parallel 499 ohm 1206 bias resistors each, individual filter branches, current links, 100 pF coupling, default 10 dB pi pad, calibration SMA selection links, and five 30.1 ohm divider arms feeding four SMA outputs.

- [ ] **Step 4: Draw the power sheet**

Implement protected 15 V entry; separate TP5100-module and L78M12 branches; protected two-wire battery connector; MT3608 with 191 kohm/10.0 kohm feedback; external-presence transistor pulling boost enable low; relay with external 12 V on normally open, boost 12 V on normally closed, selected 12 V on common; relay flyback diode; RF enable; pi filtering; LEDs; and named test points.

- [ ] **Step 5: Annotate safety and assembly data**

Add schematic text stating `2S ONLY — 8.4 V MAX`, `CHARGER TO P+/P- ONLY`, `5 V USB NOT SUPPORTED`, `SHIELDED-ROOM USE ONLY`, and `TERMINATE UNUSED PORTS 50R`. Mark alternate attenuator parts, optional choke footprints, and direct-test link as DNP.

- [ ] **Step 6: Run structural tests and ERC**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

After KiCad installation run: `kicad-cli sch erc -o rf-noise-generator/hardware/fabrication/erc.rpt rf-noise-generator/hardware/rf-noise-generator.kicad_sch`

Expected: Python tests pass and ERC has zero unwaived errors. Every waiver must include a written reason in `docs/verification-report.md`.

### Task 6: Establish Board Stackup, Mechanics, and RF Rules

**Files:**

- Create: `rf-noise-generator/config/fabrication.json`
- Create: `rf-noise-generator/hardware/rf-noise-generator.kicad_pcb`
- Modify: `rf-noise-generator/docs/calculations.md`
- Modify: `rf-noise-generator/tests/test_kicad_structure.py`

**Interfaces:**

- Consumes: completed schematic, selected SMA connector, JLC04161H-7628 stackup.
- Produces: 100 mm by 70 mm four-layer board with net classes `RF_50R`, `POWER_SWITCH`, `POWER_DC`, and `DEFAULT`.

- [ ] **Step 1: Add failing board-rule tests**

Assert four copper layers, exact 100 mm by 70 mm rectangular outline, four M3 holes, four output SMA footprints on the same edge, 1.5 mm RF-compartment via-fence rule, and no RF net assigned to a non-RF net class.

- [ ] **Step 2: Run the tests and verify board-file failure**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

Expected: failure because the PCB is absent or incomplete.

- [ ] **Step 3: Create board setup and mechanical outline**

Assign L1 signal/ground pour, L2 uninterrupted ground, L3 DC islands, and L4 ground/low-frequency power. Place M3 holes at 4 mm inset from each corner, reserve the 100 mm output edge for four equal-pitch SMA connectors, and reserve the opposite side for calibration SMA and DC connectors.

- [ ] **Step 4: Freeze the initial CPWG geometry**

Start with 0.36 mm RF trace width, 0.20 mm coplanar gap, 1 oz outer copper, and 0.2104 mm L1-to-L2 dielectric height. Cross-check in JLCPCB's impedance calculator; record the returned impedance and any manufacturing-approved adjustment in both `fabrication.json` and `calculations.md` before routing. Use only the recorded final width/gap in the `RF_50R` class.

- [ ] **Step 5: Run board-structure tests**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

Expected: layer, outline, hole, connector-edge, and net-class tests pass.

### Task 7: Place and Route the RF and Power Compartments

**Files:**

- Modify: `rf-noise-generator/hardware/rf-noise-generator.kicad_pcb`
- Modify: `rf-noise-generator/tests/test_kicad_structure.py`
- Create: `rf-noise-generator/docs/layout-review.md`

**Interfaces:**

- Consumes: frozen board rules, footprints, and complete schematic connectivity.
- Produces: fully placed and routed PCB with filled ground zones and documented visual-review checkpoints.

- [ ] **Step 1: Add failing placement constraints**

Test that Q1→U1→attenuator→U2→divider appears in monotonic RF-path order, RF segment lengths remain below 25 mm each, the divider branches differ by no more than 1.0 mm, and no MT3608 switch-node copper overlaps the RF compartment bounding box.

- [ ] **Step 2: Place the RF chain and divider**

Keep coupling capacitors adjacent to device pins, put at least two ground vias beside each ERA-3SM+ ground pad, use no thermal relief on MMIC RF grounds, minimize the star-center copper area, and give all four SMA launches identical geometry.

- [ ] **Step 3: Place the power system**

Put the TP5100 module header, MT3608 switch loop, relay, and 15 V connector in the isolated power compartment. Keep the boost inductor, diode, input capacitor, and output capacitor in the smallest practical loop. Place the L78M12 copper heat spreader away from Q1 and the MMICs.

- [ ] **Step 4: Route, pour, and fence**

Use continuous L2 ground under every RF route, avoid 90-degree RF bends, add RF path via fences at 2.0 mm maximum pitch and compartment fences at 1.5 mm maximum pitch, route charger/converter returns to the controlled power-entry star, and keep L3 switching copper out from under the RF chain.

- [ ] **Step 5: Add silkscreen and assembly boundaries**

Include output numbers, signal direction, attenuator default, battery polarity, charger module orientation, test-point names, shield-can outline, `SHIELDED-ROOM USE ONLY`, `2S 8.4V MAX`, and `TERMINATE UNUSED PORTS 50R` without placing silkscreen on exposed pads.

- [ ] **Step 6: Run tests and DRC**

Run: `py -m pytest rf-noise-generator/tests/test_kicad_structure.py -v`

After KiCad installation run: `kicad-cli pcb drc -o rf-noise-generator/hardware/fabrication/drc.rpt rf-noise-generator/hardware/rf-noise-generator.kicad_pcb`

Expected: structural checks pass and DRC has zero unwaived errors. Record impedance, clearance, courtyard, and board-edge review results in `layout-review.md`.

### Task 8: Generate BOM, CPL, and Fabrication Outputs

**Files:**

- Create: `rf-noise-generator/scripts/export_fabrication.py`
- Create: `rf-noise-generator/scripts/inspect_outputs.py`
- Create: `rf-noise-generator/tests/test_fabrication_outputs.py`
- Create: `rf-noise-generator/docs/fabrication-readme.md`
- Generate: `rf-noise-generator/hardware/fabrication/*`

**Interfaces:**

- Consumes: DRC-clean PCB, ERC-clean schematic, and frozen component manifest.
- Produces: Gerber archive, Excellon drills, schematic PDF, JLCPCB BOM, JLCPCB CPL, and human-readable complete BOM.

- [ ] **Step 1: Write failing fabrication-package tests**

```python
from pathlib import Path
from scripts.inspect_outputs import inspect_fabrication_directory


ROOT = Path(__file__).parents[1]


def test_required_manufacturing_outputs_exist_and_are_nonempty():
    report = inspect_fabrication_directory(ROOT / "hardware/fabrication")
    assert report.missing == []
    assert report.empty == []
    assert report.dnp_in_cpl == []
```

- [ ] **Step 2: Run the test and verify missing-output failures**

Run: `py -m pytest rf-noise-generator/tests/test_fabrication_outputs.py -v`

Expected: missing Gerber, drill, BOM, CPL, and report files.

- [ ] **Step 3: Implement deterministic exports**

The exporter invokes KiCad CLI for schematic PDF, Gerbers, and drills; derives BOM rows from `components.csv`; derives CPL rows from the PCB position export; excludes `HAND` and `DNP` rows from CPL; and writes every output into a newly cleared project-local staging directory without touching files outside `rf-noise-generator/hardware/fabrication`.

- [ ] **Step 4: Validate output schemas**

BOM columns are `Comment,Designator,Footprint,LCSC Part #`; CPL columns are `Designator,Mid X,Mid Y,Layer,Rotation`. The inspector requires F.Cu, In1.Cu, In2.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts, plated drill, and non-plated drill outputs.

- [ ] **Step 5: Export and inspect**

Run: `py rf-noise-generator/scripts/export_fabrication.py --project rf-noise-generator/hardware/rf-noise-generator`

Run: `py -m pytest rf-noise-generator/tests/test_fabrication_outputs.py -v`

Expected: all artifacts exist, archive members are non-empty, coordinate units are millimetres, DNP parts are absent from CPL, and the full BOM still lists hand-installed parts.

- [ ] **Step 6: Write exact JLCPCB ordering selections**

Record four layers, 100 mm by 70 mm, 1.6 mm, JLC04161H-7628, 1 oz outer/0.5 oz inner copper, ENIG, green mask, white silkscreen, controlled impedance enabled, and the frozen RF trace width/gap from Task 6.

### Task 9: Produce Beginner Assembly and Electrical Test Instructions

**Files:**

- Create: `rf-noise-generator/docs/assembly-and-test.md`
- Modify: `rf-noise-generator/docs/battery-wiring.md`
- Modify: `rf-noise-generator/README.md`

**Interfaces:**

- Consumes: final designators, test-point names, module orientations, and accepted manufacturing outputs.
- Produces: a linear build-and-test procedure that does not require the user to infer circuit behavior.

- [ ] **Step 1: Document separate RF-board and battery-pack assembly**

List visual inspection, resistance checks, ERA-3SM+ hand soldering, SMA installation, shield installation, matched-cell checks, BMS wiring order, keyed harness continuity, and fuse installation. Generate `battery-harness-reference.svg` from the frozen connector pinout, showing connector orientation, pin numbers, and polarity; do not instruct the user to guess wire color.

- [ ] **Step 2: Document current-limited RF bring-up**

Require four 50-ohm loads, battery and charger disconnected, direct-test link configured, laboratory supply at 12 V/100 mA, expected selected/filtered rail readings, and immediate shutdown at current limit. Record expected MMIC pins at approximately 3.0–3.4 V.

- [ ] **Step 3: Document battery and charge-and-run validation**

Use a battery simulator or two current-limited sources before real cells where available. Check battery-only 12 V, external-priority transfer, boost disable, no reverse pack current, 8.4 V maximum charge, charge-current taper, module/connector temperature, and relay transfer in the exact order defined by the specification.

- [ ] **Step 4: Document RF measurements at the user's knowledge level**

Explain RBW, external 20 dB analyzer protection, termination of the other three ports, battery-only quiet mode, broadband-noise versus narrow-spur interpretation, four-port comparison, and the -10 dBm per-port stop boundary without assuming RF-design knowledge. The measurement sheet records 50 MHz–3 GHz coverage, 10 dB peak-to-peak flatness window, no more than 2 dB port-to-port difference, -30 dBm to -10 dBm integrated power per port, and failure for any persistent narrow line more than 10 dB above the local noise baseline.

- [ ] **Step 5: Check all references against the PCB**

Search every test-point, connector, switch, LED, and module reference in the documents and assert that the same designator exists in the schematic and PCB.

### Task 10: Final Verification and Delivery Review

**Files:**

- Create: `rf-noise-generator/docs/verification-report.md`
- Modify: `rf-noise-generator/README.md`
- Modify: `.tasks/active/051_rf-noise-generator-pcb/AUDIT.md`
- Modify: `.tasks/active/051_rf-noise-generator-pcb/STATE.md`
- Modify: `.tasks/active/051_rf-noise-generator-pcb/RUNLOG.ndjson`

**Interfaces:**

- Consumes: all source, test, documentation, and fabrication artifacts.
- Produces: evidence-backed delivery package and explicit list of measurements that remain for the physical prototype.

- [ ] **Step 1: Run the complete local test suite**

Run: `py -m pytest rf-noise-generator/tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run authoritative KiCad checks**

Run ERC, DRC, zone refill followed by DRC again, schematic PDF export, Gerber/drill export, and independent Gerber inspection. Record the exact KiCad version, command, exit status, report path, warning count, and waiver reasons.

- [ ] **Step 3: Perform a fresh requirement-to-artifact audit**

Map every specification section to schematic sheets, PCB locations, calculations, manufacturing files, or physical-test gates. Reject delivery if any safety marking, module pinout, RF connector, attenuation option, BMS connection, source-selection state, or JLCPCB selection lacks an artifact.

- [ ] **Step 4: Package without overstating physical performance**

The README must distinguish `calculated`, `ERC/DRC checked`, `fabrication-output inspected`, and `requires assembled-prototype measurement`. It must not call the 50 MHz–3 GHz response, spectral flatness, charge temperature, or output power verified until actual measurement records exist.

- [ ] **Step 5: Present the package for user review**

Provide clickable links to the KiCad project, schematic PDF, PCB renders, Gerber ZIP, drill ZIP, JLCPCB BOM/CPL, battery wiring diagram, fabrication README, assembly guide, calculation report, and verification report. Do not place an order or commit files unless the user separately authorizes that action.
