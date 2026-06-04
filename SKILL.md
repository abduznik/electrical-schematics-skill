---
name: kicad-schematic-generation
description: "Generate KiCad 7/8 schematics (.kicad_sch) programmatically from Python by writing S-expression files directly. For when you need full control over symbol placement, wire routing, and component definitions — without going through SKiDL or the KiCad GUI."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [kicad, schematic, eda, circuit, python, s-expression]
    related_skills: [drawio-diagrams, electrical-schematics, skidl-circuit-design]
---

# KiCad Schematic Generation from Python

Generate valid KiCad 7/8 `.kicad_sch` files by writing S-expression structured text from Python. This gives you full control over symbol placement, wire routing, and inline symbol definitions — without needing KiCad installed or any external library.

The output is a plain .kicad_sch file you open in KiCad alongside its .kicad_pro project file.

## When to Use

- You already have a wiring diagram (draw.io, hand-drawn, etc.) and need a KiCad schematic fast
- You're generating schematics from structured data (pinouts, netlists, config files)
- You need inline custom symbols that don't depend on external libraries
- The SKiDL abstraction layer is overkill — you want direct control

Don't use for:
- Complex multi-sheet designs that are better done in KiCad GUI
- PCB layout (this generates schematics only, not .kicad_pcb)
- Designs requiring SPICE simulation (use KiCad's built-in symbol libraries)

## How It Works

A KiCad 8 `.kicad_sch` file is an S-expression document with this structure:

```
(kicad_sch (version 20230121) (generator "your_tool")
  (paper "A4" landscape)              ;; ← NOT (paper "A4" (orientation landscape))
  
  (title_block ...)
  
  (lib_symbols                         ;; ← Inline symbol definitions
    (symbol "MY_CUSTOM_PART" ...
      (symbol "MY_CUSTOM_PART_0_1" ... )  ;; ← ALL pins + body here
    )
  )
  
  ;; Placed component instances
  (symbol (lib_id "MY_CUSTOM_PART") (at x y 0) (unit 1) ... )
  
  ;; Wiring
  (wire (pts (xy x1 y1) (xy x2 y2)) (stroke ...))
  
  ;; Labels
  (global_label "NAME" (shape input) (at x y 0) ...)
  
  ;; Sheet + symbol instance registrations
  (sheet_instances ...)
  (symbol_instances ...)
)
```

## Mandatory Layout Rules — No Visual Preview Safety Net

When generating schematics in code you **cannot visually preview**, follow these rules to guarantee professional, non-overlapping results.

### SHEET BOUNDS (A4)
- A4 sheet = 297mm x 210mm
- Usable area: X: 20-277mm, Y: 20-190mm
- Visual center: approximately (148mm, 105mm)
- Cluster all components around center
- No wire endpoint at X < 10mm, Y < 10mm, X > 280mm, Y > 200mm

### ROW SPACING — minimum 20mm for multi-pin components
- **Multi-pin components** (switches, connectors, terminal blocks): minimum **20mm** center-to-center Y
- **2-pin components** (resistors, buzzer): minimum **15mm** center-to-center Y
- All components in same row share exact same Y coordinate
- The 20mm rule supersedes any earlier 10mm guidelines — 10mm caused body overlap with ±6.35mm button symbols
- Use '(label ...)' not '(global_label ...)' for single-sheet designs

### COMPONENT CLEARANCE - Real Bounding Boxes
Know body half-dimensions and add 5mm clearance:

GX16-6: +/-5.08mm X, +/-7.62mm Y from origin
WAGO-6: +/-7.62mm X, +/-7.62mm Y
ILLUM_PB: +/-6.35mm X, +/-6.35mm Y
R_US: +/-3.81mm X, +/-1.27mm Y
BUZZER: +/-5.08mm X, +/-5.08mm Y

Check every pair of components for overlap before writing.

### WIRES - No Overlaps
- Orthogonal only - strictly horizontal or vertical, no diagonals
- Never route two wires over same XY segment
- Crossing nets: perpendicular with NO junction dot
- Junction only at T or + intersections
- Per-signal routing columns - each signal from multi-pin connector gets unique X column for fan-out
- GND stubs to multiple pins: each at unique X, bridge horizontally to common pin X
- Every wire endpoint connects to a pin or another wire - no floating endpoints

### COMPONENT PROPERTIES
- Reference designators ABOVE body, 6-10mm offset
- Value text BELOW body, 6-10mm offset
- Alternate offsets per row when spacing is tight
- No two text items share same XY

### POWER SYMBOLS
- GND points downward, +V upward
- Min 100mil/2.54mm stub wire from symbol to net
- Use (power) flag, (in_bom no), hide on #PWR reference
- Reference and Value at different Y positions

### SELF-AUDIT Before Delivery
Print component audit table with ref, value, center, bounds, OK? for every component. Fix any NO. THEN run linter. Only deliver on PASS.

**v9+ self-check questions — answer explicitly before delivering:**
- "LED- wire from SW1: how many segments? Start XY? End XY?"
- "LED- wire from SW2: how many segments? Start XY? End XY?"
- "LED- wire from SW3: how many segments? Start XY? End XY?"
- "+V symbol XY position? Distance from LS1 origin in mm?"
- "Does any GND wire segment pass through TB1 bounding box? YES/NO"
- "GND symbol XY? Is it connected to a wire? YES/NO"

For each GND return wire, verify:
1. The horizontal stub is ≤ 15mm (preferably 5mm)
2. The vertical drop is a straight line down to the GND bus
3. There's a junction where it meets the GND bus
4. No part of the wire enters any component's bounding box (except the pin endpoint)

### LAYOUT — Left to Right Signal Flow

Use dedicated X ranges (in mm, rough):

| X range | Section |
|---------|---------|
| 50–100 | Input connector / power entry |
| 100–140 | Distribution block (WAGO, junction) |
| 140–180 | Series resistors / passives |
| 180–230 | Output loads (LED buttons, buzzer) |

Use dedicated Y rows spaced **20mm** apart (25mm if buzzer is included), centered around sheet Y=105mm:

| Y (mm) | Channel |
|--------|---------|
| 40 | +V power rail |
| 60 | CH1 — RED button (R1, SW1) |
| 80 | CH2 — GREEN button (R2, SW2) |
| 100 | CH3 — WHITE button (R3, SW3) |
| 120 | LS1 — Buzzer |
| 140 | WAGO GND bus (TB1) |

These are pre-centering coordinates. After calculating all component positions, compute the bounding box center and shift everything to align with sheet center (148mm, 105mm).

### WIRES — No Overlaps

- **Orthogonal only** — strictly horizontal or vertical segments, no diagonals
- Never route two wires over the same XY segment
- When two nets cross: perpendicular crossing with **no junction dot**
- Add `(junction ...)` only at T or + intersections where wires intentionally meet
- Signal wires and GND return wires must use **different vertical trunk columns** (different X coordinates)
- Each channel gets its own horizontal routing band

### ROUTING RULE — NEVER ROUTE THROUGH SYMBOL BODIES

Before writing any wire, calculate the bounding box of every component it passes near. A wire must never have any point (including intermediate path) inside a component bounding box unless that point is exactly on a pin endpoint. If a wire needs to cross from one side of a component to the other, route AROUND the component — go further left/right/up/down to bypass the body entirely. Treat component bodies as solid obstacles.

### SPACING RULE — MINIMUM 20mm BETWEEN MULTI-PIN COMPONENTS

For any component with more than 2 pins (switches, connectors, terminal blocks), the minimum Y distance between consecutive component origins is 20mm. For 2-pin components (resistors, buzzer), minimum Y distance is 15mm.

When calculating clearances, ensure body edges (not clearance zones) of adjacent components are at least 5mm apart. Clearance zones (body + 5mm margin) may overlap when component heights sum to more than the spacing — this is acceptable as long as actual body-to-body gap is ≥ 5mm.

### CONNECTOR INPUT ROUTING — J1 (GX16-6) Pattern

J1 pins exit on the LEFT side of the symbol at X = J1_x - 10.16mm, length 5.08mm right. Wire connects at the pin endpoint: X = J1_x - 5.08mm.

Routing per pin (v13+ 4mm spacing):
```python
turn_x = j1_conn_x - 4.0 * pn  # pn = pin number 1-6 counting from bottom
```
1. Horizontal LEFT from pin endpoint to `turn_x` (range: 76.92mm to 56.92mm)
2. Vertical wire to target row Y (each pin on its own unique X — NO shared X)
3. Horizontal RIGHT toward circuit

**The fan-out columns range from ~X=57mm to ~X=77mm.** The vertical runs must never share an X coordinate.

**Pin numbering:** pin 1 = bottom of connector (y_off = -6.35), pin 6 = top (y_off = +6.35).

**Color-swap hazard:** When the user says "swap the colors on pins 1 and 6," change ONLY the `net_color_key` in the GX16_PINS tuple. Do NOT swap pin names in the symbol definition, routing destinations, or anything else. See `references/gx16-color-swap-pattern.md` for the exact workflow and coordinates.

No wire may bend, turn, or have a waypoint inside the J1 bounding box (X: J1_x ± 5.08mm, Y: J1_y ± 7.62mm). All routing corners must be outside this box.

**History:** 5mm (v9, too wide) → 2.54mm (v10, too cramped) → 4mm (v13, clean spacing).

### LED+ SIGNAL ROUTING (Resistor → LED+ pin)

The LED+ pin is at offset (-10.16mm, -2.54mm) from the ILLUM_PB origin, length 3.81mm right. Wire connects at X = SW_x - 6.35mm, Y = SW_y - 2.54mm.

Route pattern (v10+):
```
1. From resistor right pin (X = R_x + 7.62), jog UP/DOWN by 2.54mm to the LED+ Y level
1. From resistor right pin endpoint (X = R_x + 11.43), jog UP/DOWN by 2.54mm to the LED+ Y level
2. Then horizontal RIGHT from the jog point to the LED+ pin at X = SW_x - 6.35

**The jog happens at the RESISTOR right pin endpoint (X = R_x + 11.43), NOT at the LED+ pin.** Do NOT route all the way to the LED+ pin first and then jog — that creates a vertical wire segment inside the SW bounding box.

```python
# ✅ CORRECT (v11+)
# Jog at resistor right pin endpoint (R pin endpoint = R_x + 11.43)
wire(R_x + 11.43, ch_y, R_x + 11.43, ch_y - 2.54, net_color)  # vertical jog, 2.54mm
wire(R_x + 11.43, ch_y - 2.54, SW_x - 6.35, ch_y - 2.54, net_color)  # horizontal to LED+
```

The long horizontal segment at the LED+ Y level (ch_y - 2.54) is correct — it runs alongside the LED- wire (at ch_y + 2.54) at a different Y, preventing cross-net overlaps.

### WAGO OUTPUT ROUTING — RIGHT Side Exit Pattern

WAGO output pins exit on the RIGHT side at X = TB1_x + 7.62mm, length 5.08mm right. Connection point: X = TB1_x + 12.70mm.

1. Horizontal stub going RIGHT from pin, minimum 10mm long (never go left or up from a right-side pin)
2. Vertical wire going to the target row Y
3. Horizontal wire going RIGHT to the target pin

No wire from a WAGO output pin may travel LEFT or pass through the WAGO bounding box (X: TB1_x ± 7.62mm, Y: TB1_y ± 7.62mm).

### WAGO GND output wires must route to the LED- pin Y-level (component Y + 2.54mm for SW buttons) — NOT to the component center Y — to avoid overlapping with signal wires (R output → LED+) at the center Y. For buzzer GND, offset the horizontal WAGO wire by 5mm from the buzzer center Y to avoid overlapping with the +V signal wire.

### RULE: NEVER LEAVE LED- OR COMPONENT NEGATIVE PINS FLOATING

After placing every component, immediately write the GND return wire before moving to the next component. Pattern: LED-/negative pin → horizontal stub left → vertical down → GND bus. Do not place all components first and wire later — wire each one completely before placing the next.

### RULE: WIRE COLOR BY NET NAME

Any net whose name contains "GND" or "BLK" → black stroke (color 0 0 0 255). Contains "+V", "VCC", "RED" → red stroke (color 214 0 0 255). Contains "SIG1" or "BLU" → blue stroke (color 0 70 200 255). Contains "SIG2" or "YEL" → yellow stroke (color 200 160 0 255). Contains "SIG3" or "GRN" → green stroke (color 0 150 0 255). Contains "COM" or "PNK" → pink stroke (color 220 80 150 255). Apply this mapping to every wire segment when writing it. Default green only for unlabeled nets.

### RULE: FAN-OUT CONNECTOR PINS WITH UNIQUE X LANES

Multi-pin connectors where all pins exit a single side must use staggered stub lengths — each pin gets a unique stub length so vertical runs never share an X coordinate.

**Stub formula (v13+):** `stub_length = 4.0mm * pin_number` (pin_number 1-6 counting from bottom of connector). This gives clean spacing that looks good in KiCad — 2.54mm was too cramped (v10) and 5mm was too wide (v9).

```python
turn_x = (connector_x - 5.08) - 4.0 * pn  # pn = pin number 1-6
# Range: pin 1 ~ 77mm, pin 6 ~ 57mm
```

This is mandatory for any connector with 3+ pins on the same side.

### RULE: LED- AND NEGATIVE PINS USE LOCAL STUBS ONLY

A negative/cathode/LED- pin return to GND must NEVER route more than 15mm horizontally before dropping to the GND bus. The drop must be a straight vertical wire directly below or beside the component. Routing a GND return wire across the entire schematic is always wrong — if you find yourself routing a GND wire more than 20mm horizontally, stop and use a local GND power symbol instead.

### RULE: POWER SYMBOLS HAVE EXCLUSIVE ZONES

Each power symbol (+V, GND) owns a 15mm radius exclusion zone. No other component, wire junction, or symbol body may exist within that radius. Before placing a power symbol, verify the zone is clear. If it isn't, move the power symbol further along its stub wire until the zone is clear.

### RULE: GND_PWR PLACEMENT — ONE SYMBOL ON THE TRUNK WITH CLEARANCE (USER-CORRECTED)

**Critical user preference (learned across 14 revisions):** When the GND bus interconnects all ground returns (e.g. WAGO → trunk → per-channel stubs), ONE GND_PWR symbol is sufficient. The user explicitly rejected one-per-component placement — it adds visual clutter with no benefit since the bus already connects everything.

- Place ONE GND_PWR on the main GND trunk, not one per component
- Minimum **10mm** clearance from any component body edge (not just signal wires)
- Below the WAGO body is a good default (Y = TB1_Y + 10mm)

```python
# ✅ CORRECT — single GND at trunk, clear of components
gnd_x = 157.78  # main trunk X
gnd_y = TB1_Y + 10  # 10mm below WAGO body
wire(trunk_bottom_y, gnd_x, gnd_y, gnd_x, "GND")
emit(power_instance("GND_PWR", "#PWR01", "GND", gnd_x, gnd_y))

# ❌ WRONG — per-component GNDs (user rejected)
for ch_y in channels:
    emit(power_instance("GND_PWR", ...))  # don't do this
```

Do NOT place GND_PWR right next to a component body — the user complained specifically about this. "a bit of an offset" means ≥10mm from the nearest bounding box edge.

See `references/single-gnd-placement.md` for the exact coordinates and removal procedure used in the v14 project.

The GND_PWR triangle must use `(fill (type outline))` — without it the triangle appears as an open outline and the direction is ambiguous.

**Shipped polyline (tip-at-connection variant, in user's approved v14):**
```
(polyline (pts (xy 0 0) (xy -3.81 3.81) (xy 3.81 3.81) (xy 0 0))
  (stroke (width 0.254) (type default)) (fill (type outline)))
```
This puts the TIP at Y=0 (the connection point) and the flat bar at Y=3.81 (below).

**⚠️ DO NOT experiment with other GND variants.** The user shipped v14 with the tip-at-connection variant and called it "perfect." During this project I attempted a flat-bar-at-top variant `(xy -3.81 0) (xy 3.81 0) (xy 0 3.81)` — this was part of an over-engineered delivery that got rejected. The user never separately validated that GND style; they rejected the WHOLE delivery because I changed too many things at once. The GND was never the issue — the scope creep was. Stick with the shipped variant.

If the user ever says GND is "upside down" in the future, do NOT independently try to fix it. Ask specifically: "Do you want me to change the GND_PWR triangle direction?" If they say yes, then and only then experiment. Otherwise, leave it as-is. Unsolicited GND changes cost 3 revisions.
### RULE: POWER SYMBOL PLACEMENT — BUS vs LOCAL

When to use a physical GND bus vs local GND_PWR symbols depends on the user's preference. Two valid approaches:

**APPROACH A — Single GND on a shared trunk (this user's preference):** When all ground returns share a common bus (e.g. WAGO → vertical trunk → per-channel stubs), place ONE GND_PWR on the trunk with ≥10mm clearance from component bodies. Do NOT place one per component — this user explicitly rejected that as visual clutter.

**APPROACH B — Local GND_PWR per component (KiCad convention):** For single-sheet schematics where each component has its own isolated ground stub, place a GND_PWR symbol locally at each component's ground return. Power symbols create implicit global connections in KiCad — that is their purpose.

**Default to Approach A** for this user unless they specify otherwise. A physical GND bus wire longer than 30mm is acceptable here because the trunk serves as the visual GND reference for the entire schematic.

### RULE: R_US SYMBOL — CONTINUOUS ZIGZAG POLYLINE, HIDDEN PINS (v11+)

The KiCad built-in R_US resistor has a zigzag body (3 humps). The inline custom symbol must use a single continuous polyline from left pin origin to right pin origin, with the zigzag in between. Pins are hidden (length 0, hide) — the polyline IS the visible body.

Full polyline: `(xy -7.62 0) → (xy -3.81 0) → (xy -2.54 1.27) → (xy -1.27 -1.27) → (xy 0 1.27) → (xy 1.27 -1.27) → (xy 2.54 1.27) → (xy 3.81 0) → (xy 7.62 0)`

This creates a seamless continuous line from the left pin connection point to the right pin connection point, with the 3-hump zigzag in between. No gaps between pin and body.

Do NOT use:
- A `(rectangle ...)` body (user rejected — doesn't match real component)
- Separate pin lines: `(length 3.81)` creates visible pin lines that may appear disconnected from the body
- A polyline that only covers (-3.81,0) to (3.81,0) with visible pins — the gaps are visible in KiCad

### RULE: INLINE SYMBOL PINS MUST ORIGINATE AT BODY EDGE (v12+)

For every inline `lib_symbols` definition, the pin `(at ...)` coordinate must place the pin origin at the body edge — the `(rectangle ...)` boundary. A pin with its origin outside the body rectangle creates a visible gap where the pin appears disconnected.

**Correct pattern:**
```python
# GX16-6: rectangle (-5.08, -7.62) to (5.08, 7.62)
# Left pins: origin at -10.16, length 5.08 right → endpoint at -5.08 = body left edge ✓
(pin passive line (at -10.16 -6.35 0) (length 5.08))

# WAGO-6: rectangle (-7.62, -7.62) to (7.62, 7.62)  
# Left (IN) pins: origin at -12.7, length 5.08 right → endpoint at -7.62 = body left edge ✓
# Right (OUT) pins: origin at 7.62, length 5.08 right → endpoint at 12.70 ✓
(pin passive line (at 7.62 -3.81 0) (length 5.08))  # NOT at 12.7!
```

**Verification:** For each symbol, calculate `body_edge = rectangle_start_X + width` (or `rectangle_end_X`). Pin endpoint = `pin_at_X + pin_length * direction_sign`. These must match or the pin will float disconnected.

| Symbol | Body left | Body right | Left pin endpoint | Right pin origin |
|--------|-----------|------------|------------------|-----------------|
| GX16-6 | -5.08 | +5.08 | -10.16+5.08=-5.08 ✓ | n/a (all left) |
| WAGO-6 | -7.62 | +7.62 | -12.7+5.08=-7.62 ✓ | **7.62** (NOT 12.7!) |
| ILLUM_PB | -6.35 | +6.35 | -10.16+3.81=-6.35 ✓ | **6.35** (NOT 10.16!) |
| BUZZER_PL | -5.08 | +5.08 | -10.16+5.08=-5.08 ✓ | **5.08** (NOT 10.16!) |

### RULE: USE INLINE SYMBOLS FOR PORTABILITY

For self-contained schematics, define ALL symbols inline in `lib_symbols`. Do NOT reference external library symbols like `Device:R_US` — they show as question marks when the .kicad_sch file has no library symbol table configured in the .kicad_pro project.

Only use `Device:` library references when you explicitly configure the project's `sym_lib_table`. For drop-in schematics (the common case), inline symbols are mandatory.

**R_US (v13+):** Must be inline with continuous polyline (see routing-patterns.md for exact definition). Left pin at (-7.62, 0) length 3.81 right → endpoint at X_R - 3.81. Right pin at (+7.62, 0) length 3.81 right → endpoint at X_R + 11.43.

### RULE: LINTER v2.0 — Automated Checks (run after every edit)

The `kicad_linter.py` script (at `scripts/kicad_linter.py`) runs **12 checks** automatically. Iterate until PASS before delivery. Do not skip this step — the linter catches structural issues that the user will see as "?" or missing connections.

**v2.0 checks added after 14-revision battle hardening:**

1. **GRID** — off-grid coordinates (every symbol, wire endpoint)
2. **SHORT** — wires shorter than 25 mil (power stubs are exempt)
3. **DIAGONAL** — non-orthogonal wires (KiCad requires orthogonal)
4. **OVERLAP** — component bodies too close (<300 mil center-to-center)
5. **LABEL** — overlapping text labels
6. **TJUNCTION** — T-intersections missing junction dots
7. **COLOR-CROSS** — wire endpoint of one net color lands on a different-color wire (accidental short detection)
8. **ROWS** — same-class component rows too close (<300 mil gap)
9. **SYMBOL** — every `lib_id` used in an instance must have a matching inline definition in `lib_symbols`. Catches the "R_US not found" / "?" issue automatically.
10. **DUPLICATE** — warns if any symbol is defined twice in `lib_symbols` (harmless but wasteful)
11. **POWER-COUNT** — flags if GND_PWR or VCC_PWR instances exceed 1 per net. User preference: 1 GND_PWR on the trunk, not per-component.
12. **GND-CLR** — checks GND_PWR has ≥10mm clearance from component bodies

If the linter flags a violation, fix and re-run before delivery. Only deliver on PASS.

**Used color palette:**
| Net | Color (RGBA) |
|-----|-------------|
| GND/BLACK | (0, 0, 0, 255) |
| RED/+V | (214, 0, 0, 255) |
| BLUE/SIG1 | (0, 70, 200, 255) |
| YELLOW/SIG2 | (200, 160, 0, 255) |
| GREEN/SIG3 | (0, 150, 0, 255) |
| PINK/COM | (220, 80, 150, 255) |
| Default | (0, 150, 0, 255) |

**CRITICAL LESSON — color-swap over-engineering (cost 3 revisions):** The user may ask you to "swap the colors" on a connector pin pair. This means: change ONLY the `net_color_key` value in the GX16_PINS tuple. Do NOT swap pin names in the symbol definition. Do NOT swap routing destinations. Do NOT "fix" the GND_PWR triangle, do NOT adjust components, do NOT change anything else.

The pin name is the SIGNAL name (e.g. "PINK/COM" = the COM signal). The wire color reflects the PHYSICAL wire color of the user's cable assembly. They can legitimately differ when the user's physical cable has non-standard wire-to-pin mapping.

Example: user has a GX16 cable where the BLACK wire carries COM and the PINK wire carries GND.
- CORRECT: Pin 1 name stays "PINK/COM" but `net_color_key` changes from `"PINK"` to `"BLACK"` (wire renders black, matching physical cable). Pin 6 name stays "BLACK/GND" but `net_color_key` changes from `"BLACK"` to `"PINK"`.
- WRONG (over-engineering): Also swapping the pin names to "BLACK/GND" on pin 1, changing the WAGO routing destination, or "fixing" the GND triangle. Only the color key changes.

Before making any change, ask yourself: "Is this what the user asked for, or am I 'fixing' something else?" If the latter — STOP. The user will call it out and reject the delivery.

### RULE: WIRES AT EXACT PIN ENDPOINTS — NEVER INSIDE BODY

Every wire must connect to the **exact pin endpoint coordinate**, calculated as:
`pin_endpoint_X = symbol_origin_X + pin_offset_X + pin_length * cos(pin_direction)`

For pins with direction 0 (right): `endpoint_X = origin_X + offset_X + length`
For pins with direction 180 (left): `endpoint_X = origin_X + offset_X - length`

**R_US:** Left pin at (-7.62, 0), length 3.81 right → endpoint = (symbol_X - 3.81, symbol_Y). Right pin at (+7.62, 0), length 3.81 right → endpoint = (symbol_X + 11.43, symbol_Y). Signal wires must terminate at X = symbol_X - 3.81 (left pin endpoint), not X = symbol_X - 5 (mid-pin).

**ILLUM_PB LED+:** Pin at (-10.16, -2.54), length 3.81 right → endpoint = (symbol_X - 6.35, symbol_Y - 2.54). Do NOT use symbol_X - 8 (that's inside the pin line, not at the endpoint).

Do NOT use approximate offsets. The user explicitly corrected this — wires must connect to the visible pin endpoint (the "leg"), not halfway along or inside the component body.

## Pre-Delivery Fast Checklist (avoids iterative fixes)

Before sending a schematic to the user, run through this checklist in 30 seconds.
Skipping it caused 14 revisions on one project. Don't skip it.

### Visual Checks (that the linter won't catch)
1. **GND_PWR triangle direction** — is it the user-approved variant? `(xy 0 0) (xy -3.81 3.81) (xy 3.81 3.81) (xy 0 0)` — tip at connection, flat bar below. Do NOT substitute with flat-bar-at-top.
2. **GND_PWR count** — if the GND bus interconnects everything, is there exactly ONE instance? `grep 'GND_PWR.*at ' file.kicad_sch` should return 1 line. The user rejected per-component GND symbols.
3. **GX16 wire colors** — for each pin, does the wire STROKE COLOR match the PHYSICAL wire color in the user's cable? The pin NAME may differ (that's intentional when the physical cable has non-standard mapping). If unsure, ask the user.
4. **Signal flow** — does each GX16 pin route to the correct destination component? Trace pin 1 → dest, pin 2 → dest, etc.
5. **Wire color matches intended net** — verify the wire color is what the user expects to see when tracing their physical wires on the schematic.
6. **Component clearance** — run the self-audit. Verify all OK? = YES, minimum body gap ≥ 5mm.
7. **Check for scope creep** — did you change ONLY what the user asked for? If you "also fixed" anything (GND direction, routing, pin names, component positions), revert it. Unsolicited changes cost 3+ revisions on this project alone.

### Integrity Checks
6. **Generator ↔ .kicad_sch sync** — if you have a generator (gen_v6.py), does it produce ALL elements of the .kicad_sch including inline symbol definitions? Run `python3 gen_v6.py` and diff the output against the hand-edited file. If the generator lacks inline symbols (e.g. R_US, GND_PWR), OR has stale constants (e.g. TB1_Y = 115 when the file has TB1 at Y=145), update the generator FIRST before regenerating. Regenerating from an outdated generator WILL destroy manual edits (this cost 2 revisions in one project).
7. **Revision bump** — did you update the revision string in both the generator AND the schematic? (They're out of sync if different.)
8. **Linter passes** — PASS: No violations found.

### First-Time Deliveries
9. **Ask user to open in KiCad** — tell them to open the .kicad_sch on their machine. Ask them to confirm it renders without parser errors. Do NOT assume parser correctness without user confirmation.
10. **After user confirms** — only then finalize the generator. Do NOT move on to new features before the user confirms the base opens.

Workflow: gen → lint → checklist → zip → deliver → user confirms → done.

## Pitfalls & Lessons

### Cardinal Rule: Surgical Changes Only

When the user says "go back to v14 and swap only the colors," do EXACTLY that. Identify the minimal set of bytes that need to change. Change ONLY those bytes. Do not:

- "Also fix" the GND_PWR triangle direction
- "Also improve" the routing
- "Also clean up" pin names or WAGO labels
- "Also fix" anything else you think is wrong

The user's shipping version was WORKING — they have a physical device wired to that schematic. Every unsolicited change you make is a new failure point they have to validate against their physical wiring. Over-engineering caused three rejected deliveries in one session.

**If you feel the urge to "also fix" something: stop, do not touch it, deliver the minimal change, and if the user asks about it later, offer it as a separate conversation.**

### Double Symbol Definition Hazard

The v14 file had TWO `(symbol "R_US" ...)` definitions in `lib_symbols` — one with visible pins (length 3.81) and one with hidden pins (length 0 hide) and continuous polyline. This happens when a generator is updated to add a new symbol body without removing the old one. KiCad uses the LAST definition, but the duplicate causes confusion and 2x file size for no benefit.

Always ensure your generator emits exactly ONE definition per inline symbol. When updating a symbol definition in code, remove or replace the old template string — do not append a new one alongside it. If you find a double in an existing file, the generator needs fixing, not more manual edits.

### Generator Must Know All Manual Edits

Manual edits to .kicad_sch files (e.g. moving TB1 from Y=115 to Y=145, adding the R_US inline definition) MUST be reflected in the generator before any regeneration. If the generator hasn't been updated, regenerating will destroy those edits and you'll have to redo them.

Workflow when both generator and manual edits exist:
1. Identify all manual edits that differ from generator output
2. Update generator constants/symbol definitions to match
3. THEN regenerate from generator
4. Verify diff is empty against the hand-edited file
5. Run linter
6. Deliver